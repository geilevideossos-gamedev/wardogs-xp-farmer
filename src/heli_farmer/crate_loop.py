import logging
import threading
import time
from collections import Counter
from collections.abc import Callable

import numpy as np

from heli_farmer.config import merge
from heli_farmer.detectors import Marker, Vision
from heli_farmer.flight import Pilot
from heli_farmer.inputs import Input
from heli_farmer.killswitch import wait

log = logging.getLogger(__name__)

STEPS = ("buy", "climb", "turn", "drop", "land")
ROUND = ("buy", "climb", "turn", "drop", "turn", "land")


class LeaveLayer(Exception):
    pass


class StepFailed(Exception):
    pass


class CrateLoop:
    def __init__(
        self,
        vision: Vision,
        inp: Input,
        grab: Callable[[], np.ndarray],
        stop: threading.Event,
        config: dict,
        map_name: str = "default",
        clock: Callable[[], float] = time.monotonic,
    ):
        self._vision = vision
        self._inp = inp
        self._grab = grab
        self._stop = stop
        self._keys = config["keys"]
        self._buy = config["buy"]
        self._flight = config["flight"]
        self._timeouts = config["timeouts"]
        self._confirm = config["vision"]["confirm"]
        self._origin = (config["game_region"]["left"], config["game_region"]["top"])
        self._map = merge(config["maps"]["default"], config["maps"].get(map_name) or {})
        self._clock = clock
        self._pilot = Pilot(inp, self._keys, self._flight, clock)
        self._heli_lost_since: float | None = None
        self.stats: Counter = Counter()

    def run(self, steps: tuple[str, ...] = (), once: bool = False) -> None:
        try:
            if steps:
                for name in steps:
                    self.step(name)
                return
            while True:
                for name in ROUND:
                    self.step(name)
                self.stats["rounds"] += 1
                log.info("Runde fertig: %s", dict(self.stats))
                if once:
                    return
        finally:
            self._inp.release_all()

    def step(self, name: str) -> None:
        log.info("Schritt %s", name)
        try:
            getattr(self, name)()
        finally:
            self._pilot.release()

    def observe(self) -> np.ndarray:
        wait(self._stop, self._flight["tick_s"])
        self._pilot.update()
        self._inp.release_overdue(self._timeouts["max_hold_s"])
        frame = self._grab()
        if self._vision.first_aid(frame):
            raise LeaveLayer("Erste-Hilfe-Symbol: Spieler tot")
        if self._vision.in_lakota(frame):
            self._heli_lost_since = None
            if self._vision.heli_damaged(frame):
                raise LeaveLayer("Heli beschädigt")
        elif self._vision.garage_menu(frame) is None:
            now = self._clock()
            self._heli_lost_since = self._heli_lost_since or now
            if now - self._heli_lost_since > self._timeouts["heli_lost_s"]:
                raise LeaveLayer("Heli-Anzeige weg (Crash oder ausgestiegen)")
        return frame

    def wait_for(
        self, check: Callable[[np.ndarray], object], timeout_s: float, confirm: int = 1
    ) -> object:
        deadline = self._clock() + timeout_s
        hits = 0
        while self._clock() < deadline:
            result = check(self.observe())
            hits = hits + 1 if result else 0
            if hits >= confirm:
                return result
        return None

    def click(self, name: str) -> None:
        x, y = self._buy["clicks"][name]
        self._inp.click(self._origin[0] + x, self._origin[1] + y)
        wait(self._stop, self._buy["pause_s"])

    def buy(self) -> None:
        frame = self.observe()
        if self._vision.crate_loaded(frame):
            log.info("Crate ist schon geladen")
            return
        for attempt in range(1, self._buy["attempts"] + 1):
            if not self._vision.buy_prompt(frame) and self._vision.garage_menu(frame) is None:
                raise StepFailed("Kein Kauf-Hinweis: Heli steht nicht im Kaufbereich der Base")
            if self._vision.garage_menu(frame) is None:
                self._inp.tap(self._keys["shop"], self._flight["tap_s"])
            menu = self.wait_for(self._vision.garage_menu, self._buy["menu_timeout_s"])
            if menu == "main":
                self.click("logistics")
                self.wait_for(
                    lambda f: self._vision.garage_menu(f) == "logistics",
                    self._buy["menu_timeout_s"],
                )
            if menu:
                self.click("pallets")
                self.click("ammo_pallet")
                self.wait_for(
                    lambda f: self._vision.garage_menu(f) == "main", self._buy["menu_timeout_s"]
                )
                self.click("confirm")
            if self.wait_for(self._vision.crate_loaded, self._buy["loaded_timeout_s"]):
                self.stats["bought"] += 1
                log.info("Crate gekauft (Versuch %d)", attempt)
                return
            log.warning("Crate nicht im Bild nach Kaufversuch %d", attempt)
            frame = self.observe()
        raise StepFailed("Crate-Kauf fehlgeschlagen (zu wenig Geld oder Menü unbekannt)")

    def climb(self) -> None:
        target = self._map["cruise_agl"]
        deadline = self._clock() + self._flight["climb_timeout_s"]
        while self._clock() < deadline:
            agl, _ = self._hold(self.observe(), target, 0)
            if agl is not None and agl >= target - self._flight["agl_band"]:
                log.info("Sichere Höhe erreicht: %s m", agl)
                return
        raise StepFailed("Steigen dauert zu lange")

    def turn(self) -> None:
        deadline = self._clock() + self._flight["turn_timeout_s"]
        while self._clock() < deadline:
            frame = self.observe()
            self._hold(frame, self._map["cruise_agl"], 0)
            marker = self._target(frame)
            if marker is None:
                self._pilot.search()
            elif self._pilot.yaw(marker.x):
                log.info("Zielrichtung erreicht: Marker bei x=%d", marker.x)
                return
        raise StepFailed("Drehen zum Ziel dauert zu lange")

    def drop(self) -> None:
        deadline = self._clock() + self._flight["leg_timeout_s"]
        arrived = False
        while self._clock() < deadline:
            frame = self.observe()
            marker = self._vision.zone_marker(frame)
            if marker and not self._at_edge(marker) and marker.y >= self._map["zone_arrive_y"]:
                if not arrived:
                    log.info("Über der Zone: Marker bei y=%d", marker.y)
                arrived = True
            if not arrived:
                self._fly(frame, marker, self._map["cruise_agl"], self._map["cruise_speed"])
                continue
            agl, speed = self._hold(frame, self._map["drop_agl"], self._map["drop_speed"])
            low = agl is not None and agl <= self._map["drop_agl"] + self._flight["agl_band"]
            slow = (
                speed is not None and speed <= self._map["drop_speed"] + self._flight["speed_band"]
            )
            if low and slow:
                self._release_crate()
                return
        raise StepFailed("Zone nicht rechtzeitig erreicht")

    def land(self) -> None:
        deadline = self._clock() + self._flight["land_timeout_s"] + self._flight["leg_timeout_s"]
        phase = "cruise"
        landed_since = None
        while self._clock() < deadline:
            frame = self.observe()
            if phase == "cruise":
                marker = self._vision.hq_marker(frame)
                self._fly(frame, marker, self._map["cruise_agl"], self._map["cruise_speed"])
                near = (
                    marker and not self._at_edge(marker) and marker.y >= self._map["hq_approach_y"]
                )
                if near or self._vision.buy_prompt(frame):
                    log.info("Base erreicht, bremsen")
                    phase = "brake"
            elif phase == "brake":
                _, speed = self._hold(frame, self._map["cruise_agl"], 0)
                if speed is not None and speed <= self._map["approach_speed"]:
                    log.info("Sinkflug")
                    phase = "descend"
            else:
                agl = self._vision.agl(frame)
                speed = self._vision.speed(frame)
                self._pilot.descend(agl, self._vision.asl(frame), speed)
                on_ground = agl is not None and agl <= self._flight["landed_agl"]
                still = speed is not None and speed <= self._flight["landed_speed"]
                if not (on_ground and still):
                    landed_since = None
                    continue
                landed_since = landed_since or self._clock()
                if self._clock() - landed_since >= self._flight["landed_hold_s"]:
                    self._pilot.release()
                    if not self.wait_for(self._vision.buy_prompt, self._buy["menu_timeout_s"]):
                        raise StepFailed("Gelandet, aber kein Kauf-Hinweis im Bild")
                    log.info("Gelandet im Kaufbereich")
                    return
        raise StepFailed("Landung dauert zu lange")

    def _release_crate(self) -> None:
        self._inp.tap(self._keys["drop"], self._flight["tap_s"])
        gone = self.wait_for(
            lambda f: not self._vision.crate_loaded(f),
            self._flight["drop_timeout_s"],
            self._confirm,
        )
        if gone:
            self.stats["dropped"] += 1
            log.info("Crate abgeworfen")
            if self.wait_for(self._vision.delivered, self._flight["delivered_wait_s"]):
                self.stats["delivered"] += 1
                log.info("Lieferung bestätigt")
            return
        raise StepFailed("Crate nach G noch geladen")

    def _fly(self, frame: np.ndarray, marker: Marker | None, agl: float, speed: float) -> None:
        self._hold(frame, agl, speed)
        if marker is not None:
            self._pilot.yaw(marker.x)

    def _hold(self, frame: np.ndarray, agl: float, speed: float) -> tuple[int | None, int | None]:
        current_agl = self._vision.agl(frame)
        current_speed = self._vision.speed(frame)
        self._pilot.fly(current_agl, self._vision.asl(frame), current_speed, agl, speed)
        return current_agl, current_speed

    def _target(self, frame: np.ndarray) -> Marker | None:
        if self._vision.crate_loaded(frame):
            return self._vision.zone_marker(frame)
        return self._vision.hq_marker(frame)

    def _at_edge(self, marker: Marker) -> bool:
        margin = self._flight["edge_margin"]
        return marker.x < margin or marker.x > 2 * self._flight["center_x"] - margin

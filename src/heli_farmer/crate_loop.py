import logging
import statistics
import threading
import time
from collections import Counter, deque
from collections.abc import Callable

import numpy as np

from heli_farmer.config import merge
from heli_farmer.detectors import Marker, Vision
from heli_farmer.flight import Pilot
from heli_farmer.inputs import Input
from heli_farmer.killswitch import wait

log = logging.getLogger(__name__)

STEPS = ("buy", "climb", "turn", "drop", "leave", "land")
ROUND = ("buy", "climb", "turn", "drop", "leave", "turn", "land")


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
        self,
        check: Callable[[np.ndarray], object],
        timeout_s: float,
        confirm: int = 1,
        each: Callable[[np.ndarray], object] | None = None,
    ) -> object:
        deadline = self._clock() + timeout_s
        hits = 0
        while self._clock() < deadline:
            frame = self.observe()
            if each is not None:
                each(frame)
            result = check(frame)
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
        target = self._map["turn_agl"]
        deadline = self._clock() + self._flight["climb_timeout_s"]
        while self._clock() < deadline:
            agl, _ = self._fly(self.observe(), target, 0)
            if agl is not None and agl >= target:
                log.info("Abgehoben: %s m", agl)
                return
        raise StepFailed("Steigen dauert zu lange")

    def turn(self) -> None:
        frame = self.observe()
        outbound = self._vision.crate_loaded(frame)
        target = self._map["turn_agl"] if outbound else self._map["cruise_agl"]
        deadline = self._clock() + self._flight["turn_timeout_s"]
        while self._clock() < deadline:
            self._fly(frame, target, 0)
            marker = self._vision.zone_marker(frame) if outbound else self._vision.hq_marker(frame)
            if marker is None:
                self._pilot.search()
            elif self._pilot.yaw(marker.x):
                log.info("Zielrichtung erreicht: Marker bei x=%d", marker.x)
                return
            frame = self.observe()
        raise StepFailed("Drehen zum Ziel dauert zu lange")

    def drop(self) -> None:
        deadline = self._clock() + self._flight["leg_timeout_s"]
        distances: deque[int] = deque(maxlen=self._flight["distance_history"])
        approach = False
        inside_hits = 0
        entered: float | None = None
        while self._clock() < deadline:
            frame = self.observe()
            marker = self._vision.zone_marker(frame)
            if marker is not None and entered is None:
                self._pilot.yaw(marker.x)
            inside = (
                marker is not None and marker.kind == "HZ" and self._vision.minimap_in_zone(frame)
            )
            inside_hits = inside_hits + 1 if inside else 0
            if entered is None and inside_hits >= self._confirm:
                entered = self._clock()
                log.info("In der Zone (HZ + Minimap), Abwurf in %s s", self._flight["drop_delay_s"])
            if entered is None:
                if marker is not None and marker.kind == "CZ" and marker.distance is not None:
                    distances.append(marker.distance)
                full = len(distances) == distances.maxlen
                if not approach and full:
                    distance = statistics.median(distances)
                    approach = distance <= self._map["brake_distance"]
                    if approach:
                        log.info("Zone in %d m: bremsen und sinken", distance)
                if approach:
                    self._approach(frame)
                else:
                    self._cruise(frame)
                continue
            agl, _ = self._approach(frame)
            waited = self._clock() - entered
            if waited < self._flight["drop_delay_s"]:
                continue
            if agl is not None and agl <= self._map["drop_max_agl"]:
                self._release_crate()
                return
            if waited > self._flight["drop_wait_s"]:
                raise StepFailed("In der Zone nicht tief genug für den Abwurf")
        raise StepFailed("Zone nicht rechtzeitig erreicht")

    def leave(self) -> None:
        frame = self.observe()
        marker = self._vision.zone_marker(frame)
        right = marker is not None and marker.x > self._flight["center_x"]
        away = "yaw_left" if right else "yaw_right"
        log.info("Umdrehen mit %s", self._keys[away].upper())
        turned = self._clock() + self._flight["turnaround_s"]
        deadline = turned + self._flight["leg_timeout_s"]
        outside_hits = 0
        left: float | None = None
        while self._clock() < deadline:
            if self._clock() < turned:
                self._fly(frame, self._map["cruise_agl"], 0)
                self._pilot.search(away)
                frame = self.observe()
                continue
            self._cruise(frame)
            if left is not None:
                if self._clock() - left >= self._flight["leave_margin_s"]:
                    return
                frame = self.observe()
                continue
            marker = self._vision.zone_marker(frame)
            if marker is not None:
                outside = marker.kind == "CZ"
            else:
                outside = not self._vision.minimap_in_zone(frame)
            outside_hits = outside_hits + 1 if outside else 0
            if outside_hits >= self._confirm:
                left = self._clock()
                log.info("Zone verlassen, noch %s s weiter", self._flight["leave_margin_s"])
            frame = self.observe()
        raise StepFailed("Zone nicht verlassen")

    def land(self) -> None:
        deadline = self._clock() + self._flight["land_timeout_s"] + self._flight["leg_timeout_s"]
        phase = "cruise"
        landed_since = None
        seen = self._clock()
        while self._clock() < deadline:
            frame = self.observe()
            if phase == "cruise":
                marker = self._vision.hq_marker(frame)
                self._cruise(frame)
                if marker is not None:
                    self._pilot.yaw(marker.x)
                near = (
                    marker and not self._at_edge(marker) and marker.y >= self._map["hq_approach_y"]
                )
                if near or self._vision.buy_prompt(frame):
                    log.info("Base erreicht, tief und langsam anfliegen")
                    phase = "approach"
                    seen = self._clock()
            elif phase == "approach":
                marker = self._vision.hq_marker(frame)
                landing = self._map["approach_agl"]
                self._fly(frame, landing, self._map["approach_speed"], 0, sink=True)
                if marker is not None:
                    seen = self._clock()
                    self._pilot.yaw(marker.x)
                prompt = self._vision.buy_prompt(frame)
                if prompt or self._clock() - seen > self._flight["hq_lost_s"]:
                    log.info("Sinkflug (%s)", "Kauf-Hinweis" if prompt else "HQ unter dem Heli")
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
            self._approach,
        )
        if not gone:
            raise StepFailed("Crate nach G noch geladen")
        self.stats["dropped"] += 1
        log.info("Crate abgeworfen")
        delivered = self.wait_for(
            self._vision.delivered, self._flight["delivered_wait_s"], each=self._approach
        )
        if delivered:
            self.stats["delivered"] += 1
            log.info("Lieferung bestätigt")

    def _cruise(self, frame: np.ndarray) -> tuple[int | None, int | None]:
        return self._fly(
            frame, self._map["cruise_agl"], self._map["cruise_speed"], self._map["min_agl"]
        )

    def _approach(self, frame: np.ndarray) -> tuple[int | None, int | None]:
        drop_agl = self._map["drop_agl"]
        floor = drop_agl - self._flight["agl_band"]
        return self._fly(frame, drop_agl, self._map["drop_speed"], floor, sink=True)

    def _fly(
        self, frame: np.ndarray, agl: float, speed: float, floor: float = 0, sink: bool = False
    ) -> tuple[int | None, int | None]:
        current_agl = self._vision.agl(frame)
        current_speed = self._vision.speed(frame)
        asl = self._vision.asl(frame)
        self._pilot.fly(current_agl, asl, current_speed, agl, speed, floor, sink)
        return current_agl, current_speed

    def _at_edge(self, marker: Marker) -> bool:
        margin = self._flight["edge_margin"]
        return marker.x < margin or marker.x > 2 * self._flight["center_x"] - margin

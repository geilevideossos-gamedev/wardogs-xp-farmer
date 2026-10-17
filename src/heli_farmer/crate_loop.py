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
from heli_farmer.states import RoundOver

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
        self._side = "yaw_right"
        self._settled: float | None = None
        self._curving: bool | None = None
        self._traced = -1e9
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
        self._inp.wait_for_focus()
        self._pilot.update()
        self._inp.release_overdue(self._timeouts["max_hold_s"])
        frame = self._grab()
        if self._vision.round_over(frame):
            raise RoundOver
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
        self._inp.click(
            self._origin[0] + x, self._origin[1] + y, self._buy["hover_s"], self._buy["press_s"]
        )
        wait(self._stop, self._buy["pause_s"])

    def buy(self) -> None:
        frame = self.observe()
        if self._vision.crate_loaded(frame):
            log.info("Crate ist schon geladen")
            return
        for attempt in range(1, self._buy["attempts"] + 1):
            if self._vision.garage_menu(frame) is None:
                if not self._vision.buy_prompt(frame):
                    raise StepFailed("Kein Kauf-Hinweis: Heli steht nicht im Kaufbereich der Base")
                self._inp.tap(self._keys["shop"], self._flight["tap_s"])
            menu = self.wait_for(self._vision.garage_menu, self._buy["menu_timeout_s"])
            if menu:
                self._choose_pallet(menu)
                self._confirm_exit()
            if self.wait_for(self._vision.crate_loaded, self._buy["loaded_timeout_s"]):
                self.stats["bought"] += 1
                log.info("Crate gekauft (Versuch %d)", attempt)
                return
            log.warning("Crate nicht im Bild nach Kaufversuch %d", attempt)
            frame = self.observe()
        raise StepFailed("Crate-Kauf fehlgeschlagen (zu wenig Geld oder Menü unbekannt)")

    def _choose_pallet(self, menu: str) -> None:
        if menu == "main":
            if self._vision.slots_full(self.observe()):
                log.info("LOGISTICS SLOTS FULL: Palette ist schon geladen, nur bestätigen")
                return
            self.click("logistics")
            if not self.wait_for(
                lambda f: self._vision.garage_menu(f) == "logistics", self._buy["menu_timeout_s"]
            ):
                log.warning("Logistik-Menü ging nicht auf")
                return
        self.click("pallets")
        self.click("ammo_pallet")
        self.wait_for(lambda f: self._vision.garage_menu(f) == "main", self._buy["menu_timeout_s"])

    def _confirm_exit(self) -> None:
        for attempt in range(1, self._buy["confirm_attempts"] + 1):
            self.click("confirm")
            if self.wait_for(
                lambda f: self._vision.garage_menu(f) is None, self._buy["menu_timeout_s"]
            ):
                return
            log.warning("Kaufmenü nach CONFIRM & EXIT noch offen (Versuch %d)", attempt)
        raise StepFailed("Kaufmenü geht nicht zu: CONFIRM & EXIT wirkt nicht")

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
        outbound = self._vision.crate_loaded(self.observe())
        target = self._map["turn_agl"] if outbound else self._map["cruise_agl"]
        deadline = self._clock() + self._flight["turn_timeout_s"]
        self._side, self._settled = "yaw_right", None
        while self._clock() < deadline:
            frame = self.observe()
            marker = self._vision.zone_marker(frame) if outbound else self._vision.hq_marker(frame)
            if self._align(frame, marker, target):
                log.info("Zielrichtung erreicht: Marker bei x=%d", marker.x)
                return
        raise StepFailed("Drehen zum Ziel dauert zu lange")

    def drop(self) -> None:
        deadline = self._clock() + self._flight["leg_timeout_s"]
        distances: deque[int] = deque(maxlen=self._flight["distance_history"])
        approach = False
        inside_hits = 0
        entered: float | None = None
        waiting = False
        min_agl = self._map["drop_min_agl"]
        while self._clock() < deadline:
            frame = self.observe()
            marker = self._vision.zone_marker(frame)
            hz = marker is not None and marker.kind == "HZ"
            inside = hz or (approach and self._vision.minimap_in_zone(frame))
            inside_hits = inside_hits + 1 if inside else 0
            if entered is None and inside_hits >= self._confirm:
                entered = self._clock()
                log.info(
                    "In der Zone (%s), Abwurf in %s s",
                    "HZ" if hz else "Minimap",
                    self._flight["drop_delay_s"],
                )
            if entered is None:
                x = marker.x if marker is not None else None
                if marker is not None and marker.kind == "CZ" and marker.distance is not None:
                    distances.append(marker.distance)
                if not approach and len(distances) == distances.maxlen:
                    distance = statistics.median(distances)
                    approach = distance <= self._map["brake_distance"]
                    if approach:
                        log.info("Zone in %d m: bremsen und sanft sinken", distance)
                if approach:
                    self._approach(frame, x)
                else:
                    self._cruise(frame, x)
                continue
            agl, _ = self._hold_level(frame)
            waited = self._clock() - entered
            if waited < self._flight["drop_delay_s"]:
                continue
            if agl is not None and agl >= min_agl:
                log.info("Abwurf bei AGL %d m", agl)
                self._release_crate()
                return
            if not waiting:
                waiting = True
                log.info("Warte auf Abwurfhöhe: AGL %s m, mindestens %s m", agl, min_agl)
            if waited > self._flight["drop_wait_s"]:
                raise StepFailed(f"In der Zone nicht über {min_agl} m (AGL {agl})")
        raise StepFailed("Zone nicht rechtzeitig erreicht")

    def leave(self) -> None:
        if self.wait_for(
            self._outside, self._flight["outside_check_s"], self._confirm, self._hold_level
        ):
            log.info("Schon aus der Zone raus (Schwung nach dem Abwurf)")
            return
        marker = self._vision.zone_marker(self.observe())
        right = marker is not None and marker.x > self._flight["center_x"]
        away = "yaw_left" if right else "yaw_right"
        log.info("Umdrehen mit %s", self._keys[away].upper())
        turned = self._clock() + self._flight["turnaround_s"]
        deadline = turned + self._flight["leg_timeout_s"]
        outside_hits = 0
        left: float | None = None
        while self._clock() < deadline:
            frame = self.observe()
            if self._clock() < turned:
                speed = self._vision.speed(frame)
                if speed is not None and speed > self._flight["curve_min_speed"]:
                    self._curve(frame, self._map["cruise_agl"], 0, self._edge(away))
                else:
                    self._fly(frame, self._map["cruise_agl"], 0)
                    self._pilot.search(away)
                continue
            self._cruise(frame)
            if left is not None:
                if self._clock() - left >= self._flight["leave_margin_s"]:
                    return
                continue
            outside_hits = outside_hits + 1 if self._outside(frame) else 0
            if outside_hits >= self._confirm:
                left = self._clock()
                log.info("Zone verlassen, noch %s s weiter", self._flight["leave_margin_s"])
        raise StepFailed("Zone nicht verlassen")

    def land(self) -> None:
        deadline = self._clock() + self._flight["leg_timeout_s"]
        land_deadline: float | None = None
        phase = "cruise"
        distances: deque[int] = deque(maxlen=self._flight["distance_history"])
        nearest: float | None = None
        over_base = away = 0
        landed_since = None
        seen = self._clock()
        self._side, self._settled = "yaw_right", None
        while self._clock() < deadline:
            frame = self.observe()
            now = self._clock()
            if land_deadline is not None and now > land_deadline:
                raise StepFailed("Landeanflug dauert zu lange")
            marker = self._vision.hq_marker(frame)
            if marker is not None:
                seen = now
                self._side = "yaw_right" if marker.x > self._flight["center_x"] else "yaw_left"
                if marker.distance is not None:
                    distances.append(marker.distance)
            full = len(distances) == distances.maxlen
            distance = statistics.median(distances) if full else None
            lost = now - seen > self._flight["hq_lost_s"]
            prompt = self._vision.buy_prompt(frame)
            if phase == "turn":
                agl = self._map["cruise_agl" if land_deadline is None else "approach_agl"]
                if prompt and land_deadline is not None:
                    log.info("Sinkflug (Kauf-Hinweis)")
                    phase, away = "descend", 0
                elif self._align(frame, marker, agl):
                    log.info("HQ-Marker mittig, weiter Richtung Base")
                    phase = "cruise" if land_deadline is None else "approach"
                    distances.clear()
                    nearest, over_base, seen = None, 0, now
            elif phase == "cruise":
                if lost:
                    log.info("HQ-Marker weg: anhalten und suchen")
                    phase, self._settled = "turn", None
                    continue
                self._cruise(frame, marker.x if marker is not None else None)
                near = distance is not None and distance <= self._map["land_distance"]
                low = (
                    marker and not self._at_edge(marker) and marker.y >= self._map["hq_approach_y"]
                )
                if near or low or prompt:
                    log.info("Base in %s m: bremsen und sinken (Landeanflug)", distance)
                    phase = "approach"
                    land_deadline = now + self._flight["land_timeout_s"]
            elif phase == "approach":
                if distance is not None:
                    nearest = distance if nearest is None else min(nearest, distance)
                close = distance is not None and distance <= self._flight["hq_overhead_distance"]
                self._fly(
                    frame,
                    self._map["approach_agl"],
                    self._approach_speed(distance),
                    sink_rate=self._flight["approach_sink_rate"],
                    x=marker.x if marker is not None and not close else None,
                )
                over_base = over_base + 1 if self._vision.minimap_over_base(frame) else 0
                farther = (
                    distance is not None
                    and nearest is not None
                    and distance > nearest + self._flight["hq_overshoot_m"]
                )
                if farther or (lost and not over_base):
                    log.info("Base überflogen (HQ %s m, vorher %s m): umdrehen", distance, nearest)
                    phase, self._settled = "turn", None
                elif prompt or (over_base >= self._confirm and (close or lost)):
                    log.info("Sinkflug (%s)", "Kauf-Hinweis" if prompt else "Base unter dem Heli")
                    phase, away = "descend", 0
            else:
                below = prompt or self._vision.minimap_over_base(frame)
                away = 0 if below else away + 1
                if away >= self._confirm:
                    log.info("Base nicht mehr unter dem Heli: steigen, umdrehen")
                    phase, self._settled, landed_since = "turn", None, None
                    continue
                if self._descend(frame):
                    landed_since = landed_since or now
                    if now - landed_since >= self._flight["landed_hold_s"]:
                        self._pilot.release()
                        if not self.wait_for(self._vision.buy_prompt, self._buy["menu_timeout_s"]):
                            raise StepFailed("Gelandet, aber kein Kauf-Hinweis im Bild")
                        log.info("Gelandet im Kaufbereich")
                        return
                else:
                    landed_since = None
        raise StepFailed("Landung dauert zu lange")

    def _descend(self, frame: np.ndarray) -> bool:
        agl = self._vision.agl(frame)
        speed = self._vision.speed(frame)
        self._pilot.descend(agl, self._vision.asl(frame), speed)
        roll = self._vision.roll(frame)
        self._pilot.bank(roll, speed)
        self._trace(agl, speed, roll, None)
        on_ground = agl is not None and agl <= self._flight["landed_agl"]
        return on_ground and speed is not None and speed <= self._flight["landed_speed"]

    def _release_crate(self) -> None:
        self._inp.tap(self._keys["drop"], self._flight["tap_s"])
        gone = self.wait_for(
            lambda f: not self._vision.crate_loaded(f),
            self._flight["drop_timeout_s"],
            self._confirm,
            self._hold_level,
        )
        if not gone:
            raise StepFailed("Crate nach G noch geladen")
        self.stats["dropped"] += 1
        log.info("Crate abgeworfen")
        delivered = self.wait_for(
            self._vision.delivered, self._flight["delivered_wait_s"], each=self._hold_level
        )
        if delivered:
            self.stats["delivered"] += 1
            log.info("Lieferung bestätigt")

    def _align(self, frame: np.ndarray, marker: Marker | None, agl: float) -> bool:
        center = self._flight["center_x"]
        if marker is not None:
            self._side = "yaw_right" if marker.x > center else "yaw_left"
        speed = self._vision.speed(frame)
        threshold = self._flight["curve_min_speed"]
        if self._curving:
            threshold -= self._flight["speed_band"]
        curve = speed is not None and speed > threshold
        if curve != self._curving:
            self._curving = curve
            log.info("Drehen %s (%s km/h)", "im Kurvenflug" if curve else "auf der Stelle", speed)
        if curve:
            x = marker.x if marker is not None else self._edge(self._side)
            floor = min(self._map["min_agl"], agl - self._flight["agl_band"])
            self._curve(frame, agl, floor, x)
            done = marker is not None and self._pilot.on_target
        elif marker is None:
            self._fly(frame, agl, 0)
            self._pilot.search(self._side)
            done = False
        else:
            _, speed = self._fly(frame, agl, 0, x=marker.x)
            slow = speed is not None and speed <= self._flight["hover_speed"]
            done = self._pilot.on_target and slow
        if not done:
            self._settled = None
            return False
        self._settled = self._settled or self._clock()
        return self._clock() - self._settled >= self._flight["yaw_settle_s"]

    def _curve(self, frame: np.ndarray, agl: float, floor: float, x: float) -> None:
        speed, bank = self._flight["turn_speed"], self._flight["turn_bank"]
        self._fly(frame, agl, speed, floor, x=x, bank=bank)

    def _approach_speed(self, distance: float | None) -> float:
        slowest = self._map["approach_speed"]
        if distance is None:
            return slowest
        return max(slowest, distance * self._flight["approach_speed_per_m"])

    def _edge(self, side: str) -> float:
        return 2 * self._flight["center_x"] if side == "yaw_right" else 0

    def _outside(self, frame: np.ndarray) -> bool:
        marker = self._vision.zone_marker(frame)
        if marker is not None:
            return marker.kind == "CZ"
        return not self._vision.minimap_in_zone(frame)

    def _cruise(self, frame: np.ndarray, x: float | None = None) -> tuple[int | None, int | None]:
        return self._fly(
            frame, self._map["cruise_agl"], self._map["cruise_speed"], self._map["min_agl"], x=x
        )

    def _approach(self, frame: np.ndarray, x: float | None) -> tuple[int | None, int | None]:
        drop_agl = self._map["drop_agl"]
        floor = drop_agl - self._flight["agl_band"]
        sink_rate = self._flight["drop_sink_rate"]
        return self._fly(frame, drop_agl, self._map["drop_speed"], floor, sink_rate, x)

    def _hold_level(self, frame: np.ndarray) -> tuple[int | None, int | None]:
        drop_agl = self._map["drop_agl"]
        floor = drop_agl - self._flight["agl_band"]
        return self._fly(frame, drop_agl, None, floor, self._flight["drop_sink_rate"])

    def _fly(
        self,
        frame: np.ndarray,
        agl: float,
        speed: float | None,
        floor: float = 0,
        sink_rate: float = 0,
        x: float | None = None,
        bank: float = 0,
    ) -> tuple[int | None, int | None]:
        current_agl = self._vision.agl(frame)
        current_speed = self._vision.speed(frame)
        asl = self._vision.asl(frame)
        loaded = self._vision.crate_loaded(frame)
        self._pilot.fly(current_agl, asl, current_speed, agl, speed, floor, sink_rate, loaded)
        lead = None
        if x is not None:
            self._pilot.yaw(x)
            lead = self._pilot.lead
        roll = self._vision.roll(frame)
        self._pilot.bank(roll, current_speed, lead, bank)
        self._trace(current_agl, current_speed, roll, x)
        return current_agl, current_speed

    def _trace(self, agl: int | None, speed: int | None, roll: int | None, x: float | None) -> None:
        now = self._clock()
        if now - self._traced < self._flight["trace_s"]:
            return
        self._traced = now
        log.info(
            "Flug: AGL %s m, %s km/h, Schräglage %s°, Neigung %+.1f Tipps, Marker %s, Tasten %s%s",
            agl,
            speed,
            roll,
            self._pilot.tilt,
            "-" if x is None else round(x),
            ",".join(self._inp.held()) or "-",
            ", Sicherheit: steigen" if self._pilot.recovering else "",
        )

    def _at_edge(self, marker: Marker) -> bool:
        margin = self._flight["edge_margin"]
        return marker.x < margin or marker.x > 2 * self._flight["center_x"] - margin

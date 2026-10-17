from collections import deque
from collections.abc import Callable

import numpy as np

from heli_farmer.inputs import Input

FLIGHT_KEYS = ("up", "down", "forward", "back", "yaw_left", "yaw_right", "roll_left", "roll_right")


class Trend:
    def __init__(self, window_s: float):
        self._window_s = window_s
        self._samples: deque[tuple[float, float]] = deque()

    def add(self, t: float, value: float | None) -> None:
        if value is None:
            return
        self._samples.append((t, value))
        while self._samples and t - self._samples[0][0] > self._window_s:
            self._samples.popleft()

    def reset(self) -> None:
        self._samples.clear()

    @property
    def ready(self) -> bool:
        return len(self._samples) >= 2

    @property
    def span(self) -> float:
        return self._samples[-1][0] - self._samples[0][0] if self._samples else 0.0

    def rate(self) -> float:
        if len(self._samples) < 2:
            return 0.0
        times, values = np.array(self._samples).T
        times = times - times.mean()
        spread = float((times * times).sum())
        return float((times * (values - values.mean())).sum() / spread) if spread else 0.0


def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


class Pilot:
    def __init__(self, inp: Input, keys: dict, flight: dict, clock: Callable[[], float]):
        self._inp = inp
        self._keys = keys
        self._cfg = flight
        self._clock = clock
        self._agl = Trend(flight["history_s"])
        self._asl = Trend(flight["history_s"])
        self._ground = Trend(flight["history_s"])
        self._aim = Trend(flight["yaw_history_s"])
        self._pulses: dict[str, float] = {}
        self._taps: dict[str, deque[float]] = {"forward": deque(), "back": deque()}
        self._last_pitch = -1e9
        self._yaw_free_at = -1e9
        self._last_roll = -1e9
        self._roll = 0
        self.reverse = False
        self._tapped: tuple[bool, float] | None = None
        self._suspect = 0
        self._learn_after = -1e9
        self._last_brake = -1e9
        self._slowing = False
        self.ground: float | None = None
        self.height: int | None = None
        self.lead: float | None = None
        self.recovering = False
        self.diving = False
        self.drifting = False
        self._sinking = False

    @property
    def climb(self) -> float:
        return self._asl.rate() if self._asl.ready else self._agl.rate()

    @property
    def accel(self) -> float:
        if self._ground.span < self._cfg["history_s"] / 2:
            return 0.0
        return self._ground.rate()

    @property
    def yawing(self) -> bool:
        return self._keys["yaw_left"] in self._pulses or self._keys["yaw_right"] in self._pulses

    def update(self) -> None:
        now = self._clock()
        for key, until in list(self._pulses.items()):
            if now >= until:
                self._inp.key_up(key)
                del self._pulses[key]

    def release(self) -> None:
        for key in FLIGHT_KEYS:
            self._inp.hold(self._keys[key], False)
        self._pulses.clear()

    def speed_limit(self, agl: float) -> float:
        heights, speeds = zip(*self._cfg["speed_limits"], strict=True)
        return float(np.interp(agl, heights, speeds))

    def fly(
        self,
        agl: int | None,
        asl: int | None,
        speed: int | None,
        target_agl: float,
        target_speed: float | None,
        floor: float = 0,
        sink_rate: float = 0,
        loaded: bool = False,
    ) -> None:
        self._track(agl, asl, speed)
        if agl is None:
            return
        ground, accel, climb = self.ground, self.accel, self.climb
        fast = ground is not None and ground > self._cfg["safe_speed"]
        self._watch_dive(ground, accel, climb)
        low = agl < floor or (agl < self._cfg["safe_agl"] and fast)
        self.recovering = low or self.diving
        sinking_fast = sink_rate > 0 and climb < -sink_rate - self._cfg["sink_band"]
        lift = self.recovering or sinking_fast or self._lift(agl, target_agl)
        predicted = agl + self._agl.rate() * self._cfg["agl_lookahead_s"]
        above = predicted > target_agl + self._cfg["agl_band"]
        self._inp.hold(self._keys["up"], lift)
        self._inp.hold(
            self._keys["down"], sink_rate > 0 and above and not lift and climb > -sink_rate
        )
        if ground is None:
            return
        hover = target_speed is not None and target_speed <= self._cfg["hover_speed"]
        self._watch_direction(speed, ground, accel, loaded, hover)
        band = self._cfg["accel_band"]
        sinking = climb < -self._cfg["sink_guard"]
        sagging = lift and sinking and not sink_rate
        too_fast = ground > self.speed_limit(agl) + self._cfg["speed_band"]
        if self.diving:
            self._pull_up(ground, accel, climb)
        elif low or sagging:
            if accel > 0 and (fast or sagging):
                self._tap(self._brake_key())
            elif accel < -band and sinking:
                self._tap("forward")
        elif too_fast:
            self._tap(self._brake_key())
        elif target_speed is not None and abs(climb) <= self._cfg["vertical_limit"]:
            target = min(target_speed, self.speed_limit(agl))
            self._pitch_for(ground, target, accel, sinking)

    def descend(self, agl: int | None, asl: int | None, speed: int | None) -> None:
        self._track(agl, asl, speed)
        if agl is None:
            return
        ground, accel, climb = self.ground, self.accel, self.climb
        slow_agl = agl <= self._cfg["sink_slow_agl"]
        allowed = self._cfg["touchdown_speed" if slow_agl else "descend_speed"]
        if self._sinking:
            allowed += self._cfg["speed_band"]
        calm = ground is not None and ground <= allowed
        self._sinking = calm
        target = 0.0
        if calm:
            target = -self._cfg["sink_rate_min" if slow_agl else "sink_rate"]
        band = self._cfg["sink_band"]
        self._inp.hold(self._keys["up"], climb < target - band)
        self._inp.hold(self._keys["down"], climb > target + band)
        if ground is None or abs(climb) > self._cfg["vertical_limit"]:
            return
        self._watch_direction(speed, ground, accel, False, True)
        self._pitch_for(ground, 0, accel, False)

    def yaw(self, x: float) -> None:
        now = self._clock()
        error = x - self._cfg["center_x"]
        if self.recovering or abs(self._roll) > self._cfg["roll_limit"]:
            self._aim.reset()
            self.lead = None
            return
        if abs(error) >= self._cfg["center_x"] - self._cfg["edge_margin"]:
            self._aim.reset()
            self.lead = error
            self._yaw_pulse("yaw_right" if error > 0 else "yaw_left", self._cfg["yaw_max_s"])
            return
        self._aim.add(now, x)
        if not self._aim.ready:
            self.lead = error
            return
        rate = self._aim.rate()
        self.lead = error + rate * self._cfg["yaw_lookahead_s"]
        still = abs(rate) <= self._cfg["yaw_still"]
        if abs(self.lead) <= self._cfg["yaw_deadband" if still else "yaw_coast_band"]:
            return
        seconds = clamp(
            abs(self.lead) * self._cfg["yaw_s_per_px"],
            self._cfg["yaw_min_s"],
            self._cfg["yaw_max_s"],
        )
        self._yaw_pulse("yaw_right" if self.lead > 0 else "yaw_left", seconds)

    def search(self, direction: str = "yaw_right") -> None:
        self._aim.reset()
        self._yaw_pulse(direction, self._cfg["yaw_max_s"])

    def bank(
        self, roll: int | None, lead: float | None = None, limit: float = 0, band: float = 0
    ) -> None:
        if roll is None:
            return
        self._roll = roll
        target = 0.0
        ground = self.ground or 0.0
        if lead is not None and not self.recovering:
            limit = limit or self._cfg["max_bank"] * min(1.0, ground / self._cfg["bank_speed"])
            target = clamp(lead * self._cfg["bank_per_px"], -limit, limit)
        error = target - roll
        now = self._clock()
        rolling = (
            self._keys["roll_left"] in self._pulses or self._keys["roll_right"] in self._pulses
        )
        steep = abs(roll) > self._cfg["roll_limit"] and roll * error < 0
        if abs(error) <= (band or self._cfg["roll_band"]) or rolling:
            return
        if now - self._last_roll < self._cfg["roll_interval_s"] and not steep:
            return
        seconds = clamp(
            abs(error) * self._cfg["roll_s_per_deg"],
            self._cfg["roll_min_s"],
            self._cfg["roll_max_s"],
        )
        self._pulse(self._keys["roll_right" if error > 0 else "roll_left"], seconds)
        self._last_roll = now

    def _track(self, agl: int | None, asl: int | None, speed: int | None) -> None:
        now = self._clock()
        self.height = agl if agl is not None else self.height
        self._agl.add(now, agl)
        self._asl.add(now, asl)
        settled = max(self._asl.span, self._agl.span) >= self._cfg["history_s"] / 2
        if speed is None or not settled:
            self.ground = None
            return
        vertical = self.climb * 3.6
        self.ground = float(np.sqrt(max(speed * speed - vertical * vertical, 0.0)))
        self._ground.add(now, self.ground)

    def _lift(self, agl: int, target: float) -> bool:
        predicted = agl + self._agl.rate() * self._cfg["agl_lookahead_s"]
        if predicted < target - self._cfg["agl_band"]:
            return True
        if predicted > target + self._cfg["agl_band"]:
            return False
        return self._inp.is_down(self._keys["up"])

    def _pitch_for(self, ground: float, target: float, accel: float, sinking: bool) -> None:
        hover = self._cfg["hover_speed"]
        band = self._cfg["accel_band"]
        if target <= hover or self.reverse:
            drifting = (
                self._cfg["trim_speed"] < ground <= hover and accel > self._cfg["drift_accel"]
            )
            braking = ground > hover and accel > -self._cfg["brake_gain"] * ground
            if drifting or braking:
                self._tap(self._brake_key(), self._cfg["hover_tap_s"])
            return
        limit = self._cfg["accel_max"]
        wanted = clamp(self._cfg["speed_gain"] * (target - ground), -limit, limit)
        lagging = ground < target - self._cfg["speed_band"] and accel <= 0
        leading = ground > target + self._cfg["speed_band"] and accel >= 0
        if (accel < wanted - band or lagging) and not sinking:
            self._tap("forward")
        elif accel > wanted + band or leading:
            self._tap(self._brake_key())

    def _pull_up(self, ground: float, accel: float, climb: float) -> None:
        now = self._clock()
        if now - self._last_pitch < self._cfg["dive_interval_s"]:
            return
        if accel < -self._cfg["lean_accel"] or ground <= self._cfg["hover_speed"]:
            return
        seconds = clamp(
            -climb * self._cfg["dive_tap_s_per_ms"],
            self._cfg["hover_tap_s"],
            self._cfg["dive_tap_max_s"],
        )
        self._pulse(self._keys["back"], seconds)
        self._last_pitch = now
        self._taps["back"].append(now)

    def _watch_dive(self, ground: float | None, accel: float, climb: float) -> None:
        agl_falling = self._agl.rate() < -self._cfg["dive_agl_rate"]
        sinking = climb < -self._cfg["dive_sink"]
        falling = sinking or (agl_falling and accel > self._cfg["dive_accel"])
        if falling and ground is not None and ground > self._cfg["forward_speed"]:
            self.diving = True
        elif not falling and climb > -self._cfg["dive_exit"]:
            self.diving = False

    def _watch_direction(
        self, speed: int, ground: float, accel: float, loaded: bool, hover: bool
    ) -> None:
        now = self._clock()
        window = self._cfg["tap_window_s"]
        moving = speed > self._cfg["trim_speed"]
        own = now - self._last_pitch < window
        self.drifting = moving and not own and accel > self._cfg["drift_accel"]
        if ground > self._cfg["forward_speed"]:
            self.reverse, self._suspect, self._slowing = False, 0, False
            return
        band = self._cfg["reverse_accel"]
        if not moving:
            recent = [(t, key) for key, taps in self._taps.items() for t in taps]
            last = max(recent)[1] if recent else None
            backward = self.reverse and loaded if last is None else last == "back"
            self.reverse = hover and backward
            self._suspect, self._learn_after = 0, now + self._cfg["history_s"]
        elif ground < self._cfg["crossing_speed"] and now - self._last_brake < window:
            if self._slowing and accel > band and now >= self._learn_after:
                self.reverse = not self.reverse
                self._suspect, self._learn_after = 0, now + self._cfg["history_s"]
                self._slowing = False
        if accel < -band:
            self._slowing = True
        elif accel > band:
            self._slowing = False
        if ground >= self._cfg["learn_speed"]:
            return
        if loaded and hover and self.drifting:
            self.reverse = True
        self._learn_direction(ground, accel)

    def _learn_direction(self, ground: float, accel: float) -> None:
        if self._tapped is None or not self._pitch_ready():
            return
        brake, before = self._tapped
        self._tapped = None
        if self._clock() < self._learn_after:
            return
        clear = ground > self._cfg["hover_speed"] and 3.6 * abs(self.climb) < ground / 2
        worse = accel > self._cfg["reverse_accel"] and accel > before - self._cfg["brake_effect"]
        self._suspect = self._suspect + 1 if brake and worse and clear else 0
        if self._suspect >= 2:
            self.reverse, self._suspect = not self.reverse, 0

    def _pitch_ready(self) -> bool:
        return self._clock() - self._last_pitch >= self._cfg["pitch_interval_s"]

    def _brake_key(self) -> str:
        return "forward" if self.reverse else "back"

    def _tap(self, key: str, seconds: float = 0) -> None:
        brake = key == self._brake_key()
        if not self._pitch_ready() or not self._may_tap(key, brake):
            return
        now = self._clock()
        self._pulse(self._keys[key], seconds or self._cfg["pitch_tap_s"])
        self._last_pitch = now
        self._taps[key].append(now)
        self._tapped = (brake, self.accel)
        if brake:
            self._last_brake = now

    def _may_tap(self, key: str, brake: bool) -> bool:
        now = self._clock()
        taps = self._taps[key]
        while taps and now - taps[0] > self._cfg["tap_window_s"]:
            taps.popleft()
        accel = self.accel
        if brake:
            if accel < -self._cfg["lean_accel"]:
                return False
            return self.recovering or len(taps) < self._cfg["window_taps"]
        return accel < self._cfg["lean_accel"] and len(taps) < self._cfg["window_taps"]

    def _yaw_pulse(self, direction: str, seconds: float) -> None:
        now = self._clock()
        if self.yawing or now < self._yaw_free_at:
            return
        self._pulse(self._keys[direction], seconds)
        self._yaw_free_at = now + seconds + self._cfg["yaw_wait_s"]

    def _pulse(self, key: str, seconds: float) -> None:
        self._inp.key_down(key)
        self._pulses[key] = self._clock() + seconds

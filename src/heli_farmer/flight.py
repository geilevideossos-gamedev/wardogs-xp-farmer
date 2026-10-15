from collections import deque
from collections.abc import Callable

import numpy as np

from heli_farmer.inputs import Input


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

    def rate(self) -> float:
        if len(self._samples) < 2:
            return 0.0
        (t0, v0), (t1, v1) = self._samples[0], self._samples[-1]
        return (v1 - v0) / (t1 - t0) if t1 > t0 else 0.0


class Pilot:
    def __init__(self, inp: Input, keys: dict, flight: dict, clock: Callable[[], float]):
        self._inp = inp
        self._keys = keys
        self._cfg = flight
        self._clock = clock
        self._agl = Trend(flight["history_s"])
        self._asl = Trend(flight["history_s"])
        self._speed = Trend(flight["history_s"])
        self._pulses: dict[str, float] = {}
        self._last_pitch = -1e9
        self._last_yaw = -1e9

    def update(self) -> None:
        now = self._clock()
        for key, until in list(self._pulses.items()):
            if now >= until:
                self._inp.key_up(key)
                del self._pulses[key]

    def release(self) -> None:
        for key in ("up", "down", "forward", "back", "yaw_left", "yaw_right"):
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
        target_speed: float,
        floor: float = 0,
    ) -> None:
        self._track(agl, asl, speed)
        if agl is None:
            return
        low = agl < floor
        lift = low or self._lift(agl, target_agl)
        self._inp.hold(self._keys["up"], lift)
        self._inp.hold(self._keys["down"], False)
        if speed is None:
            return
        limit = self.speed_limit(agl)
        sinking = self._asl.rate() < -self._cfg["sink_guard"]
        accel = self._speed.rate()
        if speed > limit + self._cfg["speed_band"] or (lift and sinking) or (low and accel > 0):
            self._pitch("back")
        elif not low:
            self._pitch_for(speed, min(target_speed, limit), accel, sinking)

    def descend(self, agl: int | None, asl: int | None, speed: int | None) -> None:
        self._track(agl, asl, speed)
        if agl is None:
            return
        if speed is not None and speed > self.speed_limit(agl):
            target = 0.0
        elif agl > self._cfg["sink_slow_agl"]:
            target = -self._cfg["sink_rate"]
        else:
            target = -self._cfg["sink_rate_min"]
        rate = self._asl.rate()
        band = self._cfg["sink_band"]
        self._inp.hold(self._keys["up"], rate < target - band)
        self._inp.hold(self._keys["down"], rate > target + band)
        if speed is not None:
            self._pitch_for(speed, 0, self._speed.rate(), False)

    def yaw(self, x: float) -> bool:
        error = x - self._cfg["center_x"]
        if abs(error) <= self._cfg["yaw_deadband"]:
            return True
        now = self._clock()
        if self._yawing() or now - self._last_yaw < self._cfg["yaw_interval_s"]:
            return False
        seconds = abs(error) * self._cfg["yaw_s_per_px"]
        seconds = max(self._cfg["yaw_min_s"], min(self._cfg["yaw_max_s"], seconds))
        self._pulse(self._keys["yaw_right" if error > 0 else "yaw_left"], seconds)
        self._last_yaw = now
        return False

    def search(self, direction: str = "yaw_right") -> None:
        if not self._yawing():
            self._pulse(self._keys[direction], self._cfg["yaw_max_s"])

    def _track(self, agl: int | None, asl: int | None, speed: int | None) -> None:
        now = self._clock()
        self._agl.add(now, agl)
        self._asl.add(now, asl)
        self._speed.add(now, speed)

    def _lift(self, agl: int, target: float) -> bool:
        predicted = agl + self._agl.rate() * self._cfg["agl_lookahead_s"]
        if predicted < target - self._cfg["agl_band"]:
            return True
        if predicted > target + self._cfg["agl_band"]:
            return False
        return self._inp.is_down(self._keys["up"])

    def _pitch_for(self, speed: int, target: float, accel: float, sinking: bool) -> None:
        limit = self._cfg["accel_max"]
        wanted = max(-limit, min(limit, self._cfg["speed_gain"] * (target - speed)))
        band = self._cfg["accel_band"]
        if accel < wanted - band and not sinking:
            self._pitch("forward")
        elif accel > wanted + band:
            self._pitch("back")

    def _pitch(self, key: str) -> None:
        now = self._clock()
        if now - self._last_pitch < self._cfg["pitch_interval_s"]:
            return
        self._pulse(self._keys[key], self._cfg["pitch_tap_s"])
        self._last_pitch = now

    def _yawing(self) -> bool:
        return self._keys["yaw_left"] in self._pulses or self._keys["yaw_right"] in self._pulses

    def _pulse(self, key: str, seconds: float) -> None:
        self._inp.key_down(key)
        self._pulses[key] = self._clock() + seconds

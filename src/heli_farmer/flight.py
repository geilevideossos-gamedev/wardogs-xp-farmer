from collections import deque
from collections.abc import Callable

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
        self._speed = Trend(flight["history_s"])
        self._pulses: dict[str, float] = {}
        self._last_speed_tap = -1e9
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

    def altitude(self, agl: int | None, target: float) -> None:
        self._agl.add(self._clock(), agl)
        if agl is None:
            return
        band = self._cfg["agl_band"]
        predicted = agl + self._agl.rate() * self._cfg["agl_lookahead_s"]
        up = self._inp.is_down(self._keys["up"])
        down = False
        if predicted < target - band:
            up = True
        elif predicted > target + band:
            up = False
            down = predicted > target + 3 * band
        self._inp.hold(self._keys["up"], up)
        self._inp.hold(self._keys["down"], down)

    def sink(self, agl: int | None) -> None:
        self._agl.add(self._clock(), agl)
        if agl is None:
            return
        rate = self._agl.rate()
        target = -self._cfg["sink_rate"] if agl > 10 else -self._cfg["sink_rate_min"]
        band = self._cfg["sink_band"]
        self._inp.hold(self._keys["up"], rate < target - band)
        self._inp.hold(self._keys["down"], rate > target + band)

    def speed(self, speed: int | None, target: float) -> None:
        now = self._clock()
        self._speed.add(now, speed)
        if speed is None or now - self._last_speed_tap < self._cfg["speed_tap_interval_s"]:
            return
        limit = self._cfg["accel_max"]
        wanted = max(-limit, min(limit, self._cfg["speed_gain"] * (target - speed)))
        accel = self._speed.rate()
        band = self._cfg["accel_band"]
        if accel < wanted - band:
            self._pulse(self._keys["forward"], self._cfg["tap_s"])
            self._last_speed_tap = now
        elif accel > wanted + band:
            self._pulse(self._keys["back"], self._cfg["tap_s"])
            self._last_speed_tap = now

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

    def search(self) -> None:
        if not self._yawing():
            self._pulse(self._keys["yaw_right"], self._cfg["yaw_max_s"])

    def _yawing(self) -> bool:
        return self._keys["yaw_left"] in self._pulses or self._keys["yaw_right"] in self._pulses

    def _pulse(self, key: str, seconds: float) -> None:
        self._inp.key_down(key)
        self._pulses[key] = self._clock() + seconds

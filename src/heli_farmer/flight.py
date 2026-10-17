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

    def rate(self) -> float:
        if len(self._samples) < 2:
            return 0.0
        (t0, v0), (t1, v1) = self._samples[0], self._samples[-1]
        return (v1 - v0) / (t1 - t0) if t1 > t0 else 0.0


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
        self._speed = Trend(flight["history_s"])
        self._aim = Trend(flight["yaw_history_s"])
        self._pulses: dict[str, float] = {}
        self._last_pitch = -1e9
        self._yaw_free_at = -1e9
        self._last_roll = -1e9
        self.tilt = 0
        self.reverse = False
        self._brake_accel: float | None = None
        self.lead: float | None = None
        self.on_target = False

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
        low = agl < floor
        rate = self._asl.rate()
        sinking_fast = sink_rate > 0 and rate < -sink_rate - self._cfg["sink_band"]
        lift = low or sinking_fast or self._lift(agl, target_agl)
        predicted = agl + self._agl.rate() * self._cfg["agl_lookahead_s"]
        above = predicted > target_agl + self._cfg["agl_band"]
        self._inp.hold(self._keys["up"], lift)
        self._inp.hold(
            self._keys["down"], sink_rate > 0 and above and not lift and rate > -sink_rate
        )
        if speed is None:
            return
        limit = self.speed_limit(agl)
        sinking = rate < -self._cfg["sink_guard"]
        accel = self._speed.rate()
        too_fast = speed > limit + self._cfg["speed_band"]
        nose_low = lift and sinking and not sink_rate
        if too_fast or nose_low or (low and accel > 0 and self.tilt > 0):
            self._pitch("back")
        elif not low and target_speed is not None:
            self._pitch_for(speed, min(target_speed, limit), accel, sinking, loaded)

    def descend(self, agl: int | None, asl: int | None, speed: int | None) -> None:
        self._track(agl, asl, speed)
        if agl is None:
            return
        slow_agl = agl <= self._cfg["sink_slow_agl"]
        if speed is not None and speed > self.speed_limit(agl):
            target = 0.0
        elif slow_agl and speed is not None and speed > self._cfg["touchdown_speed"]:
            target = 0.0
        elif not slow_agl:
            target = -self._cfg["sink_rate"]
        else:
            target = -self._cfg["sink_rate_min"]
        rate = self._asl.rate()
        band = self._cfg["sink_band"]
        self._inp.hold(self._keys["up"], rate < target - band)
        self._inp.hold(self._keys["down"], rate > target + band)
        if speed is not None:
            self._pitch_for(speed, 0, self._speed.rate(), False)

    def yaw(self, x: float) -> None:
        now = self._clock()
        error = x - self._cfg["center_x"]
        if abs(error) >= self._cfg["center_x"] - self._cfg["edge_margin"]:
            self._aim.reset()
            self.lead, self.on_target = error, False
            self._yaw_pulse("yaw_right" if error > 0 else "yaw_left", self._cfg["yaw_max_s"])
            return
        self._aim.add(now, x)
        if not self._aim.ready:
            self.lead, self.on_target = error, False
            return
        rate = self._aim.rate()
        self.lead = error + rate * self._cfg["yaw_lookahead_s"]
        deadband = self._cfg["yaw_deadband"]
        still = abs(rate) <= self._cfg["yaw_still"]
        self.on_target = abs(error) <= deadband and still and not self.yawing
        if abs(self.lead) <= (deadband if still else self._cfg["yaw_coast_band"]):
            return
        seconds = clamp(
            abs(self.lead) * self._cfg["yaw_s_per_px"],
            self._cfg["yaw_min_s"],
            self._cfg["yaw_max_s"],
        )
        self._yaw_pulse("yaw_right" if self.lead > 0 else "yaw_left", seconds)

    def search(self, direction: str = "yaw_right") -> None:
        self._aim.reset()
        self.on_target = False
        self._yaw_pulse(direction, self._cfg["yaw_max_s"])

    def bank(self, roll: int | None, speed: int | None, lead: float | None = None) -> None:
        if roll is None:
            return
        target = 0.0
        if lead is not None and speed is not None and speed >= self._cfg["bank_speed"]:
            limit = self._cfg["max_bank"]
            target = clamp(lead * self._cfg["bank_per_px"], -limit, limit)
        error = target - roll
        now = self._clock()
        rolling = (
            self._keys["roll_left"] in self._pulses or self._keys["roll_right"] in self._pulses
        )
        if abs(error) <= self._cfg["roll_band"] or rolling:
            return
        if now - self._last_roll < self._cfg["roll_interval_s"]:
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
        self._agl.add(now, agl)
        self._asl.add(now, asl)
        self._speed.add(now, speed)
        if agl is not None and speed is not None:
            if agl <= self._cfg["landed_agl"] and speed <= self._cfg["landed_speed"]:
                self.tilt = 0

    def _lift(self, agl: int, target: float) -> bool:
        predicted = agl + self._agl.rate() * self._cfg["agl_lookahead_s"]
        if predicted < target - self._cfg["agl_band"]:
            return True
        if predicted > target + self._cfg["agl_band"]:
            return False
        return self._inp.is_down(self._keys["up"])

    def _pitch_for(
        self, speed: int, target: float, accel: float, sinking: bool, loaded: bool = False
    ) -> None:
        hover = self._cfg["hover_speed"]
        band = self._cfg["accel_band"]
        if target <= hover:
            if speed <= self._cfg["trim_speed"]:
                self.reverse, self._brake_accel = False, None
            if speed <= hover:
                if speed > self._cfg["trim_speed"] and accel > 0:
                    self._drift(loaded)
            elif accel > -self._cfg["brake_accel"] and self._pitch_ready():
                last = self._brake_accel
                if last is not None and accel > max(last, self._cfg["reverse_accel"]):
                    self.reverse = not self.reverse
                self._pitch("forward" if self.reverse else "back")
                self._brake_accel = accel
            return
        limit = self._cfg["accel_max"]
        wanted = clamp(self._cfg["speed_gain"] * (target - speed), -limit, limit)
        if accel < wanted - band and not sinking:
            if self.tilt < self._cfg["max_tilt"]:
                self._pitch("forward")
            elif accel < self._cfg["trim_accel"]:
                self._pitch("forward", self._cfg["trim_tap_s"], counted=False)
        elif accel > wanted + band:
            self._pitch("back")

    def _drift(self, loaded: bool) -> None:
        if self.tilt > 0:
            self._pitch("back")
        elif self.tilt < 0 or self.reverse:
            self._pitch("forward")
        elif loaded:
            self._pitch("forward", self._cfg["trim_tap_s"], counted=False)

    def _pitch_ready(self) -> bool:
        return self._clock() - self._last_pitch >= self._cfg["pitch_interval_s"]

    def _pitch(self, key: str, seconds: float | None = None, counted: bool = True) -> None:
        if not self._pitch_ready():
            return
        self._pulse(self._keys[key], seconds or self._cfg["pitch_tap_s"])
        self._last_pitch = self._clock()
        if counted:
            self.tilt += 1 if key == "forward" else -1

    def _yaw_pulse(self, direction: str, seconds: float) -> None:
        now = self._clock()
        if self.yawing or now < self._yaw_free_at:
            return
        self._pulse(self._keys[direction], seconds)
        self._yaw_free_at = now + seconds + self._cfg["yaw_wait_s"]

    def _pulse(self, key: str, seconds: float) -> None:
        self._inp.key_down(key)
        self._pulses[key] = self._clock() + seconds

import math
import threading
from collections import deque
from unittest.mock import Mock

import numpy as np
import pytest

from heli_farmer.config import load_config
from heli_farmer.crate_loop import CrateLoop, LeaveLayer, StepFailed
from heli_farmer.detectors import Marker
from heli_farmer.flight import Pilot
from heli_farmer.inputs import Input
from heli_farmer.states import RoundOver

FRAME = np.zeros((4, 4, 3), np.uint8)
TICK = 0.05
GROUND_ASL = 100.0
PITCH_RATE = 25.0
YAW_RATE = 40.0
YAW_DELAY = 0.3
YAW_LAG = 0.2
YAW_COAST = 0.5
WEATHERVANE = 60.0
SIDE_FORCE = 20.0
TRANSLATIONAL_LIFT = 0.05
ROLL_RATE = 35.0
CRATE_DRIFT = 0.3
SHIFT_LIFT = 1 / math.cos(math.radians(15))
CTRL_LIFT = 0.93
FOV_HALF = 45.0
BASE_RADIUS = 80.0
BASE_AREA = 200.0


class World:
    def __init__(self, clicks: dict):
        self.now = 0.0
        self.agl = 0.0
        self.vel = [0.0, 0.0]
        self.pitch = 0.0
        self.roll = 0.0
        self.climb = 0.0
        self.pos = [0.0, 0.0]
        self.heading = 90.0
        self.yaw_rate = 0.0
        self._yaw_input = 0.0
        self._yaw_queue = deque([0] * round(YAW_DELAY / TICK), maxlen=round(YAW_DELAY / TICK))
        self.substeps = 1
        self.errors: list[float] = []
        self.zone = (0.0, 2000.0)
        self.radius = 250.0
        self.tint = True
        self.hz = True
        self.base_tint_until = math.inf
        self.base = (0.0, 0.0)
        self.crate = False
        self.menu = None
        self.prompt = True
        self.delivered = False
        self.first_aid = False
        self.round_over = False
        self.damaged = False
        self.lakota = True
        self.buy_works = True
        self.confirm_misses = 0
        self.mouse = (0, 0)
        self.keys: set[str] = set()
        self._clicks = {tuple(v): k for k, v in clicks.items()}
        self.clicked: list[str] = []
        self.drops: list[dict] = []
        self.entered: float | None = None
        self.entry_speed: float | None = None
        self.track: list[tuple[float, float]] = []
        self.pressed: list[str] = []
        self.max_pitch = 0.0
        self.min_pitch = 0.0
        self.min_agl = math.inf
        self.zone_samples: list[tuple[float, float]] = []

    def press(self, name: str, down: bool) -> None:
        if down:
            self.keys.add(name)
            self.pressed.append(name)
            if name == "b" and self.buy_prompt():
                self.menu = "main"
                self.lakota = False
            if name == "g" and self.crate:
                self.crate = False
                self.delivered = self.inside() and self.agl <= 90
                drop = {
                    "t": self.now,
                    "inside": self.inside(),
                    "agl": self.agl,
                    "speed": self.ground_speed,
                    "roll": self.roll,
                }
                self.drops.append(drop)
        else:
            self.keys.discard(name)

    def move(self, x: int, y: int) -> None:
        self.mouse = (x, y)

    def click(self) -> None:
        name = self._clicks[self.mouse]
        self.clicked.append(name)
        if name == "logistics" and self.menu == "main" and not self.slots_full():
            self.menu = "logistics"
        elif name == "ammo_pallet" and self.menu == "logistics" and self.buy_works:
            self.crate = True
            self.menu = "main"
        elif name == "confirm" and self.confirm_misses:
            self.confirm_misses -= 1
        elif name == "confirm":
            self.menu = None
            self.lakota = True

    def slots_full(self) -> bool:
        return self.menu == "main" and self.crate

    def step(self) -> np.ndarray:
        for _ in range(self.substeps):
            self.now += TICK
            if not self.menu:
                self.fly()
            if self.inside() and self.entered is None:
                self.entered, self.entry_speed = self.now, self.ground_speed
        return FRAME

    @property
    def speed(self) -> float:
        h = math.radians(self.heading)
        return self.vel[0] * math.sin(h) + self.vel[1] * math.cos(h)

    @speed.setter
    def speed(self, value: float) -> None:
        h = math.radians(self.heading)
        self.vel = [value * math.sin(h), value * math.cos(h)]

    @property
    def ground_speed(self) -> float:
        return math.hypot(*self.vel)

    def sideslip(self) -> float:
        if self.ground_speed < 1:
            return 0.0
        track = math.degrees(math.atan2(self.vel[0], self.vel[1]))
        return (track - self.heading + 180) % 360 - 180

    def yaw(self) -> None:
        delayed = self._yaw_queue[0]
        self._yaw_queue.append(1 if "e" in self.keys else -1 if "q" in self.keys else 0)
        self._yaw_input += (delayed - self._yaw_input) * TICK / YAW_LAG
        authority = YAW_RATE * max(0.2, 1 - self.ground_speed / 200)
        self.yaw_rate += (authority * self._yaw_input - self.yaw_rate) * TICK / YAW_COAST

    def fly(self) -> None:
        if "w" in self.keys:
            self.pitch = min(35.0, self.pitch + PITCH_RATE * TICK)
        if "s" in self.keys:
            self.pitch = max(-40.0, self.pitch - PITCH_RATE * TICK)
        if "d" in self.keys:
            self.roll = min(60.0, self.roll + ROLL_RATE * TICK)
        if "a" in self.keys:
            self.roll = max(-60.0, self.roll - ROLL_RATE * TICK)
        if self.crate and self.agl > 0:
            self.pitch -= CRATE_DRIFT * TICK
        lift = SHIFT_LIFT if "shift" in self.keys else CTRL_LIFT if "ctrl" in self.keys else 1.0
        tilt = math.cos(math.radians(self.pitch)) * math.cos(math.radians(self.roll))
        tilt *= 1 + TRANSLATIONAL_LIFT * (self.ground_speed / 250) ** 2
        wanted = 80 * (lift * tilt - 1)
        self.climb += (wanted - self.climb) * TICK / 0.5
        self.agl = max(0.0, self.agl + self.climb * TICK)
        self.yaw()
        if self.agl == 0:
            self.climb, self.speed = max(0.0, self.climb), 0.0
            self.pitch = self.roll = self.yaw_rate = 0.0
            return
        h = math.radians(self.heading)
        forward, right = (math.sin(h), math.cos(h)), (math.cos(h), -math.sin(h))
        slip = math.sin(math.radians(self.sideslip()))
        grip = (self.ground_speed / 150) ** 2
        push = 1.2 * self.pitch
        side = 3.6 * 9.81 * math.tan(math.radians(self.roll)) + SIDE_FORCE * slip * grip
        for i in range(2):
            self.vel[i] += (push * forward[i] + side * right[i] - 0.1 * self.vel[i]) * TICK
        turn = self.yaw_rate + WEATHERVANE * slip * grip
        self.heading = (self.heading + turn * TICK) % 360
        self.pos[0] += self.vel[0] / 3.6 * TICK
        self.pos[1] += self.vel[1] / 3.6 * TICK
        self.track.append((self.agl, self.ground_speed))
        self.max_pitch = max(self.max_pitch, self.pitch)
        self.min_pitch = min(self.min_pitch, self.pitch)
        self.min_agl = min(self.min_agl, self.agl)
        if self.inside() and self.crate:
            self.zone_samples.append((self.climb, self.roll))

    def bearing(self, target: tuple[float, float]) -> tuple[float, float]:
        dx, dy = target[0] - self.pos[0], target[1] - self.pos[1]
        error = (math.degrees(math.atan2(dx, dy)) - self.heading + 180) % 360 - 180
        return error, math.hypot(dx, dy)

    def marker(self, target: tuple[float, float], **extra) -> Marker:
        error, distance = self.bearing(target)
        if abs(error) <= FOV_HALF:
            x = round(960 + error * 900 / FOV_HALF)
        else:
            x = 120 if error < 0 else 1800
        y = 400 + round(200 * min(1.0, 300 / max(distance, 1.0)))
        return Marker(x, y, 0.9, **extra)

    def inside(self) -> bool:
        return self.bearing(self.zone)[1] < self.radius

    def buy_prompt(self) -> bool:
        return self.prompt and self.bearing(self.base)[1] < BASE_RADIUS and self.agl < 40


class FakeVision:
    def __init__(self, world: World):
        self.w = world

    def first_aid(self, frame):
        return self.w.first_aid

    def round_over(self, frame):
        return self.w.round_over

    def in_lakota(self, frame):
        return self.w.lakota

    def heli_damaged(self, frame):
        return self.w.damaged

    def garage_menu(self, frame):
        return self.w.menu

    def slots_full(self, frame):
        return self.w.slots_full()

    def crate_loaded(self, frame):
        return self.w.lakota and self.w.crate

    def buy_prompt(self, frame):
        return self.w.buy_prompt() and not self.w.menu

    def delivered(self, frame):
        return self.w.delivered

    def agl(self, frame):
        return round(self.w.agl) if self.w.lakota else None

    def asl(self, frame):
        return round(GROUND_ASL + self.w.agl) if self.w.lakota else None

    def speed(self, frame):
        return round(self.w.ground_speed) if self.w.lakota else None

    def roll(self, frame):
        return round(self.w.roll) if self.w.lakota else None

    def zone_marker(self, frame):
        distance = self.w.bearing(self.w.zone)[1]
        if self.w.inside() and self.w.hz:
            return self.w.marker(self.w.zone, kind="HZ", distance=round(distance))
        return self.w.marker(self.w.zone, kind="CZ", distance=round(distance - self.w.radius))

    def hq_marker(self, frame):
        error, _ = self.w.bearing(self.w.base)
        if self.w.inside() or abs(error) > FOV_HALF:
            return None
        return self.w.marker(self.w.base, distance=round(self.w.bearing(self.w.base)[1]))

    def minimap_over_base(self, frame):
        return self.minimap_in_zone(frame)

    def minimap_in_zone(self, frame):
        over_base = self.w.bearing(self.w.base)[1] < BASE_AREA
        over_base = over_base and self.w.now < self.w.base_tint_until
        return (self.w.inside() and self.w.tint) or over_base


@pytest.fixture
def config():
    config = load_config("config.yaml")
    config["flight"]["tick_s"] = 0
    config["flight"]["tap_s"] = TICK
    config["buy"]["pause_s"] = 0
    return config


@pytest.fixture
def world(config):
    return World(config["buy"]["clicks"])


@pytest.fixture
def loop(config, world):
    backend = Mock()
    backend.keyDown.side_effect = lambda key: world.press(key, True)
    backend.keyUp.side_effect = lambda key: world.press(key, False)
    backend.moveTo.side_effect = world.move
    backend.mouseUp.side_effect = lambda button: world.click()
    inp = Input(threading.Event(), backend=backend, clock=lambda: world.now)
    return CrateLoop(
        FakeVision(world), inp, world.step, threading.Event(), config, clock=lambda: world.now
    )


def airborne(
    loop: CrateLoop, world: World, agl: float, speed: float, heading: float, pos=(0.0, 0.0)
) -> None:
    world.agl, world.heading, world.pos = agl, heading, list(pos)
    world.speed = speed
    tap = PITCH_RATE * loop._flight["pitch_tap_s"]
    loop._pilot.tilt = round(speed / 12 / tap)
    world.pitch = loop._pilot.tilt * tap


def assert_never_low_and_fast(world: World, config: dict) -> None:
    limit = Pilot(Mock(), config["keys"], config["flight"], lambda: 0).speed_limit
    band = config["flight"]["speed_band"]
    too_fast = [(round(a), round(s)) for a, s in world.track if s > limit(a) + 2 * band]
    assert not too_fast


def test_buy_walks_through_menu(loop, world):
    loop.step("buy")
    assert world.crate and world.menu is None
    assert world.clicked == ["logistics", "pallets", "ammo_pallet", "confirm"]
    assert loop.stats["bought"] == 1


def test_buy_skips_when_crate_loaded(loop, world):
    world.crate = True
    loop.step("buy")
    assert world.clicked == []


def test_buy_only_confirms_when_slots_full(loop, world):
    world.crate, world.menu, world.lakota = True, "main", False
    loop.step("buy")
    assert world.clicked == ["confirm"]
    assert world.menu is None and loop.stats["bought"] == 1


def test_buy_repeats_confirm_until_menu_closes(loop, world):
    world.confirm_misses = 2
    loop.step("buy")
    assert world.clicked == ["logistics", "pallets", "ammo_pallet", "confirm", "confirm", "confirm"]
    assert world.crate and world.menu is None


def test_buy_stops_when_confirm_never_works(loop, world):
    world.confirm_misses = 99
    with pytest.raises(StepFailed, match="CONFIRM"):
        loop.step("buy")


def test_buy_needs_buy_prompt(loop, world):
    world.prompt = False
    with pytest.raises(StepFailed):
        loop.step("buy")


def test_buy_gives_up_without_money(loop, world):
    world.buy_works = False
    with pytest.raises(StepFailed):
        loop.step("buy")


def test_climb_lifts_off_a_few_meters(loop, world, config):
    loop.step("climb")
    assert config["maps"]["default"]["turn_agl"] - 1 <= world.agl < 40
    assert world.ground_speed < 5
    assert not world.keys


def first_yaw(world: World) -> str:
    return next(key for key in world.pressed if key in ("q", "e"))


def assert_aimed(world, target, config):
    flight = config["flight"]
    assert abs(world.marker(target).x - flight["center_x"]) <= flight["yaw_deadband"]
    assert abs(world.yaw_rate) < 3


def test_turn_yaws_to_zone_marker_only(loop, world, config):
    world.crate = True
    airborne(loop, world, 25, 0, 90)
    loop.step("turn")
    assert_aimed(world, world.zone, config)
    assert world.ground_speed < 5


def test_turn_toward_marker_at_left_edge_never_searches_right(loop, world, config):
    world.crate = True
    airborne(loop, world, 25, 0, 90)
    world.zone = (-350.0, 2000.0)
    loop.step("turn")
    assert_aimed(world, world.zone, config)
    assert first_yaw(world) == "q"


@pytest.mark.parametrize("substeps", [1, 3])
@pytest.mark.parametrize("heading", [0, 45, 90, 180, 300])
def test_turn_settles_without_pendulum(loop, world, config, heading, substeps):
    world.crate, world.substeps = True, substeps
    airborne(loop, world, 25, 0, heading)
    errors = []
    grab = loop._grab
    loop._grab = lambda: (errors.append(world.marker(world.zone).x - 960), grab())[1]
    loop.step("turn")
    assert_aimed(world, world.zone, config)
    pairs = zip(errors, errors[1:], strict=False)
    overshoots = sum(1 for a, b in pairs if a * b < 0 and abs(b) > 80)
    assert overshoots <= 1
    assert world.now < config["flight"]["turn_timeout_s"] / 2


def test_turn_brakes_heli_that_still_rotates(loop, world, config):
    world.crate = True
    airborne(loop, world, 25, 0, 355)
    world.yaw_rate = 40.0
    loop.step("turn")
    assert first_yaw(world) == "q"
    assert_aimed(world, world.zone, config)


def test_hover_with_crate_holds_position(loop, world):
    world.crate = True
    loop.step("climb")
    loop.step("turn")
    assert world.ground_speed < 10
    assert "w" in world.pressed


def test_turn_searches_hq_when_not_visible(loop, world, config):
    airborne(loop, world, 100, 0, 90, pos=(0, 1500))
    loop.step("turn")
    assert_aimed(world, world.base, config)


def test_drop_waits_three_seconds_inside(loop, world, config):
    world.crate = True
    airborne(loop, world, 100, 0, 0)
    loop.step("drop")
    (drop,) = world.drops
    assert drop["inside"] and drop["agl"] >= config["maps"]["default"]["drop_min_agl"]
    assert drop["t"] - world.entered >= config["flight"]["drop_delay_s"]
    assert loop.stats["dropped"] == 1 and loop.stats["delivered"] == 1
    assert_never_low_and_fast(world, config)


def test_cruise_keeps_tilt_moderate(loop, world, config):
    world.crate = True
    airborne(loop, world, 100, 0, 0)
    loop.step("drop")
    flight = config["flight"]
    assert world.max_pitch <= flight["max_tilt"] * PITCH_RATE * flight["pitch_tap_s"] + 3


def test_zone_hold_is_level_and_sinks_gently(loop, world, config):
    world.crate = True
    airborne(loop, world, 100, 0, 0)
    loop.step("drop")
    assert world.zone_samples
    assert min(climb for climb, _ in world.zone_samples) > -2 * config["flight"]["drop_sink_rate"]
    assert max(abs(roll) for _, roll in world.zone_samples) <= config["flight"]["roll_band"] + 2


def test_drop_banks_into_turn_at_speed(loop, world):
    world.crate = True
    airborne(loop, world, 100, 150, 60)
    loop.step("drop")
    assert world.drops[0]["inside"]
    assert "a" in world.pressed


def test_drop_brakes_before_zone(loop, world, config):
    world.crate, world.zone = True, (0.0, 5000.0)
    airborne(loop, world, 100, 0, 0)
    loop.step("drop")
    cruise_speed = config["maps"]["default"]["cruise_speed"]
    assert max(speed for _, speed in world.track) > cruise_speed - 30
    drop_speed = config["maps"]["default"]["drop_speed"]
    assert world.entry_speed <= drop_speed + 2 * config["flight"]["speed_band"]


def test_drop_with_hz_when_minimap_circle_is_white(loop, world, config):
    world.crate, world.tint = True, False
    airborne(loop, world, 100, 0, 0)
    loop.step("drop")
    (drop,) = world.drops
    assert drop["inside"]
    assert drop["t"] - world.entered < config["flight"]["drop_delay_s"] + 1


def test_drop_with_minimap_when_marker_shows_no_hz(loop, world, config):
    world.crate, world.hz = True, False
    airborne(loop, world, 100, 0, 0)
    loop.step("drop")
    (drop,) = world.drops
    assert drop["inside"]
    assert drop["t"] - world.entered < config["flight"]["drop_delay_s"] + 1


def test_drop_ignores_tinted_minimap_over_base(loop, world):
    world.crate, world.hz = True, False
    airborne(loop, world, 30, 0, 0)
    loop.step("drop")
    assert world.drops[0]["inside"]


def test_drop_has_no_upper_height_limit(loop, world, config):
    world.crate = True
    airborne(loop, world, 130, 0, 0, pos=(0, 1800))
    loop.step("drop")
    (drop,) = world.drops
    assert drop["inside"] and drop["agl"] > 100
    assert drop["t"] < config["flight"]["drop_delay_s"] + 1


def test_leave_turns_around_and_flies_out(loop, world):
    airborne(loop, world, 70, 100, 0, pos=(0, 1800))
    loop.step("leave")
    assert not world.inside()
    assert 60 < world.heading < 300


def test_leave_skips_turnaround_when_already_outside(loop, world, config):
    airborne(loop, world, 70, 120, 0, pos=(0, 2300))
    loop.step("leave")
    assert world.now < config["flight"]["outside_check_s"] + 0.5
    assert "q" not in world.pressed and "e" not in world.pressed


def test_land_brakes_descends_and_checks_prompt(loop, world, config, caplog):
    airborne(loop, world, 100, 150, 180, pos=(0, 1500))
    with caplog.at_level("INFO"):
        loop.step("land")
    land_distance = config["maps"]["default"]["land_distance"]
    (approach,) = [r.args[0] for r in caplog.records if "Landeanflug" in r.msg]
    assert land_distance - 100 <= approach <= land_distance
    assert world.agl <= 1 and world.ground_speed <= 3
    assert world.buy_prompt()
    assert not world.keys


def test_land_turns_back_when_hq_distance_grows(loop, world, caplog):
    airborne(loop, world, 60, 200, 180, pos=(0, 450))
    world.base_tint_until = 0.0
    with caplog.at_level("INFO"):
        loop.step("land")
    assert any("überflogen" in r.msg for r in caplog.records)
    assert world.agl <= 1 and world.buy_prompt()


def test_land_searches_hq_when_marker_lost(loop, world, caplog):
    airborne(loop, world, 60, 0, 180, pos=(0, -900))
    with caplog.at_level("INFO"):
        loop.step("land")
    assert any("HQ-Marker weg" in r.msg for r in caplog.records)
    assert world.agl <= 1 and world.buy_prompt()


def test_land_never_touches_down_outside_base(loop, world, config, caplog):
    airborne(loop, world, 30, 0, 180, pos=(0, 100))
    world.prompt, world.base_tint_until = False, 8.0
    lowest = []
    grab = loop._grab
    loop._grab = lambda: (world.now > 8.0 and lowest.append(world.agl), grab())[1]
    with caplog.at_level("INFO"), pytest.raises(StepFailed, match="Landeanflug"):
        loop.step("land")
    assert any("nicht mehr unter dem Heli" in r.msg for r in caplog.records)
    assert min(lowest[40:]) > config["flight"]["landed_agl"]
    assert not world.keys


@pytest.mark.parametrize("bearing", [30, 100, 170, -120])
def test_turn_with_speed_flies_a_safe_curve(loop, world, config, bearing):
    airborne(loop, world, 90, 150, 0, pos=(0.0, 0.0))
    world.base = (
        3000 * math.sin(math.radians(bearing)),
        3000 * math.cos(math.radians(bearing)),
    )
    world.lakota = True
    loop.step("turn")
    assert_aimed(world, world.base, config)
    assert world.min_agl > 40
    assert world.min_pitch > -15
    assert "a" in world.pressed or "d" in world.pressed


@pytest.mark.parametrize("heading", [90, 180, 270])
def test_turn_hovering_with_crate_stays_safe(loop, world, config, heading):
    world.crate = True
    airborne(loop, world, 25, 0, heading)
    loop.step("turn")
    assert_aimed(world, world.zone, config)
    assert world.min_agl > 15
    assert world.min_pitch > -15


def test_first_aid_leaves_layer(loop, world):
    world.first_aid = True
    with pytest.raises(LeaveLayer):
        loop.step("climb")
    assert not world.keys


def test_round_end_stops_safely(loop, world):
    airborne(loop, world, 50, 0, 0)
    world.round_over, world.lakota = True, False
    with pytest.raises(RoundOver, match="Runde vorbei"):
        loop.step("land")
    assert not world.keys


def test_damage_leaves_layer(loop, world):
    world.agl, world.damaged = 50, True
    with pytest.raises(LeaveLayer):
        loop.step("climb")


def test_lost_heli_leaves_layer_after_grace(loop, world, config):
    world.lakota = False
    with pytest.raises(LeaveLayer):
        loop.step("climb")
    assert world.now > config["timeouts"]["heli_lost_s"]


def test_once_runs_full_round(loop, world, config):
    loop.run(once=True)
    assert loop.stats["rounds"] == 1
    assert loop.stats["bought"] == 1 and loop.stats["dropped"] == 1
    assert loop.stats["delivered"] == 1
    assert world.drops[0]["inside"]
    assert world.agl <= 1 and world.buy_prompt()
    assert_never_low_and_fast(world, config)

import math
import threading
from unittest.mock import Mock

import numpy as np
import pytest

from heli_farmer.config import load_config
from heli_farmer.crate_loop import CrateLoop, LeaveLayer, StepFailed
from heli_farmer.detectors import Marker
from heli_farmer.flight import Pilot
from heli_farmer.inputs import Input

FRAME = np.zeros((4, 4, 3), np.uint8)
TICK = 0.05
GROUND_ASL = 100.0
PITCH_RATE = 25.0
YAW_RATE = 40.0
SHIFT_LIFT = 1 / math.cos(math.radians(20))
CTRL_LIFT = 0.93
FOV_HALF = 45.0
BASE_RADIUS = 80.0


class World:
    def __init__(self, clicks: dict):
        self.now = 0.0
        self.agl = 0.0
        self.speed = 0.0
        self.pitch = 0.0
        self.climb = 0.0
        self.pos = [0.0, 0.0]
        self.heading = 90.0
        self.zone = (0.0, 2000.0)
        self.radius = 250.0
        self.tint = True
        self.base = (0.0, 0.0)
        self.crate = False
        self.menu = None
        self.prompt = True
        self.delivered = False
        self.first_aid = False
        self.damaged = False
        self.lakota = True
        self.buy_works = True
        self.keys: set[str] = set()
        self._clicks = {tuple(v): k for k, v in clicks.items()}
        self.clicked: list[str] = []
        self.drops: list[dict] = []
        self.entered: float | None = None
        self.entry_speed: float | None = None
        self.track: list[tuple[float, float]] = []

    def press(self, name: str, down: bool) -> None:
        if down:
            self.keys.add(name)
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
                    "speed": self.speed,
                }
                self.drops.append(drop)
        else:
            self.keys.discard(name)

    def click(self, x: int, y: int) -> None:
        name = self._clicks[(x, y)]
        self.clicked.append(name)
        if name == "logistics" and self.menu == "main":
            self.menu = "logistics"
        elif name == "ammo_pallet" and self.menu == "logistics" and self.buy_works:
            self.crate = True
            self.menu = "main"
        elif name == "confirm":
            self.menu = None
            self.lakota = True

    def step(self) -> np.ndarray:
        self.now += TICK
        if not self.menu:
            self.fly()
        if self.inside() and self.entered is None:
            self.entered, self.entry_speed = self.now, self.speed
        return FRAME

    def fly(self) -> None:
        if "w" in self.keys:
            self.pitch = min(35.0, self.pitch + PITCH_RATE * TICK)
        if "s" in self.keys:
            self.pitch = max(-20.0, self.pitch - PITCH_RATE * TICK)
        lift = SHIFT_LIFT if "shift" in self.keys else CTRL_LIFT if "ctrl" in self.keys else 1.0
        wanted = 80 * (lift * math.cos(math.radians(self.pitch)) - 1)
        self.climb += (wanted - self.climb) * TICK / 0.5
        self.agl = max(0.0, self.agl + self.climb * TICK)
        if self.agl == 0:
            self.climb, self.speed, self.pitch = max(0.0, self.climb), 0.0, 0.0
            return
        self.speed = max(0.0, self.speed + (1.2 * self.pitch - 0.1 * self.speed) * TICK)
        turn = YAW_RATE if "e" in self.keys else -YAW_RATE if "q" in self.keys else 0
        self.heading = (self.heading + turn * TICK) % 360
        step = self.speed / 3.6 * TICK
        self.pos[0] += step * math.sin(math.radians(self.heading))
        self.pos[1] += step * math.cos(math.radians(self.heading))
        self.track.append((self.agl, self.speed))

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
        y = 400 + round(200 * min(1.0, 600 / max(distance, 1.0)))
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

    def in_lakota(self, frame):
        return self.w.lakota

    def heli_damaged(self, frame):
        return self.w.damaged

    def garage_menu(self, frame):
        return self.w.menu

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
        return round(self.w.speed) if self.w.lakota else None

    def zone_marker(self, frame):
        distance = self.w.bearing(self.w.zone)[1]
        if self.w.inside():
            return self.w.marker(self.w.zone, kind="HZ", distance=round(distance))
        return self.w.marker(self.w.zone, kind="CZ", distance=round(distance - self.w.radius))

    def hq_marker(self, frame):
        error, _ = self.w.bearing(self.w.base)
        if self.w.inside() or abs(error) > FOV_HALF:
            return None
        return self.w.marker(self.w.base)

    def minimap_in_zone(self, frame):
        return self.w.inside() and self.w.tint


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
    backend.moveTo.side_effect = world.click
    inp = Input(threading.Event(), backend=backend, clock=lambda: world.now)
    return CrateLoop(
        FakeVision(world), inp, world.step, threading.Event(), config, clock=lambda: world.now
    )


def airborne(world: World, agl: float, speed: float, heading: float, pos=(0.0, 0.0)) -> None:
    world.agl, world.speed, world.heading, world.pos = agl, speed, heading, list(pos)
    world.pitch = speed / 12


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
    assert world.speed < 5
    assert not world.keys


def test_turn_yaws_to_zone_marker_only(loop, world, config):
    world.crate = True
    airborne(world, 15, 0, 90)
    loop.step("turn")
    assert abs(world.marker(world.zone).x - config["flight"]["center_x"]) <= 40
    assert world.speed < 5


def test_turn_searches_hq_when_not_visible(loop, world, config):
    airborne(world, 100, 0, 90, pos=(0, 1500))
    loop.step("turn")
    assert abs(world.marker(world.base).x - config["flight"]["center_x"]) <= 40


def test_drop_waits_three_seconds_inside_and_drops_low(loop, world, config):
    world.crate = True
    airborne(world, 100, 0, 0)
    loop.step("drop")
    (drop,) = world.drops
    assert drop["inside"] and drop["agl"] <= config["maps"]["default"]["drop_max_agl"]
    assert drop["t"] - world.entered >= config["flight"]["drop_delay_s"]
    assert loop.stats["dropped"] == 1 and loop.stats["delivered"] == 1
    assert_never_low_and_fast(world, config)


def test_drop_brakes_before_zone(loop, world, config):
    world.crate = True
    airborne(world, 100, 0, 0)
    loop.step("drop")
    cruise_speed = config["maps"]["default"]["cruise_speed"]
    assert max(speed for _, speed in world.track) > cruise_speed - 30
    drop_speed = config["maps"]["default"]["drop_speed"]
    assert world.entry_speed <= drop_speed + 2 * config["flight"]["speed_band"]


def test_drop_needs_minimap_and_hz(loop, world, config):
    config["flight"]["leg_timeout_s"] = 90
    world.crate, world.tint = True, False
    airborne(world, 100, 0, 0)
    with pytest.raises(StepFailed):
        loop.step("drop")
    assert world.crate and not world.drops


def test_leave_turns_around_and_flies_out(loop, world, config):
    airborne(world, 70, 100, 0, pos=(0, 1800))
    loop.step("leave")
    assert not world.inside()
    assert 90 < world.heading < 270


def test_land_brakes_descends_and_checks_prompt(loop, world):
    airborne(world, 100, 150, 180, pos=(0, 1500))
    loop.step("land")
    assert world.agl <= 1 and world.speed <= 3
    assert world.buy_prompt()
    assert not world.keys


def test_first_aid_leaves_layer(loop, world):
    world.first_aid = True
    with pytest.raises(LeaveLayer):
        loop.step("climb")
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

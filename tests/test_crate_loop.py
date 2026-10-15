import math
import threading
from unittest.mock import Mock

import numpy as np
import pytest

from heli_farmer.config import load_config
from heli_farmer.crate_loop import CrateLoop, LeaveLayer, StepFailed
from heli_farmer.detectors import Marker
from heli_farmer.inputs import Input

FRAME = np.zeros((4, 4, 3), np.uint8)
TICK = 0.05
GROUND_ASL = 100.0
PITCH_RATE = 60.0
SHIFT_LIFT = 1 / math.cos(math.radians(20))
CTRL_LIFT = 0.93


class World:
    def __init__(self, clicks: dict):
        self.now = 0.0
        self.agl = 0.0
        self.speed = 0.0
        self.pitch = 0.0
        self.climb = 0.0
        self.track: list[tuple[float, float]] = []
        self.crate = False
        self.menu = None
        self.prompt = True
        self.delivered = False
        self.first_aid = False
        self.damaged = False
        self.lakota = True
        self.zone = [400.0, 400.0]
        self.hq = None
        self.buy_works = True
        self.keys: set[str] = set()
        self._clicks = {tuple(v): k for k, v in clicks.items()}
        self.clicked: list[str] = []

    def press(self, name: str, down: bool) -> None:
        if down:
            self.keys.add(name)
            if name == "b" and self.prompt:
                self.menu = "main"
                self.lakota = False
            if name == "g" and self.crate:
                self.crate = False
                self.delivered = True
        else:
            self.keys.discard(name)

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
        else:
            self.speed = max(0.0, self.speed + (1.2 * self.pitch - 0.1 * self.speed) * TICK)
        self.track.append((self.agl, self.speed))

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
            turn = 40 if "q" in self.keys else -40 if "e" in self.keys else 0
            for marker in (self.zone, self.hq):
                if marker:
                    marker[0] += turn
                    marker[1] += self.speed * TICK * 0.5
        return FRAME


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
        return self.w.prompt and self.w.agl < 30 and not self.w.menu

    def delivered(self, frame):
        return self.w.delivered

    def agl(self, frame):
        return round(self.w.agl) if self.w.lakota else None

    def asl(self, frame):
        return round(GROUND_ASL + self.w.agl) if self.w.lakota else None

    def speed(self, frame):
        return round(self.w.speed) if self.w.lakota else None

    def zone_marker(self, frame):
        return Marker(int(self.w.zone[0]), int(self.w.zone[1]), 0.9) if self.w.zone else None

    def hq_marker(self, frame):
        return Marker(int(self.w.hq[0]), int(self.w.hq[1]), 0.9) if self.w.hq else None


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


def test_climb_reaches_cruise_altitude(loop, world, config):
    loop.step("climb")
    assert (
        round(world.agl) >= config["maps"]["default"]["cruise_agl"] - config["flight"]["agl_band"]
    )
    assert not world.keys


def test_turn_centers_zone_marker(loop, world, config):
    world.agl, world.crate, world.zone = 100, True, [120.0, 300.0]
    loop.step("turn")
    assert abs(world.zone[0] - config["flight"]["center_x"]) <= config["flight"]["yaw_deadband"]


def test_turn_searches_hq_when_not_visible(loop, world, config):
    world.agl = 100

    def appear() -> np.ndarray:
        if world.now > 1 and world.hq is None:
            world.hq = [1700.0, 400.0]
        return World.step(world)

    loop._grab = appear
    loop.step("turn")
    assert abs(world.hq[0] - config["flight"]["center_x"]) <= config["flight"]["yaw_deadband"]


def test_drop_flies_to_zone_and_releases_crate(loop, world):
    world.agl, world.crate, world.zone = 100, True, [960.0, 400.0]
    loop.step("drop")
    assert not world.crate
    assert loop.stats["dropped"] == 1 and loop.stats["delivered"] == 1


def test_land_brakes_descends_and_checks_prompt(loop, world):
    world.agl, world.speed, world.hq = 100, 150, [960.0, 400.0]
    loop.step("land")
    assert world.agl <= 1 and world.speed <= 3
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


def test_once_runs_full_round(loop, world):
    original = world.step

    def scripted() -> np.ndarray:
        if not world.crate and world.zone and not world.menu and world.agl > 40:
            world.zone, world.hq = None, [960.0, 400.0]
        return original()

    loop._grab = scripted
    loop.run(once=True)
    assert loop.stats["rounds"] == 1
    assert loop.stats["bought"] == 1 and loop.stats["dropped"] == 1
    assert world.agl <= 1

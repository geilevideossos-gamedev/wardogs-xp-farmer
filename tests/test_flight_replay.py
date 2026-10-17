import csv
import threading
from pathlib import Path
from unittest.mock import Mock

import numpy as np
import pytest

from heli_farmer.config import load_config
from heli_farmer.crate_loop import CrateLoop, StepFailed
from heli_farmer.detectors import Marker
from heli_farmer.flight import Pilot
from heli_farmer.inputs import Input

FIXTURES = Path("tests/fixtures/flight")
FILES = ["turn_crash_052616.csv", "drop_crash_052853.csv"]
FRAME = np.zeros((4, 4, 3), np.uint8)


class Clock:
    def __init__(self):
        self.now = 0.0

    def __call__(self) -> float:
        return self.now


def number(value: str) -> int | None:
    return int(value) if value else None


def replay(name: str) -> list[tuple[dict, set[str]]]:
    config = load_config("config.yaml")
    flight, area = config["flight"], config["maps"]["default"]
    clock = Clock()
    backend = Mock()
    inp = Input(threading.Event(), backend=backend, clock=clock)
    pilot = Pilot(inp, config["keys"], flight, clock)
    curve_agl = max(area["turn_agl"], flight["safe_agl"] + flight["agl_band"])
    decisions = []
    with open(FIXTURES / name, encoding="utf-8") as file:
        for row in csv.DictReader(file):
            clock.now = float(row["t"])
            pilot.update()
            before = len(backend.keyDown.call_args_list)
            state = number(row["agl"]), number(row["asl"]), number(row["speed"])
            if row["step"] == "drop":
                pilot.fly(
                    *state, area["cruise_agl"], area["cruise_speed"], area["min_agl"], loaded=True
                )
            elif row["turn"] == "kurve":
                floor = min(area["min_agl"], curve_agl - flight["agl_band"])
                pilot.fly(*state, curve_agl, flight["turn_speed"], floor, loaded=True)
            elif row["step"] == "turn":
                pilot.fly(*state, area["turn_agl"], 0, loaded=True)
            else:
                pilot.fly(*state, area["turn_agl"] + flight["agl_band"], None, loaded=True)
            keys = {call.args[0] for call in backend.keyDown.call_args_list[before:]}
            keys |= {key for key in ("w", "s") if inp.is_down(key)}
            decisions.append((row, keys))
    return decisions


def diving(row: dict) -> bool:
    return row["ground"] not in ("", "-") and float(row["ground"]) > 60 and float(row["climb"]) < -5


@pytest.mark.parametrize("name", FILES)
def test_never_w_while_diving(name):
    decisions = replay(name)
    dives = [keys for row, keys in decisions if diving(row)]
    assert dives
    assert not [keys for keys in dives if "w" in keys]
    assert any("s" in keys for keys in dives)


def test_hover_drift_with_crate_gets_w():
    decisions = replay("turn_crash_052616.csv")
    hover = [(row, keys) for row, keys in decisions if row["turn"] == "stelle"]
    drift = [
        keys
        for row, keys in hover
        if 4 < float(row["ground"]) <= 15 and float(row["accel"]) > 1 and "w" not in row["keys"]
    ]
    assert drift
    pitch = [key for keys in drift for key in sorted(keys) if key in ("w", "s")]
    assert pitch and pitch[0] == "w"


class RowVision:
    def __init__(self, loaded: bool):
        self.loaded = loaded
        self.row: dict = {}

    def round_over(self, frame):
        return False

    def first_aid(self, frame):
        return False

    def in_lakota(self, frame):
        return True

    def heli_damaged(self, frame):
        return False

    def crate_loaded(self, frame):
        return self.loaded

    def agl(self, frame):
        return number(self.row["agl"])

    def asl(self, frame):
        return number(self.row["asl"])

    def speed(self, frame):
        return number(self.row["speed"])

    def roll(self, frame):
        return number(self.row["roll"])

    def zone_marker(self, frame):
        return self.marker()

    def hq_marker(self, frame):
        return self.marker()

    def marker(self) -> Marker | None:
        x = self.row["marker"]
        return None if x in ("", "-", "0", "1920") else Marker(int(x), 500, 0.9)


def replay_turn(name: str, loaded: bool, side: str | None = None):
    config = load_config("config.yaml")
    config["flight"]["tick_s"] = 0
    with open(FIXTURES / name, encoding="utf-8") as file:
        rows = iter(list(csv.DictReader(file)))
    vision, clock, backend = RowVision(loaded), Clock(), Mock()
    inp = Input(threading.Event(), backend=backend, clock=clock)
    modes = []

    def grab():
        if vision.row:
            modes.append((vision.row, loop._curving))
        vision.row = next(rows)
        clock.now = float(vision.row["t"])
        return FRAME

    loop = CrateLoop(vision, inp, grab, threading.Event(), config, clock=clock)
    loop._turn_side = side
    try:
        loop.step("turn")
        end = clock.now
    except (StopIteration, StepFailed):
        end = None
    keys = [call.args[0] for call in backend.keyDown.call_args_list]
    return end, modes, keys


def test_turn_after_climb_ends_once_marker_in_view():
    end, modes, _ = replay_turn("turn_climb_063523.csv", loaded=True)
    assert end is not None and end < 134320
    assert not any(curving for _, curving in modes)


def test_turn_after_climb_never_curves():
    _, modes, _ = replay_turn("turn_climb_063300.csv", loaded=True)
    assert modes and not any(curving for _, curving in modes)


@pytest.mark.parametrize("name", ["turn_climb_063300.csv", "turn_climb_063523.csv"])
def test_turn_never_curves_below_curve_height(name):
    _, modes, _ = replay_turn(name, loaded=False)
    low = [curving for row, curving in modes if number(row["agl"]) and int(row["agl"]) < 50]
    assert low and not any(low)


def test_turn_back_keeps_leave_direction():
    _, _, keys = replay_turn("turn_back_062829.csv", loaded=False, side="yaw_left")
    yaws = [key for key in keys if key in ("q", "e")]
    assert yaws and yaws[0] == "q" and yaws.count("q") > yaws.count("e")

import csv
import threading
from pathlib import Path
from unittest.mock import Mock

import pytest

from heli_farmer.config import load_config
from heli_farmer.flight import Pilot
from heli_farmer.inputs import Input

FIXTURES = Path("tests/fixtures/flight")
FILES = ["turn_crash_052616.csv", "drop_crash_052853.csv"]


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

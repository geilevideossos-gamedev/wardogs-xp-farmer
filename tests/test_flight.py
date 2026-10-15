import threading
from unittest.mock import Mock

import pytest

from heli_farmer.config import load_config
from heli_farmer.flight import Pilot, Trend
from heli_farmer.inputs import Input


class Clock:
    def __init__(self):
        self.now = 0.0

    def __call__(self) -> float:
        return self.now


@pytest.fixture
def setup():
    config = load_config("config.yaml")
    clock = Clock()
    inp = Input(threading.Event(), backend=Mock(), clock=clock)
    return Pilot(inp, config["keys"], config["flight"], clock), inp, clock, config["flight"]


def test_trend_rate_over_window():
    trend = Trend(1.0)
    for i in range(30):
        trend.add(i * 0.1, i * 2.0)
    assert trend.rate() == pytest.approx(20.0)
    trend.add(3.0, None)
    assert trend.rate() == pytest.approx(20.0)


def test_altitude_climbs_below_band(setup):
    pilot, inp, clock, _ = setup
    pilot.altitude(50, 100)
    assert inp.is_down("shift") and not inp.is_down("ctrl")
    clock.now = 1.0
    pilot.altitude(55, 100)
    assert inp.is_down("shift")


def test_altitude_descends_far_above_target(setup):
    pilot, inp, _, _ = setup
    pilot.altitude(140, 100)
    assert not inp.is_down("shift") and inp.is_down("ctrl")


def test_altitude_lets_go_early_when_climbing_fast(setup):
    pilot, inp, clock, _ = setup
    pilot.altitude(70, 100)
    clock.now = 1.0
    pilot.altitude(90, 100)
    assert not inp.is_down("shift")


def test_altitude_ignores_missing_reading(setup):
    pilot, inp, _, _ = setup
    pilot.altitude(None, 100)
    assert not inp.is_down("shift") and not inp.is_down("ctrl")


def test_speed_taps_forward_then_waits_interval(setup):
    pilot, inp, clock, flight = setup
    pilot.speed(0, 200)
    assert inp.is_down("w")
    clock.now = flight["tap_s"] + 0.01
    pilot.update()
    assert not inp.is_down("w")
    pilot.speed(0, 200)
    assert not inp.is_down("w")
    clock.now = flight["speed_tap_interval_s"] + 0.01
    pilot.speed(0, 200)
    assert inp.is_down("w")


def test_speed_brakes_when_too_fast(setup):
    pilot, inp, clock, _ = setup
    pilot.speed(300, 0)
    clock.now = 0.5
    pilot.speed(300, 0)
    assert inp.is_down("s")


def test_yaw_pulses_toward_marker_and_reports_centered(setup):
    pilot, inp, clock, flight = setup
    assert pilot.yaw(flight["center_x"] + 10) is True
    assert pilot.yaw(flight["center_x"] + 400) is False
    assert inp.is_down("e") and not inp.is_down("q")
    clock.now = flight["yaw_max_s"] + 0.01
    pilot.update()
    assert not inp.is_down("e")
    clock.now += flight["yaw_interval_s"]
    pilot.yaw(120)
    assert inp.is_down("q")


def test_sink_holds_rate(setup):
    pilot, inp, clock, _ = setup
    pilot.sink(30)
    clock.now = 1.0
    pilot.sink(30)
    assert inp.is_down("ctrl") and not inp.is_down("shift")
    clock.now = 2.0
    pilot.sink(15)
    assert inp.is_down("shift") and not inp.is_down("ctrl")


def test_release_lets_go_of_all_flight_keys(setup):
    pilot, inp, _, _ = setup
    pilot.altitude(10, 100)
    pilot.speed(0, 200)
    pilot.yaw(1800)
    pilot.release()
    assert not any(inp.is_down(key) for key in ("shift", "ctrl", "w", "s", "q", "e"))

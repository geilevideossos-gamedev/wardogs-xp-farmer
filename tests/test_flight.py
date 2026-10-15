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


def fly(pilot, agl, speed, target_agl=100, target_speed=0, floor=0, asl=None):
    pilot.fly(agl, 100 + agl if asl is None else asl, speed, target_agl, target_speed, floor)


def test_fly_climbs_with_shift_below_target(setup):
    pilot, inp, clock, _ = setup
    fly(pilot, 50, 0)
    assert inp.is_down("shift") and not inp.is_down("ctrl")
    clock.now = 1.0
    fly(pilot, 55, 0)
    assert inp.is_down("shift")


def test_fly_lets_shift_go_above_target_without_ctrl(setup):
    pilot, inp, _, _ = setup
    fly(pilot, 140, 0)
    assert not inp.is_down("shift") and not inp.is_down("ctrl")


def test_fly_lets_go_early_when_climbing_fast(setup):
    pilot, inp, clock, _ = setup
    fly(pilot, 70, 0)
    clock.now = 1.0
    fly(pilot, 90, 0)
    assert not inp.is_down("shift")


def test_fly_ignores_missing_reading(setup):
    pilot, inp, _, _ = setup
    pilot.fly(None, None, None, 100, 200)
    assert not any(inp.is_down(key) for key in ("shift", "ctrl", "w", "s"))


def test_fly_taps_forward_then_waits_interval(setup):
    pilot, inp, clock, flight = setup
    fly(pilot, 100, 0, target_speed=200)
    assert inp.is_down("w")
    clock.now = flight["pitch_tap_s"] + 0.01
    pilot.update()
    assert not inp.is_down("w")
    fly(pilot, 100, 0, target_speed=200)
    assert not inp.is_down("w")
    clock.now = flight["pitch_interval_s"] + 0.01
    fly(pilot, 100, 0, target_speed=200)
    assert inp.is_down("w")


def test_fly_brakes_when_too_fast(setup):
    pilot, inp, clock, _ = setup
    fly(pilot, 100, 240)
    clock.now = 0.5
    fly(pilot, 100, 240)
    assert inp.is_down("s")


def test_speed_limit_depends_on_height(setup):
    pilot, _, _, flight = setup
    heights = [height for height, _ in flight["speed_limits"]]
    assert pilot.speed_limit(28) < pilot.speed_limit(80) < pilot.speed_limit(120)
    assert pilot.speed_limit(0) == pilot.speed_limit(heights[0])


def test_fly_low_and_fast_noses_up_with_shift(setup):
    pilot, inp, clock, _ = setup
    braked = 0
    for step in range(20):
        clock.now = step * 0.1
        pilot.update()
        fly(pilot, 28, 215, target_agl=100, target_speed=250, floor=80)
        assert inp.is_down("shift") and not inp.is_down("w")
        braked += inp.is_down("s")
    assert braked


def test_fly_below_floor_stops_accelerating(setup):
    pilot, inp, clock, _ = setup
    for step, speed in enumerate((60, 70, 80)):
        clock.now = step * 0.4
        fly(pilot, 50, speed, target_speed=200, floor=80)
    assert inp.is_down("shift") and inp.is_down("s") and not inp.is_down("w")


def test_fly_noses_up_when_sinking_despite_shift(setup):
    pilot, inp, clock, _ = setup
    for step in range(3):
        clock.now = step * 0.5
        fly(pilot, 60, 200, target_speed=200, asl=300 - 3 * step)
    assert inp.is_down("shift") and inp.is_down("s")


def test_fly_does_not_accelerate_while_sinking(setup):
    pilot, inp, clock, _ = setup
    for step in range(4):
        clock.now = step * 0.5
        pilot.update()
        fly(pilot, 150, 100, target_speed=200, asl=300 - 3 * step)
    assert not inp.is_down("shift") and not inp.is_down("w")


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


def test_descend_holds_rate(setup):
    pilot, inp, clock, _ = setup
    pilot.descend(30, 130, 0)
    clock.now = 1.0
    pilot.descend(30, 130, 0)
    assert inp.is_down("ctrl") and not inp.is_down("shift")
    clock.now = 2.0
    pilot.descend(15, 115, 0)
    assert inp.is_down("shift") and not inp.is_down("ctrl")


def test_descend_waits_while_too_fast_for_height(setup):
    pilot, inp, clock, _ = setup
    pilot.descend(30, 130, 200)
    clock.now = 1.0
    pilot.descend(30, 130, 200)
    assert not inp.is_down("ctrl")
    assert inp.is_down("s")


def test_release_lets_go_of_all_flight_keys(setup):
    pilot, inp, _, _ = setup
    fly(pilot, 10, 0, target_speed=200)
    pilot.yaw(1800)
    pilot.release()
    assert not any(inp.is_down(key) for key in ("shift", "ctrl", "w", "s", "q", "e"))

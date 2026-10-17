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
    pilot.tilt = 3
    for step, speed in enumerate((60, 70, 80)):
        clock.now = step * 0.4
        fly(pilot, 50, speed, target_speed=200, floor=80)
    assert inp.is_down("shift") and inp.is_down("s") and not inp.is_down("w")


def test_fly_below_floor_never_pitches_up_from_level(setup):
    pilot, inp, clock, _ = setup
    for step, speed in enumerate((5, 10, 15)):
        clock.now = step * 0.4
        fly(pilot, 50, speed, target_speed=200, floor=80)
    assert inp.is_down("shift") and not inp.is_down("s") and not inp.is_down("w")


def test_fly_hovers_without_pitch_taps_while_still(setup):
    pilot, inp, clock, _ = setup
    pilot.tilt = -2
    for step in range(3):
        clock.now = step * 0.5
        fly(pilot, 100, 3, target_speed=0)
    assert not inp.is_down("w") and not inp.is_down("s")


def test_fly_levels_out_when_drifting_after_braking(setup):
    pilot, inp, clock, _ = setup
    pilot.tilt = -2
    for step in range(3):
        clock.now = step * 0.5
        fly(pilot, 100, 5 + 2 * step, target_speed=0)
    assert inp.is_down("w") and pilot.tilt == -1


def test_fly_brakes_with_s_until_slow(setup):
    pilot, inp, clock, _ = setup
    for step in range(3):
        clock.now = step * 0.5
        fly(pilot, 100, 60 - step, target_speed=0)
    assert inp.is_down("s")


def test_fly_brakes_with_w_when_s_makes_it_faster(setup):
    pilot, inp, clock, flight = setup
    speeds = (20, 22, 24, 27, 31, 36)
    pressed = []
    for step, speed in enumerate(speeds):
        clock.now = step * flight["pitch_interval_s"]
        pilot.update()
        fly(pilot, 30, speed, target_speed=0)
        pressed.append("w" if inp.is_down("w") else "s" if inp.is_down("s") else "")
    assert pressed[0] == "s" and pressed[-1] == "w"
    assert pilot.reverse


def test_fly_counts_pitch_taps(setup):
    pilot, _, _, _ = setup
    fly(pilot, 100, 0, target_speed=200)
    assert pilot.tilt == 1


def test_tilt_resets_on_ground(setup):
    pilot, inp, _, _ = setup
    pilot.tilt = 3
    fly(pilot, 0, 0, target_agl=0)
    assert pilot.tilt == 0 and not inp.is_down("w") and not inp.is_down("s")


def test_fly_uses_ctrl_only_in_sink_mode(setup):
    pilot, inp, _, _ = setup
    fly(pilot, 100, 100, target_agl=70, target_speed=100)
    assert not inp.is_down("ctrl")
    pilot.fly(100, 200, 100, 70, 100, 0, sink_rate=2)
    assert inp.is_down("ctrl") and not inp.is_down("shift")


def test_fly_sinks_no_faster_than_sink_rate(setup):
    pilot, inp, clock, _ = setup
    pilot.fly(100, 200, 100, 70, 100, 0, sink_rate=2)
    clock.now = 1.0
    pilot.fly(98, 198, 100, 70, 100, 0, sink_rate=2)
    assert not inp.is_down("ctrl")
    clock.now = 2.0
    pilot.fly(94, 194, 100, 70, 100, 0, sink_rate=2)
    assert inp.is_down("shift") and not inp.is_down("ctrl")


def test_fly_without_target_speed_keeps_pitch(setup):
    pilot, inp, clock, _ = setup
    for step in range(5):
        clock.now = step * 0.5
        pilot.update()
        pilot.fly(70, 170, 120 - 5 * step, 70, None)
    assert not inp.is_down("w") and not inp.is_down("s") and pilot.tilt == 0


def test_fly_stops_tilting_forward_at_max_tilt(setup):
    pilot, inp, clock, flight = setup
    for step in range(12):
        clock.now = step * flight["pitch_interval_s"]
        pilot.update()
        fly(pilot, 100, 50 + 5 * step, target_speed=200)
    assert pilot.tilt == flight["max_tilt"]


def test_fly_trims_forward_when_speed_stalls_at_max_tilt(setup):
    pilot, inp, clock, flight = setup
    pilot.tilt = flight["max_tilt"]
    for step in range(3):
        clock.now = step * 0.5
        fly(pilot, 100, 100, target_speed=200)
    assert inp.is_down("w") and pilot.tilt == flight["max_tilt"]


def test_fly_trims_backward_drift_with_crate(setup):
    pilot, inp, clock, flight = setup
    for step in range(3):
        clock.now = step * 0.5
        pilot.fly(15, 115, 5 + 2 * step, 15, 0, loaded=True)
    assert inp.is_down("w") and pilot.tilt == 0


def test_bank_into_turn_only_at_speed(setup):
    pilot, inp, clock, flight = setup
    pilot.bank(0, flight["bank_speed"] - 1, 840)
    assert not inp.is_down("d")
    pilot.bank(0, flight["bank_speed"], 840)
    assert inp.is_down("d") and not inp.is_down("a")


def test_bank_levels_out(setup):
    pilot, inp, clock, flight = setup
    pilot.bank(flight["roll_band"], 150)
    assert not inp.is_down("a") and not inp.is_down("d")
    pilot.bank(12, 150)
    assert inp.is_down("a")
    clock.now = flight["roll_max_s"] + 0.01
    pilot.update()
    pilot.bank(-12, 150)
    assert not inp.is_down("d")
    clock.now = flight["roll_interval_s"] + 0.01
    pilot.bank(-12, 150)
    assert inp.is_down("d")
    pilot.bank(None, 150)


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


def aim(pilot, clock, *xs, start=10.0):
    for step, x in enumerate(xs):
        clock.now = start + step * 0.1
        pilot.yaw(x)


def test_yaw_reports_on_target_only_when_centered_and_still(setup):
    pilot, inp, clock, flight = setup
    center = flight["center_x"]
    aim(pilot, clock, center + 10)
    assert not pilot.on_target
    aim(pilot, clock, center + 10, center + 10)
    assert pilot.on_target and not inp.is_down("e")
    aim(pilot, clock, center + 70, center + 10, start=11)
    assert not pilot.on_target


def test_yaw_pulses_toward_marker_and_waits_for_coasting(setup):
    pilot, inp, clock, flight = setup
    aim(pilot, clock, flight["center_x"] + 400, flight["center_x"] + 400)
    assert inp.is_down("e") and not inp.is_down("q")
    clock.now += flight["yaw_max_s"]
    pilot.update()
    assert not inp.is_down("e")
    clock.now += flight["yaw_wait_s"] - 0.1
    pilot.yaw(flight["center_x"] + 400)
    assert not inp.is_down("e")


def test_yaw_brakes_with_counter_key_when_overshoot_ahead(setup):
    pilot, inp, clock, flight = setup
    center = flight["center_x"]
    aim(pilot, clock, center + 300, center + 200, center + 100)
    assert pilot.lead < -flight["yaw_coast_band"]
    assert inp.is_down("q") and not inp.is_down("e")


def test_yaw_lets_heli_coast_into_target(setup):
    pilot, inp, clock, flight = setup
    center = flight["center_x"]
    aim(pilot, clock, center + 200, center + 180, center + 160)
    assert not inp.is_down("q") and not inp.is_down("e")


def test_yaw_at_screen_edge_turns_toward_it(setup):
    pilot, inp, clock, flight = setup
    pilot.yaw(120)
    assert inp.is_down("q") and not pilot.on_target


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


def test_descend_brakes_before_touchdown(setup):
    pilot, inp, clock, flight = setup
    agl = flight["sink_slow_agl"]
    pilot.descend(agl, 100 + agl, flight["touchdown_speed"] + 5)
    clock.now = 1.0
    pilot.descend(agl, 100 + agl, flight["touchdown_speed"] + 5)
    assert not inp.is_down("ctrl") and inp.is_down("s")


def test_release_lets_go_of_all_flight_keys(setup):
    pilot, inp, _, _ = setup
    fly(pilot, 10, 0, target_speed=200)
    pilot.yaw(1800)
    pilot.bank(0, 200, 840)
    pilot.release()
    assert not any(inp.is_down(key) for key in ("shift", "ctrl", "w", "s", "q", "e", "a", "d"))

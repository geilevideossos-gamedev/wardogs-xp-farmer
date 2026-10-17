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


def feed(pilot, clock, samples, dt=0.1, start=0.0, **kwargs):
    for step, (agl, asl, speed) in enumerate(samples):
        clock.now = start + step * dt
        pilot.update()
        pilot.fly(agl, asl, speed, kwargs.get("target_agl", 100), kwargs.get("target_speed"))


def level(agl, speeds):
    return [(agl, 100 + agl, speed) for speed in speeds]


def pressed(inp):
    return [call.args[0] for call in inp._backend.keyDown.call_args_list]


def test_ground_speed_leaves_out_climb_rate(setup):
    pilot, _, clock, _ = setup
    feed(pilot, clock, [(10 * i, 110 + 9 * i, 33) for i in range(12)], dt=0.1)
    assert pilot.climb == pytest.approx(90, rel=0.05)
    assert pilot.ground is None or pilot.ground < 10


def test_ground_speed_needs_settled_trends(setup):
    pilot, _, _, _ = setup
    fly(pilot, 30, 30)
    assert pilot.ground is None


def test_fly_taps_forward_then_waits_interval(setup):
    pilot, inp, clock, flight = setup
    feed(pilot, clock, level(100, [0] * 14), target_speed=200, dt=0.05)
    assert pressed(inp).count("w") == 1
    feed(pilot, clock, level(100, [0] * 6), target_speed=200, dt=0.05, start=clock.now + 0.05)
    assert pressed(inp).count("w") == 1
    feed(pilot, clock, level(100, [0] * 6), target_speed=200, dt=0.05, start=clock.now + 0.4)
    assert pressed(inp).count("w") == 2


def test_fly_brakes_when_too_fast(setup):
    pilot, inp, clock, _ = setup
    feed(pilot, clock, level(100, [260] * 12), target_speed=200)
    assert "s" in pressed(inp)


def test_speed_limit_depends_on_height(setup):
    pilot, _, _, flight = setup
    heights = [height for height, _ in flight["speed_limits"]]
    assert pilot.speed_limit(28) < pilot.speed_limit(80) < pilot.speed_limit(120)
    assert pilot.speed_limit(0) == pilot.speed_limit(heights[0])


def test_no_pitch_taps_while_climbing_fast(setup):
    pilot, inp, clock, _ = setup
    pressed = set()
    for step in range(20):
        clock.now = step * 0.1
        pilot.update()
        pilot.fly(step, 100 + step, 30, 25, 0)
        pressed |= {key for key in ("w", "s") if inp.is_down(key)}
    assert not pressed


def test_dive_means_level_wings_shift_and_nose_up(setup):
    pilot, inp, clock, _ = setup
    samples = [(120 - 3 * i, 220 - 3 * i, 150 + 2 * i) for i in range(15)]
    feed(pilot, clock, samples, target_agl=60, target_speed=200)
    assert pilot.recovering and inp.is_down("shift") and "s" in pressed(inp)
    pilot.bank(20, 840)
    assert inp.is_down("a")


def test_fly_safety_climb_when_low_and_fast(setup):
    pilot, inp, clock, flight = setup
    agl = flight["safe_agl"] - 5
    feed(pilot, clock, level(agl, [flight["safe_speed"] + 20] * 8), target_agl=10)
    assert pilot.recovering and inp.is_down("shift")
    pilot.yaw(1500)
    pilot.bank(0, 600)
    assert not inp.is_down("e") and not inp.is_down("d")


def test_no_nose_up_below_floor_when_slow(setup):
    pilot, inp, clock, _ = setup
    for step, speed in enumerate((5, 10, 15, 20, 25, 30)):
        clock.now = step * 0.4
        pilot.update()
        pilot.fly(50, 150, speed, 100, 200, 80)
    assert pilot.recovering and inp.is_down("shift") and not inp.is_down("s")


def test_lean_back_stops_once_braking_hard(setup):
    pilot, inp, clock, flight = setup
    speeds = [200 - 1.5 * i for i in range(20)]
    feed(pilot, clock, level(100, speeds), target_speed=0)
    before = pressed(inp).count("s")
    assert pilot.accel < -flight["lean_accel"]
    feed(pilot, clock, level(100, [170 - 1.5 * i for i in range(10)]), 0.1, clock.now + 0.1)
    assert pressed(inp).count("s") == before


def test_forward_taps_limited_per_window(setup):
    pilot, inp, clock, flight = setup
    taps = 0
    for step in range(int(flight["tap_window_s"] / 0.05)):
        clock.now = step * 0.05
        pilot.update()
        was = inp.is_down("w")
        fly(pilot, 100, 50, target_speed=200)
        taps += inp.is_down("w") and not was
    assert taps <= flight["window_taps"]


def test_fly_hovers_without_pitch_taps_while_still(setup):
    pilot, inp, clock, _ = setup
    feed(pilot, clock, level(100, [3] * 15), target_speed=0)
    assert not inp.is_down("w") and not inp.is_down("s")


def test_fly_brakes_with_s_until_slow(setup):
    pilot, inp, clock, _ = setup
    feed(pilot, clock, level(100, [60] * 12), target_speed=0)
    assert "s" in pressed(inp)


def test_brakes_with_w_after_braking_through_zero(setup):
    pilot, inp, clock, flight = setup
    speeds = [40, 40, 40, 36, 32, 28, 24, 20, 16, 12, 8, 4, 3, 2, 4, 8, 12, 14, 14, 12, 10]
    keys = []
    for step, speed in enumerate(speeds):
        clock.now = step * 0.4
        pilot.update()
        fly(pilot, 100, speed, target_speed=0)
        keys = pressed(inp)
    assert keys[0] == "s" and keys[-1] == "w"
    assert pilot.reverse


def test_fly_brakes_with_w_when_s_keeps_speeding_up(setup):
    pilot, inp, clock, flight = setup
    speeds = [12 + step for step in range(25)]
    for step, speed in enumerate(speeds):
        clock.now = step * 0.2
        pilot.update()
        fly(pilot, 30, speed, target_speed=0)
    keys = [key for key in pressed(inp) if key in ("w", "s")]
    assert keys[0] == "s" and "w" in keys


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
    feed(pilot, clock, level(70, [120 - step for step in range(12)]), target_agl=70)
    assert not inp.is_down("w") and not inp.is_down("s")


def test_bank_into_turn_grows_with_speed(setup):
    pilot, inp, clock, flight = setup
    pilot.bank(0, 840)
    assert not inp.is_down("d")
    feed(pilot, clock, level(100, [flight["bank_speed"]] * 8))
    pilot.bank(0, 840)
    assert inp.is_down("d") and not inp.is_down("a")


def test_bank_levels_out(setup):
    pilot, inp, clock, flight = setup
    pilot.bank(flight["roll_band"])
    assert not inp.is_down("a") and not inp.is_down("d")
    pilot.bank(12)
    assert inp.is_down("a")
    clock.now = flight["roll_max_s"] + 0.01
    pilot.update()
    pilot.bank(-12)
    assert not inp.is_down("d")
    clock.now = flight["roll_interval_s"] + 0.01
    pilot.bank(-12)
    assert inp.is_down("d")
    pilot.bank(None)


def test_bank_corrects_steep_roll_at_once(setup):
    pilot, inp, clock, flight = setup
    pilot.bank(10)
    clock.now = flight["roll_max_s"] + 0.01
    pilot.update()
    pilot.bank(flight["roll_limit"] + 10, 840, flight["turn_bank"])
    assert inp.is_down("a")


def test_no_yaw_in_steep_bank(setup):
    pilot, inp, _, flight = setup
    pilot.bank(flight["roll_limit"] + 5)
    pilot.yaw(1500)
    assert not inp.is_down("e") and not inp.is_down("q")


def test_hover_band_allows_small_roll(setup):
    pilot, inp, _, flight = setup
    pilot.bank(flight["hover_roll_band"] - 1, None, 0, flight["hover_roll_band"])
    assert not inp.is_down("a") and not inp.is_down("d")


def test_fly_noses_up_when_sinking_fast_despite_shift(setup):
    pilot, inp, clock, _ = setup
    samples = [(100 - 3 * i, 200 - 3 * i, 200 + 2 * i) for i in range(15)]
    feed(pilot, clock, samples, target_agl=150, target_speed=200)
    assert inp.is_down("shift") and "s" in pressed(inp)


def test_fly_does_not_accelerate_while_sinking(setup):
    pilot, inp, clock, _ = setup
    samples = [(150, 300 - 3 * i, 100) for i in range(12)]
    feed(pilot, clock, samples, target_agl=100, target_speed=200)
    assert not inp.is_down("w")


def aim(pilot, clock, *xs, start=10.0):
    for step, x in enumerate(xs):
        clock.now = start + step * 0.1
        pilot.yaw(x)


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
    pilot.bank(0, 840)
    pilot.release()
    assert not any(inp.is_down(key) for key in ("shift", "ctrl", "w", "s", "q", "e", "a", "d"))

from unittest.mock import Mock

import numpy as np
import pytest

from heli_farmer.states import (
    Detectors,
    Layer,
    StateMachine,
    UnknownStateTimeout,
    Watchdog,
    classify,
)

FRAME = np.zeros((1080, 1920, 3), np.uint8)


class FakeWorld:
    def __init__(self, on_server=True, in_team_blue=True, has_heli=True):
        self.on_server = on_server
        self.in_team_blue = in_team_blue
        self.has_heli = has_heli

    def detectors(self) -> Detectors:
        return Detectors(
            on_server=lambda frame: self.on_server,
            in_team_blue=lambda frame: self.in_team_blue,
            has_heli=lambda frame: self.has_heli,
        )


class FakeClock:
    def __init__(self):
        self.now = 0.0

    def __call__(self) -> float:
        return self.now


@pytest.mark.parametrize(
    ("on_server", "in_team_blue", "has_heli", "layer"),
    [
        (True, True, True, Layer.CRATE_LOOP),
        (True, True, False, Layer.VEHICLE),
        (True, False, True, Layer.TEAM),
        (False, True, True, Layer.SERVER),
        (False, False, False, Layer.SERVER),
        (None, True, True, Layer.UNKNOWN),
        (True, None, True, Layer.UNKNOWN),
        (True, True, None, Layer.UNKNOWN),
        (False, None, None, Layer.SERVER),
    ],
)
def test_classify_checks_outside_in(on_server, in_team_blue, has_heli, layer):
    results = {"on_server": on_server, "in_team_blue": in_team_blue, "has_heli": has_heli}
    assert classify(results) == layer


def test_default_detectors_are_stubs():
    machine = StateMachine(Detectors(), {}, Watchdog(30), FakeClock())
    assert machine.tick(FRAME) == Layer.UNKNOWN


def test_falls_back_to_outer_layer_and_runs_its_handler():
    world = FakeWorld()
    handlers = {layer: Mock() for layer in Layer}
    machine = StateMachine(world.detectors(), handlers, Watchdog(30), FakeClock())

    assert machine.tick(FRAME) == Layer.CRATE_LOOP
    world.has_heli = False
    assert machine.tick(FRAME) == Layer.VEHICLE
    world.has_heli = True
    world.on_server = False
    assert machine.tick(FRAME) == Layer.SERVER
    world.on_server = True
    world.in_team_blue = False
    assert machine.tick(FRAME) == Layer.TEAM

    for layer in (Layer.CRATE_LOOP, Layer.VEHICLE, Layer.SERVER, Layer.TEAM):
        handlers[layer].assert_called_once_with(FRAME)
    handlers[Layer.UNKNOWN].assert_not_called()


def test_watchdog_stops_after_unknown_timeout():
    world = FakeWorld(has_heli=None)
    clock = FakeClock()
    machine = StateMachine(world.detectors(), {}, Watchdog(30), clock)

    machine.tick(FRAME)
    clock.now = 30
    assert machine.tick(FRAME) == Layer.UNKNOWN
    clock.now = 30.1
    with pytest.raises(UnknownStateTimeout):
        machine.tick(FRAME)


def test_watchdog_resets_on_known_state():
    world = FakeWorld(has_heli=None)
    clock = FakeClock()
    machine = StateMachine(world.detectors(), {}, Watchdog(30), clock)

    machine.tick(FRAME)
    clock.now = 25
    world.has_heli = True
    machine.tick(FRAME)
    world.has_heli = None
    clock.now = 26
    machine.tick(FRAME)
    clock.now = 55
    assert machine.tick(FRAME) == Layer.UNKNOWN
    clock.now = 56.1
    with pytest.raises(UnknownStateTimeout):
        machine.tick(FRAME)

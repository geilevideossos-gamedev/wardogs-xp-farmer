import threading
from unittest.mock import Mock

import numpy as np
import pytest
from pynput import keyboard

from heli_farmer.config import load_config
from heli_farmer.inputs import Input
from heli_farmer.killswitch import Killswitch, Stopped
from heli_farmer.main import Finished, build_machine, hold_test, parse_args
from heli_farmer.states import Layer, SafeStop

FRAME = np.zeros((1080, 1920, 3), np.uint8)


def test_hold_test_holds_key_until_stop():
    stop = threading.Event()
    backend = Mock()
    inp = Input(stop, backend=backend)
    killswitch = Killswitch("f2", stop, inp.release_all)
    timer = threading.Timer(0.1, lambda: killswitch._on_press(keyboard.Key.f2))
    timer.start()

    with pytest.raises(Stopped):
        hold_test(inp, stop, "w", 0.01, 0)

    assert backend.keyDown.call_count >= 2
    backend.keyUp.assert_called_once_with("w")


def test_once_and_step_need_layer():
    with pytest.raises(SystemExit):
        parse_args(["--once"])
    args = parse_args(["--layer", "1", "--step", "buy", "--map", "ozeti"])
    assert (args.layer, args.step, args.map) == (1, "buy", "ozeti")


def test_layer_one_assumes_server_and_team_and_stubs_outer_layers():
    config = load_config("config.yaml")
    vision = Mock()
    vision.has_heli.return_value = False
    loop = Mock()
    inp = Mock()
    machine = build_machine(config, parse_args(["--layer", "1", "--once"]), vision, loop, inp)
    with pytest.raises(SafeStop, match="VEHICLE"):
        machine.tick(FRAME)
    vision.has_heli.return_value = True
    with pytest.raises(Finished):
        machine.tick(FRAME)
    loop.run.assert_called_once_with((), True)


def test_without_layer_outer_layers_stay_unknown():
    vision = Mock()
    vision.has_heli.return_value = True
    inp = Mock()
    machine = build_machine(load_config("config.yaml"), parse_args([]), vision, Mock(), inp)
    assert machine.tick(FRAME) == Layer.UNKNOWN
    inp.release_all.assert_called_once()

import threading
from unittest.mock import Mock

import pytest
from pynput import keyboard

from heli_farmer.inputs import Input
from heli_farmer.killswitch import Killswitch, Stopped
from heli_farmer.main import hold_test


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

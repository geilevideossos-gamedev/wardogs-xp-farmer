import threading
import time
from unittest.mock import Mock, call

import pytest
from pynput import keyboard

from heli_farmer.inputs import Input
from heli_farmer.killswitch import Killswitch, Stopped, key_name, wait


def make(stop_key="f2"):
    stop = threading.Event()
    backend = Mock()
    inp = Input(stop, backend=backend)
    return stop, backend, inp, Killswitch(stop_key, stop, inp.release_all)


def test_release_all_releases_keys_and_buttons():
    _, backend, inp, _ = make()
    inp.key_down("w")
    inp.key_down("shift")
    inp.mouse_down("right")

    inp.release_all()

    assert backend.keyUp.call_args_list == [call("shift"), call("w")]
    assert backend.mouseUp.call_args_list == [call(button="right")]
    backend.reset_mock()
    inp.release_all()
    backend.keyUp.assert_not_called()


def test_released_key_is_not_released_again():
    _, backend, inp, _ = make()
    inp.key_down("w")
    inp.key_up("w")
    backend.reset_mock()

    inp.release_all()

    backend.keyUp.assert_not_called()


def test_release_all_continues_after_backend_error():
    _, backend, inp, _ = make()
    inp.key_down("a")
    inp.key_down("b")
    backend.keyUp.side_effect = [RuntimeError("boom"), None]

    inp.release_all()

    assert backend.keyUp.call_args_list == [call("a"), call("b")]


def test_f2_sets_stop_and_releases_everything_fast():
    stop, backend, inp, killswitch = make()
    inp.key_down("w")
    inp.mouse_down("left")

    killswitch._on_press(keyboard.Key.f2)

    assert stop.is_set()
    backend.keyUp.assert_called_once_with("w")
    backend.mouseUp.assert_called_once_with(button="left")
    assert killswitch.latency_ms < 100


def test_other_keys_do_not_stop():
    stop, backend, inp, killswitch = make()
    inp.key_down("w")

    killswitch._on_press(keyboard.Key.f3)
    killswitch._on_press(keyboard.KeyCode.from_vk(0x57, char="w"))
    killswitch._on_press(None)

    assert not stop.is_set()
    backend.keyUp.assert_not_called()


def test_no_input_after_stop():
    _, backend, inp, killswitch = make()
    killswitch.trigger("test")

    with pytest.raises(Stopped):
        inp.key_down("w")
    with pytest.raises(Stopped):
        inp.mouse_down()
    backend.keyDown.assert_not_called()
    backend.mouseDown.assert_not_called()


def test_wait_wakes_up_immediately_on_stop():
    stop = threading.Event()
    timer = threading.Timer(0.05, stop.set)
    started = time.perf_counter()
    timer.start()

    with pytest.raises(Stopped):
        wait(stop, 5)

    assert time.perf_counter() - started < 0.15


def test_dry_run_only_logs(caplog):
    inp = Input(threading.Event(), dry_run=True)
    with caplog.at_level("INFO"):
        inp.key_down("w")
        inp.release_all()

    assert "dry-run: keyDown w" in caplog.text
    assert "dry-run: keyUp w" in caplog.text


@pytest.mark.parametrize(
    ("key", "name"),
    [
        (keyboard.Key.f2, "f2"),
        (keyboard.Key.space, "space"),
        (keyboard.KeyCode.from_vk(0x42, char="B"), "b"),
        (keyboard.KeyCode.from_vk(0x41, char="\x01"), "a"),
        (keyboard.KeyCode.from_vk(0x31, char="!"), "1"),
        (keyboard.KeyCode.from_vk(0xBC, char=","), ","),
        (keyboard.KeyCode.from_vk(0xFF), "vk255"),
    ],
)
def test_key_name(key, name):
    assert key_name(key) == name


def test_hold_sends_only_on_change():
    _, backend, inp, _ = make()
    inp.hold("shift", True)
    inp.hold("shift", True)
    inp.hold("shift", False)
    inp.hold("shift", False)
    assert backend.keyDown.call_args_list == [call("shift")]
    assert backend.keyUp.call_args_list == [call("shift")]


def test_tap_presses_and_releases():
    _, backend, inp, _ = make()
    inp.tap("b", 0)
    backend.keyDown.assert_called_once_with("b")
    backend.keyUp.assert_called_once_with("b")
    assert not inp.is_down("b")


def test_click_moves_then_clicks():
    _, backend, inp, _ = make()
    inp.click(955, 520)
    backend.moveTo.assert_called_once_with(955, 520)
    backend.mouseDown.assert_called_once_with(button="left")
    backend.mouseUp.assert_called_once_with(button="left")


def test_release_overdue_lets_go_of_long_holds():
    now = [0.0]
    backend = Mock()
    inp = Input(threading.Event(), backend=backend, clock=lambda: now[0])
    inp.key_down("shift")
    now[0] = 5.0
    inp.key_down("w")
    now[0] = 21.0
    assert inp.release_overdue(20) == ["shift"]
    assert inp.is_down("w") and not inp.is_down("shift")

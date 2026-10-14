import logging
import threading
import time
from collections.abc import Callable

from pynput import keyboard

log = logging.getLogger(__name__)


class Stopped(Exception):
    pass


def wait(stop: threading.Event, seconds: float) -> None:
    if stop.wait(seconds):
        raise Stopped


def key_name(key: keyboard.Key | keyboard.KeyCode) -> str:
    if isinstance(key, keyboard.Key):
        return key.name
    vk = key.vk
    if vk is not None and (0x30 <= vk <= 0x39 or 0x41 <= vk <= 0x5A):
        return chr(vk).lower()
    if key.char:
        return key.char.lower()
    return f"vk{vk}"


class Killswitch:
    def __init__(self, stop_key: str, stop: threading.Event, on_stop: Callable[[], None]):
        self._stop_key = stop_key
        self._stop = stop
        self._on_stop = on_stop
        self._listener: keyboard.Listener | None = None
        self.latency_ms: float | None = None

    def start(self) -> None:
        self._listener = keyboard.Listener(on_press=self._on_press)
        self._listener.start()

    def close(self) -> None:
        if self._listener is not None:
            self._listener.stop()

    def _on_press(self, key: keyboard.Key | keyboard.KeyCode | None) -> None:
        if key is not None and key_name(key) == self._stop_key:
            self.trigger(f"{self._stop_key} gedrückt")

    def trigger(self, reason: str) -> None:
        started = time.perf_counter()
        self._stop.set()
        self._on_stop()
        self.latency_ms = (time.perf_counter() - started) * 1000
        log.warning("Stopp (%s): alle Eingaben losgelassen nach %.1f ms", reason, self.latency_ms)

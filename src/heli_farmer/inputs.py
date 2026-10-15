import logging
import threading
import time
from collections.abc import Callable
from types import ModuleType

from heli_farmer.killswitch import Stopped, wait

log = logging.getLogger(__name__)


def _pydirectinput() -> ModuleType:
    import pydirectinput

    pydirectinput.PAUSE = 0
    pydirectinput.FAILSAFE = False
    return pydirectinput


class Input:
    def __init__(
        self,
        stop: threading.Event,
        dry_run: bool = False,
        backend=None,
        clock: Callable[[], float] = time.monotonic,
    ):
        self._stop = stop
        self._dry_run = dry_run
        self._backend = backend if backend is not None or dry_run else _pydirectinput()
        self._clock = clock
        self._lock = threading.Lock()
        self._keys: dict[str, float] = {}
        self._buttons: set[str] = set()

    def is_down(self, key: str) -> bool:
        return key in self._keys

    def key_down(self, key: str) -> None:
        with self._lock:
            self._raise_if_stopped()
            self._send("keyDown", key)
            self._keys.setdefault(key, self._clock())

    def key_up(self, key: str) -> None:
        with self._lock:
            self._send("keyUp", key)
            self._keys.pop(key, None)

    def hold(self, key: str, pressed: bool) -> None:
        if pressed and key not in self._keys:
            self.key_down(key)
        elif not pressed and key in self._keys:
            self.key_up(key)

    def tap(self, key: str, seconds: float) -> None:
        self.key_down(key)
        try:
            wait(self._stop, seconds)
        finally:
            self.key_up(key)

    def click(self, x: int, y: int) -> None:
        with self._lock:
            self._raise_if_stopped()
            self._send("moveTo", x, y)
        self.mouse_down()
        self.mouse_up()

    def mouse_down(self, button: str = "left") -> None:
        with self._lock:
            self._raise_if_stopped()
            self._send("mouseDown", button=button)
            self._buttons.add(button)

    def mouse_up(self, button: str = "left") -> None:
        with self._lock:
            self._send("mouseUp", button=button)
            self._buttons.discard(button)

    def release_overdue(self, limit_s: float) -> list[str]:
        now = self._clock()
        overdue = [key for key, since in self._keys.items() if now - since > limit_s]
        for key in overdue:
            log.warning("Taste '%s' länger als %s s gedrückt, wird losgelassen", key, limit_s)
            self.key_up(key)
        return overdue

    def release_all(self) -> None:
        with self._lock:
            for key in sorted(self._keys):
                self._send_safe("keyUp", key)
            for button in sorted(self._buttons):
                self._send_safe("mouseUp", button=button)
            self._keys.clear()
            self._buttons.clear()

    def _raise_if_stopped(self) -> None:
        if self._stop.is_set():
            raise Stopped

    def _send(self, name: str, *args, **kwargs) -> None:
        if self._dry_run:
            log.info("dry-run: %s %s", name, " ".join(map(str, (*args, *kwargs.values()))))
            return
        getattr(self._backend, name)(*args, **kwargs)

    def _send_safe(self, name: str, *args, **kwargs) -> None:
        try:
            self._send(name, *args, **kwargs)
        except Exception:
            log.exception("Loslassen fehlgeschlagen: %s %s %s", name, args, kwargs)

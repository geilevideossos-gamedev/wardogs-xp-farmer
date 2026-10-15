import logging
import time
from collections.abc import Callable
from dataclasses import dataclass, fields
from enum import IntEnum

import numpy as np

from heli_farmer.detectors import Detection

log = logging.getLogger(__name__)

Detector = Callable[[np.ndarray], Detection]
Handler = Callable[[np.ndarray], None]


class Layer(IntEnum):
    UNKNOWN = -1
    CRATE_LOOP = 1
    VEHICLE = 2
    TEAM = 3
    SERVER = 4


@dataclass(frozen=True)
class Detectors:
    on_server: Detector
    in_team_blue: Detector
    has_heli: Detector


LAYER_CHECKS = (
    ("on_server", Layer.SERVER),
    ("in_team_blue", Layer.TEAM),
    ("has_heli", Layer.VEHICLE),
)


class UnknownStateTimeout(Exception):
    pass


class SafeStop(Exception):
    pass


def not_built(layer: Layer) -> Handler:
    def handler(frame: np.ndarray) -> None:
        raise SafeStop(f"Layer {layer.name} ist noch nicht gebaut")

    return handler


def detect(frame: np.ndarray, detectors: Detectors) -> dict[str, Detection]:
    return {field.name: getattr(detectors, field.name)(frame) for field in fields(detectors)}


def classify(results: dict[str, Detection]) -> Layer:
    for name, layer in LAYER_CHECKS:
        value = results[name]
        if value is None:
            return Layer.UNKNOWN
        if not value:
            return layer
    return Layer.CRATE_LOOP


class Watchdog:
    def __init__(self, timeout_s: float):
        self._timeout_s = timeout_s
        self._unknown_since: float | None = None

    def expired(self, layer: Layer, now: float) -> bool:
        if layer != Layer.UNKNOWN:
            self._unknown_since = None
            return False
        if self._unknown_since is None:
            self._unknown_since = now
        return now - self._unknown_since > self._timeout_s


class StateMachine:
    def __init__(
        self,
        detectors: Detectors,
        handlers: dict[Layer, Handler],
        watchdog: Watchdog,
        clock: Callable[[], float] = time.monotonic,
    ):
        self._detectors = detectors
        self._handlers = handlers
        self._watchdog = watchdog
        self._clock = clock
        self.layer: Layer | None = None

    def tick(self, frame: np.ndarray) -> Layer:
        results = detect(frame, self._detectors)
        layer = classify(results)
        if layer != self.layer:
            log.info("Layer %s -> %s %s", self.layer and self.layer.name, layer.name, results)
            self.layer = layer
        if self._watchdog.expired(layer, self._clock()):
            raise UnknownStateTimeout(f"unbekannter Zustand länger als Timeout: {results}")
        handler = self._handlers.get(layer)
        if handler is not None:
            handler(frame)
        return layer

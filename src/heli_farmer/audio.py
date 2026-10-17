import logging
import threading
import time
import warnings
from collections.abc import Callable, Iterable, Iterator

import numpy as np

from heli_farmer.killswitch import Stopped

log = logging.getLogger(__name__)


class MissileWarning:
    def __init__(self, config: dict):
        self.tone_hz = config["tone_hz"]
        self.bandwidth_hz = config["bandwidth_hz"]
        self.context_hz = config["context_hz"]
        self.frame_s = config["frame_s"]
        self.ratio_min = config["ratio_min"]
        self.warn_s = config["warn_s"]
        self.max_gap_s = config["max_gap_s"]
        self._buffer = np.zeros(0, np.float32)
        self.run_s = 0.0
        self._gap_s = 0.0

    def tone_ratios(self, samples: np.ndarray, rate: int) -> np.ndarray:
        n = round(self.frame_s * rate)
        count = len(samples) // n
        frames = samples[: count * n].reshape(count, n) * np.hanning(n)
        power = np.abs(np.fft.rfft(frames, 4 * n, axis=1)) ** 2
        freqs = np.fft.rfftfreq(4 * n, 1 / rate)
        band = np.abs(freqs - self.tone_hz) <= self.bandwidth_hz
        context = (freqs >= self.context_hz[0]) & (freqs <= self.context_hz[1])
        return power[:, band].sum(1) / (power[:, context].sum(1) + 1e-12)

    def feed(self, samples: np.ndarray, rate: int) -> bool:
        if samples.ndim == 2:
            samples = samples.mean(axis=1)
        self._buffer = np.concatenate([self._buffer, samples.astype(np.float32)])
        n = round(self.frame_s * rate)
        used = len(self._buffer) // n * n
        ratios = self.tone_ratios(self._buffer[:used], rate)
        self._buffer = self._buffer[used:]
        alarm = False
        for ratio in ratios:
            if ratio >= self.ratio_min:
                self.run_s += self._gap_s + self.frame_s
                self._gap_s = 0.0
            elif self.run_s > 0:
                self._gap_s += self.frame_s
                if self._gap_s > self.max_gap_s:
                    self.run_s = 0.0
                    self._gap_s = 0.0
            alarm |= self.run_s >= self.warn_s
        return alarm


def loopback_blocks(rate: int, block_s: float) -> Iterator[np.ndarray]:
    import soundcard
    from soundcard.mediafoundation import SoundcardRuntimeWarning

    warnings.filterwarnings("ignore", category=SoundcardRuntimeWarning)
    speaker = soundcard.default_speaker()
    mic = soundcard.get_microphone(speaker.id, include_loopback=True)
    log.info("Raketenwarnung hört mit auf: %s", speaker.name)
    with mic.recorder(samplerate=rate) as recorder:
        while True:
            yield recorder.record(numframes=round(rate * block_s))


class FlareWatcher(threading.Thread):
    def __init__(
        self,
        config: dict,
        stop: threading.Event,
        on_warning: Callable[[], None],
        blocks: Iterable[np.ndarray] | None = None,
        clock: Callable[[], float] = time.monotonic,
    ):
        super().__init__(name="flare-watcher", daemon=True)
        self._config = config
        self._stop = stop
        self._on_warning = on_warning
        self._blocks = blocks
        self._clock = clock
        self._detector = MissileWarning(config)
        self.warnings = 0

    def run(self) -> None:
        rate = self._config["sample_rate"]
        blocks = self._blocks
        if blocks is None:
            blocks = loopback_blocks(rate, self._config["block_s"])
        last = -float("inf")
        try:
            for block in blocks:
                if self._stop.is_set():
                    break
                if not self._detector.feed(block, rate):
                    continue
                now = self._clock()
                if now - last < self._config["cooldown_s"]:
                    continue
                last = now
                self.warnings += 1
                log.warning("Raketenwarnung erkannt, Flares (Nr. %d)", self.warnings)
                self._on_warning()
        except Stopped:
            pass
        except Exception:
            log.exception("Raketenwarnung ausgefallen, Bot fliegt ohne Flares weiter")
        finally:
            if hasattr(blocks, "close"):
                blocks.close()

import logging
import threading
from pathlib import Path

import numpy as np
import pytest

from heli_farmer.audio import FlareWatcher, MissileWarning
from heli_farmer.config import load_config
from heli_farmer.killswitch import Stopped

RATE = 48000
BLOCK_S = 0.05
CLIP = Path(
    "wardogs_daten/Audio/nach 0.66sec des konstanten bipppppppp sounds mit v flares ab werfen.mp3"
)
VIDEOS = Path("wardogs_daten/Video")
CLIP_TONE = (4.32, 6.88)
VIDEO_ALARMS = {
    "join+Bakurani.mp4": [300.4],
    "join+Ozeti.mp4": [215.55, 221.2, 227.25],
    "join+Zestafona.mp4": [306.65, 317.2],
}
GAMEPLAY_WITHOUT_TONE = {"join+Bakurani.mp4": 250, "join+Ozeti.mp4": 280, "join+Zestafona.mp4": 245}


@pytest.fixture(scope="module")
def config():
    return load_config("config.yaml")["audio"]


def tone(seconds, hz, rate=RATE, amp=0.05):
    t = np.arange(round(seconds * rate)) / rate
    return (amp * np.sin(2 * np.pi * hz * t)).astype(np.float32)


def rotor_noise(seconds, rate=RATE, seed=0):
    rng = np.random.default_rng(seed)
    t = np.arange(round(seconds * rate)) / rate
    hum = sum(np.sin(2 * np.pi * 23 * k * t + k) / k for k in range(1, 26))
    return (0.04 * hum + 0.03 * rng.standard_normal(len(t))).astype(np.float32)


def blocks(samples, rate=RATE, block_s=BLOCK_S):
    n = round(rate * block_s)
    return [samples[i : i + n] for i in range(0, len(samples), n)]


def alarm_onsets(detector, samples, rate=RATE):
    onsets, previous = [], False
    for i, block in enumerate(blocks(samples, rate)):
        alarm = detector.feed(block, rate)
        if alarm and not previous:
            onsets.append(round((i + 1) * BLOCK_S, 2))
        previous = alarm
    return onsets


def test_constant_tone_alarms_after_warn_time(config):
    samples = np.concatenate([np.zeros(RATE, np.float32), tone(2, config["tone_hz"])])

    onsets = alarm_onsets(MissileWarning(config), samples)

    assert len(onsets) == 1
    assert 1 + config["warn_s"] <= onsets[0] <= 1 + config["warn_s"] + 0.1


def test_stereo_tone_under_rotor_and_noise_alarms(config):
    mono = tone(2, config["tone_hz"], amp=0.03) + rotor_noise(2)

    onsets = alarm_onsets(MissileWarning(config), np.stack([mono, mono], axis=1))

    assert len(onsets) == 1
    assert onsets[0] <= config["warn_s"] + 0.1


def test_rotor_and_noise_never_alarm(config):
    assert alarm_onsets(MissileWarning(config), rotor_noise(30, seed=1)) == []


def test_short_tone_does_not_alarm(config):
    samples = np.concatenate([tone(config["warn_s"] - 0.15, config["tone_hz"]), rotor_noise(2)])

    assert alarm_onsets(MissileWarning(config), samples) == []


def test_lock_beeps_do_not_alarm(config):
    beep = np.concatenate([tone(0.12, 1610), np.zeros(round(0.12 * RATE), np.float32)])
    samples = np.tile(beep, 15) + rotor_noise(len(beep) * 15 / RATE)

    assert alarm_onsets(MissileWarning(config), samples) == []


def test_short_dropout_keeps_tone_running(config):
    hz = config["tone_hz"]
    gap = np.zeros(round(0.08 * RATE), np.float32)
    samples = np.concatenate([tone(0.4, hz), gap, tone(0.4, hz)])

    assert len(alarm_onsets(MissileWarning(config), samples)) == 1


def run_watcher(config, samples, on_warning, stop=None):
    now = [0.0]

    def source():
        for block in blocks(samples):
            now[0] += BLOCK_S
            yield block

    watcher = FlareWatcher(
        config, stop or threading.Event(), on_warning, blocks=source(), clock=lambda: now[0]
    )
    watcher.start()
    watcher.join(5)
    assert not watcher.is_alive()
    return watcher


def test_watcher_fires_with_cooldown(config):
    calls = []
    seconds = config["warn_s"] + config["cooldown_s"] + 1
    cfg = {**config, "sample_rate": RATE}

    watcher = run_watcher(cfg, tone(seconds, config["tone_hz"]), lambda: calls.append(1))

    assert len(calls) == 2
    assert watcher.warnings == 2


def test_watcher_ends_on_stop_event(config):
    stop = threading.Event()

    def silence():
        while True:
            yield np.zeros(round(RATE * BLOCK_S), np.float32)

    watcher = FlareWatcher({**config, "sample_rate": RATE}, stop, lambda: None, blocks=silence())
    watcher.start()
    stop.set()
    watcher.join(2)

    assert not watcher.is_alive()


def test_watcher_ends_quietly_when_callback_stops(config, caplog):
    def on_warning():
        raise Stopped

    with caplog.at_level(logging.ERROR):
        run_watcher({**config, "sample_rate": RATE}, tone(2, config["tone_hz"]), on_warning)

    assert caplog.records == []


def test_watcher_logs_source_errors(config, caplog):
    def broken():
        yield np.zeros(10, np.float32)
        raise OSError("kein Audiogerät")

    watcher = FlareWatcher(
        {**config, "sample_rate": RATE}, threading.Event(), lambda: None, broken()
    )
    with caplog.at_level(logging.ERROR):
        watcher.start()
        watcher.join(2)

    assert not watcher.is_alive()
    assert "ohne Flares" in caplog.text


def load_audio(path, rate):
    av = pytest.importorskip("av")
    if not path.exists():
        pytest.skip(f"{path} fehlt")
    chunks = []
    with av.open(str(path)) as container:
        resampler = av.AudioResampler(format="flt", layout="mono", rate=rate)
        for frame in container.decode(audio=0):
            chunks += [f.to_ndarray().reshape(-1) for f in resampler.resample(frame)]
    return np.concatenate(chunks)


@pytest.mark.videos
@pytest.mark.parametrize("rate", [16000, 48000])
def test_clip_alarms_once_after_warn_time(config, rate):
    samples = load_audio(CLIP, rate)

    onsets = alarm_onsets(MissileWarning(config), samples, rate)

    assert len(onsets) == 1
    assert CLIP_TONE[0] + config["warn_s"] <= onsets[0] <= CLIP_TONE[0] + config["warn_s"] + 0.15


@pytest.mark.videos
def test_clip_without_constant_tone_never_alarms(config):
    samples = load_audio(CLIP, RATE)

    assert alarm_onsets(MissileWarning(config), samples[: round(CLIP_TONE[0] * RATE)]) == []


@pytest.mark.videos
@pytest.mark.parametrize("video", sorted(VIDEO_ALARMS))
def test_video_alarms_only_on_missile_tone(config, video):
    samples = load_audio(VIDEOS / video, 16000)

    onsets = alarm_onsets(MissileWarning(config), samples, 16000)

    assert onsets == pytest.approx(VIDEO_ALARMS[video], abs=0.2)


@pytest.mark.videos
@pytest.mark.parametrize("video", sorted(GAMEPLAY_WITHOUT_TONE))
@pytest.mark.parametrize("gain", [1, 3])
def test_clip_tone_mixed_with_loud_gameplay_alarms(config, video, gain):
    clip = load_audio(CLIP, 16000)
    game = load_audio(VIDEOS / video, 16000)
    start = GAMEPLAY_WITHOUT_TONE[video] * 16000
    mixed = clip + gain * game[start : start + len(clip)]

    onsets = alarm_onsets(MissileWarning(config), mixed, 16000)

    assert len(onsets) == 1
    assert onsets[0] == pytest.approx(CLIP_TONE[0] + config["warn_s"], abs=0.2)

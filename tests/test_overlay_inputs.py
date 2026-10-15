import json

import cv2
import numpy as np
import pytest

from heli_farmer.config import load_config
from tools import overlay_inputs

YELLOW = (40, 240, 240)


@pytest.fixture
def config():
    return load_config("config.yaml")


def press(frame: np.ndarray, overlay: dict, key: str) -> None:
    row, col = overlay["keys"][key]
    x0 = overlay["origin"][0] + overlay["pitch"][0] * col
    y0 = overlay["origin"][1] + overlay["pitch"][1] * row
    for x, y, w, h in overlay["patches"]:
        frame[y0 + y : y0 + y + h, x0 + x : x0 + x + w] = YELLOW


def test_key_levels_separate_pressed_keys(config):
    overlay = config["overlay"]
    frame = np.full((1080, 1920, 3), (200, 180, 170), np.uint8)
    press(frame, overlay, "shift")
    levels = overlay_inputs.key_levels(frame, overlay)
    assert levels["shift"] > overlay["threshold_on"]
    assert all(level < overlay["threshold_off"] for key, level in levels.items() if key != "shift")


def test_key_tracker_uses_hysteresis():
    tracker = overlay_inputs.KeyTracker(on=75, off=65)
    assert tracker.update(0.0, {"w": 80}) == [
        {"t": 0.0, "type": "key", "key": "w", "action": "down"}
    ]
    assert tracker.update(0.1, {"w": 70}) == []
    assert tracker.update(0.2, {"w": 60}) == [{"t": 0.2, "type": "key", "key": "w", "action": "up"}]
    assert tracker.update(0.3, {"w": 70}) == []


class FakeVision:
    def __init__(self, states):
        self.states = iter(states)
        self.current = None

    def garage_menu(self, frame):
        self.current = next(self.states)
        return self.current[0]

    def in_lakota(self, frame):
        return self.current[1] is not None

    def crate_loaded(self, frame):
        return self.current[1]


def test_image_tracker_derives_b_and_g():
    states = [
        (None, False),
        ("main", None),
        (None, True),
        (None, True),
        (None, True),
        (None, False),
        (None, True),
        (None, False),
        (None, False),
        (None, False),
    ]
    tracker = overlay_inputs.ImageTracker(FakeVision(states), {"shop": "b", "drop": "g"}, 3)
    events = [e for i in range(len(states)) for e in tracker.update(float(i), None)]
    downs = [(e["t"], e["key"]) for e in events if e["action"] == "down"]
    assert downs == [(1.0, "b"), (9.0, "g")]


def test_main_writes_jsonl_next_to_video(tmp_path, config):
    video = tmp_path / "clip.mp4"
    writer = cv2.VideoWriter(str(video), cv2.VideoWriter_fourcc(*"mp4v"), 10, (1920, 1080))
    for index in range(12):
        frame = np.full((1080, 1920, 3), (200, 180, 170), np.uint8)
        if 4 <= index < 8:
            press(frame, config["overlay"], "w")
        writer.write(frame)
    writer.release()

    assert overlay_inputs.main([str(video)]) == 0

    lines = (tmp_path / "clip.inputs.jsonl").read_text(encoding="utf-8").splitlines()
    events = [json.loads(line) for line in lines]
    assert [(e["key"], e["action"]) for e in events] == [("w", "down"), ("w", "up")]
    assert events[0]["t"] == pytest.approx(0.4, abs=0.11)

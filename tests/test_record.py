import csv
import json
import time

import cv2
import numpy as np

from tools.record import Recorder, video_size

REGION = {"left": 0, "top": 0, "width": 160, "height": 120}


class FakeCapture:
    def __init__(self, region):
        self._shape = (region["height"], region["width"], 3)
        self._count = 0

    def grab(self):
        self._count += 1
        return np.full(self._shape, self._count % 256, np.uint8)

    def close(self):
        pass


def read_frames_csv(path):
    with open(path, newline="", encoding="utf-8") as file:
        return [(int(row["frame"]), float(row["t"])) for row in csv.DictReader(file)]


def test_recorder_writes_synchronized_files(tmp_path):
    out_dir = tmp_path / "map" / "drop_x"
    recorder = Recorder(out_dir, REGION, fps=20, scale=0.5, capture_cls=FakeCapture)
    recorder.start()
    deadline = time.monotonic() + 10
    while not (out_dir / "frames.csv").exists() and time.monotonic() < deadline:
        recorder.log_input(type="move", x=1, y=2)
        time.sleep(0.01)
    recorder.log_input(type="key", key="w", action="down")
    time.sleep(0.6)
    recorder.log_input(type="key", key="w", action="up")
    assert recorder.stop()

    assert {p.name for p in out_dir.iterdir()} == {
        "video.mp4",
        "frames.csv",
        "inputs.jsonl",
        "meta.json",
    }
    frames = read_frames_csv(out_dir / "frames.csv")
    assert len(frames) >= 5
    assert [index for index, _ in frames] == list(range(len(frames)))
    frame_times = [t for _, t in frames]
    assert all(a < b for a, b in zip(frame_times, frame_times[1:], strict=False))

    lines = (out_dir / "inputs.jsonl").read_text(encoding="utf-8").splitlines()
    events = [json.loads(line) for line in lines]
    input_times = [event["t"] for event in events]
    assert all(a <= b for a, b in zip(input_times, input_times[1:], strict=False))
    assert events[-1] == {"t": events[-1]["t"], "type": "key", "key": "w", "action": "up"}
    assert frame_times[0] < events[-1]["t"]

    video = cv2.VideoCapture(str(out_dir / "video.mp4"))
    assert int(video.get(cv2.CAP_PROP_FRAME_COUNT)) == len(frames)
    width = int(video.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(video.get(cv2.CAP_PROP_FRAME_HEIGHT))
    video.release()
    assert (width, height) == video_size(REGION, 0.5)

    meta = json.loads((out_dir / "meta.json").read_text(encoding="utf-8"))
    assert meta["fps"] == 20
    assert meta["region"] == REGION


def test_input_after_stop_is_ignored(tmp_path):
    recorder = Recorder(tmp_path / "rec", REGION, fps=20, scale=1.0, capture_cls=FakeCapture)
    recorder.start()
    recorder.stop()

    recorder.log_input(type="key", key="w", action="down")

    assert (tmp_path / "rec" / "inputs.jsonl").read_text() == ""


def test_video_size_is_even():
    assert video_size({"width": 1920, "height": 1080}, 1.0) == (1920, 1080)
    assert video_size({"width": 1920, "height": 1080}, 0.3) == (576, 324)
    assert video_size({"width": 101, "height": 51}, 1.0) == (100, 50)

import csv

import cv2
import numpy as np
import pytest

from tools import extract_frames, replay
from tools.video import iter_frames

FPS = 10


@pytest.fixture
def obs_video(tmp_path):
    path = tmp_path / "obs.mp4"
    writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"mp4v"), FPS, (320, 180))
    for index in range(30):
        writer.write(np.full((180, 320, 3), index * 8, np.uint8))
    writer.release()
    return path


def test_iter_frames_uses_video_timestamps(obs_video):
    times = [t for _, t, _ in iter_frames(obs_video)]
    assert len(times) == 30
    assert times[0] == pytest.approx(0.0)
    assert times[10] == pytest.approx(1.0)


def test_iter_frames_prefers_frames_csv(obs_video):
    rows = "frame,t\n" + "".join(f"{i},{5 + i * 0.2:.4f}\n" for i in range(30))
    obs_video.with_name("frames.csv").write_text(rows, encoding="utf-8")
    times = [t for _, t, _ in iter_frames(obs_video)]
    assert times[1] == pytest.approx(5.2)


def test_extract_at_times_with_crop(obs_video, tmp_path):
    out = tmp_path / "frames"
    written = extract_frames.extract(
        obs_video, out, extract_frames.at_times([1.0, 0.0, 2.05]), crop=(10, 20, 50, 40)
    )
    assert [p.name for p in written] == ["t00000.000.png", "t00001.000.png", "t00002.100.png"]
    assert cv2.imread(str(written[0])).shape == (40, 50, 3)


def test_extract_every_interval(obs_video, tmp_path):
    written = extract_frames.extract(obs_video, tmp_path / "f", extract_frames.every(0.5))
    assert len(written) == 6
    assert cv2.imread(str(written[0])).shape == (180, 320, 3)


def test_extract_cli(obs_video, tmp_path):
    out = tmp_path / "cli"
    assert extract_frames.main([str(obs_video), "--every", "1", "--out", str(out)]) == 0
    assert len(list(out.glob("*.png"))) == 3


def test_replay_writes_timeline(obs_video, tmp_path, capsys):
    out = tmp_path / "timeline.csv"
    assert replay.main([str(obs_video), "--step", "2", "--out", str(out)]) == 0

    with open(out, newline="", encoding="utf-8") as file:
        rows = list(csv.DictReader(file))
    assert len(rows) == 15
    assert rows[0].keys() == {"frame", "t", "on_server", "in_team_blue", "has_heli", "layer"}
    assert {row["layer"] for row in rows} == {"UNKNOWN"}
    assert "UNKNOWN" in capsys.readouterr().out


def test_replay_scales_frames_to_game_region(obs_video):
    seen = []
    detectors = replay.Detectors(
        on_server=lambda frame: seen.append(frame.shape) or True,
        in_team_blue=lambda frame: True,
        has_heli=lambda frame: False,
    )
    rows = replay.timeline(obs_video, {"width": 1920, "height": 1080}, detectors, step=10)
    assert seen == [(1080, 1920, 3)] * 3
    assert [row["layer"] for row in rows] == ["VEHICLE"] * 3


def test_segments_group_consecutive_layers():
    rows = [
        {"t": 0.0, "layer": "UNKNOWN"},
        {"t": 0.1, "layer": "UNKNOWN"},
        {"t": 0.2, "layer": "VEHICLE"},
    ]
    assert replay.segments(rows) == [(0.0, 0.1, "UNKNOWN", 2), (0.2, 0.2, "VEHICLE", 1)]

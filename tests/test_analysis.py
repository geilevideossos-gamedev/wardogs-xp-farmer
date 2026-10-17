import csv

import cv2
import numpy as np
import pytest

from heli_farmer.config import load_config
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
    assert list(rows[0].keys()) == replay.COLUMNS
    assert {row["situation"] for row in rows} == {"NO_HELI"}
    printed = capsys.readouterr().out
    assert "NO_HELI" in printed and "Abwürfe bei: keine" in printed
    assert "In der Zone: nie" in printed


def test_replay_scales_frames_to_game_region(obs_video, monkeypatch):
    seen = []
    monkeypatch.setattr(replay, "readings", lambda vision, frame: seen.append(frame.shape) or ROW)
    rows = replay.timeline(obs_video, load_config("config.yaml"), step=10)
    assert seen == [(1080, 1920, 3)] * 3
    assert [row["situation"] for row in rows] == ["TO_ZONE"] * 3


ROW = {
    "lakota": True,
    "menu": None,
    "crate": True,
    "speed": 200,
    "agl": 80,
    "buy_prompt": False,
    "delivered": False,
    "first_aid": False,
    "damaged": False,
}


@pytest.mark.parametrize(
    ("change", "expected"),
    [
        ({}, "TO_ZONE"),
        ({"crate": False}, "TO_BASE"),
        ({"speed": 0, "agl": 0}, "LANDED"),
        ({"speed": 0, "agl": 1, "buy_prompt": True}, "LANDED_BASE"),
        ({"damaged": True}, "DAMAGED"),
        ({"lakota": False}, "NO_HELI"),
        ({"lakota": False, "menu": "main"}, "BUY_MENU"),
        ({"lakota": False, "first_aid": True}, "DEAD"),
    ],
)
def test_situation(change, expected):
    assert replay.situation({**ROW, **change}, landed_agl=1, landed_speed=3) == expected


def test_segments_merge_short_blips():
    rows = [{"t": i / 10, "situation": s} for i, s in enumerate("AAAABAAACCCC")]
    assert replay.segments(rows, min_rows=2) == [(0.0, 0.7, "A", 8), (0.8, 1.1, "C", 4)]


def test_drops_need_confirmation():
    crates = [True, True, True, False, False, True, True, True, False, False, False, None, False]
    rows = [{"t": float(i), "crate": c} for i, c in enumerate(crates)]
    assert replay.drops(rows, confirm=3) == [10.0]


def marker_rows(spec: str, distances: list | None = None) -> list[dict]:
    codes = {"C": ("CZ", False), "c": ("CZ", True), "H": ("HZ", True), "h": ("HZ", False)}
    codes |= {"-": ("", False), "m": ("", True)}
    rows = []
    for i, code in enumerate(spec):
        zone, minimap = codes[code]
        distance = distances[i] if distances else None
        rows.append({"t": float(i), "zone": zone, "minimap": minimap, "distance": distance})
    return rows


def visits(rows):
    return replay.zone_visits(rows, confirm=2, history=3, brake_distance=400)


def test_zone_visits_enter_on_hz_alone():
    assert visits(marker_rows("CChhCC")) == [(3.0, 5.0)]


def test_zone_visits_enter_on_minimap_only_near_the_zone():
    far = marker_rows("ccmmCC", [900, 900, None, None, 900, 900])
    assert visits(far) == []
    near = marker_rows("cccmmCC", [500, 300, 200, None, None, 300, 300])
    assert visits(near) == [(3.0, 6.0)]


def test_zone_visits_ignore_minimap_without_crate():
    rows = marker_rows("cccmm", [300, 200, 100, None, None])
    for row in rows[3:]:
        row["crate"] = False
    assert visits(rows) == []


def test_zone_visits_leave_on_untinted_minimap_without_marker():
    rows = marker_rows("HHH----") + [{"t": 9.0, "zone": None, "minimap": None, "distance": None}]
    assert visits(rows) == [(1.0, 4.0)]


def test_zone_visits_open_at_end():
    assert visits(marker_rows("CHHH")) == [(2.0, None)]


def test_brake_times_use_median_once_per_leg():
    distances = [900, 700, 380, 999, 350, 300, 30, 0, 0]
    rows = [{**row, "crate": True} for row in marker_rows("CCCCCCCHH", distances)]
    rows += [{"t": 9.0, "crate": False, "zone": "CZ", "minimap": False, "distance": 5}]
    rows += [
        {"t": 10.0 + i, "crate": True, "zone": "CZ", "minimap": False, "distance": 100}
        for i in range(3)
    ]
    assert replay.brake_times(rows, history=3, brake_distance=400) == [4.0, 12.0]

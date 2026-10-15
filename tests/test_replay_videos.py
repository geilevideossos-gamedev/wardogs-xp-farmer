from pathlib import Path

import pytest

from heli_farmer.config import load_config
from tools import replay

VIDEOS = Path("wardogs_daten/Video")
EXPECTED = {
    "join+Bakurani.mp4": {
        "drops": [173.7, 316.4],
        "menus": [102.1, 252.4, 394.4],
        "zones": [173.5, 321.0],
        "brakes": [169.5],
    },
    "join+Ozeti.mp4": {
        "drops": [216.2, 434.8],
        "menus": [143.1, 342.1, 504.0],
        "damaged": 234,
        "zones": [213.0, 428.0],
        "brakes": [],
    },
    "join+Zestafona.mp4": {
        "drops": [172.3, 307.0, 439.4],
        "menus": [103.1, 247.7, 370.0],
        "damaged": 321,
        "dead": 341,
        "zones": [170.0, 305.5, 436.0],
        "brakes": [164.0],
    },
}

pytestmark = pytest.mark.videos


@pytest.fixture(scope="module")
def config():
    return load_config("config.yaml")


@pytest.fixture(scope="module", params=EXPECTED)
def video(request, config):
    path = VIDEOS / request.param
    if not path.exists():
        pytest.skip("Video fehlt (liegt nur lokal in wardogs_daten/)")
    return EXPECTED[request.param], replay.timeline(path, config, step=6)


def test_timeline_matches_analysis(video, config):
    expected, rows = video
    assert replay.drops(rows, config["vision"]["confirm"]) == pytest.approx(
        expected["drops"], abs=0.5
    )
    starts = {key: [] for key in ("BUY_MENU", "DAMAGED", "DEAD")}
    for start, _, situation, _ in replay.segments(rows, min_rows=3):
        starts.get(situation, []).append(start)
    assert starts["BUY_MENU"] == pytest.approx(expected["menus"], abs=0.5)
    for situation in ("damaged", "dead"):
        found = starts[situation.upper()]
        assert (situation in expected) == bool(found)
        if found:
            assert found[0] == pytest.approx(expected[situation], abs=1.5)


def test_every_drop_inside_detected_zone(video, config):
    expected, rows = video
    visits = replay.zone_visits(rows, config["vision"]["confirm"])
    assert [enter for enter, _ in visits] == pytest.approx(expected["zones"], abs=1.0)
    for drop in expected["drops"]:
        assert any(enter - 5 <= drop <= leave for enter, leave in visits if leave), drop


def test_brakes_before_zone_entry(video, config):
    expected, rows = video
    brakes = replay.brake_times(
        rows,
        config["flight"]["distance_history"],
        config["maps"]["default"]["brake_distance"],
    )
    assert brakes == pytest.approx(expected["brakes"], abs=1.0)
    for brake in brakes:
        assert any(0 < enter - brake <= 20 for enter in expected["zones"]), brake


def test_hq_hidden_in_zone_and_seen_after_leaving(video, config):
    _, rows = video
    assert not [row["t"] for row in rows if row["zone"] == "HZ" and row["hq"]]
    for _, leave in replay.zone_visits(rows, config["vision"]["confirm"]):
        seen = [row["t"] for row in rows if row["hq"] and row["t"] >= leave]
        assert seen and seen[0] - leave <= 10, leave

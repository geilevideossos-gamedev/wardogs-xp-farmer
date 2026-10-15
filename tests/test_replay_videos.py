from pathlib import Path

import pytest

from heli_farmer.config import load_config
from tools import replay

VIDEOS = Path("wardogs_daten/Video")
EXPECTED = {
    "join+Bakurani.mp4": {"drops": [173.7, 316.4], "menus": [102.1, 252.4, 394.4]},
    "join+Ozeti.mp4": {"drops": [216.2, 434.8], "menus": [143.1, 342.1, 504.0], "damaged": 234},
    "join+Zestafona.mp4": {
        "drops": [172.3, 307.0, 439.4],
        "menus": [103.1, 247.7, 370.0],
        "damaged": 321,
        "dead": 341,
    },
}

pytestmark = pytest.mark.videos


@pytest.mark.parametrize("name", EXPECTED)
def test_timeline_matches_analysis(name):
    video = VIDEOS / name
    if not video.exists():
        pytest.skip("Video fehlt (liegt nur lokal in wardogs_daten/)")
    config = load_config("config.yaml")
    rows = replay.timeline(video, config, step=6)
    expected = EXPECTED[name]

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

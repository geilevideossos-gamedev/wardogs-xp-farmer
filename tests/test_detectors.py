import json
from pathlib import Path

import cv2
import numpy as np
import pytest

from heli_farmer.config import load_config
from heli_farmer.detectors import Vision

FIXTURES = Path(__file__).parent / "fixtures"
MANIFEST = json.loads((FIXTURES / "fixtures.json").read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def vision():
    return Vision(load_config("config.yaml")["vision"])


def frame_from(entry: dict) -> np.ndarray:
    crop = cv2.imread(str(FIXTURES / entry["file"]))
    frame = np.zeros((1080, 1920, 3), np.uint8)
    height, width = crop.shape[:2]
    frame[entry["y"] : entry["y"] + height, entry["x"] : entry["x"] + width] = crop
    return frame


def entries(kind: str) -> list[dict]:
    return [entry for entry in MANIFEST if entry["file"].startswith(kind + "_")]


def ids(items: list[dict]) -> list[str]:
    return [entry["file"] for entry in items]


@pytest.mark.parametrize("entry", entries("hud"), ids=ids(entries("hud")))
def test_reads_speed_and_agl(vision, entry):
    frame = frame_from(entry)
    assert vision.speed(frame) == entry["speed"]
    assert vision.agl(frame) == entry["agl"]


@pytest.mark.parametrize("entry", entries("badges"), ids=ids(entries("badges")))
def test_heli_label_and_crate_badge(vision, entry):
    frame = frame_from(entry)
    assert vision.in_lakota(frame) == entry["lakota"]
    assert vision.crate_loaded(frame) == entry["crate"]


@pytest.mark.parametrize("entry", entries("damage"), ids=ids(entries("damage")))
def test_heli_damage(vision, entry):
    assert vision.heli_damaged(frame_from(entry)) == entry["damaged"]


@pytest.mark.parametrize("entry", entries("prompt"), ids=ids(entries("prompt")))
def test_buy_prompt_and_delivered_popup(vision, entry):
    frame = frame_from(entry)
    assert vision.buy_prompt(frame) == entry["buy_prompt"]
    assert vision.delivered(frame) == entry["delivered"]


@pytest.mark.parametrize("entry", entries("first_aid"), ids=ids(entries("first_aid")))
def test_first_aid(vision, entry):
    assert vision.first_aid(frame_from(entry)) == entry["first_aid"]


@pytest.mark.parametrize("entry", entries("menu"), ids=ids(entries("menu")))
def test_garage_menu(vision, entry):
    assert vision.garage_menu(frame_from(entry)) == entry["menu"]


@pytest.mark.parametrize("kind", ["zone", "hq"])
def test_markers_found_inside_crop(vision, kind):
    detect = vision.zone_marker if kind == "zone" else vision.hq_marker
    for entry in entries(kind):
        crop = cv2.imread(str(FIXTURES / entry["file"]))
        marker = detect(frame_from(entry))
        assert marker is not None, entry["file"]
        assert entry["x"] <= marker.x < entry["x"] + crop.shape[1], entry["file"]
        assert entry["y"] <= marker.y < entry["y"] + crop.shape[0], entry["file"]


def test_markers_absent_on_hud_only_frame(vision):
    frame = frame_from(entries("hud")[0])
    assert vision.zone_marker(frame) is None
    assert vision.hq_marker(frame) is None


def test_empty_frame_reads_nothing(vision):
    frame = np.zeros((1080, 1920, 3), np.uint8)
    assert vision.speed(frame) is None
    assert vision.agl(frame) is None
    assert not vision.in_lakota(frame)
    assert vision.garage_menu(frame) is None
    assert not vision.heli_damaged(frame)

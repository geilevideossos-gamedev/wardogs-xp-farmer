import argparse
import json
import sys
from pathlib import Path

import numpy as np

from heli_farmer.config import load_config
from heli_farmer.detectors import Vision
from tools.video import iter_frames


def key_levels(frame: np.ndarray, overlay: dict) -> dict[str, float]:
    origin_x, origin_y = overlay["origin"]
    pitch_x, pitch_y = overlay["pitch"]
    pixels = frame[: origin_y + 3 * pitch_y].astype(np.int16)
    level = np.minimum(pixels[..., 1], pixels[..., 2]) - pixels[..., 0]
    levels = {}
    for name, (row, col) in overlay["keys"].items():
        x0 = origin_x + pitch_x * col
        y0 = origin_y + pitch_y * row
        values = [
            level[y0 + y : y0 + y + h, x0 + x : x0 + x + w].ravel()
            for x, y, w, h in overlay["patches"]
        ]
        levels[name] = float(np.median(np.concatenate(values)))
    return levels


def tap(t: float, key: str) -> list[dict]:
    return [
        {"t": round(t, 4), "type": "key", "key": key, "action": action} for action in ("down", "up")
    ]


class KeyTracker:
    def __init__(self, on: float, off: float):
        self._on = on
        self._off = off
        self._pressed: set[str] = set()

    def update(self, t: float, levels: dict[str, float]) -> list[dict]:
        events = []
        for name, level in levels.items():
            pressed = level >= self._off if name in self._pressed else level > self._on
            if pressed != (name in self._pressed):
                self._pressed.symmetric_difference_update({name})
                action = "down" if pressed else "up"
                events.append({"t": round(t, 4), "type": "key", "key": name, "action": action})
        return events


class ImageTracker:
    def __init__(self, vision: Vision, keys: dict, confirm: int):
        self._vision = vision
        self._keys = keys
        self._confirm = confirm
        self._menu_open = False
        self._crate: bool | None = None
        self._recent: list[bool | None] = []

    def update(self, t: float, frame: np.ndarray) -> list[dict]:
        events = []
        menu_open = self._vision.garage_menu(frame) is not None
        if menu_open and not self._menu_open:
            events += tap(t, self._keys["shop"])
        self._menu_open = menu_open
        crate = self._vision.crate_loaded(frame) if self._vision.in_lakota(frame) else None
        self._recent = (self._recent + [crate])[-self._confirm :]
        if crate is not None and self._recent.count(crate) == self._confirm:
            if self._crate and not crate:
                events += tap(t, self._keys["drop"])
            self._crate = crate
        return events


def analyse(video: Path, config: dict) -> list[dict]:
    overlay = config["overlay"]
    keys = KeyTracker(overlay["threshold_on"], overlay["threshold_off"])
    images = ImageTracker(Vision(config["vision"]), config["keys"], config["vision"]["confirm"])
    events = []
    for index, t, frame in iter_frames(video, lambda index, t: index % overlay["step"] == 0):
        events += keys.update(t, key_levels(frame, overlay))
        if index % overlay["image_step"] == 0:
            events += images.update(t, frame)
    return sorted(events, key=lambda event: event["t"])


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="python -m tools.overlay_inputs")
    parser.add_argument("videos", type=Path, nargs="+")
    parser.add_argument("--config", default="config.yaml")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    config = load_config(args.config)
    for video in args.videos:
        events = analyse(video, config)
        out = video.with_suffix(".inputs.jsonl")
        out.write_text("".join(json.dumps(event) + "\n" for event in events), encoding="utf-8")
        print(f"{video.name}: {len(events)} Ereignisse -> {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

import argparse
import csv
import sys
from pathlib import Path

import cv2
import numpy as np

from heli_farmer.config import load_config
from heli_farmer.detectors import Vision
from tools.video import iter_frames

COLUMNS = [
    "frame",
    "t",
    "lakota",
    "menu",
    "crate",
    "speed",
    "agl",
    "buy_prompt",
    "delivered",
    "first_aid",
    "damaged",
    "situation",
]


def readings(vision: Vision, frame: np.ndarray) -> dict:
    lakota = vision.in_lakota(frame)
    return {
        "lakota": lakota,
        "menu": vision.garage_menu(frame),
        "crate": vision.crate_loaded(frame) if lakota else None,
        "speed": vision.speed(frame) if lakota else None,
        "agl": vision.agl(frame) if lakota else None,
        "buy_prompt": vision.buy_prompt(frame),
        "delivered": vision.delivered(frame),
        "first_aid": vision.first_aid(frame),
        "damaged": vision.heli_damaged(frame) if lakota else None,
    }


def situation(row: dict, landed_agl: int, landed_speed: int) -> str:
    if row["first_aid"]:
        return "DEAD"
    if row["menu"]:
        return "BUY_MENU"
    if not row["lakota"]:
        return "NO_HELI"
    if row["damaged"]:
        return "DAMAGED"
    agl, speed = row["agl"], row["speed"]
    if agl is not None and speed is not None and agl <= landed_agl and speed <= landed_speed:
        return "LANDED_BASE" if row["buy_prompt"] else "LANDED"
    return "TO_ZONE" if row["crate"] else "TO_BASE"


def timeline(video: Path, config: dict, step: int) -> list[dict]:
    vision = Vision(config["vision"])
    region = config["game_region"]
    size = (region["width"], region["height"])
    flight = config["flight"]
    rows = []
    for index, t, frame in iter_frames(video, lambda index, t: index % step == 0):
        if (frame.shape[1], frame.shape[0]) != size:
            frame = cv2.resize(frame, size, interpolation=cv2.INTER_LINEAR)
        row = {"frame": index, "t": round(t, 3), **readings(vision, frame)}
        row["situation"] = situation(row, flight["landed_agl"], flight["landed_speed"])
        rows.append(row)
    return rows


def segments(rows: list[dict], min_rows: int = 1) -> list[tuple[float, float, str, int]]:
    result: list[tuple[float, float, str, int]] = []
    for row in rows:
        if result and result[-1][2] == row["situation"]:
            start, _, name, count = result[-1]
            result[-1] = (start, row["t"], name, count + 1)
        else:
            result.append((row["t"], row["t"], row["situation"], 1))
    merged: list[tuple[float, float, str, int]] = []
    for item in result:
        if merged and (item[3] < min_rows or merged[-1][2] == item[2]):
            start, _, name, count = merged[-1]
            merged[-1] = (start, item[1], name, count + item[3])
        else:
            merged.append(item)
    return merged


def drops(rows: list[dict], confirm: int) -> list[float]:
    times, loaded = [], None
    for index, row in enumerate(rows):
        recent = [r["crate"] for r in rows[max(0, index - confirm + 1) : index + 1]]
        crate = row["crate"]
        if crate is not None and recent.count(crate) == confirm:
            if loaded and not crate:
                times.append(row["t"])
            loaded = crate
    return times


def write_csv(rows: list[dict], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=COLUMNS)
        writer.writeheader()
        writer.writerows(rows)


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="python -m tools.replay")
    parser.add_argument("video", type=Path)
    parser.add_argument("--step", type=int, default=6, help="nur jedes n-te Frame prüfen")
    parser.add_argument("--min-rows", type=int, default=3, help="kürzere Abschnitte zusammenlegen")
    parser.add_argument("--out", type=Path)
    parser.add_argument("--config", default="config.yaml")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    config = load_config(args.config)
    rows = timeline(args.video, config, args.step)
    out = args.out or Path("debug") / "replay" / f"{args.video.parent.name}_{args.video.stem}.csv"
    write_csv(rows, out)
    for start, end, name, count in segments(rows, args.min_rows):
        print(f"{start:9.2f}s - {end:9.2f}s  {name:<12}  {count} Frames")
    dropped = drops(rows, config["vision"]["confirm"])
    print("Abwürfe bei:", ", ".join(f"{t:.1f}s" for t in dropped) or "keine")
    print(f"Timeline gespeichert: {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

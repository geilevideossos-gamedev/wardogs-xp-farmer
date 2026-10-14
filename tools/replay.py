import argparse
import csv
import sys
from dataclasses import fields
from pathlib import Path

import cv2

from heli_farmer.config import load_config
from heli_farmer.states import Detectors, Layer, classify, detect
from tools.video import iter_frames


def timeline(video: Path, region: dict, detectors: Detectors, step: int = 1) -> list[dict]:
    size = (region["width"], region["height"])
    rows = []
    for index, t, frame in iter_frames(video, lambda index, t: index % step == 0):
        if (frame.shape[1], frame.shape[0]) != size:
            frame = cv2.resize(frame, size, interpolation=cv2.INTER_LINEAR)
        results = detect(frame, detectors)
        rows.append({"frame": index, "t": round(t, 3), **results, "layer": classify(results).name})
    return rows


def segments(rows: list[dict]) -> list[tuple[float, float, str, int]]:
    result: list[tuple[float, float, str, int]] = []
    for row in rows:
        if result and result[-1][2] == row["layer"]:
            start, _, layer, count = result[-1]
            result[-1] = (start, row["t"], layer, count + 1)
        else:
            result.append((row["t"], row["t"], row["layer"], 1))
    return result


def write_csv(rows: list[dict], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    columns = ["frame", "t", *(field.name for field in fields(Detectors)), "layer"]
    with open(path, "w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="python -m tools.replay")
    parser.add_argument("video", type=Path)
    parser.add_argument("--step", type=int, default=1, help="nur jedes n-te Frame prüfen")
    parser.add_argument("--out", type=Path)
    parser.add_argument("--config", default="config.yaml")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    config = load_config(args.config)
    rows = timeline(args.video, config["game_region"], Detectors(), args.step)
    out = args.out or Path("debug") / "replay" / f"{args.video.parent.name}_{args.video.stem}.csv"
    write_csv(rows, out)
    width = max(len(layer.name) for layer in Layer)
    for start, end, layer, count in segments(rows):
        print(f"{start:9.2f}s - {end:9.2f}s  {layer:<{width}}  {count} Frames")
    print(f"Timeline gespeichert: {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

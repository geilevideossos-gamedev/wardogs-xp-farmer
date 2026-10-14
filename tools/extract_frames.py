import argparse
import sys
from collections.abc import Callable
from pathlib import Path

import cv2

from tools.video import iter_frames


def at_times(targets: list[float]) -> Callable[[int, float], bool]:
    pending = sorted(targets)

    def select(index: int, t: float) -> bool:
        if not pending or t < pending[0]:
            return False
        while pending and pending[0] <= t:
            pending.pop(0)
        return True

    return select


def every(seconds: float) -> Callable[[int, float], bool]:
    next_t = 0.0

    def select(index: int, t: float) -> bool:
        nonlocal next_t
        if t < next_t:
            return False
        while next_t <= t:
            next_t += seconds
        return True

    return select


def extract(
    video: Path,
    out_dir: Path,
    select: Callable[[int, float], bool],
    crop: tuple[int, int, int, int] | None = None,
) -> list[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    written = []
    for _, t, frame in iter_frames(video, select):
        if crop is not None:
            x, y, w, h = crop
            frame = frame[y : y + h, x : x + w]
        path = out_dir / f"t{t:09.3f}.png"
        cv2.imwrite(str(path), frame)
        written.append(path)
    return written


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="python -m tools.extract_frames")
    parser.add_argument("video", type=Path)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--at", type=float, nargs="+", metavar="SEKUNDE")
    mode.add_argument("--every", type=float, metavar="SEKUNDEN")
    parser.add_argument("--crop", type=int, nargs=4, metavar=("X", "Y", "BREITE", "HOEHE"))
    parser.add_argument("--out", type=Path)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    out_dir = args.out or Path("debug") / "frames" / f"{args.video.parent.name}_{args.video.stem}"
    select = at_times(args.at) if args.at else every(args.every)
    written = extract(args.video, out_dir, select, tuple(args.crop) if args.crop else None)
    print(f"{len(written)} Bilder gespeichert in {out_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

import csv
from collections.abc import Callable, Iterator
from pathlib import Path

import cv2
import numpy as np


def recorded_times(video: Path) -> list[float] | None:
    frames_csv = video.with_name("frames.csv")
    if not frames_csv.exists():
        return None
    with open(frames_csv, newline="", encoding="utf-8") as file:
        return [float(row["t"]) for row in csv.DictReader(file)]


def iter_frames(
    video: Path, select: Callable[[int, float], bool] = lambda index, t: True
) -> Iterator[tuple[int, float, np.ndarray]]:
    times = recorded_times(video)
    capture = cv2.VideoCapture(str(video))
    if not capture.isOpened():
        raise FileNotFoundError(f"Video nicht lesbar: {video}")
    try:
        index = 0
        while capture.grab():
            if times is not None and index < len(times):
                t = times[index]
            else:
                t = capture.get(cv2.CAP_PROP_POS_MSEC) / 1000
            if select(index, t):
                ok, frame = capture.retrieve()
                if ok:
                    yield index, t, frame
            index += 1
    finally:
        capture.release()

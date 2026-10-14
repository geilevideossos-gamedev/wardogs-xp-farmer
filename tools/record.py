import argparse
import csv
import json
import logging
import multiprocessing as mp
import queue
import sys
import threading
import time
from datetime import datetime
from pathlib import Path

import cv2
from pynput import keyboard, mouse

from heli_farmer.capture import REGION_KEYS, ScreenCapture
from heli_farmer.config import load_config
from heli_farmer.killswitch import key_name
from heli_farmer.logs import setup_logging

log = logging.getLogger("record")

SEQUENCES = (
    "join",
    "team",
    "buy_heli",
    "board",
    "buy_crate",
    "fly_to_zone",
    "drop",
    "fly_to_base",
    "land",
    "full_loop",
    "death",
)
QUEUE_SECONDS = 2
STOP_JOIN_TIMEOUT_S = 15


def video_size(region: dict, scale: float) -> tuple[int, int]:
    return round(region["width"] * scale) // 2 * 2, round(region["height"] * scale) // 2 * 2


def _capture_frames(capture_cls, region, fps, t0, stop, frames: queue.Queue) -> None:
    capture = capture_cls(region)
    interval = 1 / fps
    next_t = time.perf_counter() - t0
    try:
        while not stop.is_set():
            t = time.perf_counter() - t0
            frame = capture.grab()
            try:
                frames.put_nowait((t, frame))
            except queue.Full:
                pass
            next_t = max(next_t + interval, time.perf_counter() - t0)
            stop.wait(max(0.0, next_t - (time.perf_counter() - t0)))
    finally:
        capture.close()
        frames.put(None)


def record_video(
    out_dir: Path,
    region: dict,
    fps: float,
    scale: float,
    t0: float,
    stop,
    capture_cls=ScreenCapture,
) -> None:
    size = video_size(region, scale)
    writer = cv2.VideoWriter(str(out_dir / "video.mp4"), cv2.VideoWriter_fourcc(*"mp4v"), fps, size)
    if not writer.isOpened():
        raise RuntimeError("VideoWriter konnte nicht geöffnet werden")
    frames: queue.Queue = queue.Queue(maxsize=max(1, int(fps * QUEUE_SECONDS)))
    capture_thread = threading.Thread(
        target=_capture_frames, args=(capture_cls, region, fps, t0, stop, frames), daemon=True
    )
    capture_thread.start()
    with open(out_dir / "frames.csv", "w", newline="", encoding="utf-8") as csv_file:
        rows = csv.writer(csv_file)
        rows.writerow(["frame", "t"])
        index = 0
        while (item := frames.get()) is not None:
            t, frame = item
            if (frame.shape[1], frame.shape[0]) != size:
                frame = cv2.resize(frame, size, interpolation=cv2.INTER_AREA)
            writer.write(frame)
            rows.writerow([index, f"{t:.4f}"])
            index += 1
    writer.release()
    capture_thread.join()


class Recorder:
    def __init__(
        self, out_dir: Path, region: dict, fps: float, scale: float, capture_cls=ScreenCapture
    ):
        self.out_dir = out_dir
        self._region = {key: region[key] for key in REGION_KEYS}
        self._fps = fps
        self._scale = scale
        self._capture_cls = capture_cls
        self._lock = threading.Lock()
        self._inputs = None
        self._t0 = 0.0
        self._stop = mp.Event()
        self._process: mp.Process | None = None

    def start(self) -> None:
        self.out_dir.mkdir(parents=True)
        meta = {
            "region": self._region,
            "fps": self._fps,
            "scale": self._scale,
            "video_size": video_size(self._region, self._scale),
            "started": datetime.now().isoformat(timespec="seconds"),
            "clock": "perf_counter seit Start, Sekunden",
        }
        (self.out_dir / "meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
        self._inputs = open(self.out_dir / "inputs.jsonl", "w", encoding="utf-8")
        self._t0 = time.perf_counter()
        self._process = mp.Process(
            target=record_video,
            args=(
                self.out_dir,
                self._region,
                self._fps,
                self._scale,
                self._t0,
                self._stop,
                self._capture_cls,
            ),
            daemon=True,
        )
        self._process.start()

    def log_input(self, **event) -> None:
        with self._lock:
            if self._inputs is None or self._inputs.closed:
                return
            t = time.perf_counter() - self._t0
            self._inputs.write(json.dumps({"t": round(t, 4), **event}) + "\n")

    def stop(self) -> bool:
        self._stop.set()
        self._process.join(STOP_JOIN_TIMEOUT_S)
        with self._lock:
            self._inputs.close()
        if self._process.is_alive():
            self._process.kill()
        return self._process.exitcode == 0


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="python -m tools.record")
    parser.add_argument("--map", required=True)
    parser.add_argument("--seq", required=True, choices=SEQUENCES)
    parser.add_argument("--config", default="config.yaml")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    config = load_config(args.config)
    setup_logging(config["logging"]["root"], config["logging"]["level"], "record")
    settings = config["recording"]
    record_key = config["keys"]["record"]
    stop_key = config["keys"]["stop"]
    toggle = threading.Event()
    quit_requested = threading.Event()
    held: set[str] = set()
    recorder: Recorder | None = None

    def emit(**event) -> None:
        current = recorder
        if current is not None:
            current.log_input(**event)

    def on_press(key) -> None:
        if key is None:
            return
        name = key_name(key)
        if name == record_key:
            toggle.set()
        elif name == stop_key:
            quit_requested.set()
            toggle.set()
        elif name not in held:
            held.add(name)
            emit(type="key", key=name, action="down")

    def on_release(key) -> None:
        if key is None:
            return
        name = key_name(key)
        if name in held:
            held.discard(name)
            emit(type="key", key=name, action="up")

    def on_click(x, y, button, pressed) -> None:
        emit(type="button", button=button.name, action="down" if pressed else "up", x=x, y=y)

    listeners = [
        keyboard.Listener(on_press=on_press, on_release=on_release),
        mouse.Listener(on_move=lambda x, y: emit(type="move", x=x, y=y), on_click=on_click),
    ]
    for listener in listeners:
        listener.start()
    log.info(
        "Bereit: %s startet/stoppt eine Aufnahme, %s beendet", record_key.upper(), stop_key.upper()
    )
    ok = True
    try:
        while not quit_requested.is_set() or recorder is not None:
            if not toggle.wait(0.5):
                continue
            toggle.clear()
            if recorder is not None:
                ok = recorder.stop() and ok
                log.info("Aufnahme gespeichert: %s", recorder.out_dir)
                recorder = None
            elif not quit_requested.is_set():
                stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                out_dir = Path(settings["root"]) / args.map / f"{args.seq}_{stamp}"
                recorder = Recorder(
                    out_dir, config["game_region"], settings["fps"], settings["scale"]
                )
                recorder.start()
                log.info("Aufnahme läuft: %s", out_dir)
    finally:
        if recorder is not None:
            ok = recorder.stop() and ok
            log.info("Aufnahme gespeichert: %s", recorder.out_dir)
        for listener in listeners:
            listener.stop()
    if not ok:
        log.error("Mindestens ein Video wurde nicht sauber geschrieben, siehe Log")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())

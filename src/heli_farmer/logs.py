import logging
import re
from datetime import datetime
from pathlib import Path

import cv2
import numpy as np

log = logging.getLogger(__name__)


def setup_logging(root: str | Path, level: str, name: str) -> Path:
    now = datetime.now()
    run_dir = Path(root) / now.strftime("%Y-%m-%d")
    run_dir.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=level,
        format="%(asctime)s.%(msecs)03d %(levelname)s %(name)s: %(message)s",
        datefmt="%H:%M:%S",
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler(run_dir / f"{name}_{now:%H%M%S}.log", encoding="utf-8"),
        ],
        force=True,
    )
    return run_dir


def save_debug_screenshot(run_dir: Path, frame: np.ndarray, reason: str) -> Path:
    slug = re.sub(r"[^a-z0-9]+", "_", reason.lower()).strip("_")
    path = run_dir / "screenshots" / f"{datetime.now():%H%M%S_%f}_{slug}.png"
    path.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(path), frame)
    log.warning("Debug-Screenshot gespeichert: %s", path)
    return path

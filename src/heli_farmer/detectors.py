from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np

Detection = bool | None
TOPHAT_KERNEL = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5))


def on_server(frame: np.ndarray) -> Detection:
    return None


def in_team_blue(frame: np.ndarray) -> Detection:
    return None


def has_heli(frame: np.ndarray) -> Detection:
    return None


@dataclass(frozen=True)
class Marker:
    x: int
    y: int
    score: float


def read_template(path: Path) -> np.ndarray:
    image = cv2.imread(str(path), cv2.IMREAD_UNCHANGED)
    if image is None:
        raise FileNotFoundError(f"Template fehlt: {path}")
    if image.ndim == 2:
        return image.astype(np.float32)
    gray = cv2.cvtColor(image[..., :3], cv2.COLOR_BGR2GRAY).astype(np.float32)
    if image.shape[2] == 4:
        inside = image[..., 3] > 0
        gray[~inside] = gray[inside].mean()
    return gray


def best_match(gray: np.ndarray, template: np.ndarray) -> tuple[float, int, int]:
    result = np.nan_to_num(cv2.matchTemplate(gray, template, cv2.TM_CCOEFF_NORMED))
    _, score, _, (x, y) = cv2.minMaxLoc(result)
    return float(score), x, y


class Vision:
    def __init__(self, config: dict):
        self._config = config
        root = Path(config["assets"])
        self._templates = {
            name: read_template(root / spec["template"])
            for name, spec in config.items()
            if isinstance(spec, dict) and "template" in spec and name != "digits"
        }
        sheet = read_template(root / config["digits"]["template"])
        width = sheet.shape[1] // 10
        glyphs = [sheet[:, i * width : (i + 1) * width].ravel() for i in range(10)]
        self._digits = np.array([g / np.linalg.norm(g) for g in glyphs])
        self._digit_shape = (sheet.shape[0], width)

    def score(self, frame: np.ndarray, name: str) -> float:
        spec = self._config[name]
        template = self._templates[name]
        height, width = template.shape
        x, y, pad = spec["x"], spec["y"], spec["search"]
        roi = frame[max(0, y - pad) : y + height + pad, max(0, x - pad) : x + width + pad]
        return best_match(cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY).astype(np.float32), template)[0]

    def seen(self, frame: np.ndarray, name: str) -> bool:
        return self.score(frame, name) >= self._config[name]["min_score"]

    def in_lakota(self, frame: np.ndarray) -> bool:
        return self.seen(frame, "lakota")

    def crate_loaded(self, frame: np.ndarray) -> bool:
        return self.seen(frame, "crate")

    def buy_prompt(self, frame: np.ndarray) -> bool:
        return self.seen(frame, "buy_prompt")

    def delivered(self, frame: np.ndarray) -> bool:
        return self.seen(frame, "delivered")

    def first_aid(self, frame: np.ndarray) -> bool:
        return self.seen(frame, "first_aid")

    def garage_menu(self, frame: np.ndarray) -> str | None:
        if self.seen(frame, "menu_logistics"):
            return "logistics"
        if self.seen(frame, "menu_main"):
            return "main"
        return None

    def has_heli(self, frame: np.ndarray) -> Detection:
        if self.first_aid(frame):
            return False
        if self.garage_menu(frame) is not None:
            return True
        if self.in_lakota(frame):
            return not self.heli_damaged(frame)
        return None

    def heli_damaged(self, frame: np.ndarray) -> bool:
        spec = self._config["damage"]
        x, y, width, height = spec["region"]
        patch = frame[y : y + height, x : x + width].astype(np.int16)
        red = np.median(patch[..., 2] - np.maximum(patch[..., 0], patch[..., 1]))
        return bool(red >= spec["min_red"])

    def speed(self, frame: np.ndarray) -> int | None:
        return self._number(frame, self._config["speed"])

    def agl(self, frame: np.ndarray) -> int | None:
        return self._number(frame, self._config["agl"])

    def zone_marker(self, frame: np.ndarray) -> Marker | None:
        return self._marker(frame, "zone_marker")

    def hq_marker(self, frame: np.ndarray) -> Marker | None:
        return self._marker(frame, "hq_marker")

    def _marker(self, frame: np.ndarray, name: str) -> Marker | None:
        spec = self._config[name]
        top, bottom = spec["band"]
        gray = cv2.cvtColor(frame[top:bottom], cv2.COLOR_BGR2GRAY).astype(np.float32)
        score, x, y = best_match(gray, self._templates[name])
        if score < spec["min_score"]:
            return None
        anchor_x, anchor_y = spec["anchor"]
        return Marker(x + anchor_x, y + top + anchor_y, round(score, 3))

    def _number(self, frame: np.ndarray, field: dict) -> int | None:
        spec = self._config["digits"]
        height, width = self._digit_shape
        half = width // 2
        right, top, slots = round(field["right"]), field["top"], field["slots"]
        left = right - (width + 1) * slots - spec["search"] - width
        gray = cv2.cvtColor(
            frame[top - 3 : top + height + 3, left - 3 : right + width + 3], cv2.COLOR_BGR2GRAY
        )
        tophat = cv2.morphologyEx(gray, cv2.MORPH_TOPHAT, TOPHAT_KERNEL)[3:-3, 3:-3]
        tophat = tophat.astype(np.float32)
        ink = (tophat[2:-2] > spec["tophat"]).sum(axis=0)
        position = right - left
        candidates = range(position - spec["search"], position + spec["search"] + 1)
        digits = ""
        for slot in range(slots):
            if slot:
                if ink[max(0, position - width - 2) : position - half].sum() < spec["min_ink"]:
                    break
                candidates = range(position - width - 1, position - half)
            score, digit, position = self._classify(tophat, candidates, half)
            if score < spec["min_score"]:
                return None
            digits = str(digit) + digits
        return int(digits) if digits else None

    def _classify(self, tophat: np.ndarray, centers: range, half: int) -> tuple[float, int, int]:
        best = (-1.0, 0, centers[0])
        for center in centers:
            window = tophat[:, center - half : center + half + 1]
            if window.shape[1] != 2 * half + 1:
                continue
            vector = window.ravel() / (np.linalg.norm(window) + 1e-6)
            scores = self._digits @ vector
            digit = int(scores.argmax())
            if scores[digit] > best[0]:
                best = (float(scores[digit]), digit, center)
        return best

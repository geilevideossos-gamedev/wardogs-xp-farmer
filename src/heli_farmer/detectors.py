from dataclasses import dataclass, replace
from pathlib import Path

import cv2
import numpy as np

Detection = bool | None
TOPHAT_KERNEL = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5))


def on_server(frame: np.ndarray) -> Detection:
    return None


def in_team_blue(frame: np.ndarray) -> Detection:
    return None


@dataclass(frozen=True)
class Marker:
    x: int
    y: int
    score: float
    kind: str = ""
    distance: int | None = None


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
            if isinstance(spec, dict) and "template" in spec and name not in ("digits", "distance")
        }
        self._hz = read_template(root / config["zone_marker"]["hz_template"])
        sheet = read_template(root / config["digits"]["template"])
        width = sheet.shape[1] // 10
        glyphs = [sheet[:, i * width : (i + 1) * width].ravel() for i in range(10)]
        self._digits = np.array([g / np.linalg.norm(g) for g in glyphs])
        self._digit_shape = (sheet.shape[0], width)
        distance = config["distance"]
        sheet = read_template(root / distance["template"])
        edges = np.cumsum([0, *distance["widths"]])
        self._glyphs = {
            char: sheet[:, edges[i] : edges[i + 1]] for i, char in enumerate(distance["glyphs"])
        }
        minimap = config["minimap"]
        inner, outer = minimap["ring"]
        yy, xx = np.mgrid[-outer : outer + 1, -outer : outer + 1]
        self._ring = (np.hypot(xx, yy) >= inner) & (np.hypot(xx, yy) <= outer)

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

    def round_over(self, frame: np.ndarray) -> bool:
        return self.seen(frame, "round_over")

    def slots_full(self, frame: np.ndarray) -> bool:
        return self.seen(frame, "slots_full")

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

    def asl(self, frame: np.ndarray) -> int | None:
        return self._number(frame, self._config["asl"])

    def zone_marker(self, frame: np.ndarray) -> Marker | None:
        marker = self._marker(frame, "zone_marker")
        if marker is None:
            return None
        return replace(
            marker, kind=self._zone_kind(frame, marker), distance=self._distance(frame, marker)
        )

    def hq_marker(self, frame: np.ndarray) -> Marker | None:
        return self._marker(frame, "hq_marker")

    def minimap_in_zone(self, frame: np.ndarray) -> bool:
        spec = self._config["minimap"]
        x, y = spec["center"]
        outer = spec["ring"][1]
        patch = frame[y - outer : y + outer + 1, x - outer : x + outer + 1]
        median = np.median(patch[self._ring], axis=0)
        return bool(median.max() - median.min() >= spec["min_chroma"])

    def _zone_kind(self, frame: np.ndarray, marker: Marker) -> str:
        spec = self._config["zone_marker"]
        x, y, width, height = spec["letter"]
        left = marker.x - spec["anchor"][0] + x
        top = marker.y - spec["anchor"][1] + y
        roi = frame[top : top + height, left : left + width]
        if roi.shape[:2] != (height, width):
            return "CZ"
        gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY).astype(np.float32)
        letters = (slice(y, y + height), slice(x, x + width))
        hz = best_match(gray, self._hz[letters])[0]
        cz = best_match(gray, self._templates["zone_marker"][letters])[0]
        return "HZ" if hz > cz else "CZ"

    def _distance(self, frame: np.ndarray, marker: Marker) -> int | None:
        spec = self._config["distance"]
        dx, dy, width, height = spec["strip"]
        roi = frame[marker.y + dy : marker.y + dy + height, marker.x + dx : marker.x + dx + width]
        if marker.x + dx < 0 or roi.shape[:2] != (height, width):
            return None
        gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY).astype(np.float32)
        maps = {
            c: cv2.matchTemplate(gray, t, cv2.TM_CCOEFF_NORMED) for c, t in self._glyphs.items()
        }
        best = (-np.inf, "", 0.0)
        for layout in spec["formats"]:
            for shift in range(-spec["shift"], spec["shift"] + 1):
                read = self._read_layout(maps, layout, -dx + shift)
                if read[0] > best[0]:
                    best = read
        _, text, weakest = best
        if not text or weakest < spec["min_score"]:
            return None
        return round(float(text[:-2]) * 1000) if text.endswith("km") else int(text[:-1])

    def _read_layout(self, maps: dict, layout: str, center: int) -> tuple[float, str, float]:
        spec = self._config["distance"]
        advance = spec["advance"]
        x = center - sum(advance[c] for c in layout) / 2
        gain, text, weakest = 0.0, "", 1.0
        for slot in layout:
            if slot != " ":
                chars = "0123456789" if slot == "d" else slot
                lo, hi = max(0, round(x) - spec["slack"]), round(x) + spec["slack"] + 1
                score, char = max((float(maps[c][:, lo:hi].max(initial=-1.0)), c) for c in chars)
                gain += score - spec["min_gain"]
                text += char
                weakest = min(weakest, score)
            x += advance[slot]
        return gain, text, weakest

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

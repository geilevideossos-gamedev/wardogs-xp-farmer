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
        radii = np.arange(minimap["heli_radii"][0], minimap["heli_radii"][1] + 1)
        angles = np.radians(np.arange(0, 360, minimap["heli_step_deg"]))
        self._polar_dx = (radii[:, None] * np.sin(angles)).astype(np.float32)
        self._polar_dy = (-radii[:, None] * np.cos(angles)).astype(np.float32)
        heli = self._blue(self._read_color(root / minimap["heli_template"])).astype(np.float32)
        height, width = heli.shape
        profile = self._polar(heli, [(width - 1) / 2], [(height - 1) / 2])[0]
        profile -= profile.mean(axis=1, keepdims=True)
        self._heli_spectrum = np.conj(np.fft.rfft(profile / np.linalg.norm(profile), axis=1))
        self._hq = self._hq_features(self._read_color(root / minimap["hq_template"]))
        foot = minimap["foot_radius"]
        yy, xx = np.mgrid[-foot : foot + 1, -foot : foot + 1]
        self._foot_disk = np.hypot(xx, yy) <= foot
        self._refine = np.stack(np.meshgrid([-1, 0, 1], [-1, 0, 1]), axis=-1).reshape(-1, 2)
        roll = config["roll"]
        self._roll_angles = np.arange(-roll["max_deg"], roll["max_deg"] + 1)
        radii = np.arange(roll["radius"][0], roll["radius"][1] + 1)
        angles = np.radians(self._roll_angles)[:, None]
        self._roll_dx = np.rint(radii * np.cos(angles)).astype(int)
        self._roll_dy = np.rint(radii * np.sin(angles)).astype(int)

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
        strip = self._config["distance"]["strip"]
        distance = self._distance(frame, marker, strip, centered=True)
        return replace(marker, kind=self._zone_kind(frame, marker), distance=distance)

    def hq_marker(self, frame: np.ndarray) -> Marker | None:
        marker = self._marker(frame, "hq_marker")
        if marker is None:
            return None
        strip = self._config["hq_marker"]["distance_strip"]
        return replace(marker, distance=self._distance(frame, marker, strip, centered=False))

    def roll(self, frame: np.ndarray) -> int | None:
        spec = self._config["roll"]
        x, y = spec["center"]
        r = spec["radius"][1] + 3
        patch = cv2.cvtColor(frame[y - r : y + r + 1, x - r : x + r + 1], cv2.COLOR_BGR2GRAY)
        tophat = cv2.morphologyEx(patch, cv2.MORPH_TOPHAT, TOPHAT_KERNEL).astype(np.float32)
        right = tophat[r + self._roll_dy, r + self._roll_dx].mean(axis=1)
        left = tophat[r - self._roll_dy, r - self._roll_dx].mean(axis=1)
        score = np.minimum(left, right)
        best = int(score.argmax())
        if score[best] < spec["min_score"]:
            return None
        return int(self._roll_angles[best])

    def minimap_in_zone(self, frame: np.ndarray) -> bool:
        return self._minimap_chroma(frame) >= self._config["minimap"]["min_chroma"]

    def minimap_over_base(self, frame: np.ndarray) -> bool:
        return self._minimap_chroma(frame) >= self._config["minimap"]["base_chroma"]

    def minimap_heading(self, frame: np.ndarray) -> float | None:
        if self._on_foot(frame):
            return None
        own = self._own_heli(self._heli_detections(frame))
        return None if own is None else own[3]

    def minimap_position(self, frame: np.ndarray) -> tuple[float, float] | None:
        if self._on_foot(frame):
            return None
        own = self._own_heli(self._heli_detections(frame))
        if own is None:
            return None
        cx, cy = self._minimap_center()
        return own[1] - cx, own[2] - cy

    def minimap_helis(self, frame: np.ndarray) -> list[tuple[float, float]]:
        spec = self._config["minimap"]
        detections = self._heli_detections(frame)
        own = None if self._on_foot(frame) else self._own_heli(detections)
        kept: list[tuple[float, float, float, float]] = []
        for detection in sorted(detections, key=lambda d: -d[0]):
            if all(
                np.hypot(detection[1] - k[1], detection[2] - k[2]) >= spec["heli_separation"]
                for k in kept + ([own] if own else [])
            ):
                kept.append(detection)
        cx, cy = self._minimap_center()
        return [(x - cx, y - cy) for _, x, y, _ in kept]

    def minimap_hq(self, frame: np.ndarray) -> tuple[float, float] | None:
        spec = self._config["minimap"]
        x, y, width, height = spec["region"]
        features = self._hq_features(frame[y : y + height, x : x + width])
        scores = np.nan_to_num(cv2.matchTemplate(features, self._hq, cv2.TM_CCOEFF_NORMED))
        th, tw = self._hq.shape[:2]
        blue = features[..., 0].astype(np.float32)
        mean = cv2.blur(blue, (tw, th))
        std = np.sqrt(np.maximum(cv2.blur(blue * blue, (tw, th)) - mean * mean, 0))
        std = std[th // 2 : th // 2 + scores.shape[0], tw // 2 : tw // 2 + scores.shape[1]]
        scores[std < spec["hq_min_std"]] = -1
        _, score, _, (left, top) = cv2.minMaxLoc(scores)
        if score < spec["hq_min_score"]:
            return None
        cx, cy = self._minimap_center()
        return left + (tw - 1) / 2 - cx, top + (th - 1) / 2 - cy

    def _minimap_center(self) -> tuple[int, int]:
        spec = self._config["minimap"]
        return spec["center"][0] - spec["region"][0], spec["center"][1] - spec["region"][1]

    def _on_foot(self, frame: np.ndarray) -> bool:
        spec = self._config["minimap"]
        x, y = spec["center"]
        r = spec["foot_radius"]
        patch = frame[y - r : y + r + 1, x - r : x + r + 1].min(axis=2)
        return int((patch[self._foot_disk] >= spec["foot_white"]).sum()) >= spec["foot_pixels"]

    def _own_heli(self, detections: list) -> tuple | None:
        spec = self._config["minimap"]
        cx, cy = self._minimap_center()
        near = [d for d in detections if np.hypot(d[1] - cx, d[2] - cy) <= spec["heli_window"]]
        return max(near, default=None)

    def _heli_detections(self, frame: np.ndarray) -> list[tuple[float, float, float, float]]:
        spec = self._config["minimap"]
        x, y, width, height = spec["region"]
        roi = frame[y : y + height, x : x + width]
        blue = self._blue(roi)
        body = cv2.blur(blue, (5, 5))
        peaks = (body >= cv2.dilate(body, TOPHAT_KERNEL)) & (body >= spec["heli_body_min"])
        count, _, _, centers = cv2.connectedComponentsWithStats(peaks.astype(np.uint8))
        if count < 2:
            return []
        gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY).astype(np.float32)
        features = gray + blue.astype(np.float32)
        points = np.rint(centers[1:])[:, None, :] + self._refine
        profiles = self._polar(features, points[..., 0].ravel(), points[..., 1].ravel())
        profiles -= profiles.mean(axis=2, keepdims=True)
        norm = np.linalg.norm(profiles, axis=(1, 2))[:, None] + 1e-6
        spectrum = np.fft.rfft(profiles, axis=2) * self._heli_spectrum
        scores = np.fft.irfft(spectrum, n=profiles.shape[2], axis=2).sum(axis=1) / norm
        scores = scores.reshape(len(points), -1)
        detections = []
        for index, flat in enumerate(scores.argmax(axis=1)):
            score = float(scores[index, flat])
            if score >= spec["heli_min_score"]:
                offset, shift = divmod(int(flat), profiles.shape[2])
                px, py = points[index, offset]
                heading = float(shift * spec["heli_step_deg"])
                detections.append((score, float(px), float(py), heading))
        return detections

    def _polar(self, image: np.ndarray, xs: np.ndarray, ys: np.ndarray) -> np.ndarray:
        xs = np.asarray(xs, np.float32).reshape(-1, 1, 1)
        ys = np.asarray(ys, np.float32).reshape(-1, 1, 1)
        angles = self._polar_dx.shape[1]
        map_x = (xs + self._polar_dx).reshape(-1, angles)
        map_y = (ys + self._polar_dy).reshape(-1, angles)
        sampled = cv2.remap(image, map_x, map_y, cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT)
        return sampled.reshape(len(xs), -1, angles)

    def _hq_features(self, image: np.ndarray) -> np.ndarray:
        b, g, r = cv2.split(image)
        dark = cv2.subtract(self._config["minimap"]["hq_dark"], cv2.max(cv2.max(b, g), r))
        return cv2.merge([cv2.subtract(b, r), cv2.add(dark, dark)])

    @staticmethod
    def _blue(image: np.ndarray) -> np.ndarray:
        b, _, r = cv2.split(image)
        return cv2.subtract(b, r)

    @staticmethod
    def _read_color(path: Path) -> np.ndarray:
        image = cv2.imread(str(path))
        if image is None:
            raise FileNotFoundError(f"Template fehlt: {path}")
        return image

    def _minimap_chroma(self, frame: np.ndarray) -> float:
        spec = self._config["minimap"]
        x, y = spec["center"]
        outer = spec["ring"][1]
        patch = frame[y - outer : y + outer + 1, x - outer : x + outer + 1]
        median = np.median(patch[self._ring], axis=0)
        return float(median.max() - median.min())

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

    def _distance(
        self, frame: np.ndarray, marker: Marker, strip: list[int], centered: bool
    ) -> int | None:
        spec = self._config["distance"]
        dx, dy, width, height = strip
        roi = frame[marker.y + dy : marker.y + dy + height, marker.x + dx : marker.x + dx + width]
        if marker.x + dx < 0 or roi.shape[:2] != (height, width):
            return None
        gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY).astype(np.float32)
        maps = {
            c: cv2.matchTemplate(gray, t, cv2.TM_CCOEFF_NORMED) for c, t in self._glyphs.items()
        }
        best = (-np.inf, "", 0.0)
        for layout in spec["formats"]:
            span = sum(spec["advance"][c] for c in layout)
            start = -dx - span / 2 if centered else 0
            for shift in range(-spec["shift"], spec["shift"] + 1):
                read = self._read_layout(maps, layout, start + shift)
                if read[0] > best[0]:
                    best = read
        _, text, weakest = best
        if not text or weakest < spec["min_score"]:
            return None
        return round(float(text[:-2]) * 1000) if text.endswith("km") else int(text[:-1])

    def _read_layout(self, maps: dict, layout: str, x: float) -> tuple[float, str, float]:
        spec = self._config["distance"]
        advance = spec["advance"]
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

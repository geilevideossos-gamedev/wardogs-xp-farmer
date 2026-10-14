import cv2
import mss
import numpy as np

REGION_KEYS = ("left", "top", "width", "height")


class ScreenCapture:
    def __init__(self, region: dict):
        self._region = {key: region[key] for key in REGION_KEYS}
        self._sct = mss.MSS()

    def grab(self) -> np.ndarray:
        return cv2.cvtColor(np.asarray(self._sct.grab(self._region)), cv2.COLOR_BGRA2BGR)

    def close(self) -> None:
        self._sct.close()

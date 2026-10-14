import numpy as np

Detection = bool | None


def on_server(frame: np.ndarray) -> Detection:
    return None


def in_team_blue(frame: np.ndarray) -> Detection:
    return None


def has_heli(frame: np.ndarray) -> Detection:
    return None

import ctypes

TITLE_LENGTH = 256


def foreground_title() -> str:
    user32 = ctypes.windll.user32
    buffer = ctypes.create_unicode_buffer(TITLE_LENGTH)
    user32.GetWindowTextW(user32.GetForegroundWindow(), buffer, TITLE_LENGTH)
    return buffer.value


def is_foreground(title: str) -> bool:
    return foreground_title().strip().lower() == title.lower()

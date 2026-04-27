"""Estado global do agente (pause/resume)."""

_paused: bool = False


def is_paused() -> bool:
    return _paused


def set_paused(value: bool) -> None:
    global _paused
    _paused = value


def toggle() -> bool:
    global _paused
    _paused = not _paused
    return _paused

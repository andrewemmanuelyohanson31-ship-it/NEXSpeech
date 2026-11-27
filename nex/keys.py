"""Press slide keys in the focused presentation app (PowerPoint, Google Slides, Canva)."""
import os

from .profiles import PROFILES, DEFAULT_PROFILE

DRY_RUN = os.environ.get("NEX_DRY_RUN") == "1"  # log actions without pressing keys (tests, demos)
_kb = None


def _keyboard():
    global _kb
    if _kb is None:
        from pynput.keyboard import Controller  # macOS: needs Accessibility permission

        _kb = Controller()
    return _kb


def send(action, current=None, jump_mode="number"):
    """jump_mode="number" types N + Enter (PowerPoint/Google Slides);
    "arrows" presses → / ← |N - current| times (fallback for apps without number jump)."""
    kind, n = action
    if DRY_RUN:
        return
    from pynput.keyboard import Key

    kb = _keyboard()
    if kind == "next":
        kb.tap(Key.right)
    elif kind == "prev":
        kb.tap(Key.left)
    elif kind == "goto" and jump_mode == "arrows" and current:
        key = Key.right if n > current else Key.left
        for _ in range(abs(n - current)):
            kb.tap(key)
    elif kind == "goto":
        kb.type(str(n))
        kb.tap(Key.enter)


def send_shortcut(shortcut_id, profile_name=DEFAULT_PROFILE):
    """Press the shortcut key for the given profile. Respects DRY_RUN."""
    if DRY_RUN:
        return
    from pynput.keyboard import Key

    profile = PROFILES.get(profile_name, PROFILES[DEFAULT_PROFILE])
    sc = profile["shortcuts"].get(shortcut_id)
    if not sc:
        return

    kb = _keyboard()
    key_str = sc["key"]

    if "+" in key_str:
        # Modifier combo, e.g. "ctrl+l"
        parts = key_str.split("+")
        modifier = getattr(Key, parts[0] + "_l", getattr(Key, parts[0], None))
        char = parts[1]
        if modifier:
            with kb.pressed(modifier):
                kb.tap(char)
    elif key_str == "escape":
        kb.tap(Key.escape)
    else:
        kb.tap(key_str)

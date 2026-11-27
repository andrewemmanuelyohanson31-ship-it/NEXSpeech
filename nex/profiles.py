"""App profiles: each presentation app's jump mode, shortcuts, and voice triggers."""
import copy

PROFILES = {
    "canva": {
        "label": "Canva",
        "jump_mode": "arrows",
        "shortcuts": {
            "blackout": {
                "label": "Layar hitam",
                "key": "b",
                "triggers": ["layar hitam", "black screen", "blackout"],
                "enabled": True,
            },
            "exit": {
                "label": "Keluar presentasi",
                "key": "escape",
                "triggers": ["keluar presentasi", "exit present", "keluar"],
                "enabled": True,
            },
        },
    },
    "powerpoint": {
        "label": "PowerPoint",
        "jump_mode": "number",
        "shortcuts": {
            "blackout": {
                "label": "Layar hitam",
                "key": "b",
                "triggers": ["layar hitam", "black screen", "blackout"],
                "enabled": True,
            },
            "whiteout": {
                "label": "Layar putih",
                "key": "w",
                "triggers": ["layar putih", "white screen", "whiteout"],
                "enabled": True,
            },
            "laser": {
                "label": "Laser pointer",
                "key": "ctrl+l",
                "triggers": ["laser", "laser pointer"],
                "enabled": True,
            },
            "pen": {
                "label": "Pena / Ink",
                "key": "ctrl+p",
                "triggers": ["pena", "pen", "ink"],
                "enabled": True,
            },
            "exit": {
                "label": "Keluar slideshow",
                "key": "escape",
                "triggers": ["keluar presentasi", "exit slideshow", "keluar"],
                "enabled": True,
            },
        },
    },
    "google_slides": {
        "label": "Google Slides",
        "jump_mode": "number",
        "shortcuts": {
            "blackout": {
                "label": "Layar hitam",
                "key": "b",
                "triggers": ["layar hitam", "black screen", "blackout"],
                "enabled": True,
            },
            "whiteout": {
                "label": "Layar putih",
                "key": "w",
                "triggers": ["layar putih", "white screen", "whiteout"],
                "enabled": True,
            },
            "exit": {
                "label": "Keluar presentasi",
                "key": "escape",
                "triggers": ["keluar presentasi", "exit presentation", "keluar"],
                "enabled": True,
            },
        },
    },
}

DEFAULT_PROFILE = "powerpoint"


def get_profile(name):
    """Return a deep copy of the named profile with its defaults."""
    return copy.deepcopy(PROFILES.get(name, PROFILES[DEFAULT_PROFILE]))


def shortcut_triggers(profile_name, disabled_shortcuts=()):
    """Return {trigger_phrase: shortcut_id} for all enabled shortcuts in a profile."""
    p = PROFILES.get(profile_name, PROFILES[DEFAULT_PROFILE])
    result = {}
    for sid, sc in p["shortcuts"].items():
        if sid in disabled_shortcuts or not sc["enabled"]:
            continue
        for t in sc["triggers"]:
            result[t] = sid
    return result

import pytest

from nex.commands import parse

CASES = {
    # next
    "Next.": ("next", None), "lanjut": ("next", None), "Oke, lanjut!": ("next", None),
    "next slide": ("next", None), "slide berikutnya": ("next", None), "slide selanjutnya": ("next", None),
    "lanjut ke slide berikutnya": ("next", None), "kita lanjut": ("next", None), "Next, next.": ("next", None),
    # previous
    "Back": ("prev", None), "balik": ("prev", None), "previous slide": ("prev", None),
    "slide sebelumnya": ("prev", None), "kembali ke slide sebelumnya": ("prev", None),
    # go to slide
    "Slide 2.": ("goto", 2), "slide dua": ("goto", 2), "slide ke-5": ("goto", 5),
    "go to slide twelve": ("goto", 12), "Slide 10": ("goto", 10), "slide dua belas": ("goto", 12),
    "back to slide 3": ("goto", 3), "balik ke slide dua": ("goto", 2), "slide 15": ("goto", 15),
    "kembali ke slide 3": ("goto", 3),
    # first / last slide (from the progress deck)
    "slide pertama": ("goto", 1), "first slide": ("goto", 1), "kembali ke slide pertama": ("goto", 1),
    "slide terakhir": ("last", None), "last slide": ("last", None), "the last slide": ("last", None),
    "ke slide terakhir": ("last", None),
    # stop / resume listening (from the progress deck)
    "stop": ("pause", None), "Stop.": ("pause", None), "berhenti": ("pause", None), "oke berhenti": ("pause", None),
    "mulai": ("resume", None), "Mulai!": ("resume", None),
    "kita mulai": ("resume", None),  # harmless: "mulai" only does something while paused
    # small ASR slips (fuzzy match)
    "lanjud": ("next", None), "bali": ("prev", None), "slaid tiga": ("goto", 3),
    # silence / non-commands
    "slide": None, "": None, "selamat pagi": None, "terima kasih": None, "slide nol": None, "oke": None,
    "dua": None, "lanjut dua": None, "next back": None,
}

# Phrases presenters say mid-explanation and then pause after. Every one of these used to change
# the slide; in a real talk none of them may.
IN_TALK = [
    "dan selanjutnya", "yang berikutnya", "langkah berikutnya", "selanjutnya", "berikutnya",
    "kita kembali", "kembali ke topik", "kembali", "sebelumnya", "balik lagi", "next step", "next time",
    "maju ke depan", "mundur sedikit", "di slide dua tadi", "slide tiga tadi", "tadi di slide 5 kita lihat",
    "the next topic is speech recognition", "kita kembali ke pembahasan awal tadi",
    "pertama kedua dan selanjutnya kita bahas fitur",
    "pertama", "yang terakhir", "terakhir", "mulai dari awal", "berhenti sebentar",
    "stop motion", "berhenti di slide 3", "last time", "first step",
]


@pytest.mark.parametrize("text,want", CASES.items())
def test_parse(text, want):
    assert parse(text) == want


@pytest.mark.parametrize("text", IN_TALK)
def test_explanation_phrases_never_move_the_slide(text):
    assert parse(text) is None


# --- Shortcut tests --------------------------------------------------------

SHORTCUT_CASES_PPT = {
    "layar hitam": ("shortcut", "blackout"),
    "black screen": ("shortcut", "blackout"),
    "blackout": ("shortcut", "blackout"),
    "layar putih": ("shortcut", "whiteout"),
    "white screen": ("shortcut", "whiteout"),
    "whiteout": ("shortcut", "whiteout"),
    "laser": ("shortcut", "laser"),
    "laser pointer": ("shortcut", "laser"),
    "pena": ("shortcut", "pen"),
    "pen": ("shortcut", "pen"),
    "ink": ("shortcut", "pen"),
    "keluar presentasi": ("shortcut", "exit"),
    "exit slideshow": ("shortcut", "exit"),
    "keluar": ("shortcut", "exit"),
}


@pytest.mark.parametrize("text,want", SHORTCUT_CASES_PPT.items())
def test_shortcut_parse_powerpoint(text, want):
    assert parse(text, profile="powerpoint") == want


def test_shortcut_disabled():
    assert parse("laser", profile="powerpoint", disabled_shortcuts=("laser",)) is None


def test_shortcut_disabled_blackout():
    assert parse("layar hitam", profile="powerpoint", disabled_shortcuts=("blackout",)) is None


def test_canva_has_no_whiteout():
    assert parse("layar putih", profile="canva") is None


def test_canva_has_no_laser():
    assert parse("laser", profile="canva") is None


def test_canva_has_blackout():
    assert parse("layar hitam", profile="canva") == ("shortcut", "blackout")


def test_canva_has_exit():
    assert parse("keluar", profile="canva") == ("shortcut", "exit")
    assert parse("exit present", profile="canva") == ("shortcut", "exit")


def test_google_slides_has_whiteout():
    assert parse("layar putih", profile="google_slides") == ("shortcut", "whiteout")
    assert parse("white screen", profile="google_slides") == ("shortcut", "whiteout")


def test_google_slides_has_blackout():
    assert parse("layar hitam", profile="google_slides") == ("shortcut", "blackout")
    assert parse("blackout", profile="google_slides") == ("shortcut", "blackout")


def test_google_slides_has_exit():
    assert parse("keluar presentasi", profile="google_slides") == ("shortcut", "exit")
    assert parse("exit presentation", profile="google_slides") == ("shortcut", "exit")


def test_google_slides_has_no_laser():
    assert parse("laser", profile="google_slides") is None
    assert parse("pena", profile="google_slides") is None


def test_nav_commands_take_priority_over_shortcuts():
    """Navigation words like 'next', 'back' must still be navigation, not shortcuts."""
    assert parse("lanjut", profile="powerpoint") == ("next", None)
    assert parse("balik", profile="powerpoint") == ("prev", None)
    assert parse("slide 3", profile="powerpoint") == ("goto", 3)


SHORTCUT_IN_TALK = [
    "kita lihat layar hitam di sebelah kiri",
    "warna putih dan hitam",
    "exit the building",
    "tolong ambil pena dari meja",
    "laser bisa digunakan untuk presentasi",
]


@pytest.mark.parametrize("text", SHORTCUT_IN_TALK)
def test_shortcut_phrases_in_speech_do_not_trigger(text):
    assert parse(text, profile="powerpoint") is None

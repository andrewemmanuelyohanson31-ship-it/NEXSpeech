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
]


@pytest.mark.parametrize("text,want", CASES.items())
def test_parse(text, want):
    assert parse(text) == want


@pytest.mark.parametrize("text", IN_TALK)
def test_explanation_phrases_never_move_the_slide(text):
    assert parse(text) is None

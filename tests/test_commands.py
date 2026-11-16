import pytest

from nex.commands import parse

CASES = {
    # next
    "Next.": ("next", None), "lanjut": ("next", None), "Oke, lanjut!": ("next", None),
    "berikutnya": ("next", None), "next slide": ("next", None),
    # previous
    "Back": ("prev", None), "balik": ("prev", None), "previous slide": ("prev", None),
    "sebelumnya": ("prev", None), "kembali": ("prev", None),
    # go to slide
    "Slide 2.": ("goto", 2), "slide dua": ("goto", 2), "slide ke-5": ("goto", 5),
    "go to slide twelve": ("goto", 12), "Slide 10": ("goto", 10), "slide dua belas": ("goto", 12),
    "back to slide 3": ("goto", 3), "balik ke slide dua": ("goto", 2), "slide 15": ("goto", 15),
    # small ASR slips (fuzzy match)
    "lanjud": ("next", None), "bali": ("prev", None), "slaid tiga": ("goto", 3),
    # must NOT trigger
    "the next topic is speech recognition": None, "kita kembali ke pembahasan awal tadi": None,
    "slide": None, "": None, "selamat pagi": None, "terima kasih": None, "slide nol": None,
}


@pytest.mark.parametrize("text,want", CASES.items())
def test_parse(text, want):
    assert parse(text) == want

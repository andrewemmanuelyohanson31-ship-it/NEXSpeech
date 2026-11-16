"""Speech-to-action: turn one finished utterance (ASR text) into a slide action.

Rule-based intent classifier on top of the ASR output:
  ("next", None) | ("prev", None) | ("goto", n) | None
"""
import difflib
import re

NEXT = {"next", "lanjut", "lanjutkan", "berikutnya", "selanjutnya", "maju"}
PREV = {"back", "previous", "prev", "balik", "kembali", "sebelumnya", "mundur"}
NUM = {"satu": 1, "dua": 2, "tiga": 3, "empat": 4, "lima": 5, "enam": 6, "tujuh": 7,
       "delapan": 8, "sembilan": 9, "sepuluh": 10, "sebelas": 11,
       "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7,
       "eight": 8, "nine": 9, "ten": 10, "eleven": 11, "twelve": 12}
VOCAB = sorted(NEXT | PREV | set(NUM) | {"slide", "belas"})
MAX_WORDS = 4  # a command must be its own short utterance, so "the next topic is..." never fires
FUZZY_CUTOFF = 0.8  # absorbs small ASR slips: "lanjud"->lanjut, "bali"->balik, "slaid"->slide


def _normalize(word):
    if word.isdigit() or word in VOCAB or len(word) < 3:
        return word
    hit = difflib.get_close_matches(word, VOCAB, n=1, cutoff=FUZZY_CUTOFF)
    return hit[0] if hit else word


def _number(rest):
    if not rest:
        return None
    if rest[0].isdigit():
        return int(rest[0])
    n = NUM.get(rest[0])
    if n and n < 10 and len(rest) > 1 and rest[1] == "belas":  # "dua belas" = 12
        return 10 + n
    return n


def parse(text):
    """Return ("next"|"prev", None), ("goto", n) or None for one finished utterance."""
    words = [_normalize(w) for w in re.findall(r"[a-z0-9]+", text.lower())]
    if not words or len(words) > MAX_WORDS:
        return None
    for i, w in enumerate(words):  # "slide N" wins over next/back: "back to slide 3" -> goto 3
        if w == "slide":
            n = _number([x for x in words[i + 1:] if x != "ke"])  # "slide ke dua", "slide ke-2"
            if n:
                return ("goto", n)
    for w in words:
        if w in NEXT:
            return ("next", None)
        if w in PREV:
            return ("prev", None)
    return None

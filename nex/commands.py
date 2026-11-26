"""Speech-to-action: turn one finished utterance (ASR text) into a slide action.

Rule-based intent classifier on top of the ASR output:
  ("next", None) | ("prev", None) | ("goto", n) | ("last", None)   slide actions
  ("pause", None) | ("resume", None)                                  listening on/off
  None

Built for real talks, where command words also appear inside explanations:
  * the WHOLE utterance must be a command (plus a few fillers): "kembali ke topik" -> None
  * everyday explanation words only count next to "slide": "selanjutnya" -> None,
    "slide selanjutnya" -> next
"""
import difflib
import re

NEXT = {"next", "lanjut", "lanjutkan"}                        # rarely said mid-explanation
PREV = {"back", "balik", "previous", "prev"}
NEXT_WITH_SLIDE = {"berikutnya", "selanjutnya", "maju"}       # common in explanations: need "slide"
PREV_WITH_SLIDE = {"sebelumnya", "kembali", "mundur"}
FIRST = {"pertama", "first"}                                  # only with "slide": "slide pertama"
LAST = {"terakhir", "last"}                                   # only with "slide": "slide terakhir"
PAUSE = {"stop", "berhenti"}                                  # stop listening for a while
RESUME = {"mulai"}                                            # listen again
NUM = {"satu": 1, "dua": 2, "tiga": 3, "empat": 4, "lima": 5, "enam": 6, "tujuh": 7,
       "delapan": 8, "sembilan": 9, "sepuluh": 10, "sebelas": 11,
       "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7,
       "eight": 8, "nine": 9, "ten": 10, "eleven": 11, "twelve": 12}
FILLERS = {"oke", "ok", "okay", "ya", "yuk", "ayo", "nah", "tolong", "please", "kita",
           "ke", "go", "to", "the"}
COMMAND_WORDS = (NEXT | PREV | NEXT_WITH_SLIDE | PREV_WITH_SLIDE | FIRST | LAST | PAUSE | RESUME
                 | set(NUM) | {"slide", "belas"})
VOCAB = sorted(COMMAND_WORDS)  # fuzzy targets; fillers excluded so a random word can't become one
MAX_WORDS = 4  # after removing fillers; "back to slide 3" -> back slide 3
FUZZY_CUTOFF = 0.8  # absorbs small ASR slips: "lanjud"->lanjut, "bali"->balik, "slaid"->slide


def _normalize(word):
    if word.isdigit() or word in VOCAB or word in FILLERS or len(word) < 3:
        return word
    hit = difflib.get_close_matches(word, VOCAB, n=1, cutoff=FUZZY_CUTOFF)
    return hit[0] if hit else word


def _is_num(w):
    return w.isdigit() or w in NUM


def _number(rest):
    if not rest or not _is_num(rest[0]):
        return None
    n = int(rest[0]) if rest[0].isdigit() else NUM[rest[0]]
    if n < 10 and len(rest) > 1 and rest[1] == "belas":  # "dua belas" = 12
        return 10 + n
    return n


def parse(text):
    """Return ("next"|"prev", None), ("goto", n) or None for one finished utterance."""
    words = [w for w in (_normalize(w) for w in re.findall(r"[a-z0-9]+", text.lower())) if w not in FILLERS]
    if not words or len(words) > MAX_WORDS:
        return None
    if any(w not in COMMAND_WORDS and not w.isdigit() for w in words):
        return None  # anything else in the utterance means it was speech, not a command
    if len(words) == 1 and words[0] in PAUSE:  # "stop" / "berhenti" on its own
        return ("pause", None)
    if len(words) == 1 and words[0] in RESUME:  # "mulai" on its own
        return ("resume", None)
    if any(w in PAUSE | RESUME for w in words):
        return None  # "berhenti di slide 3" etc. is speech, not a command
    has_slide = "slide" in words
    if has_slide:  # "slide N" wins over next/back: "back to slide 3" -> goto 3
        n = _number(words[words.index("slide") + 1:])
        if n:  # "slide 0" falls through and is rejected below
            return ("goto", n)
        if any(w in FIRST for w in words):  # "slide pertama", "kembali ke slide pertama"
            return ("goto", 1)
        if any(w in LAST for w in words):  # "slide terakhir": the engine knows how many slides
            return ("last", None)
    if any(w in FIRST | LAST for w in words):
        return None  # "pertama", "yang terakhir" without "slide" is speech
    if any(_is_num(w) for w in words):
        return None  # a number without "slide N" ("lanjut dua") is ambiguous
    nxt = any(w in NEXT or (has_slide and w in NEXT_WITH_SLIDE) for w in words)
    prv = any(w in PREV or (has_slide and w in PREV_WITH_SLIDE) for w in words)
    if nxt == prv:  # neither, or contradictory ("next back")
        return None
    return ("next", None) if nxt else ("prev", None)

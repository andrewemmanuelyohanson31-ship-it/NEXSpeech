# NEX: "Nex Slide? Just Say So."
### Step-by-step build guide (COMP6822001 Speech Recognition, Final Project)

NEX listens to the presenter **in real time, on the laptop (no API)**, shows a live transcript, and changes the slide when it hears a command:

| You say | NEX does |
|---|---|
| `next`, `lanjut`, `lanjutkan`, `berikutnya`, `selanjutnya`, `maju` | Next slide (→ key) |
| `back`, `previous`, `balik`, `kembali`, `sebelumnya`, `mundur` | Previous slide (← key) |
| `slide 2`, `slide dua`, `slide ke-5`, `go to slide twelve`, `balik ke slide 3` | Jump to that slide (types the number, then Enter) |

Sources used: the brief `D:\Binus\speech\20260907160650_FINAL_PROJECT_COMP6822001_Speech_Recognition.docx` and the Figma file *Speech-Recog*, which has 12 screens: Login, Home, Naskah, Mulai Sesi, Live Session, Setup, Riwayat ×2, Review, Lab Evaluasi and Pengaturan.

---

## 0. How NEX meets the brief

| Brief requirement (section) | How NEX does it |
|---|---|
| Real-time, continuous audio (§3) | The microphone streams 0.25 s blocks, Whisper runs on a 1 s cycle and partial text appears while you are still talking |
| Local model, no external API (§11) | **faster-whisper** (an open-source Whisper build) runs on your CPU. You download the model once, then it works with no internet |
| Partial and updated transcription (§3, §10) | The live transcript panel updates every second, and the finished sentence replaces the partial text |
| A real problem and a real user (§4–5) | *Students who present at BINUS have their hands busy (notes, pointer, gestures) and have to walk back to the laptop or depend on a friend to click.* You will interview 5 or more real presenters |
| WER and latency (§13) | The **Lab Evaluasi** page and the `eval/` scripts: WER, command accuracy, false triggers, latency P50/P95 and real-time factor (RTF) |
| User testing with 5 or more people (§6–9) | The **Review** page in the Figma design is your questionnaire |
| AI usage log (§21) | See Step 15. **This guide was made with AI, so log it** |

---

## 1. Tools

| Layer | Tool | Why this one |
|---|---|---|
| Language | Python 3.11 | Every ASR and audio library supports it |
| Microphone | `sounddevice` | Records straight to numpy at 16 kHz, so FFmpeg is not needed |
| ASR model | `faster-whisper` with `small` (also `base` and `tiny` for comparison) | Runs locally and handles mixed Indonesian and English. With int8 on CPU, a 1 s cycle is fast enough |
| Speech/silence detection | Energy (RMS) threshold with a 2 s noise calibration | A few lines of code. Upgrade to Silero VAD if noise testing (E1) shows false cuts |
| Command parsing | Plain Python `re` | Verified code in Step 6 |
| Pressing slide keys | `pynput` | Sends ← / → / number + Enter to PowerPoint, Google Slides or Canva |
| Backend | `FastAPI` + `uvicorn` (WebSocket) | Pushes the live transcript to the browser |
| Storage | `sqlite3` (built into Python) | Scripts (naskah), sessions and feedback |
| Frontend | Plain HTML, CSS and JS, one file per Figma screen | No build step, and FastAPI serves it |
| Evaluation | `jiwer` (WER, S/D/I), `numpy` (noise mixing) | The standard WER tool |
| Script following (optional) | `rapidfuzz` | Fuzzy-matches what you say against your naskah |

```
pip install faster-whisper sounddevice numpy pynput fastapi "uvicorn[standard]" jiwer rapidfuzz
```

> Not allowed (§11): Google Speech-to-Text, Azure, AWS Transcribe, the OpenAI Speech API, AssemblyAI and the **browser's Web Speech API** (Chrome sends the audio to Google). Do not use `webkitSpeechRecognition`.

---

## 2. Architecture (put this diagram in report §3)

```
 ┌────────── Python process (runs locally) ───────────────────────────────┐
 │                                                                         │
 │  Mic ──► sounddevice ──► audio queue ──► Segmenter (RMS + calibration)  │
 │           16 kHz mono     0.25 s blocks      │ speech buffer             │
 │                                              ▼                          │
 │                                   faster-whisper (small, int8, CPU)     │
 │                                     every 1 s ──► PARTIAL text ─┐       │
 │                                     on silence ─► FINAL text  ──┤       │
 │                                              │                  │       │
 │                                              ▼                  │       │
 │                                   Command parser (Step 6)       │       │
 │                                              │                  │       │
 │                                              ▼                  ▼       │
 │                                   pynput key press      FastAPI WebSocket
 │                                   (→ ← or "5⏎")                 │       │
 │                                              │          SQLite (log)    │
 └──────────────────────────────────────────────┼──────────────────┼───────┘
                                                ▼                  ▼
                              PowerPoint / Slides / Canva   Browser UI (Figma screens)
```

**Why Python records the microphone instead of the browser:** while presenting, PowerPoint has keyboard focus, not the browser. Browser tabs can throttle audio in the background, but a Python stream keeps running.

---

## 3. Build steps

### Step 1: Define the problem and find real users (do this before coding)
1. Write the proposal sentence: *"Target users are BINUS students and lecturers who present with slides and need to change slides without going back to the laptop or using a clicker."*
2. Talk to 5 or more real presenters for 5 minutes each: *How do you change slides now? What goes wrong? Indonesian, English or mixed?* Save their answers (anonymised as U1–U5) for report §1.
3. Write down the usage scenario: classroom, 20–40 people, some room noise, laptop microphone or headset.

### Step 2: Set up the project
```
NEX/
  nex/       app.py  audio.py  asr.py  commands.py  engine.py  keys.py  db.py
  frontend/  login.html home.html naskah.html sesi.html live.html setup.html
             riwayat.html review.html lab.html pengaturan.html
             css/tokens.css  js/live.js ...
  eval/      record.py  run_eval.py  add_noise.py  refs/  audio/
  tests/     test_commands.py
  requirements.txt
```
```
python -m venv .venv && .venv\Scripts\activate
pip install -r requirements.txt
python -c "from faster_whisper import WhisperModel; WhisperModel('small')"   # one-time download, then offline
```
Write down your hardware (CPU, RAM, microphone) for report §4.

### Step 3: Capture the microphone as a stream (`audio.py`)
```python
import queue, sounddevice as sd
SR = 16000
q = queue.Queue()
def _cb(indata, frames, t, status):
    q.put(indata[:, 0].copy())          # float32 mono block
stream = sd.InputStream(samplerate=SR, channels=1, dtype="float32",
                        blocksize=SR // 4, callback=_cb)   # 0.25 s blocks
```
`sd.query_devices()` lists the microphones for the **MIKROFON / Perangkat masuk** dropdown.
**Check:** print the RMS level of each block and watch it rise when you talk. That number drives the **LEVEL SUARA** meter on the Setup screen.

### Step 4: Load the local ASR model (`asr.py`)
```python
from faster_whisper import WhisperModel
model = WhisperModel("small", device="cpu", compute_type="int8")
PROMPT = "next, lanjut, back, balik, previous, slide dua, slide 3"   # nudges Whisper toward command words

def transcribe(audio):                      # audio = float32 numpy at 16 kHz
    segs, _ = model.transcribe(audio, language="id", beam_size=1,
                               initial_prompt=PROMPT,
                               condition_on_previous_text=False)
    return " ".join(s.text.strip() for s in segs)
```
- `language="id"` still writes English words like "next" and "slide". Compare it with `language=None` (auto-detect) as an experiment.
- `beam_size=1` (greedy decoding) is faster. Record this choice under "technical decisions".
- Report §2 material: Whisper is an encoder-decoder Transformer. It turns the audio into an 80-bin log-Mel spectrogram, the encoder reads it and the decoder writes text tokens one at a time. Compare with the HMM/acoustic-model pipeline from your lecture slides.

### Step 5: Real-time loop with partial and final text (`asr.py`)
This is what makes the app "real time" under §3.
```python
import time, numpy as np
CHUNK_S, SILENCE_S, MAX_UTT_S = 1.0, 0.6, 8.0

def calibrate(q, seconds=2):                 # measure room noise once at session start
    blocks = [q.get() for _ in range(int(seconds * 4))]
    return 3 * float(np.sqrt(np.mean(np.concatenate(blocks) ** 2)))

def run(q, on_partial, on_final):
    thr = calibrate(q)
    buf, silent, last = [], 0.0, time.time()
    while True:
        b = q.get()
        speaking = np.sqrt(np.mean(b ** 2)) > thr
        if speaking or buf:
            buf.append(b)
        silent = 0.0 if speaking else silent + 0.25
        dur = len(buf) * 0.25
        if buf and (silent >= SILENCE_S or dur >= MAX_UTT_S):      # utterance finished
            t0 = time.time(); text = transcribe(np.concatenate(buf))
            on_final(text, latency=time.time() - t0, audio_s=dur)
            buf, silent = [], 0.0
        elif buf and time.time() - last >= CHUNK_S:                  # partial update
            last = time.time(); on_partial(transcribe(np.concatenate(buf)))
```
- **Commands fire only on FINAL text.** If they fired on partial text, the same "next" would be seen again on every 1 s pass and could skip two slides.
- **Latency** = time from the end of speech to the key press, which is about `SILENCE_S` plus inference time. Log both parts.
- **Real-time factor (RTF)** = inference time ÷ audio length. Below 1 means faster than real time, which the Riwayat and Lab Evaluasi screens already show.
- `CHUNK_S` is the **UKURAN POTONGAN AUDIO** setting (0.5 / 1 / 2 s), so test all three.

### Step 6: Command parser (`commands.py`, tested with 17 cases)
```python
import re

NEXT = {"next", "lanjut", "lanjutkan", "berikutnya", "selanjutnya", "maju"}
PREV = {"back", "previous", "prev", "balik", "kembali", "sebelumnya", "mundur"}
NUM = {"satu": 1, "dua": 2, "tiga": 3, "empat": 4, "lima": 5, "enam": 6, "tujuh": 7,
       "delapan": 8, "sembilan": 9, "sepuluh": 10, "sebelas": 11,
       "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7,
       "eight": 8, "nine": 9, "ten": 10, "eleven": 11, "twelve": 12}
MAX_WORDS = 4  # a command must be its own short utterance, so "the next topic is..." never fires


def parse(text):
    """Return ("next"|"prev", None), ("goto", n) or None for one finished utterance."""
    words = re.findall(r"[a-z0-9]+", text.lower())
    if not words or len(words) > MAX_WORDS:
        return None
    for i, w in enumerate(words):  # "slide N" wins over next/back: "back to slide 3" -> goto 3
        if w == "slide":
            rest = [x for x in words[i + 1:] if x != "ke"]  # "slide ke dua", "slide ke-2"
            if rest:
                n = int(rest[0]) if rest[0].isdigit() else NUM.get(rest[0])
                if n:
                    return ("goto", n)
    for w in words:
        if w in NEXT:
            return ("next", None)
        if w in PREV:
            return ("prev", None)
    return None
```
The implemented version is `nex/commands.py`. It adds fuzzy matching for small ASR slips ("lanjud" → lanjut) and "dua belas" = 12. Its 29 test cases are in `tests/test_commands.py`; run them with `python -m pytest tests`.

**Key design decision (explain it in the report):** the `MAX_WORDS = 4` rule stops false slide changes when you say "next" or "kembali" in normal speech. The trade-off is that the presenter must pause briefly before and after a command. Measure it: count **false triggers per 10 minutes** of normal speaking. If it is still too high, add a wake word ("Nex, lanjut").
Spoken numbers go up to 12. Whisper usually writes larger numbers as digits ("slide 15"), which already works. Add more Indonesian number words if testing shows they are needed.

### Step 7: Press the slide keys (`keys.py`)
```python
from pynput.keyboard import Controller, Key
kb = Controller()
def send(cmd):
    kind, n = cmd
    if kind == "next": kb.tap(Key.right)
    elif kind == "prev": kb.tap(Key.left)
    elif kind == "goto": kb.type(str(n)); kb.tap(Key.enter)
```
Test each target app in presentation mode and put the results in the report:

| App (presenting) | → / ← | number + Enter (jump) |
|---|---|---|
| PowerPoint | test it | test it (normally supported) |
| Google Slides | test it | test it |
| Canva | test it | test it, may not be supported. If not, press → or ← (n − current) times |

- Windows: no permission is needed. macOS: the Setup screen asks for the **Accessibility** permission for Terminal/Python (the design already mentions this).
- The presentation window must have focus. That is why NEX runs as a separate local process and the browser only displays information.

### Step 8: Backend server and WebSocket (`app.py`)
- `GET /` serves `frontend/` as static files.
- `WS /ws` pushes events to the browser:
  `{"type":"partial","text":...}`, `{"type":"final","text":...,"latency":0.8}`, `{"type":"command","cmd":"next","slide":4}`, `{"type":"level","rms":0.03}`
- REST: `/api/scripts` (Naskah CRUD), `/api/sessions` (Riwayat), `/api/feedback` (Review), `/api/settings`, `POST /api/session/start|pause|stop`.
- Run the ASR loop in a background thread. To send from that thread to the WebSocket, use `asyncio.run_coroutine_threadsafe(ws.send_json(msg), loop)`.
- **Privacy (shown on the Review and Setup screens):** keep audio in memory only and save the text, not the recording. Save evaluation clips only with consent.

### Step 9: Build the web UI from Figma
**Design tokens:** copy the exact values from Figma **Dev Mode → Inspect** into `css/tokens.css`. The values below are estimated from screenshots and need checking:
```css
:root{
  --brand:#FF6A00; --brand-soft:#FFF3EA; --ink:#141A2B; --muted:#6B7280;
  --bg:#F7F7FB; --surface:#FFFFFF; --border:#ECEAF3;
  --teal:#0E7C6B; --mint:#CFF5EA; --danger:#E5484D; --radius:14px;
  --font: "Plus Jakarta Sans", system-ui, sans-serif;   /* confirm the font name in Figma */
  --mono: "JetBrains Mono", ui-monospace, monospace;    /* used for small labels like "SELASA, 20 OKTOBER" */
}
```
Most screens share one layout: a 256 px left sidebar (Home, Naskah, Mulai sesi, Riwayat, Lab evaluasi, Pengaturan), a 64 px header with search and an "Engine Siap" badge, and the main content. Build that shell once and reuse it.

| Figma frame | File | What it needs from the backend |
|---|---|---|
| Login Page | `login.html` | Optional. All data stays local, so a local profile (name only) is enough. **Build it last** |
| Home Page | `home.html` | Latest naskah, recent sessions, **Status sistem** (model loaded? microphone OK? key permission OK?), averages from SQLite |
| Naskah Page | `naskah.html` | Script list and editor (one block per slide) plus a **custom vocabulary** list that gets appended to `PROMPT` |
| Mulai Sesi Page | `sesi.html` | Choose script, microphone and options, then `POST /api/session/start` |
| 2 (Setup) | `setup.html` | Microphone choice with live level meter, model download status, key-permission test ("Tekan → sekarang") |
| Mulai Sesi (2), the **live screen** | `live.html` | WS events: highlighted sentence, **TRANSKRIP LIVE**, Latensi, Slide 03/12, timer, BERIKUTNYA preview, buttons (Jeda, ← Mundur, Berikutnya →, Akhiri sesi) |
| Riwayat Page ×2 | `riwayat.html` | Session list and details: duration, latency, auto-moved 11/12, RTF |
| Review Page | `review.html` | **The user-testing questionnaire** (participant code U1–U5, role, Likert ratings, open answers) saved to `/api/feedback` |
| Lab Evaluasi Page | `lab.html` | Shows the output of `eval/run_eval.py`: WER with S/D/I, latency P50/P95, RTF, error table |
| Pengaturan Page | `pengaturan.html` | Model (tiny = Cepat / base / small = Seimbang), language (id / en / auto), chunk size, privacy settings |

> ⚠️ The Figma screens say *"Angka … hanya contoh tampilan, bukan hasil pengujian"*: the numbers are placeholders. **Never copy those numbers (12.4% WER, 0.9 s, 92%) into the report.** §21.6 treats invented results as academic misconduct. Fill those screens only with values you actually measured.

### Step 10 (optional): Script following ("Naskah" mode)
The design highlights the current sentence and moves to the next slide *"setelah kalimat penanda selesai diucapkan"* (after the slide's last sentence is spoken). For each slide, take the last sentence of its script. On each final text, check `rapidfuzz.fuzz.partial_ratio(last_sentence, recent_text) > 80`, and if it passes, send `next`. Build this **after** the voice commands work, and evaluate it separately (correct advances vs. early advances).

### Step 11: Log everything you will need for the report
SQLite tables: `scripts`, `sessions(id, script_id, started, duration, model, chunk_s)`, `events(session_id, t, type, text, cmd, latency, audio_s, infer_s)` and `feedback(code, role, ease, responsiveness, quality, satisfaction, useful, confusing, missing)`.
The Riwayat, Lab and Home statistics are all queries on these tables.

### Step 12: Technical experiments (report §5)
1. **Record a test set** (`eval/record.py`) of 5 or more speakers. Each speaker reads (a) 30 commands from a fixed list in random order and (b) a 2-minute talk with **no commands**, used to count false triggers. Write the exact reference text in `refs/`.
2. **Conditions:**

| ID | Condition | How |
|---|---|---|
| Baseline | Quiet room, laptop mic, normal pace | as recorded |
| E1 | Background noise at SNR 20 / 10 / 5 dB | `add_noise.py` mixes recorded classroom noise |
| E2 | Different speakers / accents | the 5 speakers |
| E3 | Fast vs. normal speech | ask speakers to read fast |
| E4 | Laptop mic vs. headset | record both |
| E5 | Model tiny vs. base vs. small (and chunk size 0.5 / 1 / 2 s) | settings |

```python
# add_noise.py: mix noise into speech at a target SNR
def mix(speech, noise, snr_db):
    noise = noise[:len(speech)]
    p_s, p_n = (speech**2).mean(), (noise**2).mean()
    return speech + noise * np.sqrt(p_s / (p_n * 10**(snr_db/10)))
```
3. **Metrics** (`run_eval.py`). Feed the recorded files through the **same** `run()` loop, not a separate code path, so latency is measured honestly.
   - **WER** with `jiwer.process_words(ref, hyp)`, which gives substitutions, deletions, insertions and the word count N. Also show the formula (S+D+I)/N.
   - **Command accuracy** = correct actions ÷ commands spoken. This is NEX's most important metric.
   - **False triggers per 10 min** of normal talk.
   - **Latency** (end of speech → key press) as P50 and P95. **RTF** = inference time ÷ audio length.
4. **Error analysis table** (reference / output / error type), for example "lanjut" heard as "lanjud", "balik" heard as "bali", or "slide dua" heard as "slide 12", with the pattern behind each (accent, noise, fast speech, code-switching).

### Step 13: User testing with 5 or more real presenters (report §6)
1. **Tasks:** (a) present 5 slides using only next/lanjut, (b) go back twice, (c) jump to slide 2 and then slide 5, (d) give a 2-minute talk normally and count unwanted slide changes.
2. **Observe:** record retries, failed commands, hesitation and quotes, and write down what you see during the test.
3. **Questionnaire:** use the Review screen. Rate on a 1–5 scale: ease of use, responsiveness, recognition quality and overall satisfaction. Then the open questions: most useful feature, what was confusing, what is missing.
4. **Analyse** by linking feedback to measurements. Example: *users said "balik" sometimes didn't work → the error table shows "balik"→"bali" in 4 of 30 cases at SNR 10 dB → add "bali" as a synonym or add "balik" to the prompt*. Then re-test and report the before and after.

### Step 14: Write the report (use the §15 structure from the brief)
| Report section | Where the content comes from |
|---|---|
| 1 Introduction | Step 1 interviews |
| 2 Fundamentals | Step 4 notes on Whisper (Mel spectrogram, encoder-decoder, tokens), compared with the course slides |
| 3 System Design | Step 2 diagram, the Step 5 loop and Step 6 rules |
| 4 Implementation | Hardware and libraries list, technical decisions (int8, greedy decoding, 4-word rule, final-only commands) |
| 5 Experiments | Step 12 tables |
| 6 User Testing | Step 13 |
| 7 Discussion | Technical results combined with user feedback → strengths, weaknesses, improvements |
| 8 Conclusion | |
| Evidence (§16) | Screenshots of every screen, the architecture diagram, WER and latency tables, feedback table |

### Step 15: AI usage log (counts for 10% of the grade)
Add a row for this guide, for example:

| No | AI Tool | Purpose | Prompt summary | Output used | Student verification |
|---|---|---|---|---|---|
| 1 | Claude (Claude Code) | Plan the steps, choose tools, draft the command parser | "Make a step-by-step plan for NEX following the brief and Figma design" | Partly used: architecture, parser | Parser checked with 17 test cases. Latency and WER measured by us in Step 12 |

Add rows as you keep using AI, and finish with the §21.8 declaration.

---

## 4. Pitfalls to expect
- **Whisper invents text in silence** ("Terima kasih.", "Thanks for watching"). Only transcribe when the segmenter detects speech, and drop finals that are shorter than 0.3 s of audio.
- **Double slide changes** happen if commands fire on partial text. Fire on final text only (Step 5), and add a 1 s cooldown after each key press.
- **The browser has focus, so keys go to the wrong window.** Before saying "next", click the presentation once. Write this in the user instructions.
- **The first transcription is slow** because the model warms up. Run one silent dummy transcription at startup.
- **Too slow on a weak laptop:** switch to `base` or `tiny` or a chunk size of 2 s. Report the speed vs. accuracy trade-off as experiment E5.

## 5. Build order checklist
- [ ] Step 1 interviews (5 users)
- [ ] Steps 2–7 in the terminal: say "lanjut" and PowerPoint moves to the next slide **(core demo, finish this first)**
- [ ] Step 8 WebSocket, then Step 9 `live.html`, then the other screens
- [ ] Step 11 logging, then Step 12 experiments, then Step 13 user tests
- [ ] Optional Step 10, then the report and AI log

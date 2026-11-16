# NEX Speech: "Nex Slide? Just Say So."

Real-time, **fully local** voice control for presentation slides (COMP6822001 Speech Recognition final project).
Say **"next / lanjut"**, **"back / balik / previous"** or **"slide 2 / slide dua"**, and NEX presses the key in
PowerPoint, Google Slides or Canva. No cloud speech API: recognition runs on the laptop with
[faster-whisper](https://github.com/SYSTRAN/faster-whisper).

```
Mic ─► sounddevice (16 kHz, 0.25 s blocks) ─► StreamingRecognizer ─► faster-whisper (local)
                                                │ partial text every ~1 s ─────────────┐
                                                │ final text after 0.6 s silence        │
                                                ▼                                       ▼
                                   speech-to-action (nex/commands.py)        FastAPI WebSocket ─► web UI
                                                ▼                                       │
                                   pynput: → / ← / "N⏎"                       SQLite (text only)
```

## Test it yourself: step by step
It takes about 15 minutes. You test in 3 stages: in the terminal first, then on the web page, then with real slides.

### Step 0: What you need
- A Windows or Mac laptop with a microphone. A headset or clip-on mic works best.
- **Python 3.10–3.12.** Check with `python --version` (on Mac: `python3 --version`).
- **Git.** Check with `git --version`.
- Internet the first time only, for the packages and the Whisper model (about 75 MB). After that NEX works offline.
- Access to this repo. It's private, so ask the owner to add your GitHub account.

### Step 1: Download the code
```bash
git clone https://github.com/andrewemmanuelyohanson31-ship-it/NEXSpeech.git
cd NEXSpeech
```

### Step 2: Install
Windows (PowerShell):
```powershell
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```
Mac:
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```
- If Windows says "running scripts is disabled", run `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` once, then activate again.
- Every new terminal needs the `activate` line again before the commands below.
- **Mac only:** in System Settings → Privacy & Security, give your Terminal app **Microphone** and **Accessibility** permission. Without them NEX can't hear you or press keys.

### Step 3: Check the install
```bash
python -m pytest tests
```
You should see `69 passed`. If not, stop here and send the error to the team.

### Step 4: Find your microphone
```bash
python -m nex.try_mic --list
```
Note the number of the mic you want. The one marked `<- default` is used unless you choose another.

### Step 5: Test 1, in the terminal (no slides, no keys pressed)
```bash
python -m nex.try_mic                 # add --device 3 to use mic number 3
```
1. Wait for `Loaded in … s` (about 15 s; the first time it also downloads the model).
2. **Stay quiet** until it says `Listening`. It's measuring the room noise.
3. Say each of these on its own, with a short pause after each one:
   - "lanjut", "next", "slide berikutnya" → should show `NEXT slide`
   - "balik", "previous" → should show `PREVIOUS slide`
   - "slide tiga", "slide 5", "balik ke slide dua" → should show `GO TO slide …`
4. Then say normal sentences that contain command words, such as "dan selanjutnya kita bahas fitur" or "kita kembali ke topik". These should show `none`.
5. Press **Ctrl+C** to stop. It prints the average, best and worst time.

Each line of output means:
- `YOU SAID`: what Whisper heard
- `ACTION`: what NEX would do with the slides
- `TIME`: how long after you stopped talking the action was ready, split into waiting for silence and recognition time
- `RTF`: processing time ÷ audio length; below 1 means it keeps up with real time

### Step 6: Test 2, the live web page (still no keys pressed)
Start the server in **dry-run mode**, so it only shows what it would do:
```powershell
$env:NEX_DRY_RUN="1"        # Windows PowerShell   (Mac: export NEX_DRY_RUN=1)
python -m nex
```
1. Open **http://127.0.0.1:8000** in your browser.
2. Optionally, enter how many slides your deck has in "Jumlah slide".
3. Click **Mulai sesi**, then stay quiet until the status turns green and says **Mendengarkan**.
4. Speak the commands from Step 5. You should see:
   - grey italic text while you talk (partial transcription)
   - each finished sentence added to **Transkrip live**
   - an orange label on each recognized command, and the slide number and **Latensi** updating
5. Click **Akhiri sesi** to see the summary: duration, number of commands, latency P50/P95 and real-time factor.
6. Stop the server with **Ctrl+C** in the terminal.

### Step 7: Test 3, with real slides
1. Open a **new terminal** so dry-run mode is off. Go to the folder, activate (Step 2), and run `python -m nex`.
2. Open your deck in PowerPoint or Google Slides and start the slideshow.
3. In the browser, open http://127.0.0.1:8000 and click **Mulai sesi**. Wait for **Mendengarkan**.
4. **Click the slideshow window once.** Keys go to whichever window is in front.
5. Say "lanjut", "balik" and "slide tiga", and watch the slides move.
6. For **Canva**: if "slide 5" doesn't jump, switch to arrow mode. Stop the session, open http://127.0.0.1:8000/docs, then use **PUT /api/settings** → *Try it out* with `{"jump_mode": "arrows"}`.

### Step 8: Try other settings (optional)
- More accurate but slower: `python -m nex.try_mic --model base`
- Auto-detect Indonesian or English: `python -m nex.try_mic --language ""`
- For the web page, change the same settings with **PUT /api/settings** on `/docs`, for example `{"model": "base"}` or `{"language": ""}`. Only do this while no session is running.
- If `TIME` goes above about 2 s or `RTF` above 1, your laptop is too slow for that model. Go back to `tiny`.

### Step 9: Share what you found
Send the team:
- your laptop (CPU, Windows or Mac), microphone, and the model you used
- which commands worked and which didn't, with the exact `YOU SAID` text when NEX misheard you
- your average `TIME` from Step 5
- any normal sentence that moved a slide by mistake
- which presentation apps worked in Step 7

These notes are for the team's own testing. The report's experiments and user tests have their own procedure; see `NEX_Step_by_Step_Guide.md`.

### If something goes wrong
- **Nothing happens when you talk:** the wrong mic is selected (Step 4), or there was noise during the quiet start. Restart and stay quiet until `Listening`.
- **Text appears but the slide doesn't move:** dry-run mode is still on (open a new terminal), the slideshow isn't the window in front, or on Mac the Accessibility permission is missing.
- **"Address already in use":** another NEX server is still running. Close that terminal.
- **`pip install` fails:** check that your Python version is 3.10–3.12.
- **Very slow:** use `--model tiny` (the default) and close other heavy apps.

### Good to know
- NEX only accepts connections from your own computer, because it can press keys.
- Only text is saved (`data/nex.db`); audio is never saved by the app.
- The first session downloads the Whisper model once; after that everything works without internet.

## Speech-to-action model (`nex/commands.py`)
The model has two stages: **ASR → rule-based intent classifier.** Each *finished utterance* is classified as:

| Say | Action |
|---|---|
| next, lanjut, lanjutkan, next slide, slide berikutnya, slide selanjutnya, oke lanjut | `next` (→) |
| back, balik, previous, previous slide, slide sebelumnya, kembali ke slide sebelumnya | `prev` (←) |
| slide 2, slide dua, slide ke-5, slide dua belas, go to slide seven, balik ke slide 3 | `goto N` (types N, then Enter) |

Built for real talks, where command words also appear inside explanations:
1. **The whole utterance must be a command.** The only extra words allowed are fillers (oke, ya, kita, ke, tolong, please, go, to…). "kembali ke topik", "next step" and "di slide dua tadi" do nothing.
2. **Everyday explanation words count only next to "slide".** *selanjutnya, berikutnya, maju, sebelumnya, kembali, mundur* alone do nothing. "slide selanjutnya" works.
3. **The tail of a long sentence never triggers.** Speech is cut every 8 s. A piece that continues a cut, rather than starting after a real pause, is flagged `after_cut` and ignored.

Other rules:
- Commands fire only on **final** text, never on partial text, so one "next" can't fire twice.
- **Fuzzy matching** (`difflib`, cutoff 0.8) absorbs small ASR slips: lanjud → lanjut, bali → balik, slaid → slide.
- "slide N" takes priority over next/back. A 1 s cooldown follows each voice action, and jumps past the last slide are rejected.
- The trade-off is a **brief pause before and after a command**. `tests/test_commands.py` lists 20 explanation phrases that must never move a slide.

## Real-time pipeline (`nex/asr.py`)
- Calibrates to room noise for 2 s, then uses an energy (RMS) threshold to find speech.
- Produces a **partial** transcription about every `chunk_s` (default 1 s) while you speak, and a **final** one after `silence_s` (0.6 s) of silence or 8 s of speech.
- **Adaptive throttle:** if a partial transcription took X s, the next one waits at least 2X. On a slow CPU this stops the audio queue from backing up.
- Whisper silence hallucinations are filtered (`no_speech_prob`), and blips shorter than 0.25 s are skipped.

## API (for the web UI / Figma screens)
| Screen | Endpoints |
|---|---|
| Live session | `WS /ws` (events `partial`, `final`, `command`, `rejected`, `state`, `level`, `error`), `POST /api/session/start · pause · resume · stop · action` |
| Home / Setup | `GET /api/status` (model, microphones, session), `POST /api/model/load` |
| Naskah | `GET/POST /api/scripts`, `GET/PUT/DELETE /api/scripts/{id}` (`vocab` is added to the Whisper prompt) |
| Riwayat | `GET /api/sessions`, `GET /api/sessions/{id}` (duration, voice/manual commands, latency P50/P95, RTF, events) |
| Review | `GET/POST /api/feedback` (participant code U1…, 1–5 ratings, open answers) |
| Pengaturan | `GET/PUT /api/settings` (`model` tiny/base/small/medium, `language` id/en/"" = auto, `chunk_s`, `silence_s`, `jump_mode` number/arrows, `device`) |

Only text is stored (`data/nex.db`). Audio is never saved by the app.

## Evaluation (`eval/`)
```bash
python eval/record.py eval/prompts.txt --speaker U1 --condition baseline --seconds 3
# for the no-command talk line: read for ~2 minutes and record it with --seconds 130
python eval/add_noise.py eval/data/manifest.csv classroom_noise.wav --snr 20 10 5     # experiment E1
python eval/run_eval.py eval/data/manifest.csv --model tiny --language id
```
`run_eval.py` replays each clip through the **same** streaming code on a simulated real-time clock. The latency it reports therefore includes any backlog caused by partial transcriptions. Per condition it gives WER (with S/D/I/N), command accuracy, false triggers per 10 min of talk, latency P50/P95 and RTF. It writes a per-clip CSV for the error-analysis table. Recordings and results are git-ignored so that participants' voices stay local.

### Pipeline check (synthetic, not report data)
Machine: Intel i7-8700 (6 cores), CPU only, int8. Clips: 7 commands and 2 talks generated with Windows text-to-speech (English voice), `language=id`.

| model | command accuracy | false triggers | command latency P50 | RTF on 28 s talk |
|---|---|---|---|---|
| tiny | 7/7 | 0 | 1.14 s | 0.53 |
| base | 7/7 | 0 | 1.79 s | 1.15 |
| small | 7/7 | 0 | 4.59 s | 1.41 |

On this CPU only `tiny` stays real-time, so it is the default (change it in Pengaturan). With `language=id`, base and small *translated* English speech into Indonesian. Run `language` id vs. auto as an experiment. **These synthetic numbers only show that the pipeline works. The report must use recordings of real users (brief §21.6).**

## Tests
```bash
python -m pytest tests     # 69 tests: parser + explanation phrases, segmenter + 8 s cut, API, live page, full voice session with a fake mic
```
See `REPORT.md` for requirements, progress, and what the team still has to do.

See `NEX_Step_by_Step_Guide.md` for the full project plan (report structure, user testing, AI usage log).

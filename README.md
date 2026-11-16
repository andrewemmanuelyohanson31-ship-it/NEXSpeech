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

## Quick try (no slides, no server)
Talk and see what NEX heard, what it would do, and how long it took. No keys are pressed.
```bash
python -m nex.try_mic            # --list shows microphones, --device N picks one, --model base, --wav clip.wav
```

## Run
```bash
python -m venv .venv
.venv\Scripts\activate            # macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
python -m nex                     # open http://127.0.0.1:8000  (API docs: /docs)
```
The page at `/` is the **live session screen**: start, pause and stop, live transcript (partial and final), a badge on each recognized command, latency, slide number, mic level and a session summary (latency P50/P95, RTF). It works offline, with no CDN or web fonts.
The first session downloads the Whisper model once. After that NEX works offline.
- **Windows:** keys work out of the box. **macOS:** allow Terminal/Python under *Accessibility*.
- Click the presentation window once before speaking, because keys go to the focused window.
- `NEX_DRY_RUN=1` logs actions without pressing keys (for demos and tests).
- The server binds to `127.0.0.1` only, since it can press keys on the machine.

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
See `REQUIREMENTS_CHECK.md` for how the project maps to the final-project brief.

See `NEX_Step_by_Step_Guide.md` for the full project plan (report structure, user testing, AI usage log).

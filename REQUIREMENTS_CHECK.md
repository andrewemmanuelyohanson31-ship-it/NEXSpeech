# Requirements check: COMP6822001 Final Project brief vs. NEX

Checked against `20260907160650_FINAL_PROJECT_COMP6822001_Speech_Recognition.docx` (2026-11-16).
✅ = done in this repo · 👥 = **the team must do it** (it can't be coded, and faking it is misconduct under §21.6).

## Application (§1, §3, §10, §11, §17: worth 30% under LO-4)
| Requirement | Status | Where |
|---|---|---|
| Continuous microphone/audio stream input | ✅ | `nex/audio.py`: 16 kHz mono, 0.25 s blocks |
| Audio streaming + preprocessing | ✅ | Resampling to 16 kHz mono at capture, noise calibration, energy-based speech detection (`nex/asr.py`). Whisper computes the log-Mel features itself |
| Local ASR inference, **no external API** | ✅ | faster-whisper, CPU int8. The model downloads once from Hugging Face, then runs offline. The page loads nothing external |
| Inference **during** speech, partial transcription | ✅ | A partial about every 1 s while speaking (adaptive throttle on slow CPUs) |
| Transcription updates as speech continues | ✅ | Partial → final per utterance. Live page and `nex.try_mic` |
| No "record → upload → wait" workflow | ✅ | Streaming throughout |
| Real-time transcription displayed to the user | ✅ | `frontend/index.html` (live page) and `python -m nex.try_mic` (terminal) |
| Explain latency/responsiveness | ✅ tool / 👥 write-up | Shown live, stored per session (P50/P95, RTF), and measured offline by `eval/run_eval.py` |
| Solves the real problem (hands-free slide control) | ✅ | Speech-to-action (`nex/commands.py`) + key presses (`nex/keys.py`) |

## Technical evaluation (§12–14: worth 20% under LO-2)
| Requirement | Status | Where |
|---|---|---|
| Baseline + at least 1 experimental condition | ✅ tool / 👥 run it | `eval/record.py` (conditions: baseline, speed, mic, speaker), `eval/add_noise.py` (E1 noise at SNR 20/10/5 dB), `--model`, `--language`, `--chunk-s` |
| WER = (S+D+I)/N | ✅ | `eval/run_eval.py`, per condition and per clip |
| Real-time metric | ✅ | Latency P50/P95 (on a simulated live clock, so backlog is included) and RTF |
| Command accuracy and false triggers (specific to NEX) | ✅ | `run_eval.py` |
| Error analysis examples | ✅ tool / 👥 interpret | `eval/results/<model>_clips.csv`: reference, output and S/D/I per clip |
| **Recordings of real speakers** | 👥 | Record 5 or more people (with consent). The text-to-speech numbers in the README only prove the pipeline works |

## Real problem, real users, user testing (§4–9: worth 5% + 20%)
| Requirement | Status | Notes |
|---|---|---|
| Concrete target user and problem | 👥 | Interview real presenters (guide, Step 1). Example: "BINUS students who present with slides and have to walk back to the laptop" |
| Usage scenario | 👥 | Classroom, laptop or clip-on mic, Indonesian with some English |
| Testing with **5 or more real target users** (not the team) | 👥 | Tasks in guide Step 13. The live page makes NEX usable by non-technical testers |
| Observation + questionnaire/interview | 👥 tool ready | Ratings on the Review screen (1–5). Store them via `POST /api/feedback`, or use a paper/Google form |
| Feedback linked to the technical results | 👥 | Example: "users said X" → error table shows Y → change Z → re-test |

## Report and evidence (§15–16)
| Requirement | Status | Notes |
|---|---|---|
| Report structure, sections 1–8 | 👥 | The guide's Step 14 maps each section to its source |
| Screenshots | 👥 | Take them from the live page and the terminal tool |
| Architecture diagram | ✅ | README / guide (copy into the report) |
| Experimental results, WER, latency, transcription examples | ✅ tools / 👥 run | `eval/` |
| User testing results and feedback analysis | 👥 | |

## AI usage (§21: worth 10%)
| Requirement | Status | Notes |
|---|---|---|
| AI Usage Log | 👥 | **Most of this backend, the evaluation tools and the live page were written with Claude (Claude Code).** Log it honestly, with how you verified it (69 automated tests, real-mic smoke test, your own experiments) |
| Be able to explain the code (§21.3) | 👥 | Each member should be able to explain: the streaming loop (`asr.py`), the 3 command rules (`commands.py`), how latency and WER are measured (`run_eval.py`) |
| AI Usage Declaration | 👥 | Paste the §21.8 text at the end of the report |

## Known limits (put them in the Discussion section)
- On a CPU-only i7-8700, only `tiny` is real-time (small: about 4.6 s per command). Whisper tiny is weak on Indonesian, so measure it.
- Commands need a short pause before and after them (trade-off for 0 false triggers on explanation phrases).
- Keys go to the focused window, so the presenter must click the slideshow once.
- Jumping to a slide by number in Canva hasn't been tested. `jump_mode: "arrows"` is the fallback.
- Not built: the Naskah, Riwayat, Lab and Pengaturan pages (the API for them exists) and script following.

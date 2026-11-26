# NEX: Progress Report

Course: COMP6822001 Speech Recognition, Final Project
Brief: `20260907160650_FINAL_PROJECT_COMP6822001_Speech_Recognition.docx`
Date: 16 November 2026

## What NEX is
- A real-time speech recognition app that changes presentation slides by voice
- Commands: "next / lanjut" for the next slide, "back / balik / previous" for the previous slide, "slide 2 / slide dua" to jump
- Runs fully on the laptop, with no cloud speech API
- Target users: students and lecturers who present with slides and don't want to walk back to the laptop or rely on a friend to click

## What the brief requires
- A working real-time application
  - continuous microphone input
  - local speech recognition model, no external API
  - partial transcription while the user is still speaking
  - transcription shown to the user, with latency explained
- A real problem and a real, identified target user
- Technical evaluation
  - a baseline and at least one experimental condition (noise, speakers, speed, microphone, accent, audio quality)
  - Word Error Rate (WER)
  - at least one real-time metric (latency, response time, real-time factor)
  - error analysis with examples
- User testing
  - at least 5 real target users
  - realistic tasks, observation, and a questionnaire or interview
  - feedback analyzed and linked to the technical results
- A technical report in 8 sections, with evidence (screenshots, architecture diagram, results, feedback)
- AI usage: an honest log, verification of AI output, a declaration, and the ability to explain the code

## Done
- Real-time pipeline
  - microphone streamed in 0.25 s blocks at 16 kHz mono
  - room noise measured for 2 s at the start, then speech detected by loudness
  - partial text about every 1 s while speaking, final text after 0.6 s of silence
  - partials slow down automatically on weak CPUs, so the app never falls behind
- Local speech recognition
  - faster-whisper (Whisper tiny, base, small or medium) on CPU
  - the model downloads once, then works offline
  - filter that drops Whisper's made-up text during silence
- Speech-to-action model
  - turns each finished sentence into next, previous, go to slide N, or nothing
  - works in Indonesian and English, including "slide dua belas" = 12
  - the progress deck's commands: "slide pertama", "slide terakhir", "stop / berhenti" (pause listening), "mulai" (listen again)
  - "kembali" on its own is deliberately NOT a command (it's too common in normal speech); use "balik", "back" or "slide sebelumnya"
  - tolerates small recognition mistakes, e.g. "lanjud" → lanjut
- Protection against accidental slide changes in long talks
  - the whole sentence must be a command, not just contain a command word
  - everyday words (selanjutnya, berikutnya, kembali, sebelumnya, maju, mundur) only count together with "slide"
  - the tail of a long sentence that was cut at 8 s never triggers anything
  - 20 common explanation phrases are tested to never move a slide
- Slide control
  - presses the right/left arrow keys, or types the number and Enter, in the presentation app
  - an arrow-only mode for apps that can't jump by number
  - a dry-run mode that presses no keys, for testing
- Backend server (FastAPI)
  - live events to the browser (partial, final, command, state, mic level)
  - endpoints for sessions, scripts (naskah), history, user feedback and settings
  - accessible from this computer only, because it can press keys
  - stores text only, never audio
- Live session web page
  - start, pause and stop
  - live transcript with a label on every recognized command
  - latency, slide number, timer and mic level
  - session summary at the end (latency P50/P95, real-time factor)
  - works offline
- Terminal test tool (`python -m nex.try_mic`)
  - shows what you said, what NEX would do, and how long it took
  - can replay a recording instead of using the microphone
- Evaluation tools
  - record test clips per speaker and condition
  - add background noise at a chosen level (experiment E1)
  - measure WER (with substitutions, deletions and insertions), command accuracy, false triggers per 10 minutes, latency P50/P95 and real-time factor
  - per-clip results file for the error analysis table
- Tests and documentation
  - 96 automated tests, including a full voice session with a simulated microphone
  - README, step-by-step guide, and this report

## Partly done / in progress
- Web UI from the Figma design
  - done: the live session page
  - not built yet: Home, Naskah, Riwayat, Review, Lab Evaluasi, Pengaturan (their backend endpoints already exist)
- Voice commands on the live page with a real voice
  - checked so far: the browser display, manual buttons, the summary, and real model output in the terminal
  - still to do: a team member says "lanjut" into the live page
- Presentation apps
  - not yet tried with real keys in PowerPoint, Google Slides or Canva
  - jumping to a slide by number in Canva is unconfirmed
- Choosing the model
  - measured on one laptop (i7-8700, CPU only)
  - tiny is real-time (about 1.1 s per command), base is borderline (about 1.8 s), small is too slow (about 4.6 s)
  - each team laptop should be measured, because results will differ
- Script following (moving to the next slide automatically at the end of the slide's script)
  - planned, not started

## Still needed (team only: cannot be coded, and faking it is academic misconduct)
- Interview real presenters to confirm the problem and the target user
- Write the usage scenario (classroom, microphone type, language mix)
- Record test clips from at least 5 real speakers, with consent
  - baseline condition
  - at least one experimental condition (noise, speaking speed or microphone)
- Run the evaluation on those recordings and write the error analysis
- Compare settings, e.g. tiny vs. base, Indonesian vs. auto-detected language
- Run user testing with at least 5 real presenters who are not on the team
  - tasks: move forward, go back, jump to a slide, give a 2-minute talk with no commands
  - observe and take notes
  - questionnaire with 1–5 ratings: ease of use, responsiveness, transcription quality, overall satisfaction
- Link user feedback to the technical results, then improve and re-test
- Write the technical report (sections 1–8), with screenshots and results
- AI usage
  - fill in the AI Usage Log; most of the code was written with Claude (Claude Code), so say so
  - describe how it was verified: automated tests, real microphone test, the team's own experiments
  - every member should be able to explain the streaming loop, the command rules, and how latency and WER are measured
  - add the AI Usage Declaration at the end of the report

## Known limits (for the Discussion section)
- Commands need a short pause before and after them
- Keys go to the focused window, so the presenter must click the slideshow once
- Whisper tiny is weaker on Indonesian than the larger models
- With the language set to Indonesian, the larger models sometimes translated English speech into Indonesian
- The numbers shown in the Figma design are placeholders and must not be used as results
- Measurements so far used computer-generated speech, which only proves the pipeline works and is not report data

## Suggested next steps, in order
- Each member runs `python -m nex.try_mic` and the live page with their own voice
- Try PowerPoint and Google Slides with real key presses
- Interview presenters and fix the target user statement
- Record the speaker test set and run the evaluation
- User testing with 5 or more presenters
- Write the report and the AI usage log

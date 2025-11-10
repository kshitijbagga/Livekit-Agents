# LiveKit Voice Interruption Handler — Detailed Documentation  
**Author:** Kshitij Bagga  
**Purpose:** Submission for the SalesCode.ai Final Round Qualifier (Voice Interruption Handling Challenge)

---

## 1. Executive Summary

This project adds a non-intrusive, runtime extension to LiveKit Agents that discriminates between **meaningless filler speech** (e.g., "uh", "umm", "hmm", "haan") and **genuine user interruptions** (e.g., "stop", "wait", "hold on"). The extension prevents the agent from needlessly pausing its TTS when only fillers are detected while preserving immediate responsiveness to real commands. The solution is implemented as an external layer that intercepts ASR/transcription events and decides whether to treat the event as a valid interruption or to ignore it.

---

## 2. Objective & Requirements (from the challenge)

- **Ignore specific filler words or phrases only when the agent is currently speaking.**
- **Register those same words as valid user speech when the agent is quiet.**
- **Keep real-time responsiveness**: genuine user commands must interrupt immediately.
- **Make no changes to LiveKit’s base VAD algorithm** — implement the logic in an extension layer only.
- **Allow dynamic configuration of the filler list** (environment/runtime). Aim to be language-agnostic and scalable.
- **Log ignored vs valid interruptions** for debugging and evaluation.

This README explains precisely what was changed/added to satisfy each of the above points.

---

## 3. What changed — high level

1. **New interruption-handling module** — encapsulates filler detection, confidence thresholding, dynamic update of ignore list, and logging.
2. **Integration into the agent runtime** — transcription events are intercepted and routed through the handler before any TTS pause or action is taken.
3. **Non-invasive changes** — LiveKit core code (VAD and SDK) remains unchanged; the handler is attached using the event/callback mechanism provided by the SDK.
4. **Testing/demo script** — a lightweight script allows reviewers to run deterministic tests without spinning up the full LiveKit environment.
5. **Requirements and environment guidance** — `requirements.txt` updated for Windows-compatible development and instructions for dependency installation are provided.
6. **Documentation** — this file (README.md) fully documents design, configuration, usage, and testing procedures.

---

## 4. New files added & purpose (explicit file-level explanation)

> Note: filenames are referenced below. Each description explains *what the file does*, *how it is used*, and *why it is needed*.

### `agents/extensions/interrupt_handler.py` — core logic
- **Purpose:** Implements the `InterruptHandler` class which receives ASR transcription text and confidence and decides whether to treat it as a valid interruption or ignore it when the agent is speaking.
- **Key capabilities:**
  - `ignored_words` configuration (defaults to `['uh', 'umm', 'hmm', 'haan']`).
  - `confidence_threshold` config to ignore low-confidence ASR results.
  - `handle_transcription(transcript, agent_speaking, confidence)` async method returning `True` for a valid interruption (should stop TTS) or `False` for ignored filler.
  - `update_ignored_words(new_list)` method for dynamic updates at runtime.
  - Structured logging (separates ignored events from valid interruptions).
- **Rationale:** Centralizing interruption logic keeps it testable, modular, and independent from the rest of the agent code.

### `drivethru_agent.py` — integrated agent (modified)
- **Purpose:** The main agent entrypoint used in the challenge. It was extended to integrate the `InterruptHandler`.
- **What changed inside:**
  - `InterruptHandler` is instantiated in the entrypoint and passed into the `DriveThruAgent`.
  - A transcription callback (`session.on("transcription")`) is registered to funnel ASR transcripts to the `on_transcription_event` method on the agent.
  - `DriveThruAgent` now contains `on_transcription_event(transcript, confidence, session)` which:
    - Uses `session.is_tts_active()` or `session.is_speaking()` (depending on API availability) to determine whether the agent is speaking.
    - Calls `InterruptHandler.handle_transcription(...)`.
    - If the result is a valid interruption and the agent is speaking, triggers `session.stop_tts()` (or equivalent) to immediately pause/switch off TTS.
    - Otherwise logs the ignored filler and continues speaking.
- **Why modified:** This ties the extension into the live event loop without touching the LiveKit internals, satisfying the “extension layer only” requirement.

### `examples/voice_agent_interrupt.py` — demo/test script
- **Purpose:** A simple, deterministic script that imports `InterruptHandler` and runs a series of test cases (input text, agent speaking flag, confidence) to demonstrate expected behavior.
- **Why included:** Reviewers and developers can validate the logic quickly without booting a LiveKit session. Useful for unit-like manual testing and CI sanity checks.

### `requirements.txt` — Windows-compatible deps
- **Purpose:** Contains dependency versions that are compatible on Windows (avoids `bithuman` which lacks Windows wheels). This prevents installation failures and simplifies local testing.
- **Why changed:** The upstream dependency graph included platform-specific wheels; the trimmed requirements make local development smooth for the challenge.

---

## 5. Detailed behavior & decision rules

`InterruptHandler.handle_transcription(transcript, agent_speaking, confidence)` implements the following decision tree:

1. **Normalize input** — trim whitespace and convert to lowercase.
2. **Low-confidence filter** — if `confidence < confidence_threshold`, ignore (returns `False`). Rationale: ASR low-confidence results are likely noise.
3. **Empty / whitespace** — ignore (returns `False`).
4. **Agent speaking?**
   - **Yes:** check if the transcription is composed entirely of known filler tokens. If *all* tokens are fillers, ignore (returns `False`). If any token is not filler (e.g., "umm stop" or "umm okay stop"), treat as valid interrupt (returns `True`).
   - **No (agent is silent):** treat the transcription as normal speech (returns `True`), even if composed of filler tokens. Rationale: users speaking when agent is silent should be registered as potential inputs.
5. **Logging:** Each decision is logged:
   - `INFO` for valid interruptions (includes the transcript).
   - `DEBUG` for ignored filler/low-confidence results (includes transcript and reason).

This logic preserves conversational flow while ensuring the agent is responsive to real user intent.

---

## 6. Integration points & how the handler is wired into LiveKit

- **Where the handler plugs in:** At the ASR transcription event listener already available in the `AgentSession`. The code registers:
  ```py
  @session.on("transcription")
  async def _on_transcript(event):
      await agent.on_transcription_event(
          transcript=event.text,
          confidence=getattr(event, "confidence", 1.0),
          session=session,
      )

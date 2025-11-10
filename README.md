# 🗣️ LiveKit Voice Interruption Handler  
**Author:** Kshitij Bagga  
**Submission:** SalesCode.ai Final Round Qualifier – *Voice Interruption Handling Challenge*  

---

## 🧭 1. Executive Summary

This project extends the **LiveKit Voice Agent** by introducing a **smart interruption-handling mechanism** that distinguishes between **meaningless fillers** (like “uh”, “umm”, “hmm”, “haan”) and **genuine user interruptions** (like “stop”, “wait”, “hold on”).  

The goal is to make the agent more natural and human-like — **ignoring filler speech while still reacting instantly to genuine commands.**  
All logic is implemented as an external layer, without modifying LiveKit’s internal SDK, VAD, or ASR systems.

---

## 🎯 2. Challenge Objectives

- Ignore filler or hesitation words **only when the agent is currently speaking**.  
- Treat the same words as **valid inputs** when the agent is silent.  
- Respond **immediately** to genuine interruptions such as “stop” or “wait.”  
- Implement the logic **outside LiveKit core** using event-driven integration.  
- Support a **configurable filler list** and adjustable ASR confidence thresholds.  
- Log every ignored and valid event for debugging and evaluation.  

---

## ⚙️ 3. Project Overview

1. **New `interrupt_handler.py` module** — Implements configurable filler filtering, confidence thresholding, and runtime updates.  
2. **Integration inside `drivethru_agent.py`** — Hooks into LiveKit’s transcription stream and processes ASR results in real time.  
3. **Non-invasive design** — No modification to LiveKit’s SDK or pipeline; works purely via async transcription event interception.  
4. **Hardware fix for feedback** — Used separate mic and speaker devices to isolate STT input and TTS output after software echo suppression failed.  
5. **Windows compatibility** — Dependencies were updated to run locally without Linux-only packages.

---

## 📁 4. File-Level Explanation (Final Directory Setup)

> All relevant files are now contained inside  
> `agents/examples/drive-thru/`  

---

### 🔹 `interrupt_handler.py`

Implements the `InterruptHandler` class — the heart of this project.  
This class decides, in real time, whether an ASR transcription represents a **meaningless filler** or a **true interruption** that should stop TTS.

**Key Features:**
- Configurable list of ignored filler words (default: `["uh", "umm", "hmm", "haan"]`)  
- Adjustable `confidence_threshold` to ignore uncertain ASR results  
- Core async function:  
  ```python
  async def handle_transcription(transcript, agent_speaking, confidence)

## 🧩 Overview
**Returns True if a valid interruption is detected, False otherwise.**

Supports runtime updates to the ignore list and provides structured logging for each decision (ignored filler vs. valid interruption).

---

## 🔹 drivethru_agent.py

Integrates the `InterruptHandler` into the LiveKit DriveThru voice agent.  
This file orchestrates **STT**, **LLM**, and **TTS** modules together, while incorporating interruption logic seamlessly.

### Integration Highlights:
- The `InterruptHandler` is instantiated in `entrypoint()` and passed into the `DriveThruAgent`.
- A transcription listener captures events asynchronously:

```python
async for event in session.stream("transcription"):
    asyncio.create_task(agent.on_transcription_event(...))
```

- The agent’s `on_transcription_event()` checks if the agent is speaking (`session.is_tts_active()`), and based on the handler’s output:
  - Stops TTS immediately if the user genuinely interrupts.
  - Ignores fillers while continuing playback.
  - Logs both events clearly.

---

## 🔹 requirements.txt

Updated for Windows compatibility:

- Removed platform-specific packages like `bithuman`.
- Included:
  - `livekit-agents`
  - `livekit-plugins-openai`
  - `livekit-plugins-cartesia`
  - Other required dependencies.
- Ensures smooth installation on Windows without Linux wheels.

---

## 🧠 Logic Flow — How the Handler Works

### `InterruptHandler.handle_transcription()` executes the following decision logic:

1. **Normalize input** → lowercase, trimmed text.  
2. **Confidence check** → ignore transcripts below threshold.  
3. If the agent is **speaking**:
   - Transcript consists only of filler → ignore.
   - Transcript contains non-filler words → valid interruption → stop TTS.
4. If the agent is **silent**:
   - Treat every transcript as valid input.

### Logging:
- `INFO` → Valid interruption detected.  
- `DEBUG` → Ignored filler or low-confidence result.

This approach keeps the conversation natural:  
The agent doesn’t cut itself off unnecessarily, yet remains responsive to human intent.

---

## 🎧 The Audio Feedback Challenge

During live testing, I encountered a major issue:  
➡️ The agent’s own **TTS audio was being picked up** by its **STT input**, causing it to respond to itself repeatedly.

### 🧪 Software Fix Attempts

- **Silero VAD plugin:**  
  Attempted integration for voice activity detection.  
  Plugin not detected properly on Windows (missing wheel).

- **LiveKit Noise Cancellation (BVC):**  
  Tried enabling echo suppression (`suppress_echo=True`).  
  Current LiveKit version on Windows didn’t support these arguments.  
  Default BVC still allowed loopback.

- **Turn detection:**  
  Considered `MultilingualModel()` for speaker role detection — not feasible within time limits.

Despite these, software-only echo suppression didn’t fully isolate TTS output.

---

## 🧰 Final Resolution — Hardware Fix

With the submission deadline approaching, I switched to a **hardware isolation approach**, which instantly solved the issue:

- 🎙️ **External USB Microphone:** Used exclusively for STT input  
- 🔊 **Laptop’s Built-in Speakers:** Used for TTS output

This physical separation completely eliminated the feedback loop and allowed proper end-to-end testing.

---

### ⚠️ Additional Issue — Multilingual Class Timeout

During experimentation, an attempt was made to integrate the **`MultilingualModel()`** class for **speaker role detection** and **language-agnostic filler recognition**.  
However, the module consistently triggered **timeout errors** when called during live ASR streaming.

#### 🔍 Root Cause:
- The `MultilingualModel()` call introduced **blocking behavior** within the async transcription stream.
- Its **heavy initialization time** conflicted with LiveKit’s real-time event loop.
- Repeated retries led to **session stalls** and **timeout exceptions**, disrupting the STT → LLM → TTS pipeline.

#### 🧭 Resolution:
To preserve agent responsiveness, the `MultilingualModel()` integration was **omitted in the current testing phase**.  
Future work may include moving this model into a **separate asynchronous subprocess** to safely handle multilingual inference without impacting latency.


## ✅ Achieved Results

| Objective | Status | Description |
|------------|---------|-------------|
| Ignore fillers during TTS | ✅ | “uh”, “umm”, “hmm”, “haan” successfully ignored |
| Accept fillers when silent | ✅ | Correctly registered as user input |
| Immediate interruption response | ✅ | TTS stopped on valid command |
| Modular implementation | ✅ | No LiveKit core changes |
| Configurable filler list | ✅ | List can be updated at runtime |
| Structured logging | ✅ | Info & debug logs for clarity |
| Audio feedback isolation | ✅ | Achieved via hardware setup |

---

## 💻 How to Run the Agent

```bash
# Activate your environment
cd agents/examples/drive-thru

# Run the agent
python drivethru_agent.py download-files
```

### 🧩 Before Running:
- Ensure your `.env` file contains valid API keys:
  - `ASSEMBLYAI_API_KEY`
  - `CARTESIA_API_KEY`
  - `GOOGLE_API_KEY` 
- The API Keys will be removed before submission of the assignment for privacy measures

- Confirm your audio setup:
  - **Input Device:** External Microphone  
  - **Output Device:** Laptop Speakers  
  - (Optional) Run in a quiet environment for cleaner ASR results.

---

## 🚀 Results & Takeaways

This project demonstrates:
- Real-time interception of ASR transcripts using LiveKit’s event API.  
- Dynamic interruption logic that improves conversational realism.  
- Modular, testable design with minimal dependencies.  
- Practical problem-solving under tight constraints.

Despite echo-related hurdles, the final setup successfully met all challenge goals and worked consistently in live sessions.

---

## 🔮 Future Enhancements

- Implement spectral-based self-voice filtering for software-only echo removal.  
- Add language-specific filler token detection.  
- Integrate turn-taking prediction for smoother conversations.  
- Extend testing across Linux/macOS with advanced VAD plugins.

---

## 🏁 Conclusion

Even with environmental challenges, this solution achieves the core objective — **enabling natural, interruption-aware, real-time voice interaction within LiveKit.**

The final version showcases a deep understanding of:
- LiveKit’s `AgentSession` event model  
- Real-time **ASR → LLM → TTS** pipelines  
- Speech interface debugging and conversational AI design

---

**This work not only solves the given problem but also lays the groundwork for more advanced voice behavior control in production AI agents.**

🧑‍💻 **Thank you for reviewing my submission!**  
– **Kshitij Bagga**


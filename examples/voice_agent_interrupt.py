# examples/voice_agent_interrupt.py

import asyncio
from agents.extensions.interrupt_handler import InterruptHandler

async def main():
    handler = InterruptHandler()

    tests = [
        ("umm", True, 0.9),
        ("hmm yeah", True, 0.95),
        ("stop", True, 0.9),
        ("umm okay stop", True, 0.9),
        ("umm", False, 0.9),
        ("got it", False, 0.9),
        ("", True, 0.5),
        ("haan haan", True, 0.7),
        ("please pause", True, 0.8),
        ("uh", True, 0.4),
        ("got it", True, 0.7),
        ("theek hai", True, 0.9),
        ("hold on", True, 0.95),
        ("umm hmm", True, 0.85),
        ("wait a minute", True, 0.9),
        ("stop", False, 0.95),
        ("wait a second", True, 0.6)
    ]

    for text, speaking, conf in tests:
        result = await handler.handle_transcription(text, speaking, conf)
        print(f"Input: '{text}' | Agent Speaking: {speaking} | Valid Interrupt: {result}")

if __name__ == "__main__":
    asyncio.run(main())

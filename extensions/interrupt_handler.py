# agents/extensions/interrupt_handler.py

import asyncio
import logging

class InterruptHandler:
    """
    Handles filler-word interruption logic for LiveKit Agents.
    Filters out meaningless fillers while the agent is speaking,
    but allows real user commands to interrupt instantly.
    """

    def __init__(self, ignored_words=None, confidence_threshold=0.6):
        self.ignored_words = ignored_words or ['uh', 'umm', 'hmm', 'haan', 'theek', 'got it', 'okay', 'yeah', 'alright', 'uhh', 'huh', 'mm', 'mmhmm', 'hmm yeah']
        self.confidence_threshold = confidence_threshold
        self.logger = logging.getLogger("InterruptHandler")

    async def handle_transcription(self, transcript, agent_speaking, confidence=1.0):
        """
        Decide whether to ignore or act upon user speech.
        Returns True if it’s a valid interruption, False if ignored.
        """
        text = transcript.strip().lower()

        if not text or confidence < self.confidence_threshold:
            self.logger.debug(f"Ignored low-confidence speech: {text}")
            return False

        if agent_speaking and all(word in self.ignored_words for word in text.split()):
            self.logger.info(f"Ignored filler while agent speaking: '{text}'")
            return False

        self.logger.info(f"Valid user interruption: '{text}'")
        return True

    def update_ignored_words(self, new_list):
        """Optional: Dynamically update filler words."""
        self.ignored_words = new_list
        self.logger.info(f"Updated ignored word list: {self.ignored_words}")

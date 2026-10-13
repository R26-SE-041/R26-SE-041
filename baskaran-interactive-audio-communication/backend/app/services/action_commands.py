"""Bounded action commands; browser playback never needs an LLM call."""
import re


def parse_generation(command):
    text = re.sub(r"\s+", " ", command.strip().lower()).rstrip(".!?")
    text = re.sub(r"^(?:please |(?:can|could|would) you )", "", text)
    text = text.replace("one minute", "one-minute").replace("flash cards", "flashcards")
    if text == "create flashcards from this document and save them":
        return {"intent": "flashcards"}
    if text == "create an audio revision of this section only and save it":
        return {"intent": "audio_revision", "scope": "section"}
    if text == "create a one-minute audio revision and save it":
        return {"intent": "audio_revision", "style": "one_minute", "target_duration": 60}
    if text == "create a detailed audio revision and save it":
        return {"intent": "audio_revision", "style": "detailed"}
    match = re.fullmatch(r"create an audio revision in (tamil|sinhala|english) and save it", text)
    if match:
        return {"intent": "audio_revision", "language": match[1]}
    return None

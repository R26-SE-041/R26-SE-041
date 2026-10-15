"""Conservative Unicode word-loop detection, shared with the Modal generator.

This rejects degenerate output, not ordinary repeated subject words. It does
not trim text or claim to assess factual correctness.
"""
import unicodedata


def has_repetition_loop(text: str) -> bool:
    normalized = unicodedata.normalize("NFC", text).casefold()
    # Preserve combining marks: Python's \w splits Sinhala/Tamil words.
    words = "".join(
        char if unicodedata.category(char)[0] in "LMN" else " "
        for char in normalized
    ).split()
    # Six identical words, or four consecutive copies of a 2–8 word phrase.
    for width in range(1, 9):
        copies = 6 if width == 1 else 4
        span = width * copies
        for start in range(len(words) - span + 1):
            phrase = words[start:start + width]
            if words[start:start + span] == phrase * copies:
                return True
    return False


def require_usable_answer(answer: str) -> str:
    if not isinstance(answer, str) or not answer.strip() or has_repetition_loop(answer):
        raise ValueError("The generated answer was incomplete or repetitive. Please retry your question.")
    return answer.strip()

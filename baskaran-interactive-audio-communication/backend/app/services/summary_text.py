"""Normalize summary model artifacts and produce a readable plain-text export."""

import re


def clean_summary(text: str) -> str:
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL | re.IGNORECASE).strip()
    # Observed output contains a standalone model channel label before the title.
    # Do not remove occurrences of 'thought' inside document sentences.
    text = re.sub(r"\Athought\s*\r?\n", "", text, flags=re.IGNORECASE).strip()
    return text


def plain_summary(text: str) -> str:
    text = clean_summary(text)
    text = re.sub(r"^[ \t]*```[^\n]*$", "", text, flags=re.MULTILINE)
    text = re.sub(r"^[ \t]{0,3}#{1,6}[ \t]+", "", text, flags=re.MULTILINE)
    text = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r"\1 (\2)", text)
    text = re.sub(r"\*\*(.+?)\*\*", r"\1", text)
    text = re.sub(r"__(.+?)__", r"\1", text)
    text = re.sub(r"`([^`\n]+)`", r"\1", text)
    text = re.sub(r"(?<!\w)\*([^*\n]+)\*(?!\w)", r"\1", text)
    text = re.sub(r"^([ \t]*)\*[ \t]+", r"\1- ", text, flags=re.MULTILINE)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()

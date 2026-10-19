"""Recognize a complete top-level JSON response without stopping at nested braces."""
import json


def complete_json_object(text: str) -> bool:
    start = text.find("{")
    if start < 0:
        return False
    try:
        value, _ = json.JSONDecoder().raw_decode(text[start:])
    except ValueError:
        return False
    return isinstance(value, dict)

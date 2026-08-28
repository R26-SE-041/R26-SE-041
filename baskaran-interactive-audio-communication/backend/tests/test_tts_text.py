from app.services.tts_text import prepare_mixed_tts_text


def test_prepare_mixed_tts_text_strips_english_words():
    """English words in Tamil text must be removed — TTS reads Tamil only."""
    source = "* **Chocolate:** இதில் உள்ள theobromine நாய்களுக்கு நஞ்சாகும்."

    result = prepare_mixed_tts_text(source)

    # English words "Chocolate" and "theobromine" must be gone
    assert "Chocolate" not in result
    assert "theobromine" not in result
    # Tamil content must remain
    assert "நாய்களுக்கு" in result
    assert "நஞ்சாகும்" in result


def test_prepare_mixed_tts_text_removes_visual_markup_and_urls():
    source = "## பதில்\n- [Kidney failure](https://example.com) ஏற்படலாம்.\n- **கவனம்** தேவை [1]."

    result = prepare_mixed_tts_text(source)

    # English words and URL must be gone
    assert "http" not in result
    assert "Kidney" not in result
    assert "failure" not in result
    assert "*" not in result
    # Tamil content must remain
    assert "ஏற்படலாம்" in result
    assert "கவனம்" in result
    assert "தேவை" in result


def test_prepare_mixed_tts_text_strips_latin_unicode_accents():
    """Accented Latin characters are still Latin-script — must be stripped."""
    source = "Café மற்றும் red blood cells"

    result = prepare_mixed_tts_text(source)

    assert "Caf" not in result
    assert "red" not in result
    assert "மற்றும்" in result


def test_prepare_mixed_tts_text_strips_parenthesised_english():
    """English words inside parentheses must be stripped along with parens."""
    source = (
        "நஞ்சான உணவு வகைகள்:\n"
        "● சாக்லேட் (Chocolate)\n"
        "● திராட்சை (Grapes and Raisins)\n"
        "● வெங்காயம் மற்றும் பூண்டு (Onions and Garlic)"
    )

    result = prepare_mixed_tts_text(source)

    assert "Chocolate" not in result
    assert "Grapes" not in result
    assert "Raisins" not in result
    assert "Onions" not in result
    assert "Garlic" not in result
    # Tamil content must remain
    assert "சாக்லேட்" in result
    assert "திராட்சை" in result
    assert "வெங்காயம்" in result
    assert "பூண்டு" in result


from app.services.tts_text import prepare_mixed_tts_text


def test_prepare_mixed_tts_text_keeps_tamil_and_english_words():
    source = "* **Chocolate:** இதில் உள்ள theobromine நாய்களுக்கு நஞ்சாகும்."

    assert prepare_mixed_tts_text(source) == (
        "Chocolate: இதில் உள்ள theobromine நாய்களுக்கு நஞ்சாகும்."
    )


def test_prepare_mixed_tts_text_removes_visual_markup_and_urls():
    source = "## பதில்\n- [Kidney failure](https://example.com) ஏற்படலாம்.\n- **கவனம்** தேவை [1]."

    result = prepare_mixed_tts_text(source)

    assert result == "பதில். Kidney failure ஏற்படலாம். கவனம் தேவை."
    assert "http" not in result
    assert "*" not in result


def test_prepare_mixed_tts_text_normalizes_unicode_without_transliterating():
    source = "Cafe\u0301 மற்றும் red blood cells"

    assert prepare_mixed_tts_text(source) == "Café மற்றும் red blood cells"


def test_prepare_mixed_tts_text_turns_filled_circle_bullets_into_boundaries():
    source = (
        "நஞ்சான உணவு வகைகள்:\n"
        "● சாக்லேட் (Chocolate)\n"
        "● திராட்சை (Grapes and Raisins)\n"
        "● வெங்காயம் மற்றும் பூண்டு (Onions and Garlic)"
    )

    assert prepare_mixed_tts_text(source) == (
        "நஞ்சான உணவு வகைகள். சாக்லேட் (Chocolate). "
        "திராட்சை (Grapes and Raisins). "
        "வெங்காயம் மற்றும் பூண்டு (Onions and Garlic)"
    )

"""Unit coverage for the Mode B TTS-only normalizer (no model download needed)."""

from app.services.mixed_tts_phonetics import normalize_mixed_text_for_indicf5


def test_technical_mixed_text_keeps_tamil_and_replaces_known_words():
    original = "Artificial Intelligence பயன்படுத்தி difficult topics-ஐ simple ஆக explain பண்ணலாம்."
    normalized = normalize_mixed_text_for_indicf5(original)

    assert normalized == "ஆர்டிஃபிஷியல் இன்டெலிஜென்ஸ் பயன்படுத்தி டிஃபிகல்ட் டாபிக்ஸ்-ஐ சிம்பிள் ஆக எக்ஸ்ப்ளெயின் பண்ணலாம்."
    assert original.startswith("Artificial")  # normalizer never mutates caller input


def test_mixed_tokens_keep_tamil_suffixes_numbers_and_punctuation():
    text = "Chocolate-ல் உள்ள theobromine, GPT-4 மற்றும் cloud-based systems 2.0 பற்றி."
    assert normalize_mixed_text_for_indicf5(text) == (
        "சாக்லேட்-ல் உள்ள தியோப்ரோமைன், ஜி பி டி 4 மற்றும் கிளவுட்-பேஸ்ட் சிஸ்டம்ஸ் 2.0 பற்றி."
    )


def test_pure_tamil_and_unlisted_acronyms_are_safe():
    assert normalize_mixed_text_for_indicf5("இது தமிழ் மட்டும்.") == "இது தமிழ் மட்டும்."
    assert normalize_mixed_text_for_indicf5("XYZ-ஐ பயன்படுத்தவும்.") == "எக்ஸ் வை ஸெட்-ஐ பயன்படுத்தவும்."

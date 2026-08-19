"""No-network tests for the isolated Sinhala mixed-TTS preprocessing layer."""
import pytest

from app.services.sinhala_mixed_phonetics import SinhalaMixedPhonetics


@pytest.mark.asyncio
async def test_pure_sinhala_skips_gemma(tmp_path):
    calls: list[str] = []

    result = await SinhalaMixedPhonetics(str(tmp_path / "cache.sqlite3")).preprocess("මම අද පාසලට ගියා.")
    assert result.phonetic_text == "මම අද පාසලට ගියා."
    assert calls == []


@pytest.mark.asyncio
async def test_dictionary_and_longest_phrase_priority(tmp_path):
    result = await SinhalaMixedPhonetics(str(tmp_path / "cache.sqlite3")).preprocess("Artificial Intelligence සහ school")
    assert result.phonetic_text == "ආර්ටිෆිෂල් ඉන්ටලිජන්ස් සහ ස්කූල්"
    assert [span.source for span in result.spans] == ["dictionary", "dictionary"]


@pytest.mark.asyncio
async def test_valid_g2p_result_is_persisted_and_reused(tmp_path, monkeypatch):
    calls: list[str] = []

    def g2p(span: str):
        calls.append(span)
        return "සයිබර් සිකියුරිටි", "espeak"

    monkeypatch.setattr("app.services.sinhala_mixed_phonetics.convert_english_to_sinhala", g2p)

    cache = str(tmp_path / "cache.sqlite3")
    first = await SinhalaMixedPhonetics(cache).preprocess("cybersecurity ගැන")
    second = await SinhalaMixedPhonetics(cache).preprocess("cybersecurity ගැන")
    assert first.spans[0].source == "espeak"
    assert second.spans[0].source == "cache"
    assert calls == ["cybersecurity"]

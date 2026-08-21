"""Regression checks for the final English Kokoro-82M TTS route."""

import ast
from pathlib import Path


BACKEND = Path(__file__).resolve().parents[1]
ENDPOINT = BACKEND / "modal_endpoints" / "english_kokoro_tts.py"
MODAL_CLIENT = BACKEND / "app" / "services" / "modal_client.py"
CONFIG = BACKEND / "app" / "core" / "config.py"


def _source(path: Path) -> str:
    return path.read_text(encoding="utf-8-sig")


def test_kokoro_is_the_only_final_english_endpoint() -> None:
    source = _source(ENDPOINT)
    ast.parse(source)

    assert 'MODEL_ID = "hexgrad/Kokoro-82M"' in source
    assert 'DEFAULT_VOICE = "af_heart"' in source
    assert 'SAMPLE_RATE = 24_000' in source
    assert "ParlerTTSForConditionalGeneration" not in source
    assert not (ENDPOINT.parent / "english_parler_tts.py").exists()


def test_english_client_sends_kokoro_voice_and_speed() -> None:
    source = _source(MODAL_CLIENT)
    function = next(
        node
        for node in ast.parse(source).body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name == "call_english_tts"
    )
    function_source = ast.get_source_segment(source, function) or ""

    assert "settings.modal_english_kokoro_tts_url" in function_source
    assert "settings.modal_english_tts_url" not in function_source
    assert "settings.english_tts_voice" in function_source
    assert "settings.english_tts_speed" in function_source
    assert '"voice": effective_voice' in function_source
    assert '"speed": effective_speed' in function_source
    assert "description" not in function_source
    assert "english_parler_tts.py" not in function_source


def test_kokoro_defaults_are_configurable() -> None:
    source = _source(CONFIG)

    assert 'modal_english_kokoro_tts_url: str = ""' in source
    assert 'english_tts_voice: str = "af_heart"' in source
    assert "english_tts_speed: float = 1.0" in source
    assert "english_tts_default_description" not in source

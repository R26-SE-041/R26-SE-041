"""Regressions for the separately deployed Modal TTS endpoint."""

import ast
from pathlib import Path
import re
import unicodedata
from typing import List, Literal, NamedTuple


TTS_ENDPOINT = (
    Path(__file__).resolve().parents[1]
    / "modal_endpoints"
    / "indic_parler_mixed_tts.py"
)

NATURALNESS_TEST_CASES = {
    "pure_tamil": "இது மாணவர்களுக்கு தெளிவான தமிழ் விளக்கத்தை வழங்குகிறது.",
    "one_acronym": "இந்த AI மூலம் மாணவர்களின் கேள்விகளுக்கு சரியான பதில் கிடைக்கிறது.",
    "technical_terms": (
        "இந்த AI model ஒரு PDF ஆவணத்தை GPU மூலம் ஆய்வு செய்து RAG மற்றும் API "
        "உதவியுடன் பதில் தருகிறது."
    ),
    "meaningful_phrase": (
        "இந்த machine learning model மாணவர்களின் கேள்விகளைப் புரிந்து சரியான "
        "பதிலை வழங்குகிறது."
    ),
    "multi_bullet": (
        "# RAG விளக்கம்\n"
        "- AI மாணவரின் கேள்வியை முதலில் புரிந்துகொள்கிறது.\n"
        "- retrieval augmented generation சரியான ஆவணப் பகுதிகளைத் தேடுகிறது.\n"
        "- ChromaDB context தகவலை சேமித்து மீட்டெடுக்கிறது.\n"
        "- machine learning model கிடைத்த ஆதாரத்தின் அடிப்படையில் பதிலை உருவாக்குகிறது.\n"
        "- இறுதியில் TTS தமிழ் மற்றும் English சொற்களை இயல்பாகப் பேசுகிறது."
    ),
    "long_realistic": (
        "VoiceLearn மாணவர்கள் பதிவேற்றிய PDF ஆவணங்களிலிருந்து தேவையான தகவலை "
        "RAG முறையில் தேடுகிறது. முதலில் ASR மாணவரின் பேச்சை text ஆக மாற்றுகிறது. "
        "பின்னர் ChromaDB மற்றும் reranker தொடர்புடைய பகுதிகளைத் தேர்ந்தெடுக்கின்றன. "
        "machine learning model அந்த ஆதாரங்களை மட்டும் பயன்படுத்தி தெளிவான தமிழ் "
        "பதிலை உருவாக்குகிறது. இறுதியாக TTS அதே பதிலை இயல்பான குரலில் வாசிக்கிறது."
    ),
}


def _source_and_tree() -> tuple[str, ast.Module]:
    source = TTS_ENDPOINT.read_text(encoding="utf-8-sig")
    return source, ast.parse(source)


def _segmentation_namespace() -> dict:
    source, tree = _source_and_tree()
    wanted = {
        "SpeechSegment",
        "_clean_prompt_text",
        "_chunk_clean_text",
        "_chunk_mixed_text",
        "_split_language_runs",
        "_language_segments",
    }
    nodes = [
        node
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.ClassDef)) and node.name in wanted
    ]
    constants = [
        node
        for node in tree.body
        if isinstance(node, ast.Assign)
        and any(
            isinstance(target, ast.Name)
            and target.id in {
                "MAX_CHUNK_WORDS",
                "MAX_CHUNK_CHARS",
                "_SENTENCE_SPLIT_RE",
                "_TAMIL_RE",
                "_LANGUAGE_TOKEN_RE",
            }
            for target in node.targets
        )
    ]
    namespace = {
        "re": re,
        "unicodedata": unicodedata,
        "List": List,
        "Literal": Literal,
        "NamedTuple": NamedTuple,
    }
    exec(compile(ast.Module(body=constants + nodes, type_ignores=[]), str(TTS_ENDPOINT), "exec"), namespace)
    return namespace


def test_short_embedded_english_tokens_stay_with_jaya():
    split_runs = _segmentation_namespace()["_split_language_runs"]
    segments = split_runs("இந்த AI ML GPU model மூலம் பதில் கிடைக்கும்.")

    assert [segment.language for segment in segments] == ["tamil"]
    assert "AI ML GPU model" in segments[0].text
    assert segments[-1].ends_chunk is True
    assert all(segment.text.strip() for segment in segments)


def test_meaningful_embedded_english_phrases_keep_sentence_level_jaya():
    split_runs = _segmentation_namespace()["_split_language_runs"]

    for phrase in (
        "Artificial Intelligence",
        "machine learning model",
        "retrieval augmented generation",
    ):
        segments = split_runs(f"இந்த {phrase} மூலம் பதில் கிடைக்கும்.")
        assert [segment.language for segment in segments] == ["tamil"]
        assert phrase in segments[0].text

    english_only = split_runs("retrieval augmented generation finds relevant context.")
    assert [segment.language for segment in english_only] == ["english"]


def test_punctuation_and_numbers_never_create_standalone_segments():
    split_runs = _segmentation_namespace()["_split_language_runs"]
    segments = split_runs("தமிழ் (AI), 2026: RAG!")

    assert [segment.language for segment in segments] == ["tamil"]
    assert "AI" in segments[0].text and "RAG" in segments[0].text
    assert split_runs("...?!") == []
    numeric = split_runs("2026.")
    assert len(numeric) == 1 and numeric[0].language == "tamil"


def test_bullet_chunks_remain_independent_and_complete():
    namespace = _segmentation_namespace()
    text = "# தலைப்பு\n- முதல் bullet AI.\n- இரண்டாம் bullet RAG.\n- மூன்றாம் முடிவு."
    chunks = namespace["_chunk_mixed_text"](text)
    segments = namespace["_language_segments"](chunks)

    assert len(chunks) == 4
    assert sum(segment.ends_chunk for segment in segments) == len(chunks)
    assert "".join(segment.text for segment in segments).count("முதல்") == 1
    assert "".join(segment.text for segment in segments).count("இரண்டாம்") == 1
    assert "".join(segment.text for segment in segments).count("மூன்றாம்") == 1


def test_five_required_answer_shapes_preserve_routing_and_chunk_completeness():
    namespace = _segmentation_namespace()

    results = []
    for text in NATURALNESS_TEST_CASES.values():
        chunks = namespace["_chunk_mixed_text"](text)
        segments = namespace["_language_segments"](chunks)
        generate_calls = (len(segments) + 4 - 1) // 4

        assert chunks
        assert segments
        assert sum(segment.ends_chunk for segment in segments) == len(chunks)
        assert generate_calls <= len(segments)
        results.append(segments)

    assert [segment.language for segment in results[0]] == ["tamil"]
    assert [segment.language for segment in results[1]] == ["tamil"]
    assert all(segment.language == "tamil" for segment in results[2])
    assert all(segment.language == "tamil" for segment in results[3])
    assert all(segment.language == "tamil" for segment in results[4])
    assert all(segment.language == "tamil" for segment in results[5])


def test_synthesize_uses_one_batched_generate_path_and_audio_lengths():
    source, tree = _source_and_tree()
    synthesize = next(
        node
        for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name == "synthesize"
    )
    generate_calls = [
        node
        for node in ast.walk(synthesize)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "generate"
    ]

    assert len(generate_calls) == 1
    assert "padding=True" in source
    assert "return_dict_in_generate=True" in source
    assert "raw_audio_length = generation.audios_length[index]" in source
    assert 'hasattr(raw_audio_length, "item")' in source
    assert "GENERATION_BATCH_SIZE = 1" in source
    assert "LANGUAGE_SWITCH_PAUSE_SECONDS = 0.03" in source


def test_generated_waveform_is_always_one_dimensional_before_concatenation():
    source, _ = _source_and_tree()

    assert ".reshape(-1)" in source
    assert "if audio.size <= 1:" in source


def test_required_latency_diagnostics_do_not_log_prompt_content():
    source, _ = _source_and_tree()

    for label in (
        "preprocess",
        "chunking",
        "chunks",
        "language_segments",
        "generate_calls",
        "concat",
        "normalize/resample",
        "TOTAL",
    ):
        assert f"[TTS-LATENCY] {label}" in source
    assert "chunk[:60]" not in source

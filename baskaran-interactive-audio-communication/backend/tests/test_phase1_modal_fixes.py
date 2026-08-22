"""Regression coverage for the dependency-facing Phase 1 fixes."""

import ast
import re
from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parents[1]


def test_modal_qwen_endpoint_has_no_unsupported_num_beams_argument():
    source = (BACKEND_ROOT / "modal_endpoints" / "tamil_asr_qwen3.py").read_text(encoding="utf-8-sig")
    tree = ast.parse(source)
    transcribe_calls = [
        node for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "transcribe"
    ]
    assert len(transcribe_calls) == 1
    assert {kw.arg for kw in transcribe_calls[0].keywords} == {"audio"}
    assert all("num_beams" not in {kw.arg for kw in call.keywords} for call in transcribe_calls)


def test_modal_qwen_endpoint_pins_numpy_to_compatible_1_x_release():
    source = (BACKEND_ROOT / "modal_endpoints" / "tamil_asr_qwen3.py").read_text(encoding="utf-8-sig")
    tree = ast.parse(source)
    pip_installs = [
        node for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "pip_install"
    ]

    assert len(pip_installs) == 1
    dependencies = [
        arg.value for arg in pip_installs[0].args
        if isinstance(arg, ast.Constant) and isinstance(arg.value, str)
    ]
    numpy_dependencies = [dep for dep in dependencies if re.match(r"^numpy(?:[<>=!~]|$)", dep)]
    assert numpy_dependencies == ["numpy==1.26.4"]


def test_modal_qwen_startup_logs_numpy_and_torch_versions():
    source = (BACKEND_ROOT / "modal_endpoints" / "tamil_asr_qwen3.py").read_text(encoding="utf-8-sig")

    assert "numpy={np.__version__} torch={torch.__version__}" in source


def test_modal_qwen_success_response_schema_is_unchanged():
    source = (BACKEND_ROOT / "modal_endpoints" / "tamil_asr_qwen3.py").read_text(encoding="utf-8-sig")
    tree = ast.parse(source)
    response_key_sets = [
        {key.value for key in node.value.keys if isinstance(key, ast.Constant)}
        for node in ast.walk(tree)
        if isinstance(node, ast.Return) and isinstance(node.value, ast.Dict)
    ]

    assert {"transcript", "detected_language", "duration_ms"} in response_key_sets


def test_bge_reranker_uses_existing_persistent_model_volume():
    source = (BACKEND_ROOT / "modal_endpoints" / "bge_retrieval.py").read_text(encoding="utf-8-sig")
    tree = ast.parse(source)
    cross_encoder_calls = [
        node for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "CrossEncoder"
    ]

    assert len(cross_encoder_calls) == 1
    keywords = {kw.arg: kw.value for kw in cross_encoder_calls[0].keywords}
    assert isinstance(keywords["cache_folder"], ast.Name)
    assert keywords["cache_folder"].id == "MODELS_DIR"
    assert 'MODELS_DIR = "/bge_models"' in source
    assert 'Volume.from_name("voicelearn-bge-models"' in source
    assert "bge_volume.commit()" in source


def test_bge_image_uses_secure_torch_and_numpy_1_abi():
    source = (BACKEND_ROOT / "modal_endpoints" / "bge_retrieval.py").read_text(encoding="utf-8-sig")
    tree = ast.parse(source)
    pip_installs = [
        node for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "pip_install"
    ]

    assert len(pip_installs) == 1
    dependencies = {
        arg.value for arg in pip_installs[0].args
        if isinstance(arg, ast.Constant) and isinstance(arg.value, str)
    }
    assert "torch==2.6.0" in dependencies
    assert "numpy>=1.26,<2" in dependencies

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
    assert "cache_folder" not in keywords
    assert isinstance(keywords["cache_dir"], ast.Name)
    assert keywords["cache_dir"].id == "MODELS_DIR"
    assert isinstance(keywords["local_files_only"], ast.Constant)
    assert keywords["local_files_only"].value is True
    assert 'MODELS_DIR = "/bge_models"' in source
    assert 'Volume.from_name("voicelearn-bge-models"' in source
    assert "bge_volume.commit()" in source


def test_bge_reranker_scales_to_zero_without_parallel_replicas():
    source = (BACKEND_ROOT / "modal_endpoints" / "bge_retrieval.py").read_text(encoding="utf-8-sig")
    tree = ast.parse(source)
    reranker_class = next(
        node for node in tree.body
        if isinstance(node, ast.ClassDef) and node.name == "BGEReranker"
    )
    decorator = next(
        item for item in reranker_class.decorator_list
        if isinstance(item, ast.Call)
        and isinstance(item.func, ast.Attribute)
        and item.func.attr == "cls"
    )
    keywords = {kw.arg: kw.value for kw in decorator.keywords}
    assert keywords["min_containers"].value == 0
    assert keywords["max_containers"].value == 1
    assert keywords["buffer_containers"].value == 0
    assert keywords["scaledown_window"].value == 60


def test_bge_reranker_cache_step_is_cpu_only():
    source = (BACKEND_ROOT / "modal_endpoints" / "bge_retrieval.py").read_text(encoding="utf-8-sig")
    tree = ast.parse(source)
    cache_function = next(
        node for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name == "cache_reranker_model"
    )
    decorator = next(
        item for item in cache_function.decorator_list
        if isinstance(item, ast.Call)
        and isinstance(item.func, ast.Attribute)
        and item.func.attr == "function"
    )
    keywords = {kw.arg: kw.value for kw in decorator.keywords}
    assert "gpu" not in keywords
    assert keywords["cpu"].value == 2.0


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

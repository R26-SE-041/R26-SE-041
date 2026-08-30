"""Regression checks for the dedicated base and fine-tuned Gemma endpoints."""

import ast
from pathlib import Path


ENDPOINT = (
    Path(__file__).resolve().parents[1]
    / "modal_endpoints"
    / "gemma_answer_generator.py"
)


def _source_and_tree() -> tuple[str, ast.Module]:
    source = ENDPOINT.read_text(encoding="utf-8-sig")
    return source, ast.parse(source)


def test_v2_validates_adapter_metadata_against_canonical_model_id() -> None:
    source, tree = _source_and_tree()
    assignments = {
        node.targets[0].id: node.value.value
        for node in tree.body
        if isinstance(node, ast.Assign)
        and len(node.targets) == 1
        and isinstance(node.targets[0], ast.Name)
        and isinstance(node.value, ast.Constant)
        and isinstance(node.value.value, str)
    }

    assert assignments["_BASE_MODEL_CANONICAL_ID"] == "google/gemma-4-12B-it"
    assert 'adapter_config.get("base_model_name_or_path") != _BASE_MODEL_CANONICAL_ID' in source
    assert 'adapter_config.get("base_model_name_or_path") != _BASE_MODEL_PATH' not in source


def test_models_load_from_the_local_modal_volume_path() -> None:
    source, _ = _source_and_tree()

    assert '"VOICELEARN_GEMMA_BASE_PATH"' in source
    assert '"/models/gemma/base"' in source
    assert source.count("AutoModelForMultimodalLM.from_pretrained(\n            _BASE_MODEL_PATH") == 2


def test_finetuned_container_stays_warm_for_follow_up_questions() -> None:
    _, tree = _source_and_tree()
    v2_class = next(
        node
        for node in tree.body
        if isinstance(node, ast.ClassDef) and node.name == "FineTunedGemmaV2Answer"
    )
    decorator = next(
        item
        for item in v2_class.decorator_list
        if isinstance(item, ast.Call)
        and isinstance(item.func, ast.Attribute)
        and item.func.attr == "cls"
    )
    keywords = {keyword.arg: keyword.value for keyword in decorator.keywords}

    assert keywords["min_containers"].value == 0
    assert keywords["max_containers"].value == 1
    assert keywords["scaledown_window"].value == 600

"""The document answer deployment contains only the base model service."""
import ast
from pathlib import Path
ENDPOINT=Path(__file__).resolve().parents[1]/"modal_endpoints"/"gemma_answer_generator.py"

def test_answer_service_is_isolated_and_has_only_the_base_model():
    source=ENDPOINT.read_text(encoding="utf-8")
    tree=ast.parse(source)
    classes={node.name for node in tree.body if isinstance(node,ast.ClassDef)}
    assert classes == {"AnswerRequest", "_GemmaAnswerBase", "BaseGemmaAnswer"}
    assert '_APP_NAME = "voicelearn-document-gemma"' in source
    assert '"/models/gemma/base"' in source
    assert 'local_files_only=True' in source
    assert '/gemma/adapters/' not in source

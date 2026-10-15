import ast
from contextlib import nullcontext
from pathlib import Path
import sys
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.services import answer_quality
from app.services.answer_quality import has_repetition_loop, require_usable_answer


@pytest.mark.parametrize("text", [
    "බල්ලන්ගේ ඉතිහාසය. " + "සුනඛ " * 40,
    "බල්ලන්ගේ ඉතිහාසය. " + "පුරාණ සුනඛ වර්ග " * 6,
    "வரலாறு. " + "நாய்கள் " * 12,
    "Dogs evolved from wolves. " + "the same phrase " * 6,
])
def test_rejects_unicode_word_and_phrase_loops(text):
    assert has_repetition_loop(text)
    with pytest.raises(ValueError):
        require_usable_answer(text)


@pytest.mark.parametrize("text", [
    "බල්ලන් වෘකයන්ගෙන් පරිණාමය විය. මිනිසුන් සමඟ ජීවත් වීමට හුරු වූහ.",
    "නැහැ නැහැ නැහැ. බල්ලන්ගේ ඉතිහාසය පිළිබඳ ලේඛනය කියවන්න.",
    "Dogs share ancestry with wolves. Dogs lived near humans. Dogs were domesticated.",
    "force = mass times acceleration; force changes when mass changes.",
])
def test_keeps_normal_answers_and_legitimate_repeated_subjects(text):
    assert require_usable_answer(text) == text


def _generator(monkeypatch, outputs):
    """Execute the deployed generation method with a fake GPU/model/tokenizer."""
    from app.services import answer_quality
    monkeypatch.setitem(sys.modules, "answer_quality", answer_quality)
    monkeypatch.setitem(sys.modules, "torch", SimpleNamespace(inference_mode=nullcontext))
    monkeypatch.setitem(sys.modules, "transformers", SimpleNamespace(
        StoppingCriteria=object, StoppingCriteriaList=list,
    ))
    source = Path(__file__).resolve().parents[1] / "modal_endpoints/gemma_answer_generator.py"
    tree = ast.parse(source.read_text(encoding="utf-8"))
    nodes = [node for node in tree.body if getattr(node, "name", "") in {"_messages", "_GemmaAnswerBase"}]
    namespace = {"AnswerRequest": object, "_BASE_MODEL_CANONICAL_ID": "test-base"}
    exec(compile(ast.Module(body=nodes, type_ignores=[]), str(source), "exec"), namespace)
    class Inputs(dict):
        def to(self, device):
            return self
    class Tokens(list):
        @property
        def shape(self):
            return (1, len(self[0]))
    class Processor:
        tokenizer = SimpleNamespace(eos_token_id=0)
        def apply_chat_template(self, *args, **kwargs):
            self.messages = args[0]
            return Inputs(input_ids=Tokens([[0]]))
        def decode(self, tokens, **kwargs):
            return outputs[tokens[0]]
    calls = []
    def generate(**kwargs):
        calls.append(kwargs)
        return [[0, len(calls) - 1]]
    instance = namespace["_GemmaAnswerBase"]()
    instance.processor = Processor()
    instance.model = SimpleNamespace(device="cpu", generate=generate)
    payload = SimpleNamespace(language="sinhala", query="බල්ලන්ගේ ඉතිහාසය", context=["Dogs descended from wolves."],
                              tutor_instructions="", memento=None, route="document_rag_base")
    return instance, payload, calls, Tokens


def test_generator_stops_loop_and_retries_once_on_same_grounded_input(monkeypatch):
    good = "බල්ලන් වෘකයන්ගෙන් පරිණාමය විය."
    instance, payload, calls, Tokens = _generator(monkeypatch, ["සුනඛ " * 60, good])
    result = instance._generate(payload, document_only=True)
    assert result["answer"] == good
    assert len(calls) == 2
    assert calls[0]["input_ids"] is calls[1]["input_ids"]
    assert calls[1]["max_new_tokens"] < calls[0]["max_new_tokens"]
    assert calls[0]["repetition_penalty"] > 1
    # Exercise early stopping with a decoded loop after 32 generated tokens.
    assert calls[0]["stopping_criteria"][0](Tokens([[0] + [0] * 32]), None)


def test_generator_healthy_answer_uses_only_one_model_call(monkeypatch):
    instance, payload, calls, _ = _generator(monkeypatch, ["බල්ලන් වෘකයන්ගෙන් පරිණාමය විය."])
    instance._generate(payload, document_only=True)
    assert len(calls) == 1
    prompt = instance.processor.messages[0]["content"]
    assert "natural, simple Sinhala" in prompt
    assert "mechanically transliterating" in prompt
    assert "Use ONLY" in prompt


def test_generator_never_returns_corrupt_text_after_bounded_retry(monkeypatch):
    instance, payload, calls, _ = _generator(monkeypatch, ["සුනඛ " * 60] * 2)
    with pytest.raises(HTTPException) as exc:
        instance._generate(payload, document_only=True)
    assert exc.value.status_code == 502
    assert len(calls) == 2

def test_structured_generator_allows_repeated_schema_keys(monkeypatch):
    instance, payload, calls, _ = _generator(monkeypatch, ['{"sections":[{"id":0,"title":"Cats","script":"Cats are mammals."}]}'])
    payload.response_format='json_object'
    instance._generate(payload,document_only=True)
    assert len(calls)==1
    assert calls[0]['no_repeat_ngram_size']==0
    assert calls[0]['repetition_penalty']==1.0
    assert calls[0]['max_new_tokens']==1600
    prompt=instance.processor.messages[0]['content']
    assert 'complete, valid JSON object' in prompt
    assert 'few short sentences or bullets' not in prompt

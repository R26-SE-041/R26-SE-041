"""Deterministic, credit-safe routing for VoiceLearn answer generation."""

from __future__ import annotations

from dataclasses import dataclass
import re


DOCUMENT_RAG_BASE = "document_rag_base"
MUSCLE_FINETUNED_V2 = "muscle_finetuned_v2"
GENERAL_BASE = "general_base"

# Each stem below names a muscle the LoRA adapter was trained on, but several
# of them also begin the name of a muscle it was NOT trained on: "biceps" opens
# both biceps brachii (trained) and biceps femoris (a hamstring), "triceps"
# opens triceps surae (the calf), "pectoralis" opens pectoralis minor, and
# "deltoid" is also the name of an ankle ligament. Making the qualifier optional
# without excluding the wrong ones sends out-of-domain questions to the adapter
# on an A100-80GB, which is both a wrong answer and a real cost.
#
# So each stem carries a negative lookahead for the qualifiers that disqualify
# it. The bare stem still matches — students routinely write "the biceps" — but
# an explicit wrong qualifier no longer does.
_MUSCLE_PATTERN = re.compile(
    r"\b(?:"
    r"pectoralis(?!\s+minor)(?:\s+major)?|pecs?|"
    r"deltoids?(?!\s+ligament)|delts?|"
    r"biceps?(?!\s+femoris)(?:\s+brachii)?|"
    r"triceps?(?!\s+surae)(?:\s+brachii)?|"
    r"quadriceps(?:\s+femoris)?|quads?"
    r")\b",
    re.IGNORECASE,
)

# The five muscle names as students write them in Tamil and Sinhala. Without
# these, a Tamil-script question about the pectoralis major routes to the base
# model and never reaches the adapter trained for it — a silent failure of the
# multilingual promise, since the English-script path works fine.
_MUSCLE_PATTERN_INDIC = re.compile(
    r"(?:பெக்டோரலிஸ்|டெல்டாய்டு|பைசெப்ஸ்|டிரைசெப்ஸ்|குவாட்ரிசெப்ஸ்"
    r"|පෙක්ටෝරාලිස්|ඩෙල්ටොයිඩ්|බයිසෙප්ස්|ට්‍රයිසෙප්ස්|ක්වඩ්‍රිසෙප්ස්)",
)

# A memento resolves a follow-up only while the student is still on the same
# subject. The original pattern recognised a topic change only when the turn
# opened with one of three set phrases, so ordinary redirections — "forget that,
# what is glycolysis?" — kept the stale memento and routed anatomy questions
# that were not anatomy questions. These markers are checked anywhere in the
# turn, because "let's talk about X instead" puts the signal at the end.
_NEW_TOPIC_PATTERN = re.compile(
    r"^\s*(?:new\s+topic|topic\s+change|switch\s+topic|change\s+of\s+topic)\s*[:,-]?"
    r"|\b(?:forget\s+(?:that|it|this)|never\s+mind|nevermind|moving\s+on"
    r"|let'?s\s+(?:talk\s+about|move\s+on|switch)|instead\s*[.?!]?\s*$"
    r"|different\s+(?:topic|question|subject))\b",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class RouteDecision:
    name: str
    reason: str


def is_five_muscle_question(question: str) -> bool:
    """Match only the five LoRA-trained muscle domains and their normal variants.

    Covers the Latin nomenclature, the colloquial short forms students actually
    speak (pecs, delts, quads) and the singular misspellings ASR produces
    (bicep, tricep), in English, Tamil and Sinhala script — while excluding the
    similarly-named muscles the adapter was never trained on.
    """
    return bool(
        _MUSCLE_PATTERN.search(question)
        or _MUSCLE_PATTERN_INDIC.search(question)
    )


def choose_answer_route(
    question: str,
    *,
    document_grounded: bool,
    memento: dict | None = None,
) -> RouteDecision:
    """Select a route without retrieval or a model call.

    A document request always wins.  A short-lived memento can resolve an
    explicit follow-up only; it cannot turn a clearly new topic into anatomy.
    """
    if document_grounded:
        return RouteDecision(DOCUMENT_RAG_BASE, "explicit_document_context")

    if is_five_muscle_question(question):
        return RouteDecision(MUSCLE_FINETUNED_V2, "five_muscle_match")

    previous_question = str((memento or {}).get("previous_question") or "")
    if (
        memento
        and not _NEW_TOPIC_PATTERN.search(question)
        and is_five_muscle_question(previous_question)
    ):
        return RouteDecision(MUSCLE_FINETUNED_V2, "muscle_followup_from_session")

    return RouteDecision(GENERAL_BASE, "general_query")

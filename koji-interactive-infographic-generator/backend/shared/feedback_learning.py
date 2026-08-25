"""Turn repeated preference pairs into reviewable, agent-scoped memory candidates.

Only controlled reason codes are converted to lessons. Free-form comments remain
evidence in the database and are never promoted into model instructions.
"""

from __future__ import annotations

import hashlib
from collections import defaultdict
from typing import Any


LESSONS: dict[str, dict[str, str]] = {
    "prompt-agent": {
        "meaning_changed": "Preserve the user's original learning objective and all correct constraints during enhancement.",
        "not_visual": "Translate abstract requests into concrete composition, hierarchy, label, and reading-order instructions.",
        "too_verbose": "Keep enhanced prompts concise while retaining educational and visual requirements.",
        "factually_incorrect": "Do not add facts unless they are supported by the request or reliable educational context.",
        "wrong_level": "Match terminology and detail to the learner level stated by the user.",
    },
    "prompt-anatomy": {
        "wrong_view": "Preserve the user's requested anatomical view, section, direction, and laterality exactly.",
        "missing_structure": "Preserve every explicitly requested anatomical structure in the specification.",
        "extra_structure": "Do not add neighboring organs or anatomical structures the user did not request.",
        "labels_requested": "Keep the generated anatomy base image free of text, labels, arrows, and callouts.",
        "background_not_white": "Compile anatomy prompts with a white or very light neutral background.",
        "inaccurate_anatomy": "Prefer medically accurate anatomy and avoid unsupported structural claims.",
        "wrong_detail_level": "Match anatomical detail and terminology to the requested learner level.",
    },
    "prompt-generic": {
        "subject_changed": "Preserve the user's requested subject and action during prompt enhancement.",
        "wrong_style": "Preserve the visual style explicitly requested by the user.",
        "poor_composition": "Add concise composition guidance only when it improves the requested image.",
        "missing_detail": "Retain every explicit visual detail from the user's request.",
        "too_verbose": "Keep generic image prompts concise and avoid decorative prompt padding.",
    },
    "image-agent": {
        "bad_labels": "For labeled diagrams, prioritize legible text, clear leader lines, and non-overlapping label placement.",
        "poor_layout": "Use clear visual hierarchy, balanced spacing, and an unambiguous reading order.",
        "wrong_content": "Keep every depicted component aligned with the approved generation prompt.",
        "wrong_style": "Preserve the visual style explicitly requested by the user during regeneration.",
        "inaccurate_diagram": "Prioritize scientifically accurate relationships over decorative detail.",
    },
    "interactive-agent": {
        "wrong_region": "Ground the answer only in the selected region and state uncertainty when the selection is ambiguous.",
        "incorrect_explanation": "Use visible evidence and verified retrieval context without inventing unseen details.",
        "too_complex": "Match explanation depth and terminology to the user's question and learner level.",
        "not_useful": "Explain the selected concept's role and relationship to the overall educational image.",
    },
    "eval-agent": {
        "wrong_score": "Calibrate scores against visible evidence and keep visual and pedagogical criteria independent.",
        "missed_error": "Explicitly inspect label legibility, factual relationships, and prompt completeness before scoring.",
        "unhelpful_feedback": "Return a concrete correction that the generating agent can apply on its next attempt.",
    },
    "threed-agent": {
        "bad_geometry": "Preserve the main subject silhouette and reject visibly incomplete geometry.",
        "bad_texture": "Keep texture aligned with the source image and reject missing or corrupted texture output.",
        "wrong_subject": "Preserve the source image's primary subject during 2D-to-3D conversion.",
    },
}


def enrich_preference_pair(pair_id: str) -> dict[str, Any]:
    """Embed a completed pair and update authenticated personal preferences."""
    from shared.db import (
        get_preference_pair_learning_evidence,
        update_preference_pair_embedding,
        upsert_user_preference,
    )
    from shared.rag import embed

    evidence = get_preference_pair_learning_evidence(pair_id)
    if not evidence:
        raise ValueError(f"Unknown preference pair: {pair_id}")
    agent_name = str(evidence["agent_name"])
    negative_reasons = [str(item) for item in evidence.get("negative_reasons") or []]
    positive_reasons = [str(item) for item in evidence.get("positive_reasons") or []]
    input_context = evidence.get("input_context") or {}
    topic = " ".join(
        str(input_context.get(key) or "")[:300]
        for key in ("raw_prompt", "prompt", "question", "mode")
        if input_context.get(key)
    ).strip()
    context_text = (
        f"Agent: {agent_name}. Context: {topic or 'unspecified educational request'}. "
        f"Rejected because: {', '.join(negative_reasons)}. "
        f"Preferred retry qualities: {', '.join(positive_reasons) or 'accepted correction'}."
    )
    update_preference_pair_embedding(pair_id, context_text, embed(context_text))

    personal_results = []
    auth_user_id = evidence.get("auth_user_id")
    if auth_user_id:
        for reason in negative_reasons:
            lesson = LESSONS.get(agent_name, {}).get(reason)
            if not lesson:
                continue
            personal_results.append(upsert_user_preference(
                user_id=str(auth_user_id),
                agent_name=agent_name,
                preference_key=reason,
                content=f"User preference: {lesson}",
                embedding=embed(lesson),
                preference_pair_id=pair_id,
                metadata={"positive_reasons": positive_reasons, "source": "preference_pair"},
            ))
    return {
        "pair_id": pair_id,
        "embedded": True,
        "personal_preferences_updated": len(personal_results),
        "personal_results": personal_results,
    }


def backfill_preference_pair_embeddings(limit: int = 200) -> dict[str, Any]:
    """Retry deferred embeddings without preventing other weekly maintenance."""
    from shared.db import list_unembedded_preference_pair_ids

    completed = 0
    errors: list[str] = []
    pair_ids = list_unembedded_preference_pair_ids(limit)
    for pair_id in pair_ids:
        try:
            enrich_preference_pair(pair_id)
            completed += 1
        except Exception as exc:
            errors.append(f"{pair_id}: {type(exc).__name__}")
    return {"requested": len(pair_ids), "completed": completed, "errors": errors[:20]}


def consolidate_feedback_candidates(
    *,
    memento_min_pairs: int = 10,
    skill_min_pairs: int = 25,
    minimum_sessions: int = 3,
) -> list[dict[str, Any]]:
    """Create deterministic candidates; deployment still requires validation/review."""
    from shared.db import list_preference_reason_aggregates, upsert_agent_memory, upsert_memory_candidate
    from shared.rag import embed

    rows = list_preference_reason_aggregates(memento_min_pairs, minimum_sessions)
    candidates: list[dict[str, Any]] = []
    global_evidence: dict[str, list[dict[str, Any]]] = defaultdict(list)

    for row in rows:
        agent_name = str(row["agent_name"])
        reason = str(row["reason_code"])
        lesson = LESSONS.get(agent_name, {}).get(reason)
        if not lesson:
            continue
        evidence_count = int(row["evidence_count"])
        distinct_sessions = int(row["distinct_sessions"])
        confidence = min(0.99, 0.55 + min(evidence_count, 50) / 125 + min(distinct_sessions, 20) / 100)
        memory_type = "skill" if evidence_count >= skill_min_pairs and distinct_sessions >= 5 else "memento"
        fingerprint = hashlib.sha256(f"agent:{agent_name}:{memory_type}:{reason}".encode()).hexdigest()
        candidate = {
            "fingerprint": fingerprint,
            "scope": "agent",
            "agent_name": agent_name,
            "memory_type": memory_type,
            "lesson": lesson,
            "evidence_count": evidence_count,
            "distinct_sessions": distinct_sessions,
            "confidence": round(confidence, 4),
            "evidence_pair_ids": row.get("pair_ids") or [],
            "metadata": {
                "negative_reason": reason,
                "positive_reasons": row.get("positive_reasons") or [],
                "promotion_policy": "controlled-reason-preference-pairs",
            },
        }
        candidate["id"] = upsert_memory_candidate(candidate)
        candidate["agent_memory_id"] = upsert_agent_memory(
            fingerprint=fingerprint,
            scope="agent",
            agent_name=agent_name,
            memory_type=memory_type,
            content=lesson,
            embedding=embed(lesson),
            confidence=candidate["confidence"],
            evidence_count=evidence_count,
            source_candidate_id=candidate["id"],
            metadata=candidate["metadata"],
        )
        candidates.append(candidate)
        global_evidence[reason].append(candidate)

    # Cross-agent lessons remain proposals and require evidence from at least
    # three agents; this prevents one component's preference becoming global.
    for reason, evidence in global_evidence.items():
        if len({item["agent_name"] for item in evidence}) < 3:
            continue
        lesson = "Preserve the user's stated correction across regeneration without weakening safety or factual accuracy."
        pair_ids = [pair_id for item in evidence for pair_id in item["evidence_pair_ids"]][:100]
        candidate = {
            "fingerprint": hashlib.sha256(f"global:memento:{reason}".encode()).hexdigest(),
            "scope": "global",
            "agent_name": None,
            "memory_type": "memento",
            "lesson": lesson,
            "evidence_count": sum(item["evidence_count"] for item in evidence),
            "distinct_sessions": max(item["distinct_sessions"] for item in evidence),
            "confidence": min(item["confidence"] for item in evidence),
            "evidence_pair_ids": pair_ids,
            "metadata": {"negative_reason": reason, "source_agents": sorted(item["agent_name"] for item in evidence)},
        }
        candidate["id"] = upsert_memory_candidate(candidate)
        candidate["agent_memory_id"] = upsert_agent_memory(
            fingerprint=candidate["fingerprint"],
            scope="global",
            agent_name=None,
            memory_type="memento",
            content=lesson,
            embedding=embed(lesson),
            confidence=candidate["confidence"],
            evidence_count=candidate["evidence_count"],
            source_candidate_id=candidate["id"],
            metadata=candidate["metadata"],
        )
        candidates.append(candidate)
    return candidates

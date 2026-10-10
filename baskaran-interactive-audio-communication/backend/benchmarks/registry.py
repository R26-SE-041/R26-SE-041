"""Single source of truth for every benchmarked agent in the VoiceLearn pipeline.

Every fact here is read off the deployed code, not the README (whose GPU table
is stale — it still lists Llama 3.1 8B and Qwen2.5-3B, neither of which appears
in `backend/modal_endpoints/`).

`requested_gpu` is the string passed to `@app.cls(gpu=...)`. It is NOT the device
name a paper should cite: Modal's "A100-80GB" class reports as
`NVIDIA A100-SXM4-80GB`, "T4" as `Tesla T4`. The real name comes from the
`GET /gpu_info` endpoint added to each Modal class; `latency_bench.py` harvests it
from an already-warm container so it costs no extra GPU time.

`scaledown_window` is Modal's idle timeout. Benchmark calls are issued
back-to-back after one discarded warm-up so the container stays warm even when
the total batch duration exceeds this value.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Literal

# ── Fixed benchmark inputs ───────────────────────────────────────────────────
# One input per modality, held constant across every system so the latency
# numbers are comparable. Changing these invalidates previously collected runs.

BENCH_TEXT_EN = (
    "The pectoralis major is a thick fan-shaped muscle of the upper chest that "
    "adducts and medially rotates the humerus."
)
BENCH_TEXT_TA = (
    "பெக்டோரலிஸ் மேஜர் என்பது மார்பின் மேற்பகுதியில் உள்ள ஒரு தடிமனான "
    "விசிறி வடிவ தசை ஆகும்."
)
BENCH_TEXT_SI = (
    "පෙක්ටෝරාලිස් මේජර් යනු පපුවේ ඉහළ කොටසේ පිහිටි ඝන පංකා හැඩැති මාංශ පේශියකි."
)
BENCH_TEXT_MIXED = (
    "Pectoralis major muscle னு சொல்றது chest ல இருக்கிற ஒரு பெரிய தசை."
)

BENCH_QUERY = "What is the origin and insertion of the pectoralis major?"
BENCH_CONTEXT = [
    "The pectoralis major has a clavicular head arising from the medial half of "
    "the clavicle and a sternocostal head arising from the sternum and the "
    "upper six costal cartilages.",
    "Both heads converge and insert into the lateral lip of the intertubercular "
    "sulcus of the humerus via a bilaminar tendon.",
    "Its principal actions are adduction, flexion and medial rotation of the arm "
    "at the glenohumeral joint.",
    "Innervation is by the lateral and medial pectoral nerves, derived from the "
    "brachial plexus (C5-T1).",
    "The muscle is a common landmark in the anterior axillary fold.",
]
BENCH_EMBED_TEXTS = BENCH_CONTEXT + [BENCH_QUERY, BENCH_TEXT_TA, BENCH_TEXT_SI]

Modality = Literal["asr", "tts", "embed", "rerank", "llm"]


@dataclass(frozen=True)
class Agent:
    """One benchmarked inference service."""

    key: str                       # stable id used in output filenames
    stage: str                     # pipeline stage shown in the paper table
    model_id: str
    requested_gpu: str             # what @app.cls asked Modal for
    modality: Modality
    env_var: str                   # backend/.env key holding the endpoint URL
    scaledown_window_s: int        # warm window; batch must finish inside this
    source: str                    # file:line, for the paper's reproducibility note
    method: Literal["json", "multipart"] = "json"
    payload: dict[str, Any] | None = None
    audio_lang: str | None = None  # which fixture clip to POST (asr only)
    # Where the server reports its own inference time, if it does at all.
    server_time_key: str | None = None
    server_time_unit: Literal["ms", "s"] = "ms"
    notes: str = ""


AGENTS: list[Agent] = [
    # ── Speech-to-Text ───────────────────────────────────────────────────────
    Agent(
        key="asr_whisper_en",
        stage="ASR (English)",
        model_id="openai/whisper-large-v3 (faster-whisper, fp16)",
        requested_gpu="T4",
        modality="asr",
        env_var="MODAL_WHISPER_URL",
        scaledown_window_s=300,
        source="modal_endpoints/whisper_stt.py:84",
        method="multipart",
        payload={"language_hint": "english"},
        audio_lang="english",
        server_time_key="duration_ms",
    ),
    Agent(
        key="asr_whisper_mixed",
        stage="ASR (code-switch)",
        model_id="openai/whisper-large-v3 (faster-whisper, fp16)",
        requested_gpu="T4",
        modality="asr",
        env_var="MODAL_WHISPER_URL",
        scaledown_window_s=300,
        source="modal_endpoints/whisper_stt.py:84",
        method="multipart",
        payload={"language_hint": "mixed"},
        audio_lang="mixed",
        server_time_key="duration_ms",
        notes="Mixed mode runs an extra language-detection pass before decoding.",
    ),
    Agent(
        key="asr_tamil_qwen3",
        stage="ASR (Tamil)",
        model_id="osmapi/tamil-asr-qwen3 (bf16)",
        requested_gpu="A10G",
        modality="asr",
        env_var="MODAL_INDIC_STT_URL",
        scaledown_window_s=300,
        source="modal_endpoints/tamil_asr_qwen3.py:83",
        method="multipart",
        payload={"language_hint": "tamil"},
        audio_lang="tamil",
        server_time_key="duration_ms",
    ),
    Agent(
        key="asr_sinhala_whisper",
        stage="ASR (Sinhala)",
        model_id="Lingalingeswaran/whisper-small-sinhala (stage-2 FT, fp16)",
        requested_gpu="T4",
        modality="asr",
        env_var="MODAL_SINHALA_ASR_URL",
        scaledown_window_s=60,
        source="modal_endpoints/sinhala_whisper_asr.py:80",
        method="multipart",
        payload=None,
        audio_lang="sinhala",
        server_time_key="latency_ms",
        notes="60 s window — batch must run back-to-back with no pauses.",
    ),
    Agent(
        key="asr_indicconformer",
        stage="ASR baseline (IndicConformer)",
        model_id="ai4bharat/indic-conformer-600m-multilingual",
        requested_gpu="T4",
        modality="asr",
        env_var="MODAL_INDIC_CONFORMER_URL",
        scaledown_window_s=300,
        source="modal_endpoints/indic_stt.py:65",
        method="multipart",
        payload={"language_hint": "tamil"},
        audio_lang="tamil",
        server_time_key="duration_ms",
        notes="Baseline only — superseded by tamil-asr-qwen3. Not in .env; set "
              "MODAL_INDIC_CONFORMER_URL manually to benchmark it.",
    ),
    # ── Retrieval ────────────────────────────────────────────────────────────
    Agent(
        key="embed_bge_m3",
        stage="Retrieval — embedder",
        model_id="BAAI/bge-m3 (1024-D, normalised)",
        requested_gpu="T4",
        modality="embed",
        env_var="MODAL_BGE_EMBED_URL",
        scaledown_window_s=1200,
        source="modal_endpoints/bge_retrieval.py:117",
        payload={"texts": BENCH_EMBED_TEXTS, "normalize": True},
    ),
    Agent(
        key="rerank_bge_v2_m3",
        stage="Retrieval — reranker",
        model_id="BAAI/bge-reranker-v2-m3 (cross-encoder)",
        requested_gpu="T4",
        modality="rerank",
        env_var="MODAL_BGE_RERANK_URL",
        scaledown_window_s=60,
        source="modal_endpoints/bge_retrieval.py:187",
        payload={
            "query": BENCH_QUERY,
            "candidates": [{"text": c} for c in BENCH_CONTEXT],
            "top_k": 5,
        },
        notes="60 s window — batch must run back-to-back with no pauses.",
    ),
    # ── Generation ───────────────────────────────────────────────────────────
    Agent(
        key="llm_rag_generator_v2",
        stage="RAG answer generation (LoRA v2)",
        model_id="google/gemma-4-12B-it + PEFT LoRA v2 (bf16)",
        requested_gpu="A100-80GB",
        modality="llm",
        env_var="MODAL_RAG_GENERATOR_URL",
        scaledown_window_s=60,
        source="modal_endpoints/rag_generator.py:219",
        payload={
            "query": BENCH_QUERY,
            "context": BENCH_CONTEXT,
            "language": "english",
            "tutor_instructions": "",
            "memento": None,
        },
        server_time_key="timings_ms.total",
        notes="Already reports gpu + per-phase timings natively.",
    ),
    Agent(
        key="llm_gemma_base",
        stage="Answer generation — base",
        model_id="google/gemma-4-12B-it (bf16, no adapter)",
        requested_gpu="A100-80GB",
        modality="llm",
        env_var="MODAL_BASE_GEMMA_URL",
        scaledown_window_s=60,
        source="modal_endpoints/gemma_answer_generator.py:148",
        payload={
            "query": BENCH_QUERY,
            "context": BENCH_CONTEXT,
            "language": "english",
            "tutor_instructions": "",
            "memento": None,
            "route": "document_rag_base",
        },
        server_time_key="timings_ms.total",
    ),
    Agent(
        key="llm_gemma_finetuned_v2",
        stage="Answer generation — LoRA v2",
        model_id="google/gemma-4-12B-it + PEFT LoRA v2 (bf16)",
        requested_gpu="A100-80GB",
        modality="llm",
        env_var="MODAL_FINETUNED_GEMMA_V2_URL",
        scaledown_window_s=600,
        source="modal_endpoints/gemma_answer_generator.py:192",
        payload={
            "query": BENCH_QUERY,
            "context": [],
            "language": "english",
            "tutor_instructions": "",
            "memento": None,
            "route": "muscle_finetuned_v2",
        },
        server_time_key="timings_ms.total",
    ),
    Agent(
        key="llm_transcript_corrector",
        stage="Transcript correction",
        model_id="google/gemma-4-12B-it + LoRA v2 (shared RAG container)",
        requested_gpu="A100-80GB",
        modality="llm",
        env_var="MODAL_TRANSCRIPT_CORRECTOR_URL",
        scaledown_window_s=60,
        source="modal_endpoints/rag_generator.py:384",
        payload={
            "transcript": "what is the origin and insertion of the pectoralis major",
            "language": "english",
            "mode": "correct",
        },
    ),
    Agent(
        key="llm_localizer",
        stage="Localization (en→ta/si)",
        model_id="Qwen/Qwen2.5-7B-Instruct",
        requested_gpu="T4",
        modality="llm",
        env_var="MODAL_LOCALIZER_URL",
        scaledown_window_s=300,
        source="modal_endpoints/localizer.py:53",
        payload={"text": BENCH_TEXT_EN, "language": "tamil"},
    ),
    # ── Text-to-Speech ───────────────────────────────────────────────────────
    Agent(
        key="tts_kokoro_en",
        stage="TTS (English)",
        model_id="hexgrad/Kokoro-82M",
        requested_gpu="CPU (4 vCPU)",
        modality="tts",
        env_var="MODAL_ENGLISH_KOKORO_TTS_URL",
        scaledown_window_s=300,
        source="modal_endpoints/english_kokoro_tts.py:71",
        payload={"text": BENCH_TEXT_EN},
        notes="Only CPU-served agent — the RTF comparison against the GPU TTS "
              "models is a result in its own right.",
    ),
    Agent(
        key="tts_indicf5_ta",
        stage="TTS (Tamil)",
        model_id="ai4bharat/IndicF5",
        requested_gpu="A10G",
        modality="tts",
        env_var="MODAL_TAMIL_TTS_URL",
        scaledown_window_s=300,
        source="modal_endpoints/tamil_parler_tts.py:131",
        payload={"text": BENCH_TEXT_TA, "language": "tamil"},
    ),
    Agent(
        key="tts_indic_parler_mixed",
        stage="TTS (code-switch)",
        model_id="ai4bharat/indic-parler-tts",
        requested_gpu="A10G",
        modality="tts",
        env_var="MODAL_INDIC_PARLER_MIXED_TTS_URL",
        scaledown_window_s=300,
        source="modal_endpoints/indic_parler_mixed_tts.py:229",
        payload={"text": BENCH_TEXT_MIXED, "description": ""},
    ),
    Agent(
        key="tts_sinhala_vits",
        stage="TTS (Sinhala)",
        model_id="dialoglk/SinhalaVITS-TTS-M2",
        requested_gpu="T4",
        modality="tts",
        env_var="MODAL_SINHALA_VITS_TTS_URL",
        scaledown_window_s=300,
        source="modal_endpoints/sinhala_vits_tts.py:178",
        payload={"text": BENCH_TEXT_SI},
    ),
    Agent(
        key="tts_mms_baseline",
        stage="TTS baseline (MMS)",
        model_id="facebook/mms-tts-{eng,tam,sin}",
        requested_gpu="T4",
        modality="tts",
        env_var="MODAL_TTS_URL",
        scaledown_window_s=300,
        source="modal_endpoints/tts.py:49",
        payload={"text": BENCH_TEXT_EN, "language": "english"},
        notes="Massively Multilingual Speech — the open baseline every "
              "per-language model in this system is compared against.",
    ),
]

AGENTS_BY_KEY = {a.key: a for a in AGENTS}

# Agents that must be batched without idle pauses between calls.
TIGHT_WINDOW_KEYS = [a.key for a in AGENTS if a.scaledown_window_s <= 60]

# Rough Modal on-demand rates (USD/hour) for the credit estimate in report.py.
# Update if Modal's pricing page changes; they are only used for a cost column.
GPU_HOURLY_USD = {
    "T4": 0.59,
    "A10G": 1.10,
    "A100-80GB": 2.50,
    "CPU (4 vCPU)": 0.14,
}


def gpu_hourly(requested_gpu: str) -> float:
    return GPU_HOURLY_USD.get(requested_gpu, 0.0)

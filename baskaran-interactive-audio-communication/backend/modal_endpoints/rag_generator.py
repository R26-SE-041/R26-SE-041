"""
Modal Serverless Endpoint: Gemma 4 12B IT -- RAG Generation + Transcript Correction

Deploy:
    modal deploy backend/modal_endpoints/rag_generator.py

Endpoints:

  POST /generate
    { "query": str, "context": list[str], "language": str }
    -> { "answer": str }

  POST /correct-transcript
    { "transcript": str, "language": str, "mode": str }
    mode = "correct"        -> user-triggered ASR correction (preserves intent)
    mode = "script_correct" -> automatic romanized -> native Unicode conversion
    -> { "corrected_transcript": str }

Model: google/gemma-4-12B-it
"""

from typing import List
from pydantic import BaseModel
import modal

image = (
    modal.Image.debian_slim(python_version="3.11")
    .pip_install(
        "transformers>=5.0.0",
        "torch>=2.2.0",
        "accelerate>=0.28.0",
        "fastapi[standard]>=0.115.0",
        "pydantic>=2.0.0",
    )
)

app = modal.App("voicelearn-rag-generator", image=image)
model_volume = modal.Volume.from_name("voicelearn-models", create_if_missing=True)


class RAGRequest(BaseModel):
    query: str
    context: List[str]
    language: str = "english"


class TranscriptCorrectorRequest(BaseModel):
    transcript: str
    language: str = "english"
    mode: str = "correct"  # "correct" | "script_correct"


class SinhalaPhoneticRequest(BaseModel):
    english: str


SINHALA_PHONETIC_SYSTEM_PROMPT = """You are a Sinhala phonetic transliteration engine.
Convert the English word or phrase to its pronunciation in Sinhala script.
Do not translate, explain, reason, output analysis, or output XML/thought tags.
Return only Sinhala-script phonetic rendering.
Examples: teacher → ටීචර්; computer → කොම්පියුටර්; internet → ඉන්ටර්නෙට්; Artificial Intelligence → ආර්ටිෆිෂල් ඉන්ටලිජන්ස්."""


def _clean_sinhala_phonetic_output(value: str, source: str) -> str:
    """Return only a contract-valid phonetic completion, else an empty string."""
    import re

    value = value.strip()
    # Reasoning must never be salvaged: even an otherwise Sinhala-looking
    # completion is unsafe if Gemma emitted thought/analysis content.
    if re.search(r"(?:<\s*/?\s*(?:thought|analysis)\b|\bthought\b|\banalysis\b)", value, re.I):
        return ""
    value = re.sub(r"^```(?:text)?\s*|\s*```$", "", value, flags=re.I).strip()
    value = re.sub(r"^(?:sinhala|answer|output|translation|phonetic)\s*:\s*", "", value, flags=re.I).strip()
    if len(value) >= 2 and value[0] in ('\"', "'", "\u201c", "\u2018") and value[-1] in ('\"', "'", "\u201d", "\u2019"):
        value = value[1:-1].strip()
    # Only Sinhala, spacing, digits, and light punctuation are acceptable;
    # this rejects explanations and any remaining Latin prose.
    if not value or len(value) > max(96, len(source) * 8):
        return ""
    if not re.search(r"[\u0D80-\u0DFF]", value):
        return ""
    if not re.fullmatch(r"[\u0D80-\u0DFF0-9\s.,;:!?()\-]+", value):
        return ""
    return value


# ---------------------------------------------------------------------------
# RAG system prompts
# Writing Tamil/Sinhala prompts in their native scripts strongly encourages
# the model to respond in the correct script, even when the context is in English.
# ---------------------------------------------------------------------------
RAG_SYSTEM_PROMPTS = {
    "english": (
        "You are an academic tutor. Answer the student's question using ONLY the provided context. "
        'If the answer is not in the context, say: "I couldn\'t find that in your documents." '
        "Be concise and clear. Do not hallucinate or use external knowledge."
    ),
    "tamil": (
        "Neenga oru kalvi aasiriyar. Keezhe kodukkapatta Context (aavana paguthi) mattume "
        "payanduthu maanavar kelvikku Tamil-il patil tharunga. "
        "Context English-il irundhaalum, unga patil Tamil-iley irukkanum. "
        "Context-la illatha thavalkalai sollaadheenga. "
        "Patil thelivagavum surukkamakavum irukkattum. "
        "Thozhilnutpa sorkal (technical terms) English-iley vaikkalaam."
    ),
    "sinhala": (
        "Oba adhyaapanaya guruwaryekis. Pahath Context (lekana kothas) pamanak bhavita kara "
        "sisuwage prashnaayata Sinhalen pilituru denna. "
        "Context Ingrisin tibunath oba pilithuwa Sinhalen liyanna. "
        "Context-aye nathi thooru nokiyanna. "
        "Pilithuwa pahediliwwa ha sankshipthawa liyanna. "
        "Thakshaniya vachan Ingrisin randwa gatha hakiya."
    ),
    "mixed": (
        "You are an academic tutor. Answer using ONLY the provided context. "
        "Respond in Thanglish (Tamil words written in English script mixed with English). "
        "Do not hallucinate. Be concise."
    ),
}

_DEFAULT_RAG_PROMPT = RAG_SYSTEM_PROMPTS["english"]

# ---------------------------------------------------------------------------
# Transcript correction: mode = "correct"
# User-triggered. Fix ASR errors; preserve the speaker's intent exactly.
# ---------------------------------------------------------------------------
TRANSCRIPT_CORRECTION_SYSTEM_PROMPT = (
    "You are a multilingual ASR Transcript Correction Agent.\n"
    "Your task is to correct only clear and highly confident speech-to-text errors while "
    "preserving the user's original meaning and wording as closely as possible.\n\n"
    "Supported languages: Tamil, Sinhala, English, Tamil-English mixed speech, Sinhala-English mixed speech.\n\n"
    "Core rule: Never guess what the speaker probably meant. If a word is unclear, unfamiliar, "
    "unusual, or potentially mis-transcribed, preserve the original ASR word exactly unless the "
    "intended correction is highly certain from the transcript itself. A plausible alternative is "
    "not enough reason to replace a word.\n\n"
    "Strict rules:\n"
    "1. Make the minimum number of changes necessary.\n"
    "2. Correct only obvious spelling, punctuation, grammatical, or ASR errors with very high confidence.\n"
    "3. Preserve the speaker's original meaning exactly.\n"
    "4. Never replace an unclear word with a more common, familiar, or semantically related word just because it seems likely.\n"
    "5. Never infer a specific word from topic or context alone.\n"
    "6. Never turn an unknown word into a known entity, sport, product, place, person, or technical term without strong evidence.\n"
    "7. If uncertain between keeping the original word and replacing it, always keep the original.\n"
    "8. Do not rewrite, paraphrase, summarize, improve, simplify, or expand the sentence.\n"
    "9. Do not convert the transcript into a search query.\n"
    "10. Do not add or remove meaningful information.\n"
    "11. Preserve names, numbers, dates, locations, technical terms, model names, abbreviations, and code-switched English words.\n"
    "12. Preserve Tamil, Sinhala, and English code-switching.\n"
    "13. Do not answer the user's question.\n"
    "14. Return exactly one corrected transcript.\n"
    "15. Never repeat the transcript or include explanations, notes, labels, reasoning, quotation marks, or alternatives.\n\n"
    "When uncertain: KEEP THE ORIGINAL WORD. DO NOT GUESS.\n\n"
    "Examples:\n"
    "Input: கெரபந்து\nOutput: கெரபந்து\n"
    "Input: நாய்க்கு பால் குடுக்கலாமா\nOutput: நாய்க்கு பால் கொடுக்கலாமா?\n"
    "Input: எனக்கு கெரபந்து பற்றி சொல்லு\nOutput: எனக்கு கெரபந்து பற்றி சொல்லு."
)

# ---------------------------------------------------------------------------
# Script correction: mode = "script_correct"
# Automatic low-level fix. Convert romanized Whisper output back to native
# Tamil/Sinhala Unicode. Separate strict prompt -- NOT the correction prompt.
# ---------------------------------------------------------------------------
SCRIPT_CORRECT_PROMPTS = {
    "tamil": (
        "You are a Tamil ASR script restoration expert. "
        "Whisper (the speech recognizer) transcribed Tamil speech but produced romanized "
        "phonetic text or wrong English words instead of proper Tamil Unicode script. "
        "Common examples of Whisper's Tamil mishearings:\n"
        "  Dog (naai) -> Whisper outputs: night, naai, nai\n"
        "  What (enna) -> Whisper outputs: anna, enna, Inna\n"
        "  Cat (poonai) -> Whisper outputs: poonai, lunai, punai\n"
        "  You (neengal) -> Whisper outputs: ninga, neengal, ningal\n"
        "  Book (puthagam) -> Whisper outputs: puttakam, puthagam\n"
        "Convert the Whisper output to correct Tamil Unicode script. "
        "Do NOT explain. Do NOT add punctuation that was not implied. "
        "Return ONLY the Tamil Unicode text."
    ),
    "sinhala": (
        "You are a Sinhala ASR script restoration expert. "
        "Whisper (the speech recognizer) transcribed Sinhala speech but produced romanized "
        "phonetic text or wrong English words instead of proper Sinhala Unicode script. "
        "Convert the Whisper output to correct Sinhala Unicode script. "
        "Do NOT explain. Do NOT add information. "
        "Return ONLY the Sinhala Unicode text."
    ),
}


@app.cls(
    # Gemma 4 12B BF16 weights are ~24 GB; use 40 GB for the model,
    # generation buffers, and the retrieved RAG context.
    gpu="A100-40GB",
    volumes={"/models": model_volume},
    scaledown_window=300,
    memory=16384,
)
class RAGGenerator:
    @modal.enter()
    def load_model(self):
        from transformers import AutoTokenizer, AutoModelForCausalLM
        import torch

        model_id = "google/gemma-4-12b-it"
        self.tokenizer = AutoTokenizer.from_pretrained(model_id, cache_dir="/models")
        self.model = AutoModelForCausalLM.from_pretrained(
            model_id,
            torch_dtype=torch.bfloat16,
            device_map="auto",
            cache_dir="/models",
        )

    @modal.fastapi_endpoint(method="POST")
    async def generate(self, payload: RAGRequest):
        """RAG answer generation."""
        import torch

        query: str = payload.query
        context_chunks: List[str] = payload.context
        language: str = payload.language.lower()

        if not query or not context_chunks:
            return {"answer": "No query or context provided."}

        context_text = "\n\n---\n\n".join(context_chunks)

        system_prompt = RAG_SYSTEM_PROMPTS.get(language, _DEFAULT_RAG_PROMPT)

        lang_note = {
            "tamil":   "Student question (please answer in Tamil)",
            "sinhala": "Student question (please answer in Sinhala)",
        }.get(language, "Question")

        messages = [
            {
                "role": "user",
                "content": (
                    f"{system_prompt}\n\n"
                    f"Context:\n{context_text}\n\n"
                    f"{lang_note}: {query}"
                ),
            },
        ]

        text = self.tokenizer.apply_chat_template(
            messages,
            tokenize=False,
            add_generation_prompt=True,
        )
        inputs = self.tokenizer(text, return_tensors="pt").to(self.model.device)
        input_length = inputs["input_ids"].shape[-1]

        with torch.no_grad():
            output = self.model.generate(
                **inputs,
                max_new_tokens=512,
                do_sample=False,
                pad_token_id=self.tokenizer.eos_token_id,
            )

        answer = self.tokenizer.decode(
            output[0][input_length:], skip_special_tokens=True
        ).strip()

        return {"answer": answer}

    @modal.fastapi_endpoint(method="POST")
    async def correct_transcript(self, payload: TranscriptCorrectorRequest):
        """Multilingual ASR Transcript Correction endpoint.

        mode = "correct"
            User-triggered. Fix obvious ASR errors while preserving the speaker's
            original meaning exactly. Never rewrites or expands the query.

        mode = "script_correct"
            Automatic low-level. Convert romanized Whisper output back to native
            Tamil / Sinhala Unicode script. Separate strict prompt from above.

        Returns { "corrected_transcript": str }
        """
        import torch

        transcript: str = payload.transcript.strip()
        language: str = payload.language.lower()
        mode: str = payload.mode

        if not transcript:
            return {"corrected_transcript": transcript}

        if mode == "script_correct":
            system_prompt = SCRIPT_CORRECT_PROMPTS.get(language)
            if not system_prompt:
                # Unknown language for script correction -- return as-is
                return {"corrected_transcript": transcript}
            user_content = (
                f"Whisper transcribed this {language} audio as:\n"
                f'"{transcript}"\n\n'
                f"Convert to correct {language} Unicode script. "
                f"Return ONLY the {language} Unicode text."
            )
        else:
            # Default: user-triggered ASR correction
            system_prompt = TRANSCRIPT_CORRECTION_SYSTEM_PROMPT
            # Include explicit language instruction so the model preserves the script
            lang_note = {
                "tamil":   "This transcript is in Tamil (தமிழ்). Return the corrected Tamil text only.",
                "sinhala": "This transcript is in Sinhala (සිංහල). Return the corrected Sinhala text only.",
                "english": "This transcript is in English. Return the corrected English text only.",
                "mixed":   "This transcript is in Tamil-English mixed speech (Tanglish). Preserve all Tamil and English words as spoken.",
            }.get(language, "Return only the corrected transcript.")
            user_content = (
                f"{lang_note}\n\n"
                f"Correct the following transcript:\n{transcript}"
            )

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content},
        ]

        text = self.tokenizer.apply_chat_template(
            messages,
            tokenize=False,
            add_generation_prompt=True,
        )
        inputs = self.tokenizer(text, return_tensors="pt").to(self.model.device)
        input_length = inputs["input_ids"].shape[-1]

        # A correction should be nearly the same length as its source. Keeping the
        # completion budget tight prevents Gemma from appending a second copy or commentary.
        source_tokens = self.tokenizer(transcript, add_special_tokens=False)["input_ids"]
        max_correction_tokens = min(200, max(16, len(source_tokens) + 8))

        with torch.no_grad():
            output = self.model.generate(
                **inputs,
                max_new_tokens=max_correction_tokens,
                do_sample=False,     # greedy -- deterministic, no hallucination risk
                pad_token_id=self.tokenizer.eos_token_id,
                eos_token_id=self.tokenizer.eos_token_id,
            )

        corrected = self.tokenizer.decode(
            output[0][input_length:], skip_special_tokens=True
        ).strip()

        # Safety: if model returns empty or implausibly short output, keep original
        if not corrected or len(corrected) < 2:
            return {"corrected_transcript": transcript}

        # Strip common model prefixes that Gemma sometimes adds despite instructions
        # e.g. "Corrected: ...", "Corrected transcript: ...", "Here is the corrected..."
        import re
        strip_patterns = [
            r'^(?:corrected\s*(?:transcript)?\s*:?\s*)'.encode('utf-8').decode('utf-8'),
            r'^(?:here is the corrected\s*(?:transcript)?\s*:?\s*)',
            r'^(?:the corrected\s*(?:transcript)?\s*(?:is)?\s*:?\s*)',
            r'^(?:fixed\s*(?:transcript)?\s*:?\s*)',
        ]
        for pat in strip_patterns:
            cleaned = re.sub(pat, '', corrected, flags=re.IGNORECASE).strip()
            if cleaned:
                corrected = cleaned
                break

        # Remove surrounding quotes if model wrapped the output in them
        if len(corrected) >= 2 and corrected[0] in ('"', '\u201c', '\u2018') and corrected[-1] in ('"', '\u201d', '\u2019'):
            corrected = corrected[1:-1].strip()

        # Final safety: if stripping left nothing, return original
        if not corrected:
            return {"corrected_transcript": transcript}

        return {"corrected_transcript": corrected}

    @modal.fastapi_endpoint(method="POST")
    async def phonetic_transliterate(self, payload: SinhalaPhoneticRequest):
        """Isolated TTS helper on the same loaded Gemma model; not part of RAG."""
        import torch

        english = payload.english.strip()
        if not english or len(english) > 160:
            return {"phonetic": ""}
        messages = [
            {"role": "system", "content": SINHALA_PHONETIC_SYSTEM_PROMPT},
            {"role": "user", "content": english},
        ]
        # Gemma's chat template supports this switch.  It is intentionally
        # limited to this endpoint; RAG and transcript correction are unchanged.
        text = self.tokenizer.apply_chat_template(
            messages, tokenize=False, add_generation_prompt=True, enable_thinking=False,
        )
        inputs = self.tokenizer(text, return_tensors="pt").to(self.model.device)
        input_length = inputs["input_ids"].shape[-1]
        # `bad_words_ids` is a supported Transformers generation control. It
        # prevents a model/template mismatch from emitting thought markup even
        # if the model attempts to do so after thinking has been disabled.
        blocked_sequences = ["<thought>", "</thought>", "thought", "<analysis>", "</analysis>", "analysis"]
        bad_words_ids = [
            ids for token in blocked_sequences
            if (ids := self.tokenizer(token, add_special_tokens=False)["input_ids"])
        ]
        with torch.no_grad():
            output = self.model.generate(
                **inputs, max_new_tokens=48, do_sample=False,
                pad_token_id=self.tokenizer.eos_token_id, eos_token_id=self.tokenizer.eos_token_id,
                bad_words_ids=bad_words_ids,
            )
        raw = self.tokenizer.decode(output[0][input_length:], skip_special_tokens=True)
        return {"phonetic": _clean_sinhala_phonetic_output(raw, english)}

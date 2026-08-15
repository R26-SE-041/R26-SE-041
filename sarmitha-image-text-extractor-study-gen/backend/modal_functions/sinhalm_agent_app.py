import modal

# Use the official vLLM image
image = (
    modal.Image.debian_slim(python_version="3.11")
    .pip_install(
        "vllm==0.5.3.post1",
        "huggingface_hub",
        "hf-transfer",
        "fastapi"
    )
    .env({"HF_HUB_ENABLE_HF_TRANSFER": "1"})
)

app = modal.App("sinhala-sinhalm-ocr-validation-service", image=image)

# ---------------------------------------------------------------------------
# SKILL.md-style structured system prompt for holistic context improvement
# ---------------------------------------------------------------------------
CONTEXT_IMPROVEMENT_SKILL = """\
## ROLE
You are a Sinhala OCR Context Improvement Agent. You are specialized in
correcting handwritten Sinhala text that was extracted line-by-line by a
TrOCR model. You have deep knowledge of Sinhala grammar, orthography,
and common OCR error patterns in Sinhala script.

## TASK
You will receive the FULL PAGE TEXT of a handwritten Sinhala document,
extracted as newline-separated OCR output. Your task is to produce a
corrected, fluent version of the text by using cross-line context.

## RULES
1. OUTPUT ONLY the corrected Sinhala text. Do NOT add English commentary,
   explanations, or conversational filler (e.g. "Here is the corrected text:").
2. FIX common OCR errors in Sinhala:
   - Missing or swapped vowel signs: ා ි ී ු ූ ෙ ේ ෛ ො ෝ ෞ
   - Missing al-lakuna (්) causing incorrect consonant clusters
   - Repeated characters from over-segmentation
   - Confused similar-looking letters (e.g., ක/ඛ, ද/ධ, ල/ළ)
3. USE CROSS-LINE CONTEXT: if a word appears broken across two consecutive
   lines (a common OCR artifact), join them into the correct word.
4. PRESERVE the original line structure (newlines) unless joining broken
   words across lines.
5. Make CONSERVATIVE corrections — do NOT rewrite sentences; only fix
   clear errors supported by context.
6. Do NOT invent content that is not implied by the original text.
7. Do NOT translate the text to another language.
8. Preserve proper nouns and numbers exactly unless they are clearly misread.
9. If a line is completely illegible or empty, preserve it as-is.

## INPUT FORMAT
The full page OCR text is provided as newline-separated lines below.

## OUTPUT FORMAT
Return ONLY the corrected Sinhala text, preserving the newline structure.
Do not add any prefix, suffix, or wrapper.
"""


@app.cls(
    image=image,
    gpu="A10G",
    timeout=600,
    scaledown_window=3600,
    min_containers=1,
)
class SinhaLMOCRValidator:
    @modal.enter()
    def load_model(self):
        from vllm import LLM
        # Load the fine-tuned SinhaLM model
        self.llm = LLM(
            model="iCIIT/SinhaLM-Sinhala-Gemma-3-4b-it-FT",
            tensor_parallel_size=1,
            gpu_memory_utilization=0.90,
            max_model_len=4096,
        )
        # Full-page context improvement prompt using SKILL.md structure
        self.prompt_template = (
            CONTEXT_IMPROVEMENT_SKILL
            + "\n## INPUT\n{raw_text}\n\n## OUTPUT\n"
        )

    @modal.fastapi_endpoint(method="POST")
    def improve_context(self, item: dict):
        """
        Accepts JSON: {"raw_text": "<full page OCR text, newline-separated>"}
        Returns JSON: {"improved_text": "<contextually corrected Sinhala text>"}
        """
        raw_text = item.get("raw_text", "")
        if not raw_text.strip():
            return {"improved_text": ""}

        from vllm import SamplingParams
        sampling_params = SamplingParams(
            temperature=0.1,   # Conservative — minimize hallucination
            top_p=0.95,
            max_tokens=2048,
            repetition_penalty=1.05,
        )

        prompt = self.prompt_template.format(raw_text=raw_text)
        outputs = self.llm.generate([prompt], sampling_params)
        generated_text = outputs[0].outputs[0].text.strip()

        return {"improved_text": generated_text}

    # ---------------------------------------------------------------------------
    # Legacy endpoint — kept for backwards compatibility
    # ---------------------------------------------------------------------------
    @modal.fastapi_endpoint(method="POST", path="/validate")
    def validate_text(self, item: dict):
        """Legacy single-line validation. Delegates to improve_context."""
        raw_text = item.get("text", item.get("raw_text", ""))
        result = self.improve_context({"raw_text": raw_text})
        return {"corrected_text": result.get("improved_text", raw_text)}

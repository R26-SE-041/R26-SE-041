---
name: sinhala-context-improvement
description: >
  Guides the AI on how to improve Sinhala OCR output using the SinhaLM LLM
  context-improvement pipeline. Use this skill when working on post-extraction
  text correction, prompt engineering for Sinhala OCR, or tuning the SinhaLM
  Modal endpoint.
---

# Sinhala OCR Context Improvement Skill

## Overview

After the TrOCR model extracts text line-by-line from a handwritten Sinhala
image, a second LLM pass is performed by **SinhaLM** (`iCIIT/SinhaLM-Sinhala-Gemma-3-4b-it-FT`)
to fix cross-line OCR errors using full-page context.

```
Image → SRCNN (4× enhance) → TrOCR (line-by-line OCR) → SinhaLM (context fix)
```

---

## Pipeline Step Details

### Step 1 — SRCNN Enhancement
- Modal app: `modal_functions/srcnn_app.py`
- Client:    `backend/app/services/srcnn_client.py`
- Input:  raw image bytes
- Output: enhanced image bytes (4× resolution)

### Step 2 — TrOCR Line Extraction
- Modal app: `modal_functions/trocr_app.py`
- Client:    `backend/app/services/trocr_client.py`
- Input:  enhanced image bytes (base64 JSON)
- Output: `{"lines": [{"text": "...", "crop_b64": "...", "confidence": 0.95}]}`
- Model:  `hasindu-k/sinhala-handwritten-notes-v3`
- Segmentation: OpenCV contour-based line detection

### Step 3 — SinhaLM Context Improvement *(Step 4 in routes.py)*
- Modal app: `modal_functions/sinhalm_agent_app.py`
- Client:    `backend/app/services/sinhalm_client.py`
- Orchestrator: `backend/app/api/routes.py` → `POST /api/process`
- Input:  full-page newline-joined OCR text (`raw_text`)
- Output: `{"improved_text": "..."}` (contextually corrected Sinhala)
- Model:  `iCIIT/SinhaLM-Sinhala-Gemma-3-4b-it-FT` (Gemma-3 4B fine-tune)

**This step is OPTIONAL and currently disabled by default.**
*Warning: A temperature=0.1 LLM will hallucinate corrections based on Sinhala language priors rather than reading the image, which can actively degrade faithful TrOCR extraction. Use with caution.*

If `SINHALM_MODAL_URL` is not set in `backend/.env`,
`sinhalm_client.validate_text()` returns the raw text unchanged — the pipeline
never crashes.

---

## System Prompt Design (CONTEXT_IMPROVEMENT_SKILL in sinhalm_agent_app.py)

The system prompt is structured with SKILL.md-style sections:

| Section | Purpose |
|---------|---------|
| `## ROLE` | Establishes the agent as a Sinhala OCR expert |
| `## TASK` | Describes the full-page correction task |
| `## RULES` | 9 conservative correction rules (no hallucination, preserve structure) |
| `## INPUT FORMAT` | Tells LLM to expect newline-separated OCR text |
| `## OUTPUT FORMAT` | Constrains output to corrected Sinhala text only (no English commentary) |

### Key Rules Enforced
1. Output ONLY corrected Sinhala — no English filler
2. Fix vowel signs: `ා ි ී ු ූ ෙ ේ ෛ ො ෝ ෞ`
3. Fix missing `al-lakuna` (`්`) in consonant clusters
4. Join broken words across lines (cross-line context)
5. Preserve line structure (newlines)
6. Conservative: only fix clear errors, never rewrite
7. Never translate, never invent content
8. Preserve proper nouns and numbers
9. Preserve fully illegible lines as-is

### Sampling Parameters
```python
temperature=0.1        # Low — minimize hallucination
top_p=0.95
max_tokens=2048
repetition_penalty=1.05
```

---

## How to Enable/Disable SinhaLM

In `backend/.env`:
```env
# Set to your Modal endpoint URL to enable context improvement:
SINHALM_MODAL_URL=https://your-org--sinhala-sinhalm-ocr-validation-service-...modal.run

# Leave blank to skip (pipeline still works, returns raw TrOCR output):
# SINHALM_MODAL_URL=
```

---

## Deploying the Modal App

```bash
# From the project root:
modal deploy backend/modal_functions/sinhalm_agent_app.py
```

After deploy, copy the printed endpoint URL into `backend/.env` as
`SINHALM_MODAL_URL`.

---

## API Response Shape

`POST /api/process` now returns:

```json
{
  "original_b64": "<base64 PNG>",
  "enhanced_b64": "<base64 PNG>",
  "extracted_text": "<final full-page text after SinhaLM>",
  "context_improved": true,
  "lines": [
    {
      "crop_b64":   "<base64 JPEG of the line crop>",
      "raw_text":   "<direct TrOCR output>",
      "visual_text": "<mirrors raw_text (reserved for Qwen agent)>",
      "final_text":  "<SinhaLM-corrected text for this line>",
      "confidence":  0.94
    }
  ]
}
```

`context_improved` is `true` only if SinhaLM produced a different result from
the raw TrOCR output.

---

## Frontend Display (OcrResult.tsx)

- Shows per-line **crop image** next to **final_text** (falls back to raw_text)
- Full extracted text is in `result.extracted_text` (used for Copy button)
- Word count badge uses `extracted_text.split(/\s+/)`
- `OcrLine` TypeScript interface lives in `frontend-rn/lib/api.ts`

---

## Common OCR Error Patterns in Sinhala (for prompt tuning)

| Error Type | Example Wrong → Correct |
|------------|------------------------|
| Missing vowel sign | `කට` → `කැට` |
| Missing al-lakuna | `ශිෂ` → `ශිෂ්‍ය` |
| Over-segmentation | `ම`+`ල` → `මල` |
| Confused letters | `ද`/`ධ`, `ල`/`ළ`, `ක`/`ඛ` |
| Broken cross-line word | line N: `සිංහල`, line N+1: `ය` → join to `සිංහලය` |

---

## Files Reference

| File | Role |
|------|------|
| `backend/modal_functions/sinhalm_agent_app.py` | Modal serverless endpoint with SinhaLM + system prompt |
| `backend/app/services/sinhalm_client.py` | FastAPI backend client for the Modal endpoint |
| `backend/app/api/routes.py` | Orchestrates all pipeline steps including Step 4 |
| `backend/modal_functions/trocr_app.py` | Modal TrOCR line extraction service |
| `frontend-rn/lib/api.ts` | TypeScript types: `ProcessResult`, `OcrLine` |
| `frontend-rn/components/OcrResult.tsx` | Frontend component rendering per-line OCR results |

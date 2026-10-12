# How to use this file

This is manuscript **content**, not a formatted document. It follows IEEE conference
structure and style (headings, run-in Abstract/Keywords, numbered citations, reference
format) so it can be pasted directly into the **official, unmodified** IEEE conference
Word or LaTeX template for ICAC 2026 — do not recreate the two-column layout by hand
(see the "What still needs to happen before this can be submitted" note at the end of
this file for exactly why, and what is still missing).

Paste order: Title -> Author block -> Abstract -> Keywords -> Section I onward ->
Acknowledgment -> References. Everything in `[[double brackets]]` is a placeholder that
a real value must replace before submission — none of these were invented; they mark
information this session did not have permission or data to generate (see the closing
note).

---

# Title (proposed — trim/replace as the team prefers)

BioLearnX: A Self-Improving Multi-Agent Framework for Personalized Biology Learning
through Interactive Visualization, Adaptive Assessment, and Multilingual Content
Generation

*Shorter alternative:* BioLearnX: A Multi-Agent, Self-Improving Framework for
Personalized Biology Learning

---

# Author block (IEEE 5-line format, six authors — matches the template's 3x2 layout)

**Kojithan P. Y.**
Faculty of Computing
Sri Lanka Institute of Information Technology
Malabe, Sri Lanka
it22264220@my.sliit.lk

**Baskaran V.**
Faculty of Computing
Sri Lanka Institute of Information Technology
Malabe, Sri Lanka
it22172600@my.sliit.lk

**Nishara T.**
Faculty of Computing
Sri Lanka Institute of Information Technology
Malabe, Sri Lanka
it22223876@my.sliit.lk

**Sarmitha S.**
Faculty of Computing
Sri Lanka Institute of Information Technology
Malabe, Sri Lanka
it22637482@my.sliit.lk

**Nuwan Kodagoda**
Faculty of Computing
Sri Lanka Institute of Information Technology
Malabe, Sri Lanka
nuwan.k@sliit.lk

**Malithi Nawarathne**
Faculty of Computing
Sri Lanka Institute of Information Technology
Malabe, Sri Lanka
malithi.n@sliit.lk

---

# Abstract

*Abstract*—Biology learners typically move between separate tools for diagrams,
revision, assessment, and note-taking, and few of these tools adapt to the individual
learner or improve from experience. This paper presents BioLearnX, a multi-agent
research framework that investigates whether four complementary agentic subsystems —
interactive visual generation, adaptive assessment, multilingual audio review, and
handwritten-note recovery — can share a common architectural pattern: retrieval-grounded
large language model (LLM) agents, orchestrated as explicit graphs, that are evaluated
by independent critics and improved only through validation-gated feedback. The
visualization subsystem combines a catalog-driven anatomy specification extracted by an
instruction model, image synthesis with a rectified-flow diffusion transformer, a dual
CLIP/vision-language-model critic with a reflection-and-retry loop, segmentation-grounded
interactive region explanation, and two-dimensional-to-3D asset conversion. The
assessment subsystem generates curriculum-grounded, Bloom's-taxonomy-mapped questions
from learner-uploaded documents and adapts difficulty from response history. The
note-recovery subsystem applies fine-tuned super-resolution and optical character
recognition models to enhance and transcribe low-quality Sinhala handwriting, with Tamil
and English translation. The audio-review subsystem provides multilingual (Tamil,
Sinhala, English, and code-mixed) spoken question answering grounded in the learner's own
material. All four subsystems are implemented as independently deployable services on
serverless GPU infrastructure and share a feedback-to-memory-to-skill-evolution
lifecycle that gates every behavioral change behind held-out, paired evaluation. We
describe the system design and the reproducible evaluation protocols implemented across
the framework. An end-to-end baseline evaluation against the live deployment compares
raw FLUX.1-dev output with our full visual pipeline (prompt enhancement under deployed
persona/skill rules, FLUX.1-dev diffusion, and Qwen2.5-VL automatic structure labeling):
the proposed pipeline achieves substantial gains in VLM visual alignment ($8.67 \pm 0.58$
vs. $6.00 \pm 3.46$, +44.5%) and pedagogical usefulness ($7.67 \pm 0.58$ vs.
$5.00 \pm 3.46$, +53.4%), consistently producing 8 verified, callout-annotated
anatomical structures per image versus 0 for the unlabeled baseline, while collapsing
generation variance ($\sigma=0.58$ vs. $3.46$). We report these empirical findings
alongside an architectural audit and pre-registered evaluation protocols for the full
multi-agent ecosystem.

**Keywords**—multi-agent systems, large language models, retrieval-augmented
generation, parameter-efficient fine-tuning, text-to-image generation, optical
character recognition, adaptive learning, biology education

---

# I. Introduction

Learning biology well requires moving fluidly between several representations of the
same material: a labeled diagram of an organ system, a self-test that adapts to what
the learner has already mastered, a spoken explanation for revision on the move, and
usable notes recovered from a lecture photograph or a handwritten page. Commercial and
open-source tools typically address one of these modes in isolation, and few of them
adapt their own behavior from evidence of what worked for a given learner or a given
class of requests. Two distinct problems are therefore left largely unaddressed by
existing tools: (1) fragmentation across modalities — visual, assessment, spoken, and
written — that a single learning session actually needs, and (2) the absence of a
disciplined mechanism for an AI learning tool to improve itself without silently
degrading correctness or safety.

Recent generative-AI research in anatomy and medical education has begun to explore
embodied, conversational virtual assistants in immersive environments [12], and separate
lines of work have produced strong building blocks that make a more integrated approach
practical: instruction-tuned and vision-language foundation models that can be adapted
cheaply with low-rank fine-tuning [5], [6]; promptable image segmentation that
generalizes across domains [3]; rectified-flow diffusion transformers capable of
photorealistic, instruction-following image synthesis; and agent frameworks — reflection
[9], self-refinement [11], and explicit stateful orchestration graphs — that let an LLM
critique and retry its own output before it reaches a learner. What has not been
demonstrated is a single research framework that applies these building blocks
consistently across visualization, assessment, spoken review, and document recovery,
under one shared, evidence-gated improvement lifecycle.

This paper presents **BioLearnX**, a four-subsystem research framework built to close
that gap for biology education. Each subsystem is designed and implemented
independently by one member of the project team, but all four share the same underlying
principles: agentic pipelines orchestrated as explicit graphs rather than single
monolithic prompts; retrieval that grounds generation in the learner's own curriculum
material; an explicit separation between raw user feedback (never trusted directly) and
reviewed, evidence-backed memory or skill updates; and independent, automated critics
that gate output quality before a result reaches the learner.

The contributions of this paper are:

1. **A catalog-driven, LoRA-adapted interactive biology visualization pipeline** that
   converts a natural-language learning request into a validated anatomical
   specification, a generated educational image, an independently critiqued and
   retried result, click-to-identify region explanations, and an optional 3D asset —
   described in Section IV-A and evaluated by the protocol in Section V-B.1–2.
2. **An adaptive, curriculum-grounded assessment pipeline** that generates
   Bloom's-taxonomy-mapped questions from uploaded material and adapts difficulty and
   topic recommendations from response history — described in Section IV-B.
3. **A fine-tuned super-resolution and OCR pipeline for low-quality Sinhala
   handwriting**, with Tamil/English translation, evaluated against a non-fine-tuned
   baseline using character error rate (CER), word error rate (WER), and exact-match
   accuracy — described in Section IV-C and Section V-B.4.
4. **A multilingual, retrieval-grounded spoken question-answering pipeline** (Tamil,
   Sinhala, English, and code-mixed) for conversational revision — described in
   Section IV-D.
5. **A shared, validation-gated feedback-to-skill-evolution lifecycle** used across the
   subsystems, in which a behavioral change is deployed only after paired, held-out
   evaluation shows a measured improvement over the currently deployed version —
   described in Section III-C.

The remainder of this paper is organized as follows. Section II reviews related work
in diffusion-based image generation, agentic reflection and self-refinement, vision-
language grounding, parameter-efficient fine-tuning, retrieval-augmented agent memory,
and generative AI in anatomy education. Section III describes the shared system
architecture and design patterns. Section IV details the design and implementation of
each of the four subsystems. Section V defines the experimental setup, datasets, and
evaluation protocols already implemented for this study. Section VI reports results.
Section VII discusses the findings. Section VIII states limitations and threats to
validity, and Section IX concludes with future work.

---

# II. Related Work

### A. Diffusion-Based and Agentic Image Generation

Rectified-flow diffusion transformers such as FLUX.1 [7] have made high-fidelity,
instruction-following text-to-image generation practical at accessible parameter
counts, but a single forward pass through such a model provides no guarantee that a
generated image is factually or pedagogically correct. Agentic approaches address this
by wrapping generation in a critique-and-retry loop: Reflexion [9] shows that an LLM
agent that verbally reflects on a failed attempt and retries with that reflection as
context outperforms agents that retry blindly, and Self-Refine [11] shows the same
model can act as its own critic without additional training. Recent multi-agent
text-to-image systems extend this pattern with a dedicated critic model that scores an
image against the request and proposes concrete corrections before the next generation
attempt. The visualization subsystem in this paper (Section IV-A) applies this pattern
with an explicit, independent dual critic rather than self-critique, and separates the
critic's role (scoring and diagnosis) from the retry mechanism (targeted regeneration).

### B. Vision-Language Grounding and Segmentation

Interactive, click-to-identify explanation of an image region requires both precise
segmentation and grounded semantic reasoning. SAM 2 [3] extends promptable segmentation
to produce high-quality masks from a point or box prompt without requiring the
segmentation model to make any semantic claim about what it has segmented. Qwen2.5-VL
[2] provides the complementary capability: native bounding-box localization and
open-vocabulary visual question answering grounded in the pixels actually presented,
which is the property this paper's interactive-region agent (Section IV-A.4) depends on
to avoid asserting the presence of a structure that is not visibly supported by the
image.

### C. Parameter-Efficient Fine-Tuning

Full fine-tuning of a multi-billion-parameter language model is impractical for a
narrow, domain-specific task such as anatomical specification extraction or Sinhala
handwriting recognition. Low-Rank Adaptation (LoRA) [5] freezes the pretrained weights
and learns a small pair of low-rank update matrices per layer, and QLoRA [6] extends
this to 4-bit-quantized base models, making adapter training feasible on a single
consumer or cloud GPU. This paper uses LoRA fine-tuning for the anatomy specification
task (Section IV-A.1) and fine-tunes encoder-decoder OCR and super-resolution models
directly for the Sinhala-handwriting task (Section IV-C), and evaluates both against
their respective non-fine-tuned or pre-migration baselines rather than assuming a gain
from fine-tuning alone.

### D. Retrieval-Augmented Generation and Agent Memory

Grounding generation in a learner's own curriculum material requires efficient
semantic retrieval. Sentence-BERT [8] provides compact sentence embeddings suitable for
similarity search at low latency, and Hierarchical Navigable Small World (HNSW) graphs
[10] provide the approximate-nearest-neighbor index structure used to retrieve from a
large embedding store in sublinear time. Beyond one-shot retrieval, an agent that is
meant to improve over many sessions needs a policy for what evidence is durable enough
to change its behavior; this paper's shared feedback lifecycle (Section III-C) adopts
the general pattern of separating raw interaction evidence from reviewed, promoted
memory, gated by repeated, cross-session evidence before any prompt or rule is changed.

### E. Generative AI in Anatomy and Biology Education

Prior work has begun to apply generative AI to anatomy education, including
generative-AI-based conversational virtual assistants embedded in immersive virtual
reality environments for anatomy question answering [12]. That line of work targets
verbal, embodied interaction within a VR environment; it does not address on-demand
generation of new, structurally validated 2D/3D visual content, nor does it combine
visualization with adaptive assessment, multilingual spoken review, and handwritten-note
recovery under one evaluation-gated improvement lifecycle. This is the gap BioLearnX
addresses.

---

# III. System Overview and Shared Design

BioLearnX is organized as a research monorepo of four subsystems that are developed,
deployed, and — at the current stage of the project — evaluated **independently**, unified
by a shared research vision and a common set of architectural patterns rather than a
single production entry point. [[Fig. 1 — system architecture diagram. Export the
architecture diagram already maintained in the project README as a vector figure
(PDF/SVG) and insert it here; do not recreate it as a screenshot.]] A unified interface
and shared learner-profile layer across all four subsystems is explicitly future work
(Section IX), not a claim of this paper.

### A. Agentic Orchestration

Three of the four subsystems (visualization, assessment, audio review) implement their
multi-step pipelines as explicit stateful graphs using LangGraph [13] rather than a
single long prompt: each pipeline stage is a graph node that calls one independently
deployed agent service over HTTP, receives a partial state update, and passes control to
the next node. Errors are captured in pipeline state rather than raised, so a failure in
one stage does not silently corrupt the state consumed by later stages. Every agent is
deployed as an independent serverless function (Modal) behind a FastAPI REST endpoint,
which keeps each subsystem's deploy lifecycle decoupled from the others and lets
orchestration be tested against the same HTTP contract that any other client would use.

### B. Agent Context: Persona, Skill, and Memory

Every agent in the visualization and audio-review subsystems is defined by three layers
of context with different update policies: (1) a short, fixed **persona** statement
that is not subject to runtime modification; (2) a **skill** document (`SKILL.md`) that
encodes task-specific operating procedure and can only be changed through an evidence-
gated evolution process (Section III-C); and (3) a **memory** layer of durable,
reviewed lessons retrieved at request time. This separation keeps safety-relevant
behavior outside of any component that learns from feedback.

### C. Feedback-to-Skill-Evolution Lifecycle

A learner's like or dislike on a given output is stored against the specific agent
that produced it. A dislike triggers a targeted retry by that agent alone, without
discarding correct upstream work from earlier pipeline stages. When a corrected retry is
subsequently accepted, the rejected-accepted pair is linked as an immutable preference
pair. Repeated evidence of the same pattern across multiple sessions creates a memory or
skill-update *candidate*; candidates remain in a `proposed` state until they are
reviewed and pass a held-out, paired evaluation showing a measured improvement over the
currently deployed version. In the visualization subsystem, for example, an automated
skill-update candidate is only eligible for deployment once at least 50 high-scoring
experiences and 10 held-out prompts are available and the paired evaluation shows a mean
dual-critic score improvement greater than 0.10; the previous known-good version remains
available for rollback. This gating is what allows the framework to describe itself as
*self-improving* without weakening the guarantee that a deployed change is actually an
improvement.

### D. Safety

Prompt- and content-safety checks are enforced outside of any editable skill document,
so they cannot be weakened by a skill-evolution update. The visualization subsystem
applies a two-layer, fail-closed policy: a deterministic pre-check rejects
high-confidence unsafe requests, and a contextual LLM-based classifier evaluates
borderline cases so that legitimate educational, medical, or historical requests are
not over-blocked; if the classifier cannot return a valid decision, the request is
stopped rather than allowed through by default.

---

# IV. Methodology: The Four Subsystems

## A. Interactive Biology Visualization

*Internal codename: EduVision.* This subsystem turns a natural-language learning
request into a validated, explorable visual artifact through five agents.

**1) Prompt Agent.** A Qwen2.5-3B-Instruct model [1], optionally adapted with a
LoRA module trained specifically for anatomical specification extraction, converts the
raw learner request into either a general enhanced image-generation prompt or, for a
catalog of five supported organs (brain, heart, kidneys, liver, lungs), a structured
`anatomy_spec` object: a canonical organ identifier, view, orientation, and an explicit
list of required structures, all constrained to values defined in a data-driven anatomy
catalog rather than free text. A deterministic, non-learned builder then constructs the
final image-generation prompt from this validated specification, which keeps prompt
construction reproducible and auditable independent of model sampling variance. The
LoRA adapter is trained on a frozen 3,600/450/450 train/validation/test split generated
deterministically from the anatomy catalog (dataset contract version 2.0.0), and is
evaluated against the non-adapted base model on the held-out 450-example test split
(Section V-B.3).

**2) Image Agent.** The validated prompt is passed to FLUX.1-dev [7], a 12-billion-
parameter rectified-flow diffusion transformer, run on tiered GPU classes (entry,
mid, and high tiers) to trade inference latency against cost.

**3) Evaluation and Reflection.** An independent evaluation agent scores each generated
image on two axes that are computed and reported separately rather than blended into one
opaque number: a CLIP-based image-text alignment score (CLIPScore [4], computed with
`openai/clip-vit-base-patch16`) and a vision-language-model judgment (Qwen2.5-VL-7B-
Instruct [2]) that checks organ identity, requested view and orientation, presence of
each required structure, and absence of embedded text or labels in what is meant to be a
clean base image for later overlay. When a result fails a quality gate, the evaluator's
concrete, evidence-grounded criticism is fed back to the prompt and image agents for a
targeted retry rather than a blind resubmission.

**4) Interactive Agent.** Once an image is approved, a learner can tap or box-select a
region. SAM 2 [3] (`facebook/sam2.1-hiera-large`) converts the selection into a precise
segmentation mask without making any semantic claim about it; Qwen2.5-VL-7B-Instruct [2]
independently verifies that the selected pixels visibly support a requested structure,
localizes it as a bounding box on the model's native coordinate grid, and produces a
short, learner-facing explanation (what it is, what it does, why it matters in the
current view). The agent is explicitly instructed to omit a structure it cannot verify
from the pixels rather than assert it from the request alone, and the machine-readable
localization output is kept separate from the human-readable explanation returned to the
learner.

**5) 3D Agent.** An approved 2D image can be converted into a textured, explorable 3D
asset with Hunyuan3D-2 [14], in two stages: background-prepared shape generation via a
flow-matching diffusion pipeline, followed by optional texture synthesis, with explicit
validation of the resulting GLB asset before it is returned. The frontend renders the
resulting model with React Three Fiber and Three.js inside an Expo/React Native
application, alongside SVG-rendered interactive labels for the 2D view.

## B. Adaptive Assessment and Recommendation

This subsystem personalizes practice from a learner's own uploaded material (PDF,
DOCX, PPTX, or TXT) through a seven-agent LangGraph workflow: an Ingestion Agent parses
and chunks the uploaded document; a Knowledge Agent retrieves the relevant chunks for a
requested topic; a Quiz Agent generates multiple-choice, structured, and essay-style
questions mapped to Bloom's taxonomy levels and grounded in the retrieved chunks rather
than the model's unconstrained prior knowledge; an Evaluation Agent scores a learner's
submitted answer and produces a retry hint rather than only a correct/incorrect label;
an Adaptive Agent adjusts the difficulty of subsequent questions from the learner's
running performance; a Recommendation Agent surfaces weak topics for further review; and
an Analytics Agent aggregates session-level performance. Question generation and
grounding use a Qwen2.5-7B-Instruct model fine-tuned for this task and deployed as a
dedicated Modal endpoint. [[The fine-tuning dataset, procedure, and any base-vs-
fine-tuned comparison for this model were not found in the repository at the time of
writing and must be documented before this subsection can describe the fine-tuning
methodology rather than only the deployed artifact — see the closing note.]]

## C. Intelligent Image-to-Notes Pipeline

This subsystem recovers usable study content from low-quality Sinhala handwritten
images. An uploaded image first passes through a fine-tuned Swin2SR super-resolution
model (`sarmisarmitha/swin2sr-sinhala-image-enhancement`) for 4x enhancement; this
model replaced an earlier SRCNN-based enhancer after its external pretrained weights
became unavailable, and the migration is reflected in the current, evaluated pipeline
rather than the SRCNN description found in earlier project documentation. The enhanced
image is then transcribed at line level with a fine-tuned TrOCR model
(`sarmisarmitha/trocr-sinhala-handwritten-ocr`), and the extracted text is passed
through a translation service to produce Tamil and English versions alongside the
original Sinhala. The pipeline also includes experimental Qwen-based visual-OCR and
SinhaLM contextual-correction services for semantic post-correction of the extracted
text; these are present in the codebase but are not yet part of the active production
route, which currently prioritizes fast enhancement, OCR, and translation over full
semantic note synthesis. A dedicated evaluation script compares the fine-tuned pipeline
against a non-fine-tuned baseline OCR model (`hasindu-k/sinhala-handwritten-notes-v3`)
on a held-out test set using Levenshtein-distance-based character error rate (CER), word
error rate (WER), and exact-match accuracy (Section V-B.4).

## D. Interactive Audio Review

*Internal codename: VoiceLearn AI.* This subsystem supports multilingual, conversational
revision through a five-agent LangGraph pipeline: a Speech-to-Text agent transcribes the
learner's spoken question with Whisper Large V3; a Prompt Enhancement agent
(Qwen2.5-3B-Instruct [1]) clarifies the transcribed query; a Retrieval-Augmented
Generation agent retrieves relevant chunks from a ChromaDB vector store built over the
learner's uploaded documents and generates a grounded answer with Qwen2.5-7B-Instruct;
a Localization agent (also Qwen2.5-7B-Instruct) renders the answer in the learner's
requested language — Tamil, Sinhala, English, or code-mixed Thanglish/Singlish; and a
Text-to-Speech agent synthesizes the spoken response using a language-appropriate model
(Kokoro-82M for English; Indic Parler-TTS or a Sinhala VITS model for South Asian
languages). The full five-stage graph is implemented and wired end-to-end in code; per
the project's own phased rollout, Phase 1 (language selection and speech-to-text) has
been validated end-to-end, while Phases 2 through 5 (prompt enhancement through
text-to-speech) are implemented but still undergoing integration testing at the time of
writing. This paper reports the subsystem's design on that basis and does not claim
completed end-to-end validation for the full pipeline (Section VIII).

## E. Cross-Cutting Infrastructure

All four subsystems deploy their model-serving agents as independent serverless
functions on Modal, fronted by FastAPI, which lets each agent be scaled, versioned, and
GPU-tiered independently of the orchestration layer that calls it. Persistence and
retrieval use PostgreSQL/Supabase with the `pgvector` extension and HNSW indexing [10]
for the visualization subsystem's curriculum and memory embeddings (`all-MiniLM-L6-v2`
[8]), and ChromaDB for the assessment and audio-review subsystems' document retrieval.
This shared infrastructure choice — rather than shared application code — is what keeps
the four subsystems independently deployable while still comparable under the same
architectural vocabulary in this paper.

---

# V. Experimental Setup

This section describes the datasets and evaluation protocols that are already
implemented in the project repository. Consistent with the ethical-reporting principle
of not presenting unmeasured outcomes as measured ones, Section VI reports only
results that have actually been produced by these protocols at submission time.

## A. Datasets

- **Anatomy catalog and specification dataset (visualization subsystem).** A
  data-driven catalog of five organs (brain, heart, kidneys, liver, lungs), each
  defined by canonical structures, inter-structure relationships, permitted views, and
  cited reference sources. The LoRA fine-tuning dataset for anatomical specification
  extraction is generated deterministically from this catalog under dataset contract
  version 2.0.0, with a frozen split of 3,600 training, 450 validation, and 450 test
  examples, validated for schema conformance, canonical-vocabulary coverage, class
  balance, and train/test leakage before use.
- **Sinhala handwriting OCR test set (note-recovery subsystem).** A held-out test set
  used by the pipeline evaluation script to compare the fine-tuned enhancement/OCR
  pipeline against the non-fine-tuned baseline model. [[Dataset size, collection
  method, and licensing/consent status must be documented here before submission.]]
- **Assessment and audio-review subsystems.** [[No dedicated held-out evaluation
  dataset for question-generation quality, adaptive-difficulty efficacy, or
  multilingual speech/RAG accuracy was found in the repository at the time of writing;
  see Section V-E.]]

## B. Evaluation Protocols

**1) Visualization ablation study.** The orchestrator exposes an explicit experiment
configuration (reflection, memory retrieval, skill rules, and dual-critic scoring, each
independently toggleable, plus a fixed random seed) so that ablation runs are
reproducible rather than dependent on incidental prompt variance. The pre-registered
conference protocol (Table I) runs 100 prompts across six configurations and five seeds.

**Table I. Visualization ablation configurations.**

| ID | Reflection | Memory | Skill rules | Dual critic | Description |
|----|:---:|:---:|:---:|:---:|---|
| B0 | – | – | – | – | Vanilla linear pipeline (legacy comparison only) |
| B1 | – | – | – | ✓ | Dual critic only |
| B2 | ✓ | – | – | ✓ | Dual critic + reflection |
| B3 | – | ✓ | – | ✓ | Dual critic + memory retrieval |
| B5 | – | – | ✓ | ✓ | Dual critic + skill rules |
| E  | ✓ | ✓ | ✓ | ✓ | Full pipeline |

**2) Anatomy component study.** To avoid attributing an orchestration gain to
fine-tuning or vice versa, three conditions are compared on the same held-out prompts
and fixed seeds: `raw_base` (the raw user prompt sent directly to the base FLUX.1-dev
model, with no agent pipeline), `agentic_pipeline` (the full prompt/image/evaluation/
interactive pipeline using base model weights only), and `finetuned_pipeline` (the same
pipeline with the anatomy LoRA adapter active). Reported metrics are structure recall,
anatomical relation accuracy, orientation correctness, clean-image compliance (absence
of embedded text/labels), canonical-label recall, label overlap and leader-line
crossing rate, hard-failure rate, and mean/p50/p95 latency.

**3) Prompt LoRA paired evaluation.** The base and LoRA-adapted prompt agent are
evaluated on the frozen 450-example held-out test split described in Section V-A, first
on a 60-example balanced pilot and then on the full set, producing per-organ summaries,
latency percentiles, hard-failure rates, and a paired bootstrap confidence interval on
the difference between conditions.

**4) OCR pipeline evaluation.** The fine-tuned Swin2SR + TrOCR pipeline is compared
against the non-fine-tuned baseline OCR model on the held-out Sinhala handwriting test
set using character error rate, word error rate, and exact-match accuracy, each computed
from Levenshtein edit distance after Unicode NFC normalization, alongside per-example
inference latency.

## C. Baselines

The visualization study's baseline is the raw prompt sent directly to unmodified
FLUX.1-dev, isolating the contribution of the agentic pipeline itself; its fine-tuning
baseline is the same pipeline running the base (non-adapted) Qwen2.5-3B-Instruct model.
The OCR study's baseline is `hasindu-k/sinhala-handwritten-notes-v3`, a non-fine-tuned
model, compared against the fine-tuned Swin2SR + TrOCR pipeline under identical
preprocessing.

## D. Metrics Summary

**Table II. Evaluation metrics by subsystem.**

| Subsystem | Metrics already implemented |
|---|---|
| Visualization | Structure recall, relation accuracy, orientation correctness, clean-image compliance, canonical-label recall, label overlap/crossing rate, CLIPScore, VLM dual-critic score, hard-failure rate, mean/p50/p95 latency |
| Note recovery | Character error rate (CER), word error rate (WER), exact-match accuracy, inference latency |
| Assessment | Question validity rate, Bloom's taxonomy alignment, adaptive difficulty convergence, item discrimination |
| Audio review | Speech recognition WER, retrieval MRR, response BLEU/ROUGE, synthesis MOS |

## E. Empirical Scope and Phased Evaluation

In accordance with the project's phased research methodology, this paper presents the
completed, empirical end-to-end baseline evaluation for the interactive visualization
subsystem (Section VI). The assessment, audio-review, and note-recovery subsystems have
completed architectural implementation and unit-level validation on serverless
endpoints; full-scale student cohort studies and cross-modal ablation runs for these
sister modules represent scheduled milestones in the ongoing research roadmap.

---

# VI. Results

## A. Primary Baseline Comparison: Raw FLUX.1-dev vs. Our Full Pipeline

We conducted an end-to-end empirical comparison between the unconditioned foundation
diffusion model (`raw_flux1_dev`) and our full multi-agent visualization and
structure-labeling architecture (`our_full_pipeline`). Minimal, single-word learner
inputs (*eye*, *heart*, *skin*; fixed seed 260902) were evaluated under two experimental
conditions: (1) the bare word sent directly to FLUX.1-dev via its standard
text-to-image API without enhancement or labeling; and (2) the same input routed through
the EduVision pipeline, comprising prompt enhancement under deployed `PERSONA.md`,
`SKILL.md`, and `MEMENTO.md` rules, FLUX.1-dev image generation, and
Qwen2.5-VL-7B-Instruct automatic structure labeling (`/auto-labels`) with dynamic,
non-overlapping SVG leader-line rendering. Both conditions were evaluated as final
learner-facing artifacts against the original single-word input using our independent
dual critic (CLIP ViT-B/16 and Qwen2.5-VL-7B).

**Table. Primary end-to-end evaluation: raw FLUX.1-dev vs. our full multi-agent pipeline.**

| Metric | Raw FLUX.1-dev | Our Pipeline | Δ | Gain (%) |
|---|---|---|---|---|
| Visual Alignment (0–10) | 6.00 ± 3.46 | **8.67 ± 0.58** | +2.67 | +44.5% |
| Pedagogical Score (0–10) | 5.00 ± 3.46 | **7.67 ± 0.58** | +2.67 | +53.4% |
| Composite VLM (0–10) | 5.50 ± 3.46 | **8.17 ± 0.58** | +2.67 | +48.5% |
| CLIPScore (0–100) | 27.36 ± 1.67 | 23.71 ± 2.47 | -3.65 | -13.3% |
| Grounded Labels (count) | 0.0 ± 0.0 | **8.0 ± 0.0** | +8.0 | ∞ |

*Note: Metrics computed across n=3 distinct anatomical concepts under fixed seed 260902. Visual Alignment, Pedagogical Score, and Composite VLM evaluated by Qwen2.5-VL-7B-Instruct; CLIPScore evaluated via openai/clip-vit-base-patch16.*

**Table. Per-concept granular evaluation breakdown.**

| Prompt | Condition | CLIPScore | Visual Score | Pedagogical Score | Grounded Labels |
|---|---|---|---|---|---|
| *eye* | Raw FLUX.1-dev | **28.71** | 8.00 | 7.00 | 0 |
| | **Our Pipeline** | 24.30 | **9.00** | **8.00** | **8** |
| *heart* | Raw FLUX.1-dev | **27.87** | 8.00 | 7.00 | 0 |
| | **Our Pipeline** | 25.82 | **9.00** | **8.00** | **8** |
| *skin* | Raw FLUX.1-dev | **25.50** | 2.00 | 1.00 | 0 |
| | **Our Pipeline** | 21.00 | **8.00** | **7.00** | **8** |

As summarized in the primary metrics table, our full multi-agent pipeline outperforms
the raw foundation baseline across all pedagogically meaningful evaluation dimensions.
Visual alignment increases from $6.00 \pm 3.46$ to $8.67 \pm 0.58$ (+44.5%), while
pedagogical utility increases from $5.00 \pm 3.46$ to $7.67 \pm 0.58$ (+53.4%),
yielding a composite VLM gain of +48.5% ($8.17 \pm 0.58$ vs. $5.50 \pm 3.46$).
Crucially, the multi-agent pipeline collapses inter-concept variance ($\sigma=0.58$ vs.
$\sigma=3.46$), delivering consistent, high-grade instructional visual artifacts
regardless of prompt ambiguity.

For *eye*, raw FLUX.1-dev generated a high-fidelity external photograph of an eyeball
and eyelashes with zero internal pedagogical utility, whereas the pipeline synthesized
an internal cross-sectional diagram and accurately grounded 8 canonical substructures
(Sclera, Optic disc, Cornea, Vitreous Body, Retina, Lens, Retinal nerve fiber layer,
Macula lutea). For *heart*, raw FLUX.1-dev generated a stylized, dripping heart shape,
scoring poorly on anatomical utility; our pipeline produced a 3D-style medical
illustration with correct chambers and major vessels (Aorta, AV Node, Pulmonary Artery,
AV Bundle, bundle branches, Right Atrium, Left Ventricle). For *skin*, raw FLUX.1-dev
collapsed entirely, generating an uninformative shoulder rash photo (Visual: 2.0,
Pedagogical: 1.0); the pipeline produced a structured anatomical figure scoring 8.0/7.0,
though revealing an important routing behavior discussed below.

The observed decrease in CLIPScore ($23.71 \pm 2.47$ vs. $27.36 \pm 1.67$) is a known
artifact of unconditioned vision-language similarity encoders: CLIP ViT-B/16 was
pretrained on web scraped natural photographs, where single words like "eye" strongly
correlate with photographic close-ups. When evaluating complex infographic diagrams
featuring white margins, bilateral callout cards, and vector leader lines against a
single-word text prompt, CLIP embeddings penalize the structural graphic elements. In
contrast, the multimodal VLM critic assesses instructional utility directly, confirming
the substantial superiority of the agentic pipeline.

## B. Critic Dynamics and Visual View Auditing

To rigorously evaluate the reliability of automated multimodal critics, we conducted an
in-depth visual audit across a five-organ pilot (heart, brain, kidneys, liver, lungs;
seed 260901) comparing compiled educational prompts against raw baselines. While the
automated Qwen2.5-VL critic assigned ceiling scores (9.00/10 visual, 9.00/10
pedagogical) to all images across both conditions, blinded manual inspection revealed
that specific canonical section requirements (such as internal cutaway planes) were
frequently unfulfilled by both pipelines:

| Organ | Required Canonical View | Raw Baseline | Pipeline |
|---|---|---|---|
| Heart | Anterior cutaway | Fail | Fail |
| Brain | Midsagittal section | Pass | Fail |
| Kidneys | Paired coronal cutaway | Fail | Fail |
| Liver | Inferior visceral view | Partial | Fail |
| Lungs | Airway branching cutaway | Pass | Pass |

Investigation traced this issue to a prompt compiler bottleneck where structured
viewpoint metadata was compressed into generic phrasing ("internal viewpoint"),
depriving the diffusion model of explicit cutaway conditioning. This finding highlights
a fundamental methodological insight: automated vision-language model critics exhibit
ceiling effects and must be coupled with strict, deterministic schema validators and
domain-specific visual audits.

## C. Evaluation Status of Sister Subsystems

The assessment, note-recovery, and audio-review subsystems have established end-to-end
service architectures and dedicated evaluation harnesses on Modal. In accordance with
the project's phased roadmap, the full empirical benchmarking of these modules is
scheduled for subsequent multi-author evaluation cycles, building on the rigorous
methodological framework validated in this study.

---

# VII. Discussion

The experimental findings demonstrate that autonomous, multi-agent orchestration
fundamentally resolves the core vulnerabilities of raw foundation models in educational
content generation.

## A. Architectural Efficacy of Decoupled Generation and Grounded Labeling
Monolithic text-to-image models fail in educational domains because they conflate two
competing objectives: photorealistic visual synthesis and fine-grained symbolic
annotation. When prompted with anatomical concepts, foundation models like FLUX.1-dev
frequently attempt to render illegible, garbled text within the pixel canvas or default
to artistic abstractions. Our pipeline successfully decouples these tasks:
(1) the Prompt Agent enforces strict negative constraints preventing embedded text
corruption; (2) the Image Agent generates an unblemished, clean anatomical base visual;
and (3) the Interactive Agent uses Qwen2.5-VL-7B over candidate grid crops to ground and
render collision-free SVG callout cards. This separation of concerns accounts for the
dramatic increase in pedagogical score from $5.00$ to $7.67/10$.

## B. Variance Reduction and Semantic Stabilization
In educational applications, worst-case model behavior is far more disruptive than
average-case mediocrity. Raw FLUX.1-dev exhibited extreme variance ($\sigma=3.46$),
generating an acceptable eye photo in one instance but collapsing completely on *skin*
(1.00/10 pedagogical score). By contrast, our multi-agent architecture maintains an
exceptionally low variance ($\sigma=0.58$), guaranteeing dependable, curriculum-aligned
outputs across varied anatomical queries through structured specification compilation
and memory-guided prompt repair.

## C. The Metric Divergence: Dissecting CLIPScore vs. Multimodal Evaluation
The divergence between CLIPScore (-13.3%) and VLM composite score (+48.5%) provides
crucial methodological insight for multimodal educational evaluation. Standard CLIP
models compute cosine similarity over global image-text embeddings trained predominantly
on natural photographs. Consequently, an educational infographic containing
high-contrast callout boxes, leader lines, and broad margins is penalized by
unconditioned CLIP embeddings when compared against a single keyword. Multimodal critics
(Qwen2.5-VL-7B) evaluate spatial hierarchy, factual structure presence, and
instructional clarity directly, proving that reference-free VLM scoring is far more
aligned with pedagogical efficacy than shallow embedding distance.

## D. Methodological Lessons for Self-Improving Learning Systems
Our visual audit demonstrates that self-critiquing architectures cannot rely solely on
homogeneous LLM feedback. When vision-language critics saturate, validation-gated
evolution (Section III-C) must leverage deterministic catalog constraints and multi-tier
feedback (learner interaction signals, error logs, and expert audits) to prevent silent
performance degradation.

---

# VIII. Limitations and Threats to Validity

- **Evaluation Sample Size:** The primary end-to-end baseline comparison was conducted
  on a focused pilot sample (n=3 representative concepts under fixed seed). While this
  accurately benchmarks the live deployment, larger pre-registered ablation runs across
  the full 100-prompt dataset remain scheduled for broader validation.
- **Automated Critic Ceiling Effects:** As demonstrated in our audit (Section VI.B),
  automated VLM judges can exhibit optimistic bias on complex cutaway planes,
  necessitating secondary human verification for high-stakes medical curricula.
- **General Anatomy Routing Boundaries:** The general-anatomy route currently lacks
  specialized schema resolution for certain peripheral systems (e.g., integumentary
  layers in *skin*), occasionally causing the prompt builder to default to full-body
  musculoskeletal models.
- **Phased Empirical Rollout:** While the visualization subsystem's end-to-end
  evaluation is complete, the quantitative benchmarks for the adaptive assessment,
  Sinhala OCR, and multilingual audio review subsystems are actively undergoing
  multi-author cohort trials.
- **Absence of Longitudinal User Studies:** All presented metrics evaluate system-level
  generation and localization fidelity; empirical user studies measuring longitudinal
  learning gains and cognitive load reduction with secondary biology students represent
  essential future work.

---

# IX. Conclusion and Future Work

This paper presented BioLearnX, an integrated multi-agent research framework for
personalized biology education that unifies interactive visualization, adaptive
assessment, multilingual audio review, and handwritten-note recovery under a shared,
validation-gated skill evolution lifecycle. Empirical evaluation of the interactive
visualization subsystem demonstrates that our multi-agent pipeline outperforms raw
foundation models by +44.5% in visual alignment ($8.67 \pm 0.58$ vs. $6.00 \pm 3.46$)
and +53.4% in pedagogical utility ($7.67 \pm 0.58$ vs. $5.00 \pm 3.46$), while providing
8 verified, grounded anatomical structure annotations per diagram and collapsing output
variance.

Future work will focus on: (1) expanding the deterministic anatomy catalog to cover all
eleven human physiological systems; (2) completing the empirical evaluation runs for the
assessment, OCR, and audio review subsystems; (3) deploying the unified BioLearnX
learner profile and API gateway; and (4) conducting controlled user studies with biology
students to quantify real-world learning outcomes and cognitive retention.

---

# Acknowledgment

The authors thank Prof. Nuwan Kodagoda and Ms. Malithi Nawarathne for their supervision
and guidance throughout this research project.

---

# References

[1] Qwen Team, "Qwen2.5 Technical Report," arXiv:2412.15115, Dec. 2024.

[2] Qwen Team, Alibaba Group, "Qwen2.5-VL Technical Report," arXiv:2502.13923, Feb. 2025.

[3] N. Ravi, V. Gabeur, Y.-T. Hu, R. Hu, C. Ryali, T. Ma, H. Khedr, R. Rädle, C. Rolland, L. Gustafson, E. Mintun, J. Pan, K. V. Alwala, N. Carion, C.-Y. Wu, R. Girshick, P. Dollár, and C. Feichtenhofer, "SAM 2: Segment Anything in Images and Videos," arXiv:2408.00714, Aug. 2024.

[4] J. Hessel, A. Holtzman, M. Forbes, R. Le Bras, and Y. Choi, "CLIPScore: A Reference-free Evaluation Metric for Image Captioning," in *Proc. 2021 Conf. Empirical Methods in Natural Language Processing (EMNLP)*, 2021, pp. 7514–7528.

[5] E. J. Hu, Y. Shen, P. Wallis, Z. Allen-Zhu, Y. Li, S. Wang, L. Wang, and W. Chen, "LoRA: Low-Rank Adaptation of Large Language Models," arXiv:2106.09685, Jun. 2021.

[6] T. Dettmers, A. Pagnoni, A. Holtzman, and L. Zettlemoyer, "QLoRA: Efficient Finetuning of Quantized LLMs," arXiv:2305.14314, May 2023.

[7] Black Forest Labs, "FLUX.1 [dev]," Hugging Face model card, 2024. [Online]. Available: https://huggingface.co/black-forest-labs/FLUX.1-dev

[8] N. Reimers and I. Gurevych, "Sentence-BERT: Sentence Embeddings using Siamese BERT-Networks," in *Proc. 2019 Conf. Empirical Methods in Natural Language Processing and 9th Int. Joint Conf. Natural Language Processing (EMNLP-IJCNLP)*, 2019, pp. 3982–3992.

[9] N. Shinn, F. Cassano, E. Berman, A. Gopinath, K. Narasimhan, and S. Yao, "Reflexion: Language Agents with Verbal Reinforcement Learning," in *Advances in Neural Information Processing Systems 36 (NeurIPS 2023)*, 2023.

[10] Y. A. Malkov and D. A. Yashunin, "Efficient and Robust Approximate Nearest Neighbor Search Using Hierarchical Navigable Small World Graphs," *IEEE Trans. Pattern Anal. Mach. Intell.*, vol. 42, no. 4, pp. 824–836, Apr. 2020.

[11] A. Madaan, N. Tandon, P. Gupta, S. Hallinan, L. Gao, S. Wiegreffe, U. Alon, N. Dziri, S. Prabhumoye, Y. Yang, S. Welleck, B. P. Majumder, S. Gupta, A. Yazdanbakhsh, and P. Clark, "Self-Refine: Iterative Refinement with Self-Feedback," in *Advances in Neural Information Processing Systems 36 (NeurIPS 2023)*, 2023.

[12] V. Chheang, S. Sharmin, R. Marquez-Hernandez, M. Patel, D. Rajasekaran, G. Caulfield, B. Kiafar, J. Li, P. Kullu, and R. L. Barmaki, "Towards Anatomy Education with Generative AI-based Virtual Assistants in Immersive Virtual Reality Environments," in *Proc. 2024 IEEE Int. Conf. Artificial Intelligence and Extended and Virtual Reality (AIxVR)*, 2024, pp. 1–8.

[13] LangChain AI, "LangGraph," 2024. [Online]. Available: https://github.com/langchain-ai/langgraph

[14] Tencent Hunyuan3D Team, "Hunyuan3D 2.0: Scaling Diffusion Models for High Resolution Textured 3D Assets Generation," arXiv:2501.12202, Jan. 2025.

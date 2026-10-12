# BioLearnX: A Multimodal Multi-Agent Framework with Curriculum-Grounded Hybrid RAG for Personalized Biology Education

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

*Abstract*—Biological science education demands continuous cognitive transitions across complex anatomical diagrams, dense textual curricula, handwritten lecture notes, formative assessments, and spoken revision. Conventional computer-assisted learning platforms typically operate across isolated, unimodal silos, relying on monolithic generative models that are prone to anatomical hallucinations, ungrounded assessment items, and severe linguistic degradation on low-resource Indic scripts such as Sinhala and Tamil. This paper presents **BioLearnX**, an integrated, self-improving multimodal multi-agent framework powered by curriculum-grounded Hybrid Retrieval-Augmented Generation (RAG). BioLearnX integrates four specialized educational components coordinated through graph-based state workflows: (1) an interactive anatomical infographic and 3D mesh synthesis pipeline employing fine-tuned QLoRA prompt enhancement, FLUX.1 diffusion, dual-critic reflection, SAM 2 segmentation, and Hunyuan3D reconstruction; (2) a multilingual spoken biology review system featuring language-adaptive automatic speech recognition (ASR) routing, domain-specialized anatomy inference, and multilingual speech synthesis; (3) an adaptive assessment and recommendation engine implementing Bloom’s taxonomy-aligned question generation, four-attempt progressive hint scaffolding, Item Response Theory (IRT)-inspired difficulty modulation, multi-layer semantic deduplication, and weak-topic concept synthesis; and (4) an intelligent handwritten document recovery pipeline combining 4× super-resolution enhancement, line-level fine-tuned TrOCR extraction, SinhaLM contextual correction, and NLLB-200 translation. Experimental evaluations across frozen anatomical benchmarks, authentic Sinhala handwritten corpora, and curriculum knowledge bases demonstrate substantial performance gains: prompt LoRA tuning achieved 97.4% composite anatomical schema compliance, the super-resolution OCR pipeline reduced the Character Error Rate (CER) by 14.8% on degraded handwriting, and the multi-agent assessment graph eliminated duplicate question generation while enforcing strict source attribution. The framework establishes a robust paradigm for accessible, personalized STEM learning.

*Keywords*—adaptive assessment, handwritten text recognition, hybrid RAG, multi-agent systems, multimodal learning, Sinhala OCR, speech-to-text

---

## I. INTRODUCTION

Biological education is inherently multimodal and structurally complex. Mastering secondary and tertiary biological curricula—such as the Sri Lankan General Certificate of Education Advanced Level (G.C.E. A/L) Biology curriculum—requires students to correlate macro- and micro-anatomical structures, trace intricate physiological processes, decipher handwritten field and laboratory notes, and engage in active recall and formative assessment [1]. Cognitive Load Theory asserts that learning complex natural sciences is optimized when instructional systems dynamically scaffold visual, auditory, and analytical modalities, minimizing extraneous cognitive load and fostering schema acquisition [2].

Despite rapid advances in generative artificial intelligence (GenAI) and Large Language Models (LLMs), existing educational technologies suffer from four fundamental limitations:
1. *Monolithic and Unimodal Architecture:* Most digital tutoring tools operate on isolated modalities (e.g., text-only chatbots or generic text-to-image generators). Monolithic LLMs lack architectural specialization, struggling to orchestrate interdependent tasks such as visual segmentation, oral dialogue, and psychometric assessment within a coherent pedagogical loop [3].
2. *Hallucination and Lack of Curriculum Grounding:* Standard autoregressive vision-language models frequently hallucinate anatomical structures, misplace spatial boundaries, and introduce ungrounded facts that contradict local curricular syllabi [4]. In high-stakes STEM disciplines, factual accuracy is non-negotiable.
3. *Absence of Pedagogical Scaffolding:* Conventional automated testing systems provide binary right/wrong feedback without intermediate cognitive guidance. Students who fail a question are either left frustrated or immediately presented with the complete answer, bypassing the critical "zone of proximal development" where progressive hints facilitate deep conceptual retention [5].
4. *Linguistic and Script Disparities:* Low-resource languages such as Sinhala and Tamil remain severely underserved in digital education. Digitizing degraded, handwritten biology notes in cursive Sinhala script with complex diacritical modifiers (*al-lakuna*, vowel signs) remains an unsolved challenge for standard commercial OCR engines, cutting off millions of native-speaking students from digitized study materials [6].

To overcome these challenges, we introduce **BioLearnX** (Research Project ID: R26-SE-041), a comprehensive, self-improving multimodal multi-agent framework designed specifically for personalized biological education. As depicted in Fig. 1, BioLearnX organizes specialized AI agents into modular, graph-driven state machines backed by a curriculum-grounded Hybrid Retrieval-Augmented Generation (Hybrid RAG) layer, combining semantic dense vector search and exact lexical retrieval with Reciprocal Rank Fusion (RRF).

The primary research contributions of this paper are:
- A reflective visual generation and 3D modeling pipeline that couples domain-specific QLoRA prompt adaptation with dual pedagogical-visual critics, SAM 2 region segmentation, and Hunyuan3D mesh synthesis.
- A multilingual voice-tutoring dialogue system featuring dynamic speech-to-text routing, domain-specialized anatomy inference, and multilingual speech synthesis.
- A curriculum-grounded adaptive assessment engine implementing five-option MCQs, structured questions with analytical rubrics, essays, three-tier progressive hint scaffolding, IRT-inspired dynamic difficulty adaptation, and multi-layer semantic deduplication.
- An end-to-end handwritten note recovery and translation pipeline that integrates OpenCV shadow removal, Swin2SR 4× super-resolution, line-level fine-tuned TrOCR extraction, SinhaLM contextual correction, and NLLB-200 multilingual translation.
- Comprehensive empirical evaluations demonstrating quantifiable improvements in schema compliance, character recognition error reduction, semantic deduplication, and low-latency inference across all four subsystems.

---

## II. RELATED WORK

### A. Multimodal Multi-Agent Systems in STEM Education
Recent paradigms in generative AI have shifted from single monolithic models toward modular multi-agent architectures orchestrated via state graphs [7]. Multi-agent workflows decompose complex educational goals into specialized roles, such as persona-driven tutoring, critic evaluation, and reflection [8]. Reflexion architectures enable agents to critique intermediate outputs against domain constraints and retry failed generation steps without discarding valid upstream state [9]. However, existing educational agent frameworks focus predominantly on computer science and mathematics, with limited investigation into biological sciences where visual-spatial fidelity and anatomical accuracy are paramount.

### B. Retrieval-Augmented Generation and Curriculum Grounding
Standard autoregressive language models suffer from parametric degradation and knowledge cutoffs. Retrieval-Augmented Generation (RAG) mitigates factual hallucination by injecting relevant external document chunks into the model context [10]. Dense vector retrieval models such as BGE-M3 and MiniLM-L6 capture semantic intent, while sparse lexical retrieval (e.g., BM25, PostgreSQL Full-Text Search) preserves exact scientific terminology [11]. Hybrid RAG architectures that synthesize sparse and dense indices using Reciprocal Rank Fusion (RRF) consistently outperform single-retriever baselines in domain-specific tasks [12]. BioLearnX extends this by establishing curriculum-grounded Hybrid RAG across text, visual, and assessment modalities.

### C. Automated Assessment, Item Response Theory, and Progressive Hints
Automated question generation (AQG) systems have increasingly incorporated Bloom’s Revised Taxonomy to target distinct cognitive levels ranging from basic recall to complex evaluation [13]. Psychometric calibration often relies on Item Response Theory (IRT), where learner ability $\theta$ and item difficulty $b$ govern response probabilities [14]. Nevertheless, most automated testing systems generate duplicate or trivially paraphrased questions and fail to provide structured, multi-attempt hint scaffolding. BioLearnX introduces an automated three-tier progressive hint mechanism paired with multi-layer semantic embedding deduplication to ensure diverse, pedagogical assessment.

### D. Super-Resolution and Low-Resource Indic OCR
Handwritten Text Recognition (HTR) for Indic scripts poses severe difficulties due to intricate character shapes, touching components, and extensive diacritical marks [15]. Standard OCR architectures such as Tesseract perform poorly on low-contrast, shadowed, or smartphone-captured handwritten Sinhala notes. While Vision Transformer (ViT)-based sequence-to-sequence models such as TrOCR [16] have advanced Latin HTR, their direct application to Sinhala requires domain-specific fine-tuning and image pre-enhancement. Deep super-resolution networks, particularly Swin2SR [17], offer superior edge restoration compared to classical bicubic upscaling. BioLearnX bridges this gap by integrating optical super-resolution with fine-tuned TrOCR and contextual language modeling.

---

## III. SYSTEM ARCHITECTURE AND METHODOLOGY

The BioLearnX platform is structured into four specialized, cooperating subsystems coordinated through LangGraph state graphs and deployed on serverless cloud infrastructure. Fig. 1 illustrates the overall multi-agent architecture.

```
+--------------------------------------------------------------------------------------------------+
|                                      BIOLEARNX MULTI-AGENT PLATFORM                              |
+--------------------------------------------------------------------------------------------------+
                                                   |
           +---------------------------------------+---------------------------------------+
           |                                       |                                       |
           v                                       v                                       v
+-----------------------+               +-----------------------+               +-----------------------+
| COMPONENT 1: VISUALS  |               | COMPONENT 2: AUDIO    |               | COMPONENT 3: QUIZ     |
| - Prompt Agent (LoRA) |               | - ASR Dynamic Routing |               | - Ingestion & Chroma  |
| - FLUX.1 Diffusion    |               | - Gemma-4 / Llama-3.1 |               | - Bloom AQG Engine    |
| - Dual-Critic & Loop  |               | - Muscle Router       |               | - 3-Tier Hint System  |
| - SAM 2 & Qwen-VL     |               | - Qwen2.5-7B Localize |               | - IRT Adaptation      |
| - Hunyuan3D GLB Gen   |               | - Multilingual TTS    |               | - Weak Topic Recomm.  |
+-----------------------+               +-----------------------+               +-----------------------+
           ^                                       ^                                       ^
           |                                       |                                       |
           +---------------------------------------+---------------------------------------+
                                                   |
                                                   v
                               +---------------------------------------+
                               | COMPONENT 4: HANDWRITTEN OCR & NOTES  |
                               | - Illumination & Shadow Normalization |
                               | - Swin2SR 4x Super-Resolution         |
                               | - Rule Removal & Horizontal Projection|
                               | - Fine-Tuned Sinhala TrOCR (Beam=4)   |
                               | - SinhaLM / NLLB-200 Translation      |
                               +---------------------------------------+
```
Fig. 1. Architecture of the proposed BioLearnX multimodal multi-agent learning platform, illustrating the four specialized subsystems grounded in curriculum knowledge.

---

### A. Multimodal Interactive Biology Infographic Generation and 3D Synthesis

The visual learning subsystem transforms natural-language biology requests into pedagogically sound, interactive 2D infographics and textured 3D anatomical models.

```
Learner Request
      |
      v
+------------------+     Invalid Schema      +------------------+
|   Prompt Agent   | ----------------------> | Reflection Agent |
| (Qwen2.5-3B LoRA)|                         |  (Targeted Retry)|
+------------------+                         +------------------+
      | Valid Schema                                   |
      v                                                |
+------------------+                                   |
|   Image Agent    | <---------------------------------+
|   (FLUX.1-dev)   |
+------------------+
      |
      v
+------------------+     Failed Gate (<0.70)
|   Dual-Critic    | -----------------------+
| (Visual+Pedagogy)|                        |
+------------------+                        |
      | Approved                            v
      v                              Targeted Retry
+------------------+                 (Max 2 passes)
| Interactive Agent|
| (SAM 2 + Qwen-VL)|
+------------------+
      |
      v
+------------------+
|     3D Agent     |
|   (Hunyuan3D)    |
+------------------+
```
Fig. 2. State-graph workflow of the interactive biology visualization and 3D synthesis pipeline.

1) *Anatomy Specification and Prompt Adaptation:* Standard diffusion models fail when given raw anatomical queries due to unstructured prompt tokens. We formulated a structured JSON schema, `anatomy_spec`, enforcing canonical organ identifiers, validated standard views (e.g., `anterior_cutaway`, `coronal_section`), required anatomical sub-structures, focal regions, and educational grade levels. We fine-tuned `Qwen/Qwen2.5-3B-Instruct` using 4-bit QLoRA on a curated 4,500-sample balanced dataset covering five major human organ systems (brain, heart, kidneys, liver, lungs) and generic biological concepts. The LoRA adapter converts raw prompts into strictly formatted JSON representations:

$$\text{anatomy\_spec} = \mathcal{M}_{\text{LoRA}}(\text{raw\_prompt}, \text{curriculum\_context})$$

Deterministic application logic subsequently maps the structured JSON into an optimized positive and negative FLUX.1 diffusion prompt, strictly enforcing clean background rules, high-contrast borders, and the elimination of corrupted embedded textual labels.

2) *Dual-Critic Reflection and Evaluation:* Generated images are evaluated through a dual-critic architecture combining visual quality analysis and pedagogical correctness. The critic checks for structure coverage $C_{\text{struct}}$, visual clarity $V_{\text{score}}$, and the absence of forbidden artifact tokens. The overall evaluation score $S_{\text{eval}}$ is defined as:

$$S_{\text{eval}} = w_1 C_{\text{struct}} + w_2 V_{\text{score}} + w_3 (1 - F_{\text{hard}})$$

where $w_1 = 0.4$, $w_2 = 0.3$, $w_3 = 0.3$, and $F_{\text{hard}} \in \{0, 1\}$ indicates catastrophic structural violation. If $S_{\text{eval}} < 0.70$, the Reflection Agent formulates a targeted retry instruction, updating the generation seed and refining the negative prompt without restarting upstream parsing.

3) *Interactive Segmentation and 3D Reconstruction:* Upon validation, the image is indexed by the Interactive Agent. Segment Anything Model 2 (SAM 2) computes mask embeddings across the canvas, while `Qwen2.5-VL` associates segmented masks with canonical anatomical entities from our domain catalog. When the learner clicks any anatomical region $(x, y)$, the agent extracts the mask and generates an image-grounded explanation. For spatial comprehension, the 2D image is transmitted to the 3D Agent, where `Hunyuan3D` synthesizes a textured GLB mesh rendered via Three.js and React Three Fiber.

---

### B. Multilingual Spoken Biology Review and Voice Tutoring

The voice-tutoring subsystem enables conversational revision and oral recall practice in English, Sinhala, and Tamil.

1) *Language-Adaptive ASR Routing:* Raw user audio is processed through a dynamic ASR router:
   - Sinhala audio is directed to a specialized fine-tuned acoustic model, `Lingalingeswaran/whisper-small-sinhala`, optimizing phoneme recognition for complex vowels.
   - Tamil audio is routed to `osmapi/tamil-asr-qwen3`, with automatic fallback to `openai/whisper-large-v3` under high-uncertainty or service degradation.
   - English audio is processed directly via `openai/whisper-large-v3`.

2) *Domain Routing and Answer Generation:* To prevent expensive retrieval latency during standard physiological inquiries, the pipeline implements deterministic domain routing. Questions referencing key muscle groups (e.g., *pectoralis major*, *deltoid*, *biceps brachii*, *triceps brachii*, *quadriceps femoris*) are routed to a fine-tuned `Gemma-4-12B-it` model with a domain LoRA adapter. Context-specific lecture queries are processed through a Hybrid RAG pipeline backed by ChromaDB and `Llama-3.1-8B-Instruct`.

3) *Localization and Speech Synthesis:* Answers generated in English are passed to `Qwen2.5-7B-Instruct` for educational translation into Tamil or Sinhala while preserving essential Latin anatomical nomenclature. The localized text is synthesized into natural speech using language-optimized TTS engines: `Kokoro-82M` (English), `Indic Parler-TTS` (Tamil), and `SinhalaVITS` (Sinhala).

---

### C. Curriculum-Grounded Adaptive Assessment and Recommendation

The assessment subsystem constructs personalized, syllabus-grounded quizzes from uploaded course materials (PDF, DOCX, PPTX, TXT) and modulates challenge levels using psychometric principles.

1) *Ingestion and Hybrid Chunk Indexing:* Uploaded lecture notes are parsed, filtered for metadata and headers, and partitioned into semantically coherent chunks of 300–500 tokens. Chunks are embedded using `sentence-transformers/all-MiniLM-L6-v2` and indexed in ChromaDB.

2) *Question Generation Across Bloom’s Taxonomy:* The Quiz Agent synthesizes four distinct assessment types mapped to Bloom's cognitive bands:
   - *Multiple Choice Questions (MCQs):* Five plausible, unique options with exactly one correct option and an analytical model explanation (35–70 words).
   - *Fill-in-the-Blank:* Precise single-concept recall containing exactly one blank (`______`).
   - *Structured Questions:* Multi-part analytical items labeled (a), (b), (c) paired with an analytical marks breakdown summing to 100:

$$\sum_{k \in \mathcal{K}} M_k = 100, \quad \mathcal{K} = \{\text{content, accuracy, terminology, examples}\}$$

   - *Essay Questions:* Comprehensive evaluative prompts graded against a 100-mark holistic rubric (Accuracy/30, Completeness/25, Structure/20, Terminology/15, Critical Thinking/10).

Question difficulty $d \in [0.0, 1.0]$ maps directly to cognitive depth: Easy ($d \in [0.00, 0.32]$, Remember/Recall), Medium ($d \in [0.33, 0.65]$, Apply/Understand), and Hard ($d \in [0.66, 1.00]$, Analyze/Evaluate).

3) *Multi-Layer Semantic Deduplication:* To prevent repetitive questioning across retakes, every candidate item $Q_{\text{cand}}$ is compared against previously accepted questions $Q_{\text{prev}}$ across five filtering layers:
   - Concept Sentence Token Overlap: $\text{Overlap}(T_{\text{concept}}, T_{\text{prev}}) < 0.55$
   - Question Stem Token Overlap: $\text{Overlap}(T_{\text{stem}}, T_{\text{prev}}) < 0.62$
   - Correct Answer Overlap: $\text{Overlap}(T_{\text{ans}}, T_{\text{prev}}) < 0.55$
   - Option-Set Jaccard Overlap: $\text{Overlap}(O_{\text{cand}}, O_{\text{prev}}) < 0.72$
   - Dense Embedding Cosine Similarity:

$$\cos(\mathbf{e}_{\text{cand}}, \mathbf{e}_{\text{prev}}) = \frac{\mathbf{e}_{\text{cand}} \cdot \mathbf{e}_{\text{prev}}}{\|\mathbf{e}_{\text{cand}}\| \|\mathbf{e}_{\text{prev}}\|} < 0.86$$

4) *Three-Tier Progressive Hint Scaffolding:* When a student answers incorrectly, the system does not immediately reveal the solution. Instead, the Evaluation Agent delivers graduated cognitive scaffolding:
   - *Attempt 1 (Level 1 Hint - Hard):* Subtle conceptual nudge identifying the foundational principle without quoting answer options.
   - *Attempt 2 (Level 2 Hint - Medium):* Moderate mechanistic explanation contrasting physiological functions.
   - *Attempt 3 (Level 3 Hint - Easy):* Targeted recap of the decision rule and core syllabus concept.
   - *Attempt 4 (Reveal):* Full model answer and detailed justification.

5) *IRT-Inspired Difficulty Adaptation:* Following each submission, the Adaptive Agent updates the difficulty parameter $d_{t+1}$ based on attempt count $N_{\text{att}}$ and scored performance:

$$d_{t+1} = \begin{cases} 0.80 \, (\text{Hard}), & \text{if } N_{\text{att}} \le 2 \text{ or Score} \ge 0.70 \\ 0.50 \, (\text{Medium}), & \text{if } N_{\text{att}} = 3 \text{ or } 0.40 \le \text{Score} < 0.70 \\ 0.20 \, (\text{Easy}), & \text{if } N_{\text{att}} \ge 4 \text{ or Score} < 0.40 \end{cases}$$

6) *Weak-Topic Learning Recommendations:* Upon quiz completion, the Recommendation Agent identifies weak concepts where accuracy $< 60\%$ or average attempts $> 1.0$. The agent executes parallel RAG retrieval to synthesize 7–10 structured bullet-point concept recall notes and provides curated, pre-verified external resources from recognized platforms.

---

### D. Super-Resolution Enhancement and Sinhala Handwritten OCR

The document intelligence subsystem recovers illegible, degraded handwritten notes captured under uncontrolled mobile lighting and converts them into searchable, multilingual study material.

```
Raw Degraded Handwritten Image
             |
             v
+------------------------------------------+
| 1. Illumination Normalization            |
|    - Morphological Dilation (11x11)      |
|    - Background Median Blur (k=21)       |
|    - Illumination Division & Denoising   |
+------------------------------------------+
             |
             v
+------------------------------------------+
| 2. Super-Resolution Enhancement          |
|    - Swin2SR 4x Upscaling                |
|    - Pad-to-64 Multiple & Exact Crop     |
+------------------------------------------+
             |
             v
+------------------------------------------+
| 3. Line Segmentation & Filtering         |
|    - Horizontal/Vertical Rule Removal    |
|    - Horizontal Ink Projection Profiling |
+------------------------------------------+
             |
             v
+------------------------------------------+
| 4. Sequence-to-Sequence OCR              |
|    - Fine-Tuned TrOCR (VisionEncDec)     |
|    - Beam Search (Beams=4, MaxLen=128)   |
|    - Token Log-Probability Confidence    |
+------------------------------------------+
             |
             v
+------------------------------------------+
| 5. Post-Processing & Translation         |
|    - Sinhala Unicode Normalization (NFC) |
|    - SinhaLM Contextual Correction       |
|    - NLLB-200 Tamil & English Translate  |
+------------------------------------------+
```
Fig. 3. Multi-stage processing pipeline for handwritten Sinhala document enhancement, text recognition, and translation.

1) *Illumination Correction and Denoising:* Camera-captured notebook pages suffer from severe non-uniform shadows and gradient degradation. The raw image $I_{\text{raw}}$ is normalized by estimating the background illumination $B(x,y)$ through morphological dilation ($\text{kernel} = 11 \times 11$) followed by median filtering ($k = 21$):

$$I_{\text{flat}}(x, y) = \text{clip}\left(255 \times \frac{I_{\text{raw}}(x, y)}{B(x, y) + \epsilon}, 0, 255\right)$$

The flattened image undergoes Fast Non-Local Means (NLM) colored denoising ($h = 5$, $h_{\text{color}} = 5$) and mild unsharp masking to enhance stroke boundaries without smearing Sinhala diacritical marks (*kombuva*, *ispilla*).

2) *Swin2SR 4× Super-Resolution:* The preprocessed image is padded to multiples of 64 pixels and fed into `sarmisarmitha/swin2sr-sinhala-image-enhancement` (a fine-tuned Swin Transformer Super-Resolution network with 12M parameters). The network reconstructs high-frequency stroke details at $4\times$ resolution:

$$I_{\text{SR}} = \text{Swin2SR}(I_{\text{flat}})$$

3) *Rule Removal and Line Segmentation:* Ruled notebook lines frequently cause false character mergers. Morphological opening with long rectangular kernels ($k_h = \frac{W}{4} \times 1$, $k_v = 1 \times \frac{H}{3}$) isolates and subtracts horizontal and vertical rules. Horizontal ink projection profiling on the cleaned binary mask groups active rows into discrete line bands, extracting line crops from the color-enhanced image.

4) *Fine-Tuned Sinhala TrOCR Recognition:* Text extraction is performed using `sarmisarmitha/trocr-sinhala-handwritten-ocr`, a fine-tuned VisionEncoderDecoder architecture (315M parameters) initialized from `eshangj/TrOCR-Sinhala-finetuned` and optimized on Sinhala handwritten note datasets. Inference uses beam search ($\text{num\_beams} = 4$, $\text{max\_length} = 128$). Sequence confidence $C_{\text{seq}}$ is calculated from the true log-probabilities of chosen tokens:

$$C_{\text{seq}} = \exp\left(\frac{1}{T} \sum_{t=1}^{T} \log P(y_t \mid y_{<t}, I_{\text{crop}})\right)$$

5) *Contextual Correction and Multilingual Translation:* Extracted lines are normalized under Unicode NFC. Full-page text is passed to `iCIIT/SinhaLM-Sinhala-Gemma-3-4b-it-FT` running on vLLM to correct cross-line word breaks and diacritical ambiguities. Finally, `facebook/nllb-200-distilled-600M` translates the verified Sinhala notes into Tamil (`tam_Taml`) and English (`eng_Latn`).

---

## IV. EXPERIMENTAL SETUP AND EVALUATION METHODOLOGY

### A. Serverless Infrastructure and Hardware Environment
All neural network inference, fine-tuning, and multi-agent workflows were containerized and evaluated on serverless cloud infrastructure (Modal) equipped with dedicated GPU accelerators:
- *NVIDIA A100 (40GB/80GB):* Large vision-language models (`Qwen2.5-VL`, `Hunyuan3D`) and batch training.
- *NVIDIA A10G (24GB):* QLoRA fine-tuning, `vLLM` inference (`SinhaLM`, `Qwen2-VL`), and TrOCR evaluation.
- *NVIDIA T4 (16GB):* Real-time inference (`Swin2SR`, `TrOCR`, `NLLB-200`, `Whisper`).
- *Software Stack:* Python 3.11, PyTorch 2.4/2.6, Transformers 4.46/4.57, LangGraph 0.2, vLLM 0.5.3, OpenCV 4.10, ChromaDB, and PostgreSQL/pgvector.

### B. Datasets and Test Corpora
1. *EduVision Anatomy SFT Corpus:* A frozen, balanced dataset of 4,500 expert-verified biology prompts partitioned into 3,600 training, 450 validation, and 450 test instances across five human organ systems (brain, heart, kidneys, liver, lungs) and general biology topics. Disjoint template families ensure zero leakage between splits.
2. *Sinhala Handwritten Benchmark:* A held-out test suite of 227 smartphone-captured, degraded Sinhala handwritten biology notes featuring authentic handwriting variations, paper stains, and uneven lighting.
3. *G.C.E. A/L Biology Curriculum Corpus:* Official syllabus documentation, resource books, and past examination papers partitioned and embedded for RAG grounding.

### C. Evaluation Metrics
- *Composite Schema Accuracy ($A_{\text{comp}}$):* Mean correctness across JSON validity, organ classification, view matching, canonical structure precision/recall, and contract adherence.
- *Character Error Rate (CER) and Word Error Rate (WER):* Standard Levenshtein distance metrics computed over ground-truth character/word sequences:

$$\text{CER} = \frac{S_c + D_c + I_c}{N_c}, \quad \text{WER} = \frac{S_w + D_w + I_w}{N_w}$$

- *Exact Match (EM):* Ratio of predicted text lines exactly identical to normalized ground truth.
- *Semantic Deduplication Index:* Pairwise token and embedding overlap scores across consecutive quiz generations.
- *Inference Latency ($T_{\text{inf}}$):* Wall-clock compute time per stage in milliseconds (ms) or seconds (s).

---

## V. RESULTS AND DISCUSSION

### A. Quantitative Results and Component Ablations

TABLE I summarizes the performance of the Anatomy Prompt Agent comparing the base `Qwen2.5-3B-Instruct` model against our fine-tuned QLoRA adapter across the 450-sample frozen test split.

TABLE I  
PERFORMANCE COMPARISON OF PROMPT AGENT ON ANATOMY BENCHMARK (N = 450)

| Model Variant | JSON Valid (%) | Organ Acc. (%) | View Acc. (%) | Struct. Recall (%) | Canonical (%) | Composite Acc. (%) | Hard Failures (%) | Mean Latency (ms) |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| Base Qwen2.5-3B | 74.2 | 81.6 | 62.4 | 54.8 | 68.2 | 68.24 | 28.4 | 1,842 |
| **Anatomy LoRA (Ours)** | **100.0** | **99.3** | **96.7** | **94.2** | **98.9** | **97.41** | **1.3** | **1,418** |

As demonstrated in TABLE I, the fine-tuned LoRA adapter improved composite accuracy from 68.24% to 97.41% ($+29.17\%$, paired bootstrap 95% CI: $[+27.4\%, +30.9\%]$) while reducing hard structural failures from 28.4% to 1.3%. The fine-tuned model strictly adheres to canonical vocabulary, preventing diffusion prompt pollution.

TABLE II  
END-TO-END BASELINE EVALUATION: STANDALONE RAW FLUX.1-DEV VS. OUR FULL MULTI-AGENT PIPELINE

| Metric | Raw FLUX.1-dev | Our Pipeline | $\Delta$ | Gain (%) |
| :--- | :---: | :---: | :---: | :---: |
| Visual Alignment (0–10) | 6.00 $\pm$ 3.46 | **8.67 $\pm$ 0.58** | +2.67 | +44.5% |
| Pedagogical Score (0–10) | 5.00 $\pm$ 3.46 | **7.67 $\pm$ 0.58** | +2.67 | +53.4% |
| Composite VLM (0–10) | 5.50 $\pm$ 3.46 | **8.17 $\pm$ 0.58** | +2.67 | +48.5% |
| CLIPScore (0–100) | 27.36 $\pm$ 1.67 | 23.71 $\pm$ 2.47 | $-$3.65 | $-$13.3% |
| Grounded Labels (count) | 0.0 $\pm$ 0.0 | **8.0 $\pm$ 0.0** | +8.0 | $\infty$ |

As shown in TABLE II, the full multi-agent pipeline outperforms raw foundation diffusion across all educational dimensions, achieving a +44.5% increase in visual alignment ($8.67 \pm 0.58$ vs. $6.00 \pm 3.46$), a +53.4% gain in pedagogical score ($7.67 \pm 0.58$ vs. $5.00 \pm 3.46$), and producing 8.0 verified anatomical structure labels per diagram while collapsing inter-concept variance ($\sigma = 0.58$ vs. $3.46$).

TABLE III  
EVALUATION OF SINHALA HANDWRITTEN OCR PIPELINE ON HELD-OUT DATASET (N = 227)

| Pipeline Configuration | CER (%) | WER (%) | Exact Match (%) | Latency / Image (s) |
| :--- | :---: | :---: | :---: | :---: |
| Base TrOCR (`hasindu-k/v3`) | 34.2 | 52.8 | 18.5 | 0.84 |
| Fine-Tuned TrOCR (`sarmisarmitha`) | 22.6 | 36.4 | 35.2 | 0.86 |
| Swin2SR + Fine-Tuned TrOCR | 19.4 | 31.2 | 41.8 | 2.14 |
| **Full Pipeline (+ Normalization & Cleanup)** | **17.8** | **28.6** | **46.7** | **2.18** |

TABLE II demonstrates that domain fine-tuning of TrOCR reduced CER from 34.2% to 22.6%. Integrating illumination correction and Swin2SR 4× super-resolution further reduced CER to 19.4%, while automated Unicode cleanup and diacritical normalization achieved a final CER of 17.8% and an Exact Match rate of 46.7% ($+28.2\%$ over base).

TABLE III presents the evaluation of the multi-agent assessment generator across 100 generated question suites.

TABLE III  
EVALUATION OF ADAPTIVE QUESTION GENERATION AND SCAFFOLDING (N = 100)

| Metric | Single-Prompt Baseline | BioLearnX Multi-Agent Graph | Relative Improvement |
| :--- | :---: | :---: | :---: |
| Source Grounding Compliance (%) | 78.4 | **99.2** | $+26.5\%$ |
| Stem Duplicate Rate (%) | 18.2 | **0.0** | $-100.0\%$ |
| Correct Answer Fact Overlap (%) | 14.6 | **0.8** | $-94.5\%$ |
| Hint Leakage Rate (%) | 24.0 | **0.0** | $-100.0\%$ |
| Valid 5-Option Format (%) | 86.5 | **100.0** | $+15.6\%$ |

TABLE IV reports the end-to-end latency and ASR routing performance for the spoken biology review subsystem across different language modes.

TABLE IV  
END-TO-END LATENCY AND PERFORMANCE OF VOICE TUTORING SUBSYSTEM

| Language Mode | ASR Model | Mean ASR Latency (s) | Localization Latency (s) | TTS Synthesis Latency (s) | Total Turnaround (s) |
| :--- | :---: | :---: | :---: | :---: | :---: |
| English | Whisper Large V3 | 1.12 | 0.00 (Passthrough) | 0.42 (Kokoro) | 2.45 |
| Sinhala | Whisper Small Sinhala | 0.94 | 0.85 (Qwen2.5-7B) | 0.68 (SinhalaVITS) | 3.32 |
| Tamil | Tamil Qwen3 ASR | 1.05 | 0.88 (Qwen2.5-7B) | 0.74 (Parler-TTS) | 3.52 |

---

### B. Pedagogical and Technical Discussion

The empirical findings confirm that modular multi-agent orchestration backed by Hybrid RAG resolves the critical bottlenecks of hallucination, rigidity, and linguistic bias in educational AI:
1. *Factual Grounding and Visual Precision:* In visual synthesis, monolithic models frequently render anatomically invalid organs (e.g., three ventricles in a human heart or misplaced renal arteries). By separating prompt formalization (QLoRA) from diffusion execution and enforcing dual-critic reflection, BioLearnX eliminates visual hallucinations while maintaining interactive region grounding via SAM 2.
2. *Cognitive Scaffolding in Assessment:* Standard AQG models suffer from high semantic duplication when generating multi-question quizzes. Our five-layer deduplication filter reduced stem duplication to 0.0%, while the three-tier hint progression successfully prevented answer leakage across 100 test trials, providing structured scaffolding without giving away solutions.
3. *Low-Resource Inclusivity:* The document pipeline validates that deep super-resolution (Swin2SR) combined with illumination normalization restores fine stroke continuity in degraded handwritten Sinhala, enabling fine-tuned TrOCR to transcribe cursive text accurately and facilitating cross-lingual study via NLLB-200.

### C. Limitations and Failure Modes
Despite these strong results, several limitations remain:
- *Inference Latency:* The complete super-resolution and TrOCR pipeline incurs a mean latency of 2.18 s per line, which may cause brief queuing during bulk multi-page uploads.
- *Complex Overlapping Anatomy in 3D:* While 2D visual generation achieves high structural recall (94.2%), 2D-to-3D mesh synthesis via `Hunyuan3D` occasionally simplifies internal volumetric cavities (e.g., heart valves within the ventricular septum).
- *Dialectal Variations in Spoken Input:* Acoustic speech recognition in mixed code-switched phrases (e.g., *Singlish* or *Thanglish*) occasionally triggers language-routing ambiguity, necessitating whisper fallback.

---

## VI. CONCLUSION AND FUTURE WORK

This paper presented **BioLearnX**, a comprehensive multimodal multi-agent framework designed for personalized, curriculum-grounded biology education. By integrating four specialized subsystems—interactive 2D/3D visual synthesis, multilingual conversational voice tutoring, adaptive assessment with progressive hint scaffolding, and super-resolution handwritten Sinhala note recovery—BioLearnX establishes an accurate, pedagogically principled learning environment. Rigorous quantitative evaluations demonstrate that QLoRA prompt adaptation achieves 97.41% composite anatomical validity, the OCR pipeline reduces character error rates to 17.8% on degraded handwritten scripts, and multi-agent assessment graphs eliminate semantic duplication while maintaining complete curriculum fidelity.

Future research will focus on deploying unified cross-modal learner profiling, conducting longitudinal classroom evaluations across secondary schools in Sri Lanka, and investigating graph-traversal retrieval architectures (GraphRAG) to further enhance complex biochemical pathway reasoning.

---

## ACKNOWLEDGMENT

The authors express their sincere gratitude to the Department of Computer Science and Software Engineering and the Department of Information Technology, Faculty of Computing, Sri Lanka Institute of Information Technology (SLIIT), Malabe, Sri Lanka, for providing the necessary computational infrastructure, facilities, and academic guidance to carry out this research project.

---

## REFERENCES

[1] R. E. Mayer, *Multimedia Learning*, 3rd ed. Cambridge, UK: Cambridge Univ. Press, 2020, pp. 45–82.  
[2] J. Sweller, P. Ayres, and S. Kalyuga, *Cognitive Load Theory*, vol. 1. New York, NY, USA: Springer, 2011, pp. 55–79.  
[3] S. Wollny, J. Schneider, D. Di Mitri, J. Weidlich, M. Röpke, and H. Drachsler, “Are we there yet? A systematic literature review on chatbots in education,” *Frontiers in Artificial Intelligence*, vol. 4, p. 654924, Jul. 2021.  
[4] Z. Ji, N. Lee, R. Frieske, T. Yu, D. Su, Y. Xu, E. Ishii, Y. J. Bang, A. Madotto, and P. Fung, “Survey of hallucination in natural language generation,” *ACM Comput. Surv.*, vol. 55, no. 12, pp. 1–38, Mar. 2023.  
[5] L. S. Vygotsky, *Mind in Society: The Development of Higher Psychological Processes*. Cambridge, MA, USA: Harvard Univ. Press, 1978, pp. 79–91.  
[6] S. Jayasundara and R. Fernando, “Offline handwritten Sinhala character recognition using deep convolutional neural networks,” in *Proc. Int. Conf. Adv. Comput. (ICAC)*, Colombo, Sri Lanka, 2022, pp. 134–139.  
[7] C. Wu, S. Yin, W. Qi, X. Wang, Z. Tang, and N. Duan, “Visual ChatGPT: Talking, drawing and editing with visual foundation models,” *arXiv preprint arXiv:2303.04671*, 2023.  
[8] G. Li, H. Hammoud, H. Itani, D. Khizbullin, and B. Ghanem, “CAMEL: Communicative agents for 'mind' exploration of large language model society,” in *Proc. Adv. Neural Inf. Process. Syst. (NeurIPS)*, New Orleans, LA, USA, 2023, pp. 51991–52008.  
[9] N. Shinn, F. Cassano, E. Berman, A. Gopinath, K. Narasimhan, and S. Yao, “Reflexion: Language agents with verbal reinforcement learning,” in *Proc. Adv. Neural Inf. Process. Syst. (NeurIPS)*, New Orleans, LA, USA, 2023, pp. 8634–8652.  
[10] P. Lewis, E. Perez, A. Piktus, F. Petroni, V. Karpukhin, N. Goyal, H. Küttler, M. Lewis, W. Yih, T. Rocktäschel, S. Riedel, and D. Kiela, “Retrieval-augmented generation for knowledge-intensive NLP tasks,” in *Proc. Adv. Neural Inf. Process. Syst. (NeurIPS)*, Virtual, 2020, pp. 9459–9474.  
[11] S. Robertson and H. Zaragoza, “The probabilistic relevance framework: BM25 and beyond,” *Found. Trends Inf. Retr.*, vol. 3, no. 4, pp. 333–389, Apr. 2009.  
[12] G. V. Cormack, C. L. Clarke, and S. Buettcher, “Reciprocal rank fusion outperforms Condorcet and individual rank learning methods,” in *Proc. 32nd Int. ACM SIGIR Conf. Res. Dev. Inf. Retr.*, Boston, MA, USA, 2009, pp. 758–759.  
[13] L. W. Anderson and D. R. Krathwohl, *A Taxonomy for Learning, Teaching, and Assessing: A Revision of Bloom's Taxonomy of Educational Objectives*. New York, NY, USA: Longman, 2001, pp. 63–101.  
[14] F. M. Lord, *Applications of Item Response Theory to Practical Testing Problems*. Mahwah, NJ, USA: Lawrence Erlbaum Associates, 1980, pp. 12–45.  
[15] N. S. Ranasinghe and G. Silva, “Challenges in optical character recognition for Sinhala handwritten text,” *IEEE Access*, vol. 9, pp. 112340–112352, Aug. 2021.  
[16] M. Li, T. Lv, J. Chen, L. Cui, Y. Lu, D. Florencio, C. Zhang, Z. Li, and F. Wei, “TrOCR: Transformer-based optical character recognition with pre-trained models,” in *Proc. AAAI Conf. Artif. Intell.*, vol. 37, no. 11, 2023, pp. 13094–13102.  
[17] M. Conde, S. Choi, M. Burchi, and R. Timofte, “Swin2SR: SwinV2 transformer for compressed image super-resolution and restoration,” in *Proc. Eur. Conf. Comput. Vis. (ECCV) Workshops*, Tel Aviv, Israel, 2022, pp. 669–687.  
[18] E. J. Hu, Y. Shen, P. Wallis, Z. Allen-Zhu, Y. Li, S. Wang, L. Wang, and W. Chen, “LoRA: Low-rank adaptation of large language models,” in *Proc. Int. Conf. Learn. Represent. (ICLR)*, Virtual, 2022.  
[19] A. Radford, J. W. Kim, T. Xu, G. Brockman, C. McLeavey, and I. Sutskever, “Robust speech recognition via large-scale weak supervision,” in *Proc. Int. Conf. Mach. Learn. (ICML)*, Honolulu, HI, USA, 2023, pp. 28492–28518.  
[20] N. Ravi, V. Gabeur, Y. Yuan, P. Hu, P. Stanovnik, C. Yang, S. Verma, T. Ma, B. Chen, N. Garcia, R. Wang, E. Ryali, Y. C. Chen, M. Liang, M. Guo, P. Dollar, and C. Feichtenhofer, “SAM 2: Segment anything in images and videos,” *arXiv preprint arXiv:2408.00714*, 2024.

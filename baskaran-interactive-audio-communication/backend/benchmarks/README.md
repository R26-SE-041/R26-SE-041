# VoiceLearn benchmark suite

Everything needed for two tables in the research paper:

1. **Baseline comparison** — each stage of the pipeline against a published or
   prior-version baseline, with metrics chosen for the language pair rather than
   inherited from English ASR/MT convention.
2. **Warm-state latency and serving hardware** — per-agent p50/p95 with the
   physical GPU each agent actually ran on, cold starts excluded by design.

Two rules shape the whole suite, both about Modal credits:

- **Every raw response is written to disk before it is scored.** Metrics get
  revised while a paper is being written; re-transcribing 300 clips on an A10G
  to change a normalisation rule is the expensive way to learn that. Every
  `eval_*` script has an `--offline` mode that recomputes from saved outputs.
- **Every script resumes.** A run that dies at clip 250 keeps clips 1–249, and
  re-running skips what is already done.

---

## Layout

```
benchmarks/
  registry.py            every agent: model, GPU, endpoint, scaledown window, source line
  discover_urls.py       resolve deployed gpu_info URLs via Modal's control plane
  metrics.py             WER/CER, retrieval, chrF/BLEU, ROUGE-L, bootstrap CI — stdlib only
  latency_bench.py       warm-state latency + GPU probe
  eval_router.py         routing accuracy            — CPU, free
  eval_retrieval.py      BM25 / dense / RRF / rerank — 3 of 4 arms free
  eval_asr.py            WER, CER, native-script purity
  eval_tts.py            round-trip CER, RTF, blinded MOS study builder
  eval_generation.py     base vs LoRA vs RAG
  eval_localization.py   chrF, BLEU, term preservation
  eval_e2e.py            full-turn latency, per-stage breakdown
  report.py              Markdown + LaTeX tables from saved JSON (10 tables)
  data/                  gold sets and manifests (you supply most of these)
  fixtures/              benchmark audio clips
  results/               raw responses + computed metrics (git-ignored)
  tables/                generated tables
```

---

## Data status

| Set | File | State |
|---|---|---|
| Router | `data/router_eval_set.json` | **62 cases, done.** Runs free, results below. |
| Retrieval | `data/retrieval_gold.json` | **26 queries, pilot.** Gold ids read off the live index and verified — but see the corpus warning. |
| Generation | `data/generation_qa.json` | **26 questions**, 13 in-domain / 13 control. Expand toward ~200 before publishing. |
| TTS | `data/tts_set.json` | **30 items** across 4 languages. Sized for the MOS study. |
| Localisation | `data/localization_set.json` | **20 cases, drafted.** References are machine-drafted — a fluent speaker must review them, Sinhala first. |
| ASR | `data/asr_manifest.example.jsonl` | **Blocked.** Needs recorded audio; see below. |

### The indexed corpus is not what the paper describes

`python -m benchmarks.eval_retrieval --corpus-stats` on the current store:

```
embeddings            298
distinct_passages      18
duplication_factor   16.6
files   All About Dogs_ A Complete Guide.pdf (290), IT22172600.pdf (8)
```

Two problems, both fatal to a retrieval table if left alone:

**The corpus is a dogs guide and a STRIDE assignment**, not lecture material. Any
retrieval score computed today describes those two PDFs. It is a valid smoke
test of the four arms and nothing more.

**Every passage is stored about 17 times.** Repeated re-ingests minted a fresh
`document_id` for identical text — 30 document ids over 18 real passages. Left
alone this destroys recall@k: the retriever returns ten copies of exactly the
right passage and scores ≈ 0.06 against a gold set naming one of them.
`chunk_id()` is content-addressed to compensate, so the pilot set is sound, but
top-k still fills with duplicates and squeezes out genuine distractors, which
flatters every arm equally.

The fix before the real measurement: clear `backend/chroma_data`, ingest the
actual lecture PDFs once, re-run `--corpus-stats` to confirm the duplication
factor is ~1.0, then rebuild the gold set with `--dump-chunks`.

### Running environment

The harness imports `app.services.ingestion` for the retrieval arms, which
imports `sentence_transformers` at module level — so the retrieval evaluation
needs the backend's own dependencies, not a bare Python.

On this machine `backend/.venv/Scripts/python.exe` is blocked by an Application
Control policy, and the system Python has no `sentence_transformers`, so the
retrieval arms cannot run here yet. Everything else — the router evaluation,
the metrics, the corpus statistics, the copy-through localisation baseline, and
all report rendering — runs on the bare interpreter and has been verified.

Fix by running the suite under an interpreter that has the backend
requirements installed:

```bash
python -m venv .bench-venv && .bench-venv/Scripts/pip install -r requirements.txt
.bench-venv/Scripts/python -m benchmarks.eval_retrieval --arms bm25
```

BM25 is the arm worth running first: it reads Chroma locally and scores on CPU,
so it is a real retrieval number for zero Modal credits.

### ASR audio is the one genuine blocker

Everything else here can be produced from the repository. Recorded speech
cannot. What is needed:

- Tamil and Sinhala: Common Voice test split and FLEURS `ta_in` / `si_lk` —
  both downloadable, both with reference transcripts, both held out.
- Code-switch (Thanglish / Singlish): **no public set exists.** 50-100 in-house
  recordings with transcripts. This is the one that becomes a contribution of
  the paper rather than a borrowed benchmark.
- For the latency suite only, any clip works — reference transcripts are not
  needed there. `fixtures/bench_sinhala.ogg` is already in place; English,
  Tamil and mixed clips of 8-12 s are still missing.

---

## Order of operations

Cheapest first. Nothing below spends credits until step 3.

### 1. Router evaluation — free, runs today

```bash
python -m benchmarks.eval_router --verbose
```

CPU only, fully deterministic, exactly reproducible. Already run; see
*Current findings* below.

### 2. Deploy the `gpu_info` probe

Each Modal class now carries a `GET /gpu_info` endpoint reporting
`torch.cuda.get_device_name(0)`. This matters because the `gpu="A10G"` string in
`@app.cls` names the *requested class*, not the device: Modal's `A100-80GB`
reports as `NVIDIA A100-SXM4-80GB`, `T4` as `Tesla T4`. A paper citing only the
request string is imprecise about its own hardware.

The endpoint is a pure addition — no existing request or response contract
changed, so the running application is unaffected.

```bash
modal deploy backend/modal_endpoints/whisper_stt.py
modal deploy backend/modal_endpoints/tamil_asr_qwen3.py
# … and the rest; batch them in one session
```

`modal deploy` prints a URL per endpoint, but Modal hash-suffixes hostnames once
they grow too long, and that suffix cannot be derived locally — so about half of
these cannot be guessed from the inference URL. Ask Modal instead:

```bash
python -m benchmarks.discover_urls
```

That is a control-plane metadata lookup: it starts no container, spawns no GPU
and costs nothing. It writes `benchmarks/gpu_info_urls.json`, merging rather
than overwriting, and names any app it could not reach so you can paste that one
URL by hand.

`latency_bench.py` also guesses the URL when Modal has not truncated the name,
and reports exactly which keys it could not derive.

### 3. Warm-state latency — ~$2

```bash
python -m benchmarks.latency_bench --dry-run        # plan + cost, no requests
python -m benchmarks.latency_bench --agents all --runs 10
python -m benchmarks.report --latency --latex
```

Protocol, as it should appear in the methodology section:

> One warm-up request per agent, discarded, absorbing container scheduling,
> image pull and weight load. Then *n* = 10 requests issued back-to-back with no
> pause. Each request records client-side wall-clock latency and, where the
> endpoint exposes one, the server's own inference timer. Statistics are
> reported as median and 95th percentile by nearest rank; the mean alone is
> misleading because inference latency is right-skewed.

**The pacing is not incidental.** Four agents run a 60-second `scaledown_window`
— Sinhala ASR, the BGE reranker, and both A100 answer paths. An idle gap lets
Modal reclaim the container, and the next request silently pays a cold start
that lands in the tail statistics. The runner times each batch and sets
`warm_state_valid: false` with an explicit warning if the batch outlives the
window, rather than reporting a contaminated p95 as warm-state latency.

### 4. Retrieval ablation — nearly free

Three of the four arms cost nothing (BM25 is pure CPU; dense and RRF share one
embedding call), and only the reranker arm adds T4 time.

```bash
python -m benchmarks.eval_retrieval --corpus-stats        # check this FIRST
python -m benchmarks.eval_retrieval --arms bm25           # free arm, sanity check
python -m benchmarks.eval_retrieval --arms all
```

**Run `--corpus-stats` before trusting any retrieval number.** Duplication and
domain are invisible in the metrics themselves and both invalidate the table —
see *Data status* above for what the store currently holds.

A 26-query pilot set against the live index ships in `data/retrieval_gold.json`,
with every gold id verified present. Rebuild it with `--dump-chunks` once the
real lecture PDFs are ingested.

Report recall@k, nDCG@10 **and** MRR together. Recall is order-blind and the
reranker only reorders, so a recall-only table makes the reranker look useless
no matter how well it works.

### 5. ASR — moderate

```bash
python -m benchmarks.eval_asr --systems all --languages all
python -m benchmarks.eval_asr --offline                  # rescore, free
```

Needs `data/asr_manifest.jsonl` and clips under `fixtures/asr/`. Use held-out
data: Common Voice ta/si test, FLEURS `ta_in`/`si_lk`, plus in-house
code-switch recordings. **100 utterances per language minimum** for a confidence
interval a reviewer will accept.

Lead with **CER**, not WER. Tamil and Sinhala are agglutinative, so one wrong
morpheme condemns a whole word and WER overstates the loss to a reader. Report
both — a wide WER/CER gap is itself a finding about morphological error.

The third metric, `native_script_ratio`, is specific to this system. Whisper's
documented Indic failure is romanisation — emitting "Night" for "நாய்" — and
`whisper_stt.py` ships a 50k-token ASCII suppress list to prevent it. WER cannot
show whether that worked, because a fully romanised transcript and a garbled
native one can score identically. Verified behaviour: romanised output scores
0.0, native output 1.0.

### 6. Localisation — moderate

```bash
python -m benchmarks.eval_localization --systems all
```

Lead with **chrF**, not BLEU, for the same morphological reason. Include the
copy-through arm (emit the English unchanged): `modal_client.call_localizer`
falls back to the original text on any error, so a silent failure looks like a
successful call. Only the script check catches it.

### 7. Answer generation — most expensive, do last

```bash
python -m benchmarks.eval_generation --systems base --limit 5    # smoke test
python -m benchmarks.eval_generation --systems all
python -m benchmarks.eval_generation --offline
```

Three A100-80GB endpoints. Smoke-test with `--limit 5` before committing.

The headline is an **interaction, not an average**: the LoRA fine-tune should
beat the base model on the five trained muscles *without regressing elsewhere*.
The harness splits every metric by `in_finetune_domain` for exactly this reason;
a pooled average hides both halves of the result.

`ROUGE-L`, `token_f1` and `context_groundedness` are **screening** metrics — say
so in the paper. They reward surface overlap and penalise correct paraphrase.
Their job is to rank the set cheaply so that human review and an LLM-judge pass
can be spent on the disagreements and the low-scoring tail. Report the sample
size of the human pass alongside them.

### 8. TTS — objective now, MOS study scaffolded

```bash
python -m benchmarks.eval_tts --systems all                  # synthesise
python -m benchmarks.eval_tts --systems all --transcribe     # round-trip CER
python -m benchmarks.eval_tts --sample-mos 20 --raters 15    # listening study
```

Objective: **round-trip CER** — synthesise, send the audio back through Whisper
Large V3, score the transcript against the input text — plus RTF from the
generation pass.

State the confound rather than hiding it: round-trip CER measures the
synthesiser *and* the recogniser together, and Whisper is itself imperfect on
Tamil and Sinhala. It compares TTS systems fairly only because the same ASR
scores every arm. Add a human-speech control row and the number becomes
interpretable — that row is the floor this ASR imposes, which no synthesiser can
beat.

Subjective, and this is what carries the naturalness claim: `--sample-mos`
writes a blinded listening study — clips renamed to opaque ids, one
independently randomised CSV per rater, and a separate `key.json` that must not
be handed out. Blinding and per-rater order randomisation are not paperwork: an
unblinded sheet invites raters to score the system they expect to win, and a
fixed order lets them anchor on whatever they hear first. Report mean MOS with
95% CI per system plus inter-rater agreement (Krippendorff's alpha or ICC).

Systems: Kokoro-82M (en, CPU) · IndicF5 (ta, A10G) · Indic Parler (code-switch,
A10G) · SinhalaVITS-M2 (si, T4) · MMS-TTS (baseline, T4). The Kokoro-vs-GPU RTF
comparison is a result in its own right — it is the only CPU-served agent, and a
CPU model at acceptable RTF changes the deployment economics.

### 9. End-to-end turn latency — the number a user actually feels

```bash
python -m benchmarks.eval_e2e --dry-run
python -m benchmarks.eval_e2e --language english --runs 3
```

Table 1 times each agent in isolation; this times the real LangGraph pipeline —
STT → correction → RAG → localisation → TTS — with every node wrapped in a timer
before the graph is compiled. Stage cost is therefore measured where it happens,
not reconstructed from log lines, and the breakdown includes what summing Table 1
would miss: retrieval, Chroma, the Supabase upload inside the TTS node, and the
graph's own overhead. The harness reports that residual explicitly as
`unaccounted_ms`.

Scope to declare in the paper: it invokes the compiled graph in-process, so
FastAPI, authentication and browser transport are excluded. The measurement
isolates the AI pipeline; the user-visible turn is this plus a fixed transport
cost.

Run each language path separately and report them as separate rows — English
routes to Whisper and Kokoro, Tamil to Qwen3-ASR and IndicF5, Sinhala to
whisper-small-sinhala and SinhalaVITS. A single pooled figure would describe no
real user. One turn touches T4, A10G and A100-80GB, so keep `--runs` at 3-5;
that is enough for the stage *shares* the stacked bar chart shows.

---

## Cost control

| Group | Agents | Est. |
|---|---|---|
| Latency suite, all 16 agents × 10 runs | — | **~$2** |
| Retrieval ablation | BM25/dense/RRF free; reranker on T4 | **<$1** |
| ASR eval, 300 clips | T4 + A10G | ~$5–10 |
| Localisation, 100 cases | T4 | ~$1 |
| Generation, 200 questions × 4 systems | A100-80GB | ~$15–30 |

Rules that keep this from overrunning:

- `--dry-run` first. It prints the plan and a cost estimate and issues nothing.
- All agents already run `min_containers=0`, so there is no idle burn.
- Batch the `gpu_info` redeploys into one session — one cold start per app, not
  one per experiment.
- Never re-run a completed transcription or generation pass. Both harnesses skip
  ids already present in `results/`.
- Do the A100 generation pass **last**, after the free and cheap tables are
  finished and the metric definitions have stopped moving.

---

## Current findings — router (62 labelled queries, free to reproduce)

The router was evaluated, three defects were found, and the fix was measured on
the same set. Both columns are reproducible with one CPU command.

| | Before | After |
|---|---|---|
| Accuracy | 0.774 | **0.968** |
| Macro-F1 | 0.833 | **0.976** |
| `muscle_finetuned_v2` precision | 0.778 | **1.000** |
| Over-routing onto a paid A100 path | 6 / 62 (9.7%) | **0 (0%)** |
| Under-routing away from the fine-tune | 8 | **2** |

`results/router_eval_before.json` holds the pre-fix run; re-running
`eval_router.py` regenerates the post-fix column.

**Read the "after" column with the circularity caveat stated plainly:** the same
labelled set both revealed these defects and validated the fix, so 0.968 is an
in-sample figure and will be optimistic. The fixes are principled rather than
case-by-case — qualifier disambiguation, not a list of memorised strings — but
the honest presentation is to report the before/after delta as evidence that the
defects were real, and to validate the fixed router on a held-out set written by
someone who has not seen the regex before quoting a headline accuracy.

### The three defects

**1. Over-triggering on near-miss anatomy — 4 errors, every one a paid A100
route.** `biceps(?:\s+brachii)?` made the qualifier optional, so bare `biceps`
matched and *biceps femoris* — a hamstring — was sent to an adapter trained on
biceps brachii. The same held for `pectoralis minor`, `triceps surae`, and the
ankle's `deltoid ligament`. Fixed with a negative lookahead per stem, so the
bare form still matches (students do write "the biceps") while an explicitly
wrong qualifier no longer does.

**2. Missing colloquial and inflected forms — 5 errors.** `pecs`, `delts`,
`quads` and the singular misspellings `bicep`/`tricep` all fell through to the
base model, wasting the fine-tune that exists for exactly those questions. The
singulars matter disproportionately because they are what ASR emits from student
speech. Fixed by adding the short forms and optional-`s` variants.

**3. Topic switches without the trigger keywords — 2 errors.**
`_NEW_TOPIC_PATTERN` matched only a leading "new topic" / "topic change" /
"switch topic", so "Forget that. What is glycolysis?" kept the stale memento and
routed a biochemistry question to the muscle adapter. Fixed by recognising
ordinary redirection markers anywhere in the turn — "let's talk about X
instead" puts the signal at the end, not the start.

A fourth gap the set exposed: Tamil- and Sinhala-script muscle names did not
match at all, so `பெக்டோரலிஸ் மேஜர்` silently routed to the base model while the
identical English question reached the adapter — a failure of the multilingual
promise invisible to an English-only test. The five muscle names in both scripts
are now matched.

### What remains, and why it is left alone

The two surviving errors are ASR word-splits: `delta id` for "deltoid",
`by seps` for "biceps". These are deliberately **not** fixed in the router. A
regex that fuzzy-matches phonetic fragments would start matching unrelated text,
and the pipeline already has a component for this — the Gemma transcript
corrector runs upstream of routing. The right experiment is the pipeline
interaction: measure routing accuracy on raw ASR output versus corrected
transcripts, and report the corrector's contribution as the difference. That is
a stronger result than a wider regex would be.

Verified no regression: all nine assertions in `tests/test_hybrid_model_router.py`
still hold, and the collectible suite is unchanged at 41 passed.

## Reproducibility notes for the paper

- Text normalisation before scoring: NFC, casefold, punctuation stripped,
  whitespace collapsed. **State this.** Indic WER is not comparable across
  papers without it — combining marks have several valid encodings, and an
  unnormalised pair can differ by zero visible characters yet score non-zero CER.
- Corpus WER is total edits ÷ total reference words, not the mean of
  per-utterance rates. Averaging rates lets a three-word utterance outvote a
  thirty-word one.
- Percentiles use nearest rank. At *n* = 10–20, interpolated percentiles invent
  precision the sample size does not support.
- Every headline metric carries a 95% percentile-bootstrap CI. A 2-point WER
  difference on 100 utterances is usually inside the interval.
- `registry.py` records the `file:line` each agent's configuration was read
  from, so the hardware table can be re-derived from the source at any commit.
- The README at the repository root has a stale model table (Llama 3.1 8B,
  Qwen2.5-3B). Neither model appears in `modal_endpoints/`. Cite `registry.py`.

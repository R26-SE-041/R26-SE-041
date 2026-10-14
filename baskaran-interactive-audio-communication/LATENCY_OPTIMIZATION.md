# Latency measurements — 14 October 2026

Changes are scoped to the audio communication component. Production keeps cloud
history, private saved revisions, flashcards, Sinhala speech approval and document
ownership checks. Synthetic test data is separate from the real user's library.

## Measured results

| Check | Before (seconds) | After (seconds) | Interpretation |
| --- | ---: | ---: | --- |
| Tamil TTS, same six-sentence text, warm NVIDIA L4 | 68.074 | 36.498 | Batch size 1 versus 2; 46% less wall time |
| Tamil GPU compute for that text | 61.828 | 33.944 | 45% less compute time |
| English identical TTS request | 35.881 | 2.629 | Uncached versus cached, same payload |
| Tamil identical TTS request | 101.491 | 4.451 | Uncached versus cached, same payload |
| Sinhala identical TTS request | 43.828 | 2.560 | Uncached versus cached, same payload |
| OpenClaw sectioned revision and save | 76.224 | 47.324 | Observed 38% faster; model warmth not controlled |
| OpenClaw flashcards and save | 25.255 | 20.231 | Observed 20% faster; model warmth not controlled |
| OpenClaw summary and save | 37.032 | 50.653 | Slower in final run; no improvement claimed |

Cache comparisons do not predict fresh-question latency: new answer text still
requires speech generation. Cached audio was byte-identical. Tamil batch outputs
contained all six sentences and the negative food warning; ASR transcript
similarity was 0.992 after normalization. This is a content sanity check, not a
comprehensive pronunciation evaluation.

First English voice answer text was observed at 61.470 seconds before and 27.083
seconds after. Other languages did not show a reliable improvement: final Tamil
ASR took 155.180 seconds and its answer 86.992 seconds; Sinhala ASR took 16.170
seconds and its answer 50.075 seconds. Cold container allocation and model loading
remain variable. Tamil ASR logs showed roughly 8 seconds of actual inference
inside a much longer first-request wait. No claim of uniformly faster first
requests or guaranteed maximum latency is justified by these samples.

## Implementation and credit controls

- Pool outbound HTTP connections; run blocking cloud storage off the async loop.
- Start speech and history persistence concurrently, with ordered cloud attachment
  and Sinhala edit handling. Audio playback need not wait for a slow history upload.
- Bound owner-scoped speech caching to 32 MB and 10 minutes; coalesce duplicates.
  Query embeddings and immutable document downloads have separate bounded caches.
  Ownership and existence are checked on every document retrieval.
- Prepare configured models only when recording or a generation action starts.
  Preparation requests have cooldowns and deadlines; deployment endpoint matching
  prevents preparing the wrong workspace. Preparation manifests are in the image.
- Use one OpenClaw workflow tool for generation and durable saving. Preserve
  individual tool tracing and saved-artifact verification; stop waiting for agent
  acknowledgement once the required verified workflow completes.
- Limit the affected inference deployments to one container each. Minimum remains
  zero; existing idle windows remain unchanged. There is no periodic warmup or
  always-running GPU. These settings conserve credits but retain cold-start waits.
- Tamil ASR/TTS prefer L4 with A10G fallback. Tamil TTS optionally batches two
  original sentence prompts, preserving order, segmentation, model and voice.
  Backend callers request batch size two; other clients default to one.
- Overall speech deadline is 180 seconds; unavailable speech leaves text visible.
- Upload independent saved artifacts with bounded concurrency and only report
  saved after every required upload succeeds.

Modal model changes were separately deployed to visakanbaskaran,
krishnavaranan1, krishnavaranan and varananrp. Alternate workspaces were deployed
without running inference benchmarks. GitHub backend deployment does not deploy
Modal model sources automatically. No account switch was made.

Modal lists L4 at $0.000222/GPU-second and A10 at $0.000306/GPU-second: L4's
GPU-second rate is approximately 27% lower, not a guarantee about total billing.
No reliable actual credit consumption measurement was obtained.
Sources: [GPU selection](https://modal.com/docs/guide/gpu),
[cold starts](https://modal.com/docs/guide/cold-start),
[pricing](https://modal.com/pricing).

## Validation

Backend: 183 tests passed, including cache isolation, duplicate coalescing,
preparation matching, resumable workflow and completion-event coverage. Frontend:
TypeScript, 10 unit tests and production export passed. Browser suite had 22
passing tests after a transient microphone test passed on isolated retry; two
SDK-specific cases were skipped. Slow-cloud-history browser checks use mocked
inference to avoid consuming Modal credits. Live English/Tamil/Sinhala API and
three OpenClaw workflows succeeded; final OpenClaw outputs were saved through
the real MCP provider. Tests do not establish physical-phone microphone behavior.

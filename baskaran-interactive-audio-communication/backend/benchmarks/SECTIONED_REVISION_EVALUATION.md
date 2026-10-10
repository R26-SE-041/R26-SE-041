# Preliminary evaluation protocol: sectioned spoken revision

This is a protocol, not collected human-study results. Do not fill benchmark tables with
invented timings, accuracy, or learning gains.

Compare Single audio (baseline) versus Sectioned audio with the same document/language.
Use three short documents (anatomy, another technical topic, and text without headings),
English/Tamil/Sinhala, both modes: 18 generations if credits and quotas permit. Source limits
remain 12,000 extracted characters. Keep model/endpoints fixed; log warm/cold runs separately.

Record: mode, language, document category, success/partial/failed, elapsed generation seconds,
audio seconds, section count, localization/TTS calls, and failure category. The live checker
records structural evidence on generated fictional samples only. Single sample durations are
not reliability estimates. Gemini usage and Modal credits are distinct.

For each section, a reviewer checks each factual claim against View source and marks
supported / partly supported / unsupported. Record omissions and translation drift too.
Have Tamil/Sinhala speakers review meaning and technical-term pronunciation. Script checks
alone do not establish correctness. Review original-language sources if translation is involved.

Navigation pilot: ideally 6–8 consenting students, or explicitly report a smaller walkthrough.
Counterbalance mode order and comparable tasks/documents so practice does not favor sections.
Tasks: locate a specified fact in the audio, replay its explanation, and locate supporting text.
Measure success and completion seconds; ask ease/usefulness ratings (1–5). Baseline source
verification uses the original document independently; it has no source drawer. Report medians,
ranges, failures, and sample size. Avoid causal learning claims or significance claims from this
small convenience sample. Test at least one source-linked claim that lacks support to check
that users do not assume links guarantee truth.

Failure checks: no headings/one paragraph, invalid structured generation, unsupported source
content, native translation failure, one-section TTS failure, mismatched WAV parameters,
source deletion/change, expired job, rate limit, browser autoplay rejection.

Allowed claim after evaluation: implementation and preliminary observed navigation/source
verification behavior in this tested multilingual prototype. Novelty remains unverified until
literature review. No claim of universally accurate translation or improved learning outcomes.

For a viva, pre-generate a representative revision and disclose actual generation latency.
Demonstrate navigation/source inspection on that output; do not imply cold-start generation
is instantaneous. Section prompts permit shorter scripts for short spans rather than padding.

Control content when measuring navigation: use the same completed sectioned WAV/transcript
for both UI conditions. Uncheck Show section navigation and source view for the single-player
condition; check it for the proposed condition. This avoids confounding navigation with
different generated content and consumes no extra inference. The separate Single audio mode
is still the original generation baseline for pipeline/content comparisons. Assign only
languages participants understand, and report participants per language.

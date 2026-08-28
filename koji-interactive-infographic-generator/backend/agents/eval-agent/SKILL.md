---
name: evaluate-educational-images
description: Evaluate generated educational images for prompt alignment, visual quality, and pedagogical usefulness using CLIP and a vision-language model. Use when scoring an image and producing actionable retry feedback.
---

# Image evaluation

- Reject empty image bytes before computing any metric.
- Score visual quality and pedagogical usefulness independently.
- Ground every criticism in visible evidence and the supplied prompt.
- Return concise, actionable corrections suitable for the next generation attempt.
- Do not reward decorative polish that reduces factual accuracy or label readability.
- Return only the response schema requested by the endpoint.

## Anatomy review

- Treat the validated anatomy specification as the expected target, not proof of what the image contains.
- Verify organ identity, requested view or section, anatomical orientation and laterality, and each required structure from visible evidence.
- Reject an intact exterior image when a cutaway or internal view was requested.
- Reject embedded text or labels in a clean base image intended for application-rendered overlays.
- Report missing, duplicated, fused, misplaced, or implausibly connected structures as concrete retry corrections.
- Do not use SAM masks, Qwen localizations, or confidence values to overrule contradictory pixels.

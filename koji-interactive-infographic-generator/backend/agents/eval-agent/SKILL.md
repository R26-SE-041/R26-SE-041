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

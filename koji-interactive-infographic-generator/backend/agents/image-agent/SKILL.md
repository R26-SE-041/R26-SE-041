---
name: generate-educational-images
description: Generate safe educational images from approved prompts using FLUX. Use for deterministic image generation, GPU-tier routing, and returning validated image bytes without silently changing the requested content.
---

# Image generation

- Validate the prompt and safety decision before GPU inference.
- Preserve the supplied prompt; do not add hidden creative instructions.
- Use the supplied seed when present for reproducibility.
- Return an explicit error for empty or invalid output; never return plausible placeholder bytes.
- Keep generation settings within the selected GPU tier's tested limits.

---
name: convert-images-to-3d
description: Convert approved 2D educational images into textured GLB assets with Hunyuan3D. Use for background preparation, shape generation, optional texture synthesis, GPU routing, and GLB validation.
---

# 3D conversion

- Validate image bytes before starting expensive GPU work.
- Remove the background when possible while preserving the subject silhouette.
- Generate shape before optional texture synthesis.
- Never silently return an untextured mesh when texture was required.
- Validate non-empty GLB output and return explicit conversion errors.

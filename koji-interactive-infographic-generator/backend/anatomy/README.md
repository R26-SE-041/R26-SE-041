# Anatomy catalog

The anatomy pipeline is catalog-driven. Qwen extracts a structured `anatomy_spec`,
the validator checks it against these files, and the deterministic builder creates
the final FLUX prompt. The frontend does not contain organ-specific fallbacks.

## Add an organ

Copy an existing organ directory and add these four files under
`anatomy/<organ_id>/`:

- `structures.json`: organ aliases, trigger word, canonical structure IDs, labels,
  aliases, descriptions, and source IDs.
- `relations.json`: source/target structure IDs and their anatomical relationship.
- `views.json`: allowed views, aliases, visible structures, detail levels, and the
  default view.
- `sources.json`: uniquely identified reference sources cited by structures.

No Python or frontend routing change is required. At startup, the prompt agent
discovers the directory, builds the Qwen JSON Schema from its canonical IDs, and
exposes the organ in `/health` as part of `anatomy_organs`.

Use lowercase `snake_case` for directory, structure, and view IDs. Include common
English and local-language organ aliases so routing remains explicit and
data-driven. Every referenced structure and source must exist.

Validate the entire installed catalog from `backend/`:

```powershell
..\.venv\Scripts\python.exe -m unittest tests.test_anatomy
```

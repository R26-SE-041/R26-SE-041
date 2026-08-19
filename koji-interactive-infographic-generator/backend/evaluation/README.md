# EduVision evaluation workflows

Run commands from `backend/` after deploying the updated agents and applying
`scripts/create_tables.sql` to Supabase.

## Generation ablation

The default run is the conference protocol: 100 prompts, six configurations,
and five seeds. Results are appended to JSONL and completed combinations are
skipped when the command is resumed.

```powershell
$env:ORCHESTRATOR_URL = "https://your-orchestrator-url"
python -m evaluation.run_ablation --output results/ablation.jsonl
python -m evaluation.analyze results/ablation.jsonl --output-prefix results/ablation-summary
```

Use `--limit`, `--configs`, or `--seeds` for a smoke run before starting the
full experiment. Add `--store-db` to mirror results into `ablation_results`.

## Retrieval ablation

Copy `retrieval_queries.example.json`, replace its sources with the actual
PDF names from `knowledge_chunks`, and add manually annotated queries.

```powershell
python -m evaluation.run_retrieval_ablation retrieval_queries.json --output results/retrieval.json
```

## Automatic SKILL evolution

Deploy the weekly scheduled job from `backend/`:

```powershell
modal deploy agents/skill-generator/modal_app.py
```

It deploys only when at least 50 high-scoring experiences exist, ten held-out
prompts are available, and paired validation improves the mean dual score by
more than `0.10`. The prompt agent reloads committed Volume rules at request
time. Use `run_now` for a manual guarded trigger.

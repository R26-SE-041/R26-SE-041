# Modal workspace switching

The frontend stays unchanged. The backend calls the explicit URLs in `.env`;
switching the dashboard or CLI profile alone does not switch the application.

Supported workspaces: `visakanbaskaran`, `krishnavaranan1`, `krishnavaranan`,
`varananrp`, environment `main`.

All four passed the production smoke checks on 13 October 2026. See
[verification record](MODAL_VERIFICATION.md) for scope and switch-test results.

Run from `backend` using a Python installation with `modal==1.6.1` and `httpx`:

```powershell
python scripts/modal_workspaces.py discover krishnavaranan1
python scripts/modal_workspaces.py verify krishnavaranan1
python scripts/modal_workspaces.py switch krishnavaranan1
```

Restart FastAPI after switching. Use the same commands with another workspace
name to switch back. This tool never changes the active Modal CLI profile.

For this Windows laptop, switch and restart the recorded component backend in
one command (after the workspace has passed verification):

```powershell
.\switch-modal-workspace.ps1 -Workspace krishnavaranan1
```

The wrapper refuses to stop an unrelated PID or a different server on port 8000.
Install administrative dependencies with `pip install -r requirements-modal-tools.txt`
if using another Python installation.

Discovery writes public endpoint URLs to `modal_workspaces/<workspace>.json`.
Verification makes short, real inference requests: base and fine-tuned answers,
RAG, transcript correction, translation, English/Tamil/Sinhala WAV generation,
STT using those WAV fixtures, 1024-dimensional embeddings and reranking. It costs
compute in the selected workspace. Results are saved to the ignored
`.workspace-runtime` directory. A workspace must pass all 14 checks before
switching is allowed. Source or URL changes invalidate earlier verification.

Switching backs up `.env`, updates production endpoints and clears workspace
CLI credentials from public HTTP endpoint requests. It preserves database,
OpenClaw, document, history and other configuration. Backups contain secrets and
are ignored by Git. There is no automatic account rotation.

To deploy current production code explicitly:

```powershell
python scripts/modal_workspaces.py deploy krishnavaranan1
```

This deploys the ten production apps used by the component. Legacy deployments
remain present; they are not stopped or deleted. The Tamil endpoint key points
to Qwen3, not the older IndicConformer app. Current Sinhala ASR uses Stage2;
current Sinhala TTS uses the male M2 voice.

Tamil TTS uses the versions captured from the working production runtime and
loads explicit, complete model/tokenizer revisions offline. The inference file
fingerprints matched across all four workspace caches. A fresh empty volume
still needs those gated model files provisioned with authorized Hub access.

Model preparation helpers run remotely in the selected workspace:

```powershell
python -X utf8 -m modal run --profile krishnavaranan1 --env main modal_endpoints/hf_cloud_migration.py::prefetch_visakan
```

Private/gated downloads require a valid `huggingface-secret` with `HF_TOKEN`
and repository access. Existing caches alone do not prove secret validity.
`workspace_volume_sync.py` copies only the specifically approved Gemma V2
adapter and Sinhala ASR Stage2 folders from `visakanbaskaran`, retaining unrelated
files. It must only be run for explicitly authorized destinations.

OpenClaw/Gemini is configured separately. Switching Modal endpoints does not
change Gemini quotas, OpenClaw credentials, Modal credit eligibility or billing.

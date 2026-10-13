# Switching Koji between Modal workspaces

Koji has three registered profiles: `kojithan-y`, `ikojikn`, and `agal-koji`, all
using the `main` environment. The sample registry contains the normal ASGI URLs
for this project's app names. Compare them with each deployment's actual URLs;
custom domains or renamed endpoints must be entered explicitly.

The CPU Studio API is the stable entry point. New jobs and authenticated agent
proxy requests read `backend/modal-active.json` on each request. Jobs already
queued or running keep the URLs saved when they were submitted, including async
Modal call IDs. Keep the previous account available until those jobs finish.
Switching does not restart the API/worker, rebuild the frontend, or redeploy GPUs.

## One-time configuration

1. Copy `backend/modal-accounts.example.json` to `backend/modal-accounts.json`.
   A local copy has already been prepared for the three profiles. The live file
   is ignored by Git. It contains endpoint origins and profile names, not tokens.
2. On each workspace, deploy the same source version and prepare the model
   files/LoRA weights required by the agents. Volumes with the same name in
   different workspaces have independent contents. Create the required
   `hf-secret`, `supabase-secret`, and any other secrets referenced by the deployed
   agents. Use the same Supabase project to keep learner data and history shared.
3. Verify each account's deployed endpoint origins in the registry. Deploy the
   orchestrator with that account's own `agent-urls-secret` when using its legacy
   memory/feedback routes. Do not point its secret at a different account's agents.
4. Deploy the updated CPU backend once. For local development, restart the
   development API once after installing this code. Subsequent switches require
   no restart.
5. Configure the frontend's existing `EXPO_PUBLIC_STUDIO_API_URL` to the stable
   CPU API, and Supabase login as usual. Browser health indicators now use the
   authenticated Studio agent proxy. Direct browser-to-Modal mode without a
   Studio API continues to use build-time URLs and does not follow server switches.

On EC2, copy the live registry to `/home/ubuntu/koji/backend/modal-accounts.json`
and install `deploy/aws/switch-modal.sh` at
`/home/ubuntu/koji/deploy-control/switch-modal.sh`. Install these as operator-owned
files readable by the `ubuntu` API user. The default routing state is
`/home/ubuntu/koji/backend/modal-active.json`. The wrapper and API derive the same
paths from this layout. Keep routing files outside the `studio/` and `shared/`
directories replaced by release activation.

For a different location, set these absolute paths in backend `.env`:

```dotenv
KOJI_MODAL_ACCOUNTS_FILE=/path/to/modal-accounts.json
KOJI_MODAL_STATE_FILE=/path/to/modal-active.json
```

The switch command loads the same backend `.env`. If using environment variables,
ensure the operator command and API receive identical paths. Do not pass a custom
`--state` to a command unless the API is configured to read that file too.

## EC2 commands

```bash
sudo bash /home/ubuntu/koji/deploy-control/switch-modal.sh list
sudo bash /home/ubuntu/koji/deploy-control/switch-modal.sh check agal-koji
sudo bash /home/ubuntu/koji/deploy-control/switch-modal.sh agal-koji
sudo bash /home/ubuntu/koji/deploy-control/switch-modal.sh kojithan-y
sudo bash /home/ubuntu/koji/deploy-control/switch-modal.sh ikojikn
sudo bash /home/ubuntu/koji/deploy-control/switch-modal.sh status
sudo bash /home/ubuntu/koji/deploy-control/switch-modal.sh rollback
```

The script also accepts `switch ACCOUNT`. For a custom application root, set
`KOJI_DEPLOY_ROOT` before invoking it. No Modal login is required on EC2 merely
to change routing between these existing public endpoints.

## Windows or any Python host

From the Koji `backend/` directory, using a Python environment with the existing
Studio dependencies installed:

```powershell
.\switch-modal.ps1 -Action list
.\switch-modal.ps1 agal-koji
.\switch-modal.ps1 kojithan-y
.\switch-modal.ps1 ikojikn
.\switch-modal.ps1 -Action status
.\switch-modal.ps1 -Action rollback
```

Use `-Python C:\path\to\python.exe` if auto-detection does not find your project
interpreter. Equivalent cross-platform commands:

```bash
python -m studio.modal_accounts list
python -m studio.modal_accounts check agal-koji
python -m studio.modal_accounts switch agal-koji
python -m studio.modal_accounts status
python -m studio.modal_accounts rollback
```

`--config`, `--state`, and `--timeout` are optional global flags placed before the
command. Example: `python -m studio.modal_accounts --timeout 180 check agal-koji`.

## Deploy the same checkout to the three accounts

The local Modal CLI profiles must exist and authenticate to their matching
workspaces. They were found on the development machine, but a new deployment host
needs its own credentials. Credentials stay in Modal's local profile storage.

From the Koji project root:

```bash
python deploy/modal/deploy_accounts.py --account ikojikn --include-orchestrator
python deploy/modal/deploy_accounts.py --all --include-orchestrator
```

The helper deploys the six agents. `--include-orchestrator` refreshes the target
workspace's `agent-urls-secret` from its registry and deploys the orchestrator.
Required Hugging Face/Supabase secrets and model volume contents must be prepared
separately. The helper selects `MODAL_PROFILE` and the environment per subprocess
and removes inherited credentials that would override the profile. It stops on a
deployment failure and does not switch live routing. Existing CI model deploys
continue to use their configured CI credentials; keep standby accounts updated
using this helper when agent code changes.

## Failure and rollback behavior

All seven origins must return HTTP success and JSON `{"status":"ok"}` from
`/health` before activation. Health checks can start the CPU web containers and
cannot verify every GPU's weights or run inference. Smoke-test representative
generation, labeling, evaluation and 3D requests before relying on a standby.

Failed checks leave the old routing file untouched. Successful switches store
the previous snapshot and atomically replace the file. An operator lock prevents
simultaneous switches. `rollback` checks and restores the previous snapshot, even
if the registry has since been edited. The first switch can roll back to the
existing environment URLs. Malformed active files fail closed instead of silently
sending jobs to another account. Missing files use existing environment routing.

There is no automatic account rotation or retry on model failure. A healthy
`/health` does not guarantee credit balance or GPU capacity. Failed inference must
be handled as a failed job; inspect it before retrying to avoid duplicate work.
Protected Modal endpoints require a separate proxy-token integration; this
implementation uses the project's current public ASGI endpoints and does not send
Modal CLI tokens in HTTP requests.

## Tests

From `backend/`, with development dependencies installed:

```bash
python -m unittest discover -s tests -p test_modal_accounts.py
```

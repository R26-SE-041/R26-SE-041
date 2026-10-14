# Switching Koji between Modal workspaces

Koji has three registered profiles: `kojithan-y`, `ikojikn`, and `agal-koji`, all
using the `main` environment. The sample registry contains the normal ASGI URLs
for this project's app names. Compare them with each deployment's actual URLs;
custom domains or renamed endpoints must be entered explicitly.

The six GPU agents switch together. The EC2 data API and the existing
`kojithan-y` memory/orchestrator endpoint are shared across profiles. Production
database credentials stay with those existing data services.

## Verified production installation — 2026-10-14

The remote controller is installed on the existing EC2 host. Local HTTPS
commands switched live routing through all three accounts, restored the previous
account with rollback, and left `agal-koji` active. Unauthorized control requests
returned 401; EC2 readiness and the production frontend API proxy returned 200.
All accounts passed endpoint health checks and real Sketch inference. The missing
Sketch deployments and model files were prepared in `kojithan-y` and `ikojikn`.
The updated frontend is published to the existing Koji Vercel project.

Installation backup: `/home/ubuntu/koji/deploy-backups/modal-switch.oOhat1gp`.
Daily switching uses HTTPS and does not require changing SSH ingress rules.

## Run from the local backend folder to switch EC2

```powershell
.\switch-modal.ps1 agal-koji
.\switch-modal.ps1 kojithan-y
.\switch-modal.ps1 ikojikn
.\switch-modal.ps1 -Action status
.\switch-modal.ps1 -Action rollback
```

These commands default to **remote EC2 control** over HTTPS. They do not change
the laptop's routing file. `-Local` explicitly selects local development routing.
No SSH connection is needed for daily switching after installation.

Equivalent Python commands from `backend/`:

```bash
python switch-modal.py agal-koji
python switch-modal.py status
python switch-modal.py rollback
```

`backend/modal-remote.json` selects the EC2 HTTPS origin and the private operator
token file. The prepared local configuration points to the existing ignored
`output/ec2-release/deploy-receiver.env`; copy `modal-remote.example.json` for a
new operator and configure their own secure token storage. Never commit the token
or expose it to the frontend. The receiver uses its existing deployment token,
constant-time authorization and only permits the five account operations.
Remote client redirects are disabled and TLS verification uses the OS trust store.
If the connection fails during a switch, query remote status before retrying.

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
   `hf-secret` and any other model secrets referenced by the deployed agents.
   Learner data and history remain in the existing shared Supabase project.
3. Verify each account's deployed endpoint origins in the registry. The prepared
   registry shares the existing primary orchestrator for legacy memory routes.
4. Deploy the updated CPU backend once. For local development, restart the
   development API once after installing this code. Subsequent switches require
   no restart.
5. Configure the frontend's existing `EXPO_PUBLIC_STUDIO_API_URL` to the stable
   CPU API, and Supabase login as usual. Browser health indicators now use the
   authenticated Studio agent proxy. Direct browser-to-Modal mode without a
   Studio API continues to use build-time URLs and does not follow server switches.

On EC2, install the updated receiver and CPU routing modules, copy the live
registry to `/home/ubuntu/koji/backend/modal-accounts.json`
and install `deploy/aws/switch-modal.sh` at
`/home/ubuntu/koji/deploy-control/switch-modal.sh`. Install these as operator-owned
files readable by the `ubuntu` API user. The default routing state is
`/home/ubuntu/koji/backend/modal-active.json`. The wrapper and API derive the same
paths from this layout. Keep routing files outside the `studio/` and `shared/`
directories replaced by release activation.

`deploy/aws/install_modal_switch.sh` installs a checksum-verified bounded package,
backs up replaced files, verifies database readiness and authenticated control,
and restores previous sources if installation fails. It restarts the API and
receiver once and preserves the running worker. Daily operations serialize with
release activation and account switching. The existing Caddy deployment route
already forwards `/internal/koji-deploy/modal` to the receiver.

Generate the bounded package with
`python deploy/aws/package_modal_switch.py --output tmp/modal-switch.tar.gz`.
Stage that archive and `install_modal_switch.sh` in a new
`/home/ubuntu/koji/deploy-staging/modal-switch-*` directory using pinned SSH,
then run the installer as the existing deployment administrator. The archive
contains public routing configuration and source only; it excludes operator
tokens, backend `.env`, and all model credentials.

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

## Explicit local development routing

From the Koji `backend/` directory, using a Python environment with the existing
Studio dependencies installed:

```powershell
.\switch-modal.ps1 -Local -Action list
.\switch-modal.ps1 -Local agal-koji
.\switch-modal.ps1 -Local -Action status
.\switch-modal.ps1 -Local -Action rollback
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
python deploy/modal/deploy_accounts.py --account ikojikn --services sketch
python deploy/modal/deploy_accounts.py --all
```

The helper deploys the six agents, or only the selected `--services`.
The optional `--include-orchestrator` is for separately managed orchestrator
deployments with their required secrets already provisioned; it is not needed
for account switching. Model volume contents must be prepared separately.
The helper selects `MODAL_PROFILE` and the environment per subprocess
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
python -m unittest discover -s tests -p test_modal_remote.py
```

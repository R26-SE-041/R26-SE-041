# Koji deployment

The Koji workflow is independent of the other research components. Only changes under `koji-interactive-infographic-generator/` or its workflow trigger this pipeline. Root README and research-document changes do not deploy Koji.

## Release behavior

- Pull requests and branch pushes run TypeScript, frontend unit tests, backend tests, and PostgreSQL integration checks on GitHub-hosted runners.
- Production deployments run only from `main` or explicit `koji-release-*` tags, after both test jobs pass.
- Frontend changes deploy the tested web artifact to the existing `koji-studio` Vercel project.
- CPU backend changes deploy only `studio/` and `shared/` to EC2. Frontend-only changes do not restart the API or worker.
- EC2 automatic deployment additionally requires `KOJI_EC2_DEPLOY_ENABLED=true`. Enable it after installing and verifying the authenticated HTTPS release receiver.
- When a release changes both frontend and backend, the backend must succeed before the frontend is published.
- Agent/model changes are separate. Modal deployment requires `KOJI_MODEL_DEPLOY_ENABLED=true` or the explicit manual model-deploy option. Routine frontend changes do not redeploy GPUs.
- `KOJI_DEPLOY_ENABLED=false` pauses production jobs without disabling CI. Set it to `true` after credentials and runner access are verified.
- GitHub Actions → Koji CI/CD → Run workflow provides `all`, `frontend`, and `backend` targets for a manual fallback. Run production releases from `main`.
- If a push changes both backend and frontend while EC2 automation is paused, automatic frontend publication waits for backend deployment. After manually deploying the backend, run the workflow with target `frontend` to publish the tested client.

## Existing EC2 installation

The current Ubuntu server uses:

- SSH user: `ubuntu`.
- Application root: `/home/ubuntu/koji`.
- API and worker source: `/home/ubuntu/koji/backend`.
- Private environment: `/home/ubuntu/koji/backend/.env`.
- Service paths: `/home/ubuntu/koji/backend/.venv/bin/python`.
- Services: `koji-api.service` and `koji-worker.service`.

Activation keeps `.env` and systemd paths unchanged. It verifies the tested artifact's commit and file hashes, builds a new CPU virtual environment at a stable absolute path, checks imports and database readiness, and then replaces the two source directories and Python environment link. Failed activation or readiness restores the previous source and Python environment. Deployment does not apply database migrations. Apply reviewed migrations before releasing code that requires them.

Backups are retained in `deploy-backups/`; Python environments are retained in `deploy-environments/`. Clean old releases deliberately after identifying the active environment and a known good backup. The deployment lock prevents overlapping automatic and manual activation.

The included systemd files are installation templates matching this layout. Do not overwrite running unit definitions during routine deployment. New database migrations require a separate reviewed migration step before the release.

## GitHub settings

Public repository variables used when building the frontend:

| Variable | Purpose |
| --- | --- |
| `KOJI_STUDIO_API_URL` | HTTPS Studio API origin |
| `KOJI_STUDIO_PROXY_PATH` | Same-origin API prefix; defaults to `/studio-api` |
| `KOJI_SUPABASE_URL` | Existing Supabase authentication project |
| `KOJI_SUPABASE_ANON_KEY` | Public browser key; never a service-role key |
| `KOJI_DEPLOY_ENABLED` | Production deployment switch |
| `KOJI_EC2_DEPLOY_ENABLED` | Enable EC2 automatic deployment only after runner access is configured |
| `KOJI_MODEL_DEPLOY_ENABLED` | Optional automatic model deployment switch |

The `koji-production` environment owns these deployment variables:

| Variable | Value or purpose |
| --- | --- |
| `KOJI_EC2_HOST` | EC2 hostname/IP without a username |
| `KOJI_EC2_USER` | Defaults to `ubuntu` |
| `KOJI_EC2_ROOT` | Defaults to `/home/ubuntu/koji` |
| `KOJI_VERCEL_ORG_ID` | Existing Vercel team ID |
| `KOJI_VERCEL_PROJECT_ID` | Existing Koji project ID |

Production secrets:

- `KOJI_DEPLOY_TOKEN`: a random token of at least 40 characters, shared only with the EC2 release receiver.
- SSH credentials are only needed for the manual `ci/deploy_ec2.py` fallback.
- `KOJI_VERCEL_TOKEN`: Vercel deployment token. Use a project-scoped token where available and track its expiry.
- `KOJI_MODAL_TOKEN_ID` and `KOJI_MODAL_TOKEN_SECRET`: only needed for model deployment.

Secrets belong in GitHub's protected secret storage, never in the repository, frontend export, artifact manifest, or logs. The workflow uses strict SSH host verification and refuses unsafe release archive paths or a mismatched commit.

## Automatic EC2 releases over HTTPS

GitHub-hosted runners run all checks and upload the tested backend archive to `/internal/koji-deploy` over HTTPS. The receiver verifies the production token, GitHub workflow identity, commit, successful frontend/backend checks, completed model deployment, bounded archive contents and checksums before activation. It returns a release ID; the workflow polls until activation and readiness finish. Vercel publication waits for backend success. Model changes deploy before the API and frontend.

Install `deploy_service.py` and `activate.sh` in `/home/ubuntu/koji/deploy-control`, and install `koji-deploy.service` as a systemd unit. Store `KOJI_DEPLOY_TOKEN` in a mode-600 `.env` in that directory and as the `koji-production` encrypted secret of the same name. The service listens only on `127.0.0.1:8766`; Caddy forwards `/internal/koji-deploy*` to it and all other requests to `127.0.0.1:8000`. Keep port 8000 and 8766 private. No self-hosted Actions runner or public SSH rule is needed. SSH can remain limited to the administrator's IP.

The activation script is installed by an administrator. Changes to `activate.sh` or the receiver require updating those installed control files over pinned SSH. Routine application changes are fully automatic. Receiver/activation logs remain on EC2, outside public responses. A dedicated production environment branch policy restricts release credentials to `main` and approved release tags.

The existing Ubuntu deployment administrator can restart the two Koji services. No pull-request code runs on EC2; public-repository tests use GitHub-hosted runners. Keep the production token only in encrypted GitHub secrets and the private server environment. Never put it in repository variables or browser builds.

## Validation

```bash
python -m unittest discover -s koji-interactive-infographic-generator/ci/tests -p 'test_*.py'
```

Deployment tests check monorepo isolation, artifact contents, rejection of unsafe paths, and Linux activation/rollback. Backend PostgreSQL tests use an isolated GitHub Actions service database. Production readiness checks read existing tables without changing learner data or calling paid model endpoints.

After deployment, verify API `/ready`, API/worker service status, the production frontend, and its `/studio-api/ready` proxy. The research website is a separate Vercel project and is outside this workflow.

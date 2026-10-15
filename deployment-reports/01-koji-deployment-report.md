# Deployment Report — Interactive Infographic Generator

**Project:** BioLearnX / R26-SE-041  
**Member:** Kojithan P. Y  
**Student ID:** IT22264220  
**Component directory:** `koji-interactive-infographic-generator/`  
**Prepared:** 14 October 2026

## 1. Purpose and deployment status

The component produces interactive biology visualizations from prompts and sketches, supports anatomy labeling and image questions, saves conversation history, retrieves evidence from uploaded PDFs, and optionally generates 3D assets.

The repository documents a Vercel web client, an AWS EC2 CPU API and worker, Modal model services, and an existing Supabase project. It includes a component-specific GitHub Actions release workflow, systemd templates, an authenticated HTTPS release receiver, artifact verification, and automatic activation rollback. The documented frontend is `https://koji-studio.vercel.app`; availability and currently active release were not checked for this report. Render configuration is an alternative retained in the repository; the AWS deployment guide describes the EC2 release path.

## 2. Deployment architecture

| Layer | Implementation | Deployment responsibility |
| --- | --- | --- |
| Web client | React Native / Expo web export | Vercel serves the tested static client and `/studio-api` proxy |
| API | FastAPI, `studio.main:app` | EC2 systemd service `koji-api.service` |
| Durable worker | `python -m studio.worker` | EC2 systemd service `koji-worker.service` |
| Model inference | Prompt, image, sketch, interactive, evaluation, and 3D agents | Independent Modal deployments |
| Identity and persistent data | Supabase Auth, PostgreSQL/pgvector, private Storage | Existing Supabase project |
| Release control | GitHub Actions and HTTPS receiver | Test, package, verify, activate, and check readiness |

An authenticated request creates a durable job in PostgreSQL. The worker calls Modal and stores results and history in private Supabase storage and tables. Closing the browser does not stop the job. Browser API calls normally use the same-origin proxy; PDF uploads use the API origin directly and therefore require its CORS configuration.

## 3. Prerequisites and configuration

The documented Ubuntu installation uses `/home/ubuntu/koji/backend`, a private `.env`, and `.venv/bin/python`. Install CPU dependencies from `backend/studio/requirements.txt`; GPU dependencies belong to the respective Modal images. Provision a persistent worker and allow model-cache downloads needed for CPU PDF embeddings.

| Configuration | Location / purpose |
| --- | --- |
| `DATABASE_URL` | Backend PostgreSQL connection with TLS |
| `SUPABASE_URL`, `SUPABASE_ANON_KEY` | Backend identity validation |
| `SUPABASE_SERVICE_ROLE_KEY` | Backend-only storage and service access |
| `CORS_ORIGINS` | Exact permitted frontend origins |
| Model endpoint URLs | Values from current Modal deployments, using `backend/studio/.env.example` |
| `EXPO_PUBLIC_STUDIO_API_URL` | Public API origin embedded in frontend build |
| `EXPO_PUBLIC_STUDIO_PROXY_PATH` | `/studio-api` for the production web client |
| `EXPO_PUBLIC_SUPABASE_URL`, `EXPO_PUBLIC_SUPABASE_ANON_KEY` | Public authentication configuration |
| `KOJI_DEPLOY_ENABLED` | Enables production jobs |
| `KOJI_EC2_DEPLOY_ENABLED` | Enables the configured HTTPS EC2 release receiver |
| `KOJI_MODEL_DEPLOY_ENABLED` | Enables optional automatic model deployment |
| `KOJI_DEPLOY_TOKEN` | Private shared receiver token; at least 40 characters |
| `KOJI_VERCEL_TOKEN` | Private Vercel deployment credential |
| `KOJI_MODAL_TOKEN_ID`, `KOJI_MODAL_TOKEN_SECRET` | Private model deployment credentials |

Repository build variables map the public values through `KOJI_STUDIO_API_URL`, `KOJI_STUDIO_PROXY_PATH`, `KOJI_SUPABASE_URL`, and `KOJI_SUPABASE_ANON_KEY`. Configure project/organization IDs and the production environment following the AWS guide. Each target Modal account must contain the secrets required by its agents, including `hf-secret` where applicable.

## 4. Deployment procedure

1. Select the release commit and configure the existing Supabase project. Review and apply all required migrations before releasing dependent code. From the component backend:

   ```bash
   python -m studio.migrate
   ```

   This uses real database credentials and changes the target schema. Automatic EC2 deployment does not run migrations. The PDF feature requires the document/library migrations as well as the job/history schema.

2. Deploy changed Modal services before dependent API/client changes. The PowerShell helper `backend/deploy_all.ps1` deploys the listed agents sequentially. Its `-IncludeSupabaseServices` switch adds the orchestrator and skill generator. Use the configured destination account and required secrets.
3. For initial EC2 installation, install and verify the API/worker services. Install the receiver and activation script in `/home/ubuntu/koji/deploy-control`, configure its mode-600 environment file, and install `koji-deploy.service` following the AWS guide. Control scripts require administrator installation separately from routine application releases.
4. Configure HTTPS routing: Caddy sends `/internal/koji-deploy*` to `127.0.0.1:8766` and application requests to `127.0.0.1:8000`. Keep both internal ports private.
5. Configure the protected `koji-production` environment and production switches. Release through `.github/workflows/koji-interactive.yml` from `main`, an allowed `koji-release-*` tag, or an appropriate manual dispatch from `main`.
6. The workflow runs frontend/backend checks, packages tested artifacts, deploys affected enabled model services, activates the backend, and publishes the frontend after required backend success. A frontend-only change does not restart the API/worker.

For manual frontend packaging, run from the component frontend:

```bash
npm ci
npm run build:web
python ../ci/pack_vercel.py
```

Publish the resulting prebuilt artifact through the configured release path. Public build-variable changes require a new frontend build. Backend environment changes require restarting both API and worker; existing queued jobs retain the model URLs captured when they were created.

## 5. Release verification and acceptance

Run the prescribed frontend checks:

```bash
npm run typecheck
npm run test:unit
npm run build:web
```

From the backend, install `studio/requirements-dev.txt` and run `python ../ci/check.py`. PostgreSQL integration checks require `STUDIO_TEST_DATABASE_URL` pointing to a disposable pgvector-enabled database. Never use the production database for those checks. Deployment unit checks run from the repository root:

```bash
python -m unittest discover -s koji-interactive-infographic-generator/ci/tests -p 'test_*.py'
```

After release, verify API `/health`, API `/ready`, frontend `/studio-api/ready`, and the status of both systemd services. Perform a controlled signed-in generation, reopen saved history, edit labels, and test an owner-scoped PDF question. Check a second account cannot access the first account's private content. Test 3D conversion when that endpoint is included in the release. Model calls may consume GPU credits.

Record the commit, artifact hashes, service status, readiness results, and acceptance evidence. Readiness alone does not prove model output quality.

## 6. Operations, persistence, and rollback

Monitor API/worker logs, queue delay, failed jobs, Modal errors, database/storage usage, and embedding cache availability. Size EC2 from measured CPU/RAM and concurrent jobs; the repository does not establish a verified capacity figure for this report.

The activation process verifies commit and hashes, builds a CPU environment, checks imports/database readiness, and restores the previous source and environment if activation or readiness fails. Backups remain under `deploy-backups/`, and environments under `deploy-environments/`. Retain the active release and a known good rollback target. Database migrations and Modal model changes require their own compatibility/rollback plan; restoring application files does not reverse either.

Avoid restoring learner data merely to roll back code. Prefer a compatible previous release, then repeat readiness and a small acceptance check.

## 7. Evidence and remaining confirmation

This report establishes that deployment automation exists in source. Production receiver installation, environment-switch values, applied migrations, active Modal accounts, runtime health, and acceptance results require operator confirmation.

Repository references: [component guide](../koji-interactive-infographic-generator/README.md), [AWS release guide](../koji-interactive-infographic-generator/deploy/aws/README.md), [workflow](../.github/workflows/koji-interactive.yml), [Modal helper](../koji-interactive-infographic-generator/backend/deploy_all.ps1), and [authentication guide](../koji-interactive-infographic-generator/docs/authentication.md).

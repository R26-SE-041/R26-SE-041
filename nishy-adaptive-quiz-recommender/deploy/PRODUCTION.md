# Nishy adaptive quiz deployment

## Latency update status — 19 October 2026

The existing Modal app `nishy-qwen-adaptive-quiz` was redeployed successfully.
Its web `/health` returned HTTP 200 with the expected base model and adapter.
The release retains A10G, permits at most one GPU container, sets minimum
containers to zero, reduces the idle window to 120 seconds, and adds complete-JSON
stopping and a generation time limit. No GPU inference/warm-up was performed.

The EC2 latency release `9409e61` was deployed successfully through Systems
Manager command `c02ecca6-ecbf-49df-8b30-5c6a7a8fdd3c`. All five running source
files were checked against the local release hashes. Public HTTPS `/ready`
returned HTTP 200 from EC2, with the expected Vercel origin in the CORS response.
The local `/health` and PostgreSQL `/ready` checks passed. The API container is
healthy; databases, uploads, volumes and Caddy were preserved. Rollback files
are stored in `/opt/nishy-quiz/latency-backup-q12B1yjv`.

The runtime question budget is now 15 seconds. Embedding preloading, the bounded
embedding cache and the 30-second health cache/failure cooldown are enabled.
These settings were also synchronized into the existing encrypted
`/nishy-quiz/backend-env` parameter (version 4), preserving its credentials and
encryption key. Startup logs measured local embedding initialization at 6.764
seconds before application startup completed.

Vercel production redeployment `dpl_Bf82eJcmvV4THx9gQBJZsdUgwyw3` reached `READY`
and serves `https://nishy-adaptive-quiz.vercel.app`. This rebuild uses the existing
frontend source and inherited production settings; the performance code changes
are in the backend and Modal service. The homepage and sign-in page returned
HTTP 200. The frontend production build also passed locally.

Validation: 128 backend tests passed; packaged source matches the tested files,
embedded Python parses, and the release script passes `bash -n`. A separate SSM
verification command, `9f6b1285-c8fb-4fef-8733-07e3a6f4b8d1`, confirmed running
source hashes, public HTTPS readiness, CORS and embedding startup. No paid GPU
inference/warm-up or complete live quiz was run for this latency release.

Deployment date: 18 October 2026.

| Resource | Location |
| --- | --- |
| Frontend | https://nishy-adaptive-quiz.vercel.app |
| Backend API | https://quiz.13.63.218.37.sslip.io |
| Database | Supabase project `pnmxnivuqxriilymvtjh`, private schema `nishy_quiz` |
| AWS Region | Stockholm, `eu-north-1` |
| CloudFormation stack | `nishy-adaptive-quiz` |
| EC2 instance | `i-0a0fa0ce254342df8`, `t3.medium` |
| Elastic IP | `13.63.218.37` |
| Vercel project | `nishy-adaptive-quiz` in team `nishy2` |

The backend runs from `/opt/nishy-quiz/deploy` on EC2. Use the EC2 Console's
Session Manager connection and `sudo -i` to inspect it:

```bash
cd /opt/nishy-quiz/deploy
docker compose ps
docker compose logs --tail=100 api caddy
tail -n 100 /var/log/nishy-deploy.log
```

Production uses a shared 15-second question-generation budget. The API returns
the session immediately and the frontend polls while generation runs in the
background. A cold GPU can still exceed this budget and invoke existing validated
recovery. For a presentation, explicitly warm the deployed model once shortly
before starting; see `backend/scripts/warm_modal.py`. That optional action consumes
Modal credits and is not an automatic keep-alive.

The restricted PostgreSQL login owns only the `nishy_quiz` schema. Its runtime
environment is stored in SSM Parameter Store as SecureString
`/nishy-quiz/backend-env`, and fetched into a file readable only by root.
After updating that parameter, refresh the EC2 environment and recreate the API:

```bash
umask 077
aws ssm get-parameter --name /nishy-quiz/backend-env --with-decryption \
  --region eu-north-1 --query Parameter.Value --output text > backend.env
docker compose up -d --force-recreate api
```

The stack's private S3 bucket holds source deployment archives, with a
seven-day expiration rule. Archives contain application source and configuration
examples. Database credentials are supplied separately through SSM.

Chroma, graph checkpoints and uploads persist in the `nishy-quiz_quiz_db` and
`nishy-quiz_quiz_data` Docker volumes. Take backups/EBS snapshots before deleting
the instance or its volumes. Supabase stores the relational assessment records.
This cloud deployment starts fresh; existing local learner records, document
uploads and retrieval indexes have not been imported.

The initial API hostname uses sslip.io DNS with a public HTTPS certificate.
To use your own domain, point its A record at the Elastic IP, change `API_DOMAIN`
in EC2 `deploy/.env`, recreate Caddy, update `NEXT_PUBLIC_API_URL` in Vercel,
and redeploy the frontend. If the frontend domain changes, also update
`ALLOWED_ORIGINS` in the encrypted backend configuration and recreate the API.

EC2, EBS, public IPv4 and other AWS resources incur normal AWS usage charges.
See [DEPLOYMENT.md](../DEPLOYMENT.md) for build, migration and backup instructions.

## Deployment verification

- Production frontend pages and the embedded HTTPS API origin were verified.
- Public API health, PostgreSQL readiness and production CORS returned success.
- Chrome verified the API certificate using its normal trust checks.
- A five-question Lipids quiz completed with correct evaluation, final analytics,
  recommendations and persisted feedback.
- A synthetic text document uploaded, embedded into Chroma and appeared in the
  Supabase-backed document list. Synthetic test records were cleaned up.

Model generation still has a content limitation: the `Cell biology` topic-only
test reached four questions, then its fifth question was rejected as duplicate
or unrelated. This was not a hosting or database connection failure. The
application preserves its existing validation and generation retry controls.

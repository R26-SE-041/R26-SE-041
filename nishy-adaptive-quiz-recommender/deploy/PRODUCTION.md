# Nishy adaptive quiz deployment

## Latency update status — 19 October 2026

The existing Modal app `nishy-qwen-adaptive-quiz` was redeployed successfully.
Its web `/health` returned HTTP 200 with the expected base model and adapter.
The release retains A10G, permits at most one GPU container, sets minimum
containers to zero, reduces the idle window to 120 seconds, and adds complete-JSON
stopping and a generation time limit. No GPU inference/warm-up was performed.

The EC2 backend latency changes are **pending execution in Session Manager**;
this workstation has no configured AWS CLI/SSH access. Run the full contents of
`artifacts/latency-update-20261019.sh` in the existing instance's Session Manager
terminal. The generated script includes only five source files, checks its payload
checksum, backs up existing code and backend.env, sets the runtime question budget
to 15 seconds, rebuilds/replaces only the API container, and checks local HTTP
health/readiness. Failure triggers restoration of the previous source, runtime
environment and Docker image. It does not modify databases, volumes, Caddy, or
the SSM parameter. Preserve the same non-secret runtime overrides in
`/nishy-quiz/backend-env` before any later refresh from that parameter.

Local verification: 128 backend tests passed; packaged source matches the tested
files, embedded Python parses, and the shell script passes `bash -n`. The backend
release is not complete until the script reports `BACKEND LATENCY UPDATE SUCCESSFUL`
and the running application's behavior is verified.

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

Production allows a 120-second question-generation budget so the existing
Modal GPU service can cold-start. The API returns the session immediately and
the frontend polls for readiness while generation runs in the background.

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

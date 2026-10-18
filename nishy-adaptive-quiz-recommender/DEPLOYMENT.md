# Nishy Adaptive Quiz: Vercel + EC2 + Supabase

This guide applies only to `nishy-adaptive-quiz-recommender`.

| Part | Host | Configuration |
| --- | --- | --- |
| Next.js frontend | Vercel | `frontend/vercel.json`, `NEXT_PUBLIC_API_URL` |
| FastAPI backend | EC2, Docker Compose | `deploy/compose.yml`, `deploy/backend.env` |
| Sessions, documents, questions, answers, analytics, logs | Supabase PostgreSQL | `DATABASE_URL`, private `nishy_quiz` schema |
| Chroma retrieval index, LangGraph SQLite checkpoints, uploaded files | EC2 named Docker volumes | `quiz_db`, `quiz_data` |
| Qwen inference | Existing Modal endpoint | `MODAL_ENDPOINT_URL`, optional `MODAL_API_KEY` |

The database switch does not move the GPU model to EC2. One API process owns
the graph checkpoints and background generation jobs; do not increase Uvicorn
workers or run multiple replicas with these local stores.

## 1. Create the Supabase database

1. Create a Supabase project and keep its database password in your password manager.
2. Open **Connect > Session pooler** and copy the PostgreSQL URI (port **5432**).
   This mode supports IPv4 EC2 hosts. URL-encode special characters in the password.
3. Keep the URI on EC2 in `deploy/backend.env` as `DATABASE_URL` with
   `?sslmode=require`. The driver also requires SSL.

The deployment runs `backend/scripts/migrate.py` before replacing the API.
It creates six assessment tables in a separate `nishy_quiz` schema, indexes,
and RLS. Use the project database owner connection for this initial setup.
Do not expose this schema through the Supabase Data API. The backend accesses
it directly; frontend Supabase keys are unnecessary for this component.
Other modules' `public.documents` and `public.sessions` tables are unaffected.

## 2. Create the EC2 instance from your AWS account

The included `deploy/ec2-stack.yml` creates an Amazon Linux 2023 instance,
its network, an Elastic IP, an instance role for Session Manager, and installs
Docker and Compose. It opens only TCP 80 and 443 publicly. Port 8000 stays
inside Docker. The default `t3.medium`, 30 GiB disk and public IPv4 incur AWS
charges; review the stack resources before creating it.

1. In AWS Console, select the region you want to use.
2. Open **CloudFormation > Create stack > With new resources (standard)**.
3. Select **Upload a template file** and upload `deploy/ec2-stack.yml`.
4. Name the stack `nishy-adaptive-quiz`, keep the AMI parameter, choose the instance type.
5. Acknowledge creation of IAM resources and create the stack.
6. Wait for `CREATE_COMPLETE`; open **Outputs** for `InstanceId` and `ElasticIp`.
7. Open the instance in EC2, then **Connect > Session Manager > Connect**.
   Package installation can take a few more minutes after stack creation.
8. Run `sudo cloud-init status --wait` and check `sudo docker compose version`.
   If bootstrap failed, inspect `/var/log/cloud-init-output.log` before continuing.

No SSH key is required with Session Manager. Your signed-in AWS identity needs
permission to create the stack and open a Session Manager session.

Create an **A record** for an API subdomain you control, such as
`quiz-api.yourdomain.com`, pointing to the Elastic IP. Wait for DNS to resolve.
Caddy obtains and renews the HTTPS certificate automatically after the API is healthy.
An API domain with publicly valid HTTPS is needed for browser requests from Vercel.

## 3. Configure Vercel

1. Import this Git repository into Vercel as a new project.
2. Set **Root Directory** to `nishy-adaptive-quiz-recommender/frontend`.
3. Choose the **Next.js** framework preset. Keep the output-directory setting at its framework default.
4. Set `NEXT_PUBLIC_API_URL=https://quiz-api.yourdomain.com` in the environments
   you deploy. It is a build-time value; changing it requires a new deployment.
5. Deploy and copy your production origin, such as `https://your-quiz.vercel.app`.

The frontend build deliberately fails on Vercel if the API URL is missing or
uses HTTP. Deploying the UI before the API is ready is fine; requests will work
after the backend starts. No database credentials belong in Vercel.

## 4. Configure and start the API

Make sure your intended local changes are available in the Git revision you
clone. Deployment commands do not automatically upload uncommitted work.
In the EC2 Session Manager terminal:

```bash
sudo -iu ec2-user
git clone https://github.com/R26-SE-041/R26-SE-041.git
cd R26-SE-041/nishy-adaptive-quiz-recommender/deploy
cp .env.example .env
cp backend.env.example backend.env
chmod 600 .env backend.env
nano .env
nano backend.env
```

For a private Git repository, authenticate Git with your normal deployment
credentials. Do not embed an access token in a committed clone URL.

Set these values in `.env`:

```dotenv
API_DOMAIN=quiz-api.yourdomain.com
TLS_EMAIL=your-email@example.com
```

Set these values in `backend.env`, keeping the other example settings:

```dotenv
APP_ENV=production
DEBUG=false
ALLOWED_ORIGINS=https://your-quiz.vercel.app
DATABASE_URL=postgresql://postgres.PROJECT_REF:ENCODED_PASSWORD@YOUR_SESSION_POOLER:5432/postgres?sslmode=require
```

`ALLOWED_ORIGINS` is a comma-separated list of exact HTTPS origins. Add a
stable preview/custom domain explicitly if you need it. Review the existing
Modal endpoint and set its key if your endpoint requires authentication.
The supplied Modal timeout remains 660 seconds; Caddy allows 720 seconds for
an upstream response. Frontend requests go directly to EC2.

```bash
bash deploy.sh
curl --fail https://quiz-api.yourdomain.com/health
curl --fail https://quiz-api.yourdomain.com/ready
docker compose ps
```

The first build installs CPU PyTorch and preloads MiniLM, so allow time for
downloads. `/health` checks the HTTP service. `/ready` also verifies database
connectivity and that the assessment schema exists. Open the Vercel frontend,
upload a biology document, start a quiz, submit an answer, and view results.

## 5. Optional: bring across existing local records

A fresh deployment starts with an empty cloud database and empty EC2 volumes.
To retain relational history, stop local quiz writes, take a consistent SQLite
backup, and run this from `backend/` using its Python environment with the
Supabase `DATABASE_URL` configured:

```bash
python scripts/migrate.py
python scripts/import_sqlite.py --sqlite /path/to/sessions-backup.db
```

The import opens the source read-only, inserts in dependency order, and commits
all records together. Existing cloud primary keys are skipped and counted,
never overwritten. A constraint error rolls back the complete import.

Relational records alone do not contain the document embeddings or the live
quiz state. To resume existing sessions, also transfer the matching Chroma
directory, SQLite graph checkpoints and uploaded files into the EC2 volumes
with the API stopped. Otherwise re-upload documents and start new sessions.
Do not copy a live SQLite database without its consistent checkpoint/backup.

## Updates, logs and backups

From the repository on EC2, fast-forward to the intended published revision,
then run `bash deploy.sh` from `deploy/`. The script validates Compose without
printing credentials, builds the image, applies the database migration and
waits for healthy services. A failed migration prevents replacement of the API.
Restarting the API interrupts in-flight background generation; deploy between quizzes.

```bash
docker compose logs --tail=100 api caddy
```

Docker volumes survive container replacement and normal `docker compose down`.
Back up the EC2 disk/volumes and Supabase according to your retention needs.
`docker compose down -v` removes the volumes. Deleting the CloudFormation stack
terminates the instance and deletes its disk, so take an EBS snapshot first if
you need that data. Keep the previous application revision for rollback; the
initial database migration is additive and does not drop existing data.

## Local development and checks

Leave `DATABASE_URL` empty and `APP_ENV=development` to keep local SQLite.
Use `NEXT_PUBLIC_API_URL=http://localhost:8000` locally.

```bash
# backend, with its environment active
python -m unittest tests.test_deployment -v
python -m unittest discover -s tests -p 'test_*.py'

# frontend
npm ci
npm run build
```

## Accounts, history and recovery

Set `NEXT_PUBLIC_SUPABASE_URL` and `NEXT_PUBLIC_SUPABASE_ANON_KEY` on Vercel,
and `SUPABASE_URL` and `SUPABASE_ANON_KEY` in the EC2 backend environment.
Use the public anon key. Never ship a service-role key to the browser.
Every `/api/v1` route requires a Supabase bearer token, verified by Supabase
before backend ownership checks. Client-supplied student IDs are ignored.
Documents and histories belong to the signed-in user. Legacy records remain
stored but are not assigned to new accounts.

Set Supabase Authentication Site URL to the frontend origin and allow its exact
`/auth/callback` and `/reset-password` redirect URLs. Keep email confirmation
enabled. Configure custom SMTP for public signup and password recovery:
the default mailer only delivers to project team members, twice per hour.
See [Supabase SMTP documentation](https://supabase.com/docs/guides/auth/auth-smtp).
Recovery links establish a session for setting a new password. Account settings
require the current password and revoke other device sessions after updating.
The Supabase browser SDK refreshes tokens and synchronizes cross-tab sign-outs.

The additive `002_accounts_history.sql` migration adds ownership, titles,
soft deletion and indexes. `scripts/migrate.py` applies sorted idempotent SQL
migrations. My quizzes displays the latest 500 active sessions. Recycle bin
preserves answers, feedback, results and graph checkpoints. Restore returns
the quiz to the library. Trashed content cannot be accessed until restored.
There is no permanent-delete action or automatic purge.

Demo: create/confirm an account, sign in, finish a quiz, open My quizzes,
view results, move the quiz to the bin, restore it and reopen the results.
Use a configured SMTP inbox for signup and forgot-password email demonstrations.

Checks: `python -m unittest tests.test_auth_history tests.test_deployment -v`
and `npm run build`. Live smoke tests use disposable accounts. Administrative
test helpers and generated recovery links must never become application routes.

## Official references

- [Vercel monorepo projects and Root Directory](https://vercel.com/docs/monorepos)
- [Supabase PostgreSQL connections and session pooler](https://supabase.com/docs/guides/database/connecting-to-postgres)
- [Amazon Linux 2023 CloudFormation AMI parameter](https://docs.aws.amazon.com/linux/al2023/ug/ec2.html)
- [AWS Session Manager instance permissions](https://docs.aws.amazon.com/systems-manager/latest/userguide/setup-instance-permissions.html)
- [Docker Compose plugin installation](https://docs.docker.com/compose/install/linux/)
- [Caddy automatic HTTPS](https://caddyserver.com/docs/automatic-https)

# Sarmitha deployment

All application and deployment files stay in `sarmitha-image-text-extractor-study-gen`.

## Standalone EC2 backend (no Supabase account or purchased domain)

Use `compose.ec2.yaml` with `Caddyfile.ec2` to run the existing local storage mode.
Copy `ec2.env.example` to the ignored `deploy/.env`, fill the existing Modal URLs,
and set the hostname to `sarmitha-<elastic-ip-with-dashes>.sslip.io`. This public
DNS service resolves the embedded IP; Caddy obtains and renews HTTPS certificates.
A custom domain can replace this hostname later. No certificate email is required
by this configuration.

Store the environment file in the SecureString parameter described below. Deploy:

```powershell
./deploy/aws/deploy.ps1 -Region ap-southeast-1 -VpcId YOUR_VPC -SubnetId YOUR_SUBNET -Profile sarmitha-deploy -InstanceType t3.micro -ComposeFile compose.ec2.yaml
```

Feedback crops and training metadata persist in the Docker `feedback_data` volume
on the encrypted instance disk across container replacement. Local mode returns
OCR results to the client without storing OCR run history. Supabase is not
provisioned or required in this mode. Deleting the instance deletes this local
data; back it up before replacing or deleting the instance. To inspect services,
use `docker compose -f compose.ec2.yaml logs --tail=100 api proxy` through SSM.
Set `ALLOWED_ORIGINS` to the frontend origin before using a hosted frontend.

## Supabase-backed deployment

Vercel serves the Expo web frontend. An Ubuntu EC2 instance runs FastAPI behind
Caddy HTTPS. Supabase Postgres stores OCR text/results and corrections; private
Supabase Storage holds correction crops. Existing Modal endpoints continue to
run GPU inference, so EC2 needs no GPU. Original page images are not persisted.

## Prerequisites

- Connect Vercel and Supabase integrations, or sign in with their CLIs/dashboards.
- Install AWS CLI v2 and sign in to the intended AWS account (`aws configure sso`
  and `aws sso login --profile your-profile` if your account uses IAM Identity Center).
- Select an AWS region (Singapore `ap-southeast-1` is a reasonable starting point),
  a VPC, and a public subnet with Internet Gateway routing. The subnet must be in
  the chosen VPC. Do not supply AWS root credentials.
- A DNS hostname for the backend, such as `api.your-domain.com`. Caddy obtains
  HTTPS certificates once its DNS A record points to the instance's Elastic IP.

Cloud provisioning creates billable resources: EC2, EBS, a public IPv4 address,
and a private artifact bucket. Modal inference and Supabase usage are separate.
The default EC2 type is `t3.small`; this template is a single-instance setup.

## 1. Supabase

Create a project, choose a nearby region, and apply
[`supabase/001_ocr.sql`](supabase/001_ocr.sql), then
[`supabase/002_accounts_history.sql`](supabase/002_accounts_history.sql), and
[`supabase/003_history_images.sql`](supabase/003_history_images.sql).
The migrations are safe to rerun. RLS restricts history and account activity to
their authenticated owner. The correction storage bucket is private.
The private `ocr-history` bucket stores original and enhanced images under each
user/run ID. Apply migration 003 before deploying the updated backend. The default
`SUPABASE_HISTORY_BUCKET=ocr-history` needs no environment change. History detail
returns image links that expire after one hour; use Reload document to renew them.
Deleting a document removes both stored images and its text/translations. Older
text-only history remains readable; reprocess its source image to save images.
Set `SUPABASE_URL`, `SUPABASE_PUBLISHABLE_KEY` and `SUPABASE_SERVICE_ROLE_KEY`
on EC2, with `STORAGE_BACKEND=supabase`. The service role variable accepts either
a modern `sb_secret_` key or a legacy service-role JWT. Never put service keys
in frontend variables or commit them. The backend uses the REST API, so it needs
no public PostgreSQL port or database password at runtime.

In Auth settings, set the site and redirect URL to the production frontend,
enable email/password signup, and require at least 8 password characters.
Choose email verification to suit the deployment. Current production explicitly
uses immediate signup without verification at the owner's request; email
ownership is not verified. Enabling confirmation later requires custom SMTP
for public delivery because the default email service has delivery restrictions.
Confirmation redirect sessions are verified before being stored.
The `/api/auth/*` endpoints manage sessions, `/api/history` lists private OCR
results, and `/api/account/activity` lists account events. Passwords are handled
by Supabase Auth and never stored in application history tables.

## 2. Vercel project

Import the repository. Set Root Directory to
`sarmitha-image-text-extractor-study-gen/frontend-rn`, Framework to Other,
Build Command to `npm run build`, and Output Directory to `dist`.
Set `EXPO_PUBLIC_API_URL=https://api.your-domain.com` for Production and Preview.
Hosted builds deliberately fail if this value is absent or uses localhost/HTTP.
The project-level `vercel.json` handles SPA routing.

Record the assigned production frontend origin (no trailing slash). A build can
be published before EC2 is online, but OCR will work only after the backend is ready.
No Supabase or AWS secret belongs in Vercel for this frontend.

## 3. Backend secrets

Copy `deploy/.env.example` into a local ignored `deploy/.env` and fill all values.
Use the existing Modal endpoint URLs from `backend/.env` for enhancement, OCR
lines and optional translation. Set `ALLOWED_ORIGINS` to the exact Vercel origin;
use comma-separated origins if needed. Preview domains are not implicitly trusted.

In AWS Systems Manager > Parameter Store, create the **SecureString** parameter
`/sarmitha/production/environment` using the default AWS managed key. Its value
is the complete contents of `deploy/.env`, including `BACKEND_DOMAIN` and
`ACME_EMAIL`. The instance role can read only this named parameter. For a custom
KMS key, add a narrowly scoped `kms:Decrypt` permission to the template.

## 4. Create EC2 and deploy

From this project folder in PowerShell:

```powershell
./deploy/aws/deploy.ps1 -Region ap-southeast-1 -VpcId vpc-REPLACE -SubnetId subnet-REPLACE -Profile your-profile
```

The script deploys `aws/ec2.yaml` through CloudFormation, packages an explicit
allowlist of backend files, uploads it to private S3, and uses Systems Manager
to install the app and read secrets. It opens only 80/443; no SSH key is needed.
Python runs as an unprivileged user in a container with a read-only filesystem.
Container logs rotate. EC2 bootstrap and container builds may take several minutes.
The script verifies database readiness and throws on a failed deployment.

Point the backend DNS A record at the printed Elastic IP, then check:

```powershell
Invoke-RestMethod https://api.your-domain.com/api/ready
```

`/api/health` checks the API process; `/api/ready` additionally checks model URL
configuration and access to the Supabase table/bucket. It does not run an actual
model inference. Open the Vercel frontend and process a sample image to verify
Modal, translations, CORS and HTTPS end to end. Confirm a row in `ocr_runs`.
Corrections submitted through `/api/feedback/ocr` create an `ocr_feedback` row
and a private crop object. The account/history UI includes saved images and translations.

## Updates and operations

Rerun the same deploy script for backend changes. The Vercel Git integration
handles frontend deployments after the repository is pushed. Changing the
frontend API URL requires a rebuild. Reapply the SQL only for database setup
or deliberate migration changes. No cloud deployment happens just by editing files.

Use AWS Systems Manager Session Manager for diagnostics:

```sh
sudo cloud-init status --long
cd /opt/sarmitha/deploy
sudo docker compose logs --tail=100 api proxy
```

Supabase mode requires a verified login before processing. Tables use owner-scoped
row-level security and images remain private. Saved documents and images persist
until the owner deletes them; account deletion requires storage cleanup separately.

Removing the CloudFormation stack stops/deletes the EC2 resources and Elastic IP.
The artifact bucket is retained intentionally; manage it separately if cleaning
up. Supabase data and Caddy certificates are not a substitute for backups. The
single EC2 instance has no automatic failover.

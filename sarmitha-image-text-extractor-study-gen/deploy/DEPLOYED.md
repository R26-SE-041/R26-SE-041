# Sarmitha production deployment

Deployed on 2026-10-16 in AWS Singapore (`ap-southeast-1`).

- Frontend: https://sarmitha-ocr.vercel.app
- Vercel project: `sarmitha-ocr`
- API: https://sarmitha-18-136-176-78.sslip.io
- API documentation: https://sarmitha-18-136-176-78.sslip.io/docs
- Readiness: https://sarmitha-18-136-176-78.sslip.io/api/ready
- EC2: `i-0b6a5d44ce9e31731` (`t3.micro`, Ubuntu 24.04, encrypted 20 GB gp3 disk)
- Elastic IP: `18.136.176.78`
- CloudFormation stack: `sarmitha-ocr`
- VPC: `vpc-0b44287525402455d`
- Public subnet: `subnet-0c919124528fe4029`
- Deployment artifacts: `sarmitha-ocr-artifacts-5yucqoiajabb` (private, 14-day artifact expiry)
- Environment: SSM SecureString `/sarmitha/production/environment`
- Runtime: `/opt/sarmitha/deploy/compose.ec2.yaml`

Only ports 80 and 443 are exposed. Administration uses Systems Manager; no SSH
key was created. Caddy manages the Let's Encrypt certificate and renewals.
The existing Modal services handle enhancement, OCR, and translation.

## Storage and client configuration

The backend uses `STORAGE_BACKEND=supabase`. The Singapore project is
`sarmitha-ocr` (`atvjhttngoaukdacpmvq`), at
https://supabase.com/dashboard/project/atvjhttngoaukdacpmvq.
`001_ocr.sql`, `002_accounts_history.sql`, and `003_history_images.sql` have been applied.
Supabase Auth manages email/password accounts; `profiles` stores display names,
`auth_events` records account creation/sign-in/sign-out, and `ocr_runs` stores
each user's extracted text, translations, line metadata and filename.
Original and enhanced page images are now saved in the private `ocr-history`
bucket under owner/run-scoped paths. History detail signs those images for one
hour after verifying ownership; reloading a document renews its links. Line
crops remain excluded from OCR history. Older runs without saved images remain
text-only and can be reprocessed to save their images.
User-submitted correction crops use the private `ocr-feedback` storage bucket.

Every protected request verifies its bearer token with Supabase Auth. History
reads, inserts and deletes use that user's token and database row-level security.
The service secret remains on EC2 in the encrypted SSM environment parameter;
no Supabase secret is included in the frontend. The database password is backed
up in SecureString `/sarmitha/production/supabase-db-password`.

Email confirmation is disabled at the owner's explicit request on 2026-10-16.
Signup returns a session immediately, without requiring SMTP. An account's email
address is therefore unverified. Passwords must contain at least 8 characters.
Custom SMTP is not configured. If email verification is enabled later, configure
SMTP for public delivery; the frontend already handles confirmation redirects,
removes URL credentials immediately, and verifies the returned session.

The local `frontend-rn/.env` points `EXPO_PUBLIC_API_URL` at the deployed API.
CORS allows `https://sarmitha-ocr.vercel.app` and the local frontend origins
configured in `deploy/.env`. New frontend origins must be added explicitly to
the SSM environment before connecting a different hosted client.
Restart/rebuild the frontend after changing its API URL.

## Frontend deployment

The account/history frontend was published successfully on 2026-10-16:
`sarmitha-dmidun4iu-sarmisarmitha265-gmailcoms-projects.vercel.app`.
Production remains https://sarmitha-ocr.vercel.app. Signup/sign-in, sign-out,
account activity and private OCR history are available. History supports
reopening translations and deleting saved results. The backend requires login
before inference and saves each result to the verified user's account.

History image update published on 2026-10-16:
`sarmitha-3nh01a2oi-sarmisarmitha265-gmailcoms-projects.vercel.app`.
Opening a document shows original/enhanced images with enlargement, extracted
Sinhala, and Tamil/English translation tabs. Deletion removes stored images as
well as the row. Local verification passed 33 backend tests, 9 authentication
tests, TypeScript checking, Expo web export, and mobile/desktop browser checks
with synthetic API responses. Live synthetic verification confirmed private
storage, both signed image downloads, translation preservation, cross-account
read/delete isolation, image cleanup, and the production frontend bundle.
Temporary verification accounts and their data were removed. No new GPU
inference was run for this storage/UI change.

The frontend was redesigned and redeployed on 2026-10-16 using only Anthropic's
official website as the visual reference. See [design reference](DESIGN_REFERENCE.md)
for the measured palette, official web-font references, responsive layout, and
browser checks. The production alias remains https://sarmitha-ocr.vercel.app.
Redesign deployment: `sarmitha-9i9nwuprg-sarmisarmitha265-gmailcoms-projects.vercel.app`.

The verified Expo web export was published to Vercel production using the Build
Output API. `EXPO_PUBLIC_API_URL` is configured for Production and Preview, and
the published JavaScript points to the HTTPS EC2 endpoint. Public production
access returned HTTP 200. The backend accepted a CORS preflight from the exact
production frontend origin after its environment update.

The project has no Git integration configured. To update it from `frontend-rn`
with a local Vercel CLI login, run `vercel deploy --prod`; `vercel.json` configures
the Expo build, `dist` output, and SPA fallback. The build clears Metro's cache
so a previous API URL cannot remain in a cached bundle. Local project linking
metadata is stored in ignored `frontend-rn/.vercel/project.json`.

The deployment CLI ran on EC2 to avoid local network certificate interception.
Only the Sarmitha frontend source and static export were staged in the private
artifact bucket; no local environment files or AWS credentials were uploaded.
The CLI uses its private EC2 profile directory. Its account authorization is
retained for future deployments, so a fresh browser login is needed only when
the service expires or revokes that session. Credentials are never bundled into
source archives or static output.

## Update and inspect

With AWS CLI v2 installed, authenticate with `aws login --profile sarmitha-deploy`.
Then run from this component folder:

```powershell
./deploy/aws/deploy.ps1 -Region ap-southeast-1 -VpcId vpc-0b44287525402455d -SubnetId subnet-0c919124528fe4029 -Profile sarmitha-deploy -InstanceType t3.micro -ComposeFile compose.ec2.yaml
```

This session's CLI credentials are in ignored `.tmp/aws`, using `AWS_CONFIG_FILE`,
`AWS_SHARED_CREDENTIALS_FILE`, and `AWS_LOGIN_CACHE_DIRECTORY` overrides. A new
normal CLI login uses the standard AWS profile location instead; credentials must
never be committed.

Use Systems Manager Session Manager to connect to the instance:

```sh
cd /opt/sarmitha/deploy
sudo docker compose -f compose.ec2.yaml ps
sudo docker compose -f compose.ec2.yaml logs --tail=100 api proxy
curl --fail https://sarmitha-18-136-176-78.sslip.io/api/ready
```

EC2, disk, public IPv4, and model usage may incur charges. Removing the
CloudFormation stack deletes the instance/disk and releases the Elastic IP; the
artifact bucket is retained by the template. Back up feedback first.

## Verification

- 24 backend unit tests and 9 frontend account-session tests passed.
- EC2 system and instance status checks passed.
- API container is healthy; reverse proxy is running.
- Let's Encrypt issuance succeeded and HTTPS health/readiness/OpenAPI requests
  passed from EC2 without disabling certificate validation.
- The persistent feedback volume passed a write/remove probe as the app user.
- Vercel's public frontend and JavaScript assets returned HTTP 200, the served
  bundle contained the EC2 API URL, and SPA fallback routing passed.
- The redesign passed its production build, TypeScript check, and desktop/mobile
  Chrome checks, including real font loading, navigation, image selection, result
  rendering with a synthetic response, language switching, reset, and reduced motion.
- Production-origin CORS preflight passed; an unrelated origin was rejected.
- A synthetic Sinhala image passed the live HTTPS `/api/process` pipeline:
  enhanced image returned, one OCR line (11 characters), Tamil translation
  (8 characters), and English translation (31 characters). No private data was
  used for this model-inference check.
- An authenticated live inference was saved and reopened from Supabase. Two
  synthetic accounts verified private history at both the API and direct RLS:
  another user's list/detail/delete and forged-owner insert were denied.
  Signup/sign-in/sign-out events, token refresh and owner deletion passed.
  Synthetic accounts and their rows were removed after verification.
- Immediate public signup was tested through the deployed backend for two
  synthetic addresses. Both received a session without email confirmation and
  passed `/api/auth/me`; the full Modal/history/privacy test was repeated.
- The final account/history production HTML and JavaScript returned HTTP 200
  without Vercel authentication. The bundle contains the final session handling
  and EC2 API URL, and excludes Supabase service credentials. Account CORS and
  API/database readiness passed. Mobile/desktop Chrome checks covered signup,
  sign-in, authenticated processing, history translations, delete/cancel,
  account activity and clearing private results on logout using synthetic API
  responses. Temporary credential export files were removed after verification.

The local network presented a Fortinet-issued interception certificate and
returned a different IP for the hostname. Google public DNS returned the correct
Elastic IP. If this network blocks the API, use an unrestricted network or have
its administrator allow the hostname; do not disable HTTPS verification.

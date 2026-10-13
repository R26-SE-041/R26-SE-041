# EC2 deployment preparation

Status: deployment sources prepared. No EC2 instance has been launched, no remote
Docker build has been validated, and the public frontend still has no backend.

Use a dedicated Ubuntu 24.04 LTS **x86_64** instance for this component. A starting
configuration is t3.small (2 vCPU, 2 GiB RAM), 30 GiB encrypted gp3 root storage and 4 GiB swap. OpenClaw can use over 1 GiB RAM; monitor memory during concurrent requests.
This is a sizing estimate, not a measured guarantee. Instance, EBS, IPv4, transfer
and CPU surplus credits can incur charges; review actual AWS region pricing and
credit eligibility before launch. T3 Standard credit mode avoids surplus credit
charges but may throttle sustained CPU. No GPU is required: inference and BGE
retrieval use Modal. Avoid an 8 GiB disk for Docker builds and saved WAVs.

AWS access and an SSH key are required. Do not share private keys, AWS access keys,
Gemini keys or service-role keys in chat or commit them. Configure SSH ingress
only from the administrator's current IP, HTTP/HTTPS ports 80/443 publicly, and
**never** expose 8000, 8001 or 18789. Require IMDSv2. Preserve the data disk when
terminating/replacing an instance and maintain separate backups; EBS is not a
backup. Assign stable DNS to the backend before connecting Vercel.

## Server setup

1. Run `python deploy/ec2/package_release.py` locally. It produces a source-only
   archive under ignored `.workspace-runtime/` and excludes credentials/user data.
2. Transfer the archive by SSH/SCP, extract under `/srv/voicelearn/releases/<commit>`.
3. Run `sudo bash deploy/ec2/bootstrap.sh` on Ubuntu 24.04. It creates persistent
   directories and installs Docker from Ubuntu repositories without formatting disks.
4. Create `/etc/voicelearn/backend.env`, `openclaw.env`, and `compose.env` from the
   examples. Use owner root and mode 600. Populate real Supabase settings, verified
   Modal endpoint URLs, Gemini key, DNS domain.
5. Generate gateway/bridge secrets on the server using Python `secrets.token_urlsafe(48)`.
   Each must match between backend and gateway; keep their values private.
6. Provision Supabase `documents`/`sessions` tables and private document/audio buckets.
   Existing startup attempts are best-effort and **do not prove tables exist**.
   The frontend now supports real Supabase auth via EXPO_PUBLIC_SUPABASE_URL and
   EXPO_PUBLIC_SUPABASE_ANON_KEY. Configure the real project and verify login/JWTs
   before public use. Production uses Supabase directly, with the legacy backend
   auth proxy hidden by Caddy.
7. Run `sudo bash deploy/ec2/deploy.sh`. It checks configuration before building,
   validates OpenClaw config, starts services and waits for backend health.
8. Verify public `https://<domain>/health`, HTTPS certificate and CORS. Public MCP
   bridge paths and API docs return 404. Unauthenticated document/voice APIs return
   401. Probe the gateway/MCP internally and run an authenticated disposable document
   upload â†’ Q&A â†’ summary â†’ audio â†’ flashcards â†’ reopen workflow.
9. After those checks, set Vercel `EXPO_PUBLIC_API_URL` to this HTTPS origin and
   configure real Supabase browser auth. Redeploy; test from a separate browser.

All services use Linux host networking. Only Caddy binds public HTTP/HTTPS; FastAPI
and OpenClaw bind loopback. Chroma uses an embedded persistent client under
`/srv/voicelearn/data/chroma`. Documents/history/actions persist under the same data
root. OpenClaw state and TLS certificate state persist separately. One backend
worker is intentional for SQLite and in-process document/action state.

The existing laptop guest library is **not automatically copied** into a cloud
user's account. A separate user-approved ownership/data migration is needed.

## Updates and switching

Build a new release before replacing running services. Saved data is outside release
directories. Restarting the backend may interrupt active generation jobs; finish
requests before deploying. Retain a previous release for rollback and verify health
after every update. Backend automatic deployment and Linux Modal switching still
need implementation/live validation; the Windows switch command is not valid here.

Do not call this deployment complete until AWS resources, DNS, package downloads,
authentication, actual Docker builds, MCP, saved-file persistence after restart,
and the frontend-to-backend workflow have passed. Local tests cannot replace those
remote checks.

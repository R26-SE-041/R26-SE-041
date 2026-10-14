# EC2 deployment

Deployment verified on 2026-10-13: Linux Docker builds, HTTPS, Supabase login,
document upload and Q&A, OpenClaw flashcards and audio saving, WAV download,
user isolation, browser login/reopen, and persistence after automatic deployment.

Frontend: https://voicelearn-audio.vercel.app/study-assistant
Backend: https://voicelearn-15-134-177-14.sslip.io
The backend uses temporary sslip.io DNS; replace it with owned DNS when available.
Production signup uses confirmed email. Supabase's default email service has
recipient/rate restrictions; configure custom SMTP before general student signup.

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
after every update. GitHub Actions checks the production branch before the EC2
systemd timer deploys it. The timer checks every five minutes, retaining the old
release when checks fail and restoring it if deployment fails. This public-repo
pull mechanism requires no GitHub token or AWS IAM deployment credentials.

Install poll_release.py under /opt/voicelearn and the service/timer under
/etc/systemd/system. Enable voicelearn-deploy.timer after creating the current
release symlink. The active branch is baskaran/expo-web-migration.

For cloud Modal switching, use:
`sudo bash /srv/voicelearn/current/deploy/ec2/switch-modal.sh WORKSPACE`.
It verifies the selected workspace before changing protected backend settings,
retains the frontend URL and saved data, and restores settings if health fails.
bootstrap.sh installs the isolated Python environment used by this helper.

### Switch from your Windows laptop

From the component folder, run PowerShell:

```powershell
.\switch-modal-cloud.ps1 krishnavaranan1
.\switch-modal-cloud.ps1 -Status
```

The root-level helper uses your existing local OpenSSH key to run the verified
EC2 switch script over SSH. It does not change the laptop backend configuration
or upload credentials. Supported workspaces: visakanbaskaran, krishnavaranan1,
krishnavaranan, varananrp. Use `-Preview` to inspect the target without connecting.
The default EC2 address is 15.134.177.14 and the default key is
`$env:USERPROFILE\.ssh\voicelearn-ec2-20261013`; override with `-HostName` and
`-IdentityFile` on another laptop. OpenSSH, an authorized private key and a
previously verified EC2 host key are required. Never bypass SSH host-key checks.
If script execution is blocked, run the trusted checked-out script with:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\switch-modal-cloud.ps1 krishnavaranan1
```

Git push is not required to select a workspace. Wait for the success message;
switching restarts the backend, so finish active generation requests first. Live
workspace verification runs model probes and may consume some Modal credits.
Use `-Status` to check configuration without running inference. This helper does
not select a workspace automatically when credits run out.
Use configured names visakanbaskaran, krishnavaranan1, krishnavaranan, or varananrp.

With CLOUD_USER_STORAGE=true, documents, Q&A history and revision/flashcard
metadata persist in Supabase PostgreSQL. Original files use the private documents
bucket; transcripts, manifests, decks and WAVs use revisions; question/answer
recordings use study-history. Authenticated backend APIs check ownership before
serving any private file. Temporary generation/playback caches and vector indexes
remain on EC2, but deleting those caches does not delete the cloud saved library.

Apply supabase.sql before enabling cloud storage. migrate_cloud_storage.py copies
and verifies existing owned SQLite records without deleting originals. A legacy
guest library requires an explicitly approved --guest-owner auth UUID. Windows
snapshots can use --source-root containing actions/, history/ and documents/;
immutable SQLite reads support read-only snapshot mounts. Keep migration archives
private and remove temporary copies after verification. Supabase persistence is
not a substitute for independent backups of irreplaceable data.

Do not call this deployment complete until AWS resources, DNS, package downloads,
authentication, actual Docker builds, MCP, saved-file persistence after restart,
and the frontend-to-backend workflow have passed. Local tests cannot replace those
remote checks.

Latency changes and measured limits are recorded in [LATENCY_OPTIMIZATION.md](../../LATENCY_OPTIMIZATION.md).
Deploy Modal source changes separately; the EC2 workflow only deploys the backend
and OpenClaw configuration. Keep GPU minimum containers at zero when conserving credits.

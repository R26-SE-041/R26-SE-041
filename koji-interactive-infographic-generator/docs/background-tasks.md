# Background tasks and session recovery

With Studio configured and a signed-in account, accepted requests are stored in
PostgreSQL before the API acknowledges them. The systemd worker processes them
independently of the browser. Closing a tab, navigating away, going offline, or
an expired browser access token does not cancel an accepted task. Activity and
History retrieve saved state when the user returns.

The worker defaults to three concurrent slots (`STUDIO_WORKER_CONCURRENCY`,
1–8). Each task keeps its own renewable database lease and fenced updates. A 3D
call waiting on Modal no longer prevents unrelated drawings and labels from
starting. Restart recovery reuses a saved Modal call ID; it does not launch a
replacement conversion. Synchronous calls interrupted before a response was
saved fail explicitly because their completion cannot be inferred safely.
CPU PDF embedding remains serialized to bound memory on the existing host.

Activity prioritizes active tasks over recent completed tasks. Queued tasks
are described as waiting for a worker. A 3D call with no inference progress is
described as waiting for the 3D service. A worker-owned task is not proof that a
GPU container is currently executing; Modal can still be pending. Existing
per-user task limits and the 70-minute 3D retrieval deadline remain enforced.

Before authenticated requests, the frontend asks Supabase for the current
session. A 401 triggers one shared refresh and a single retry with the original
request body and request ID. Account changes abort pending requests. Revoked
sessions still require sign-in. Transient polling failures retry the original
job without submitting another generation. Activity refreshes on return to the
tab, network reconnection, and manual refresh.

Verification covers concurrent task progress with a blocked 3D call, lease
recovery, active jobs surviving the recent-activity limit, session refresh and
account isolation, and reconnecting polls without duplicate submission. Paid
inference is not run by unit tests. Production checks should verify accepted
jobs advancing server-side and saved results reopening from Activity/History.

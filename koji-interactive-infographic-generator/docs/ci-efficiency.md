# CI efficiency

The Koji workflow keeps build/test jobs separate from production deployment:

- Frontend changes run frontend checks; CPU/backend/model changes run backend checks.
- Test-only changes run the corresponding checks without building/uploading a release.
- Documentation-only changes skip both component check jobs. Runtime agent instruction
  files still count as model changes and receive backend checks.
- Backend checks install `studio/requirements-test.txt`, not runtime embedding/model
  packages. Torch, Transformers and sentence-transformers are not installed in CI.
  Production and full local development still use the runtime requirements.
- `setup-python` caches pip downloads against the core/test dependency files.
  Frontend npm caching remains enabled. Cache misses still download the smaller
  test dependency set; caches do not remove the package installation step.
- New runs cancel outdated checks for the same Git ref. Production deployment jobs
  retain their separate concurrency locks and finish without interruption.
- Skipped, unneeded checks do not block single-component deployments. Failed or
  cancelled required checks still block deployment.

The lightweight `frontend` gate retains the existing status name required by the
installed EC2 release receiver and branch protection. The actual Node build/test
job is `frontend_checks`; it is skipped when unnecessary. The gate succeeds only
after required frontend checks pass, or when frontend checks are not required.
This avoids requiring an out-of-band receiver upgrade for backend-only releases.

On `main`, change detection compares against the latest successful push run of this
workflow, using the job's read-only GitHub Actions token. This carries forward changes
from failed, cancelled or still-running pushes. Without a usable ancestor baseline,
both components run. Pull requests compare their base/head; manual releases and tags
retain their explicit target/full-release behavior. No extra repository secret is needed.

Run the same lightweight tests locally without downloading model libraries:

```powershell
# From the component directory, after creating/activating an isolated environment:
python -m pip install -r backend/studio/requirements-test.txt
python ci/check.py
python -m unittest discover -s ci/tests -p 'test_*.py'
```

PostgreSQL integration tests require an isolated `STUDIO_TEST_DATABASE_URL`; GitHub
Actions still starts its pgvector PostgreSQL service and runs those tests.

References: [setup-python caching](https://github.com/actions/setup-python/blob/main/docs/advanced-usage.md#caching-packages),
[job concurrency](https://docs.github.com/en/actions/how-tos/write-workflows/choose-when-workflows-run/control-workflow-concurrency),
[workflow-run API](https://docs.github.com/en/rest/actions/workflow-runs#list-workflow-runs-for-a-workflow).

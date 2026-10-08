# Contributing to the Koji interactive component

Follow the shared [contribution guidelines](../CONTRIBUTING.md),
[code of conduct](../CODE_OF_CONDUCT.md) and [security policy](../SECURITY.md).
This guide contains the setup and checks specific to this component.

## Setup and scope

Read the [component README](README.md) for its image pipelines, environment
configuration, existing Supabase project setup and deployment workflow.

Keep Koji changes inside `koji-interactive-infographic-generator/` unless a shared
change has been agreed with the relevant maintainers. Its GitHub Actions workflow
is `.github/workflows/koji-interactive.yml` at the repository root.

## Frontend checks

From `koji-interactive-infographic-generator/frontend/`:

```sh
npm ci
npm run typecheck
npm run test:unit
npm run build:web
```

For UI changes, check the affected prompt, anatomy or drawing workflow and history
restoration. Label-editing changes should preserve names, arrow targets and label
positions in both saved history and SVG export.

## Backend checks

From `koji-interactive-infographic-generator/backend/`:

```sh
python -m pip install -r studio/requirements-dev.txt
python ../ci/check.py
```

Repository integration tests require `STUDIO_TEST_DATABASE_URL` pointing to an
isolated disposable PostgreSQL database. These tests create fixtures and test
users; never use the production Supabase project. If this variable is absent,
database integration tests are skipped. State that limitation in the pull request.

Ordinary checks do not call GPU models. Use mock model endpoints for routine UI
tests. Coordinate live Modal generation tests before spending GPU credits.

## Configuration and deployment changes

- Keep actual credentials in local environment files or hosted secret stores.
  Update `.env.example` files with names and placeholders when configuration changes.
- Document database migrations and test them against a disposable database.
- Explain whether API, worker, frontend or Modal agents require redeployment.
- Record whether live migration or deployment steps have actually been performed.
- Review relevant model, dataset and dependency terms before adding assets.

# History and Recycle Bin

Deleting a creation moves its complete conversation into the Recycle Bin. Images,
3D model versions, drawings, questions and answers remain stored. Restore returns
the same creation to history without changing its original timestamps. There is
no automatic expiry. Permanent deletion is a separate, confirmed action available
inside the Bin; it removes the conversation, generations and associated assets.
Creations with queued/running jobs cannot be trashed or permanently deleted.

Cloud history stores the deletion marker on `koji_chats.deleted_at`. Normal chat
and generation lists exclude marked conversations. `GET /studio/chats?trashed=true`
lists the owner's Bin with the existing search and pagination contract.

- `DELETE /studio/chats/{id}` moves to the Bin without removing storage assets.
- `POST /studio/chats/{id}/restore` restores the creation.
- `DELETE /studio/chats/{id}/permanent` requires it to be in the Bin first.
- The legacy `DELETE /studio/history/{generation_id}` also moves the complete
  owning conversation to the Bin, so it cannot bypass recovery.

Local history stores `deletedAt` on each version in an atomic IndexedDB
transaction. Trashed entries are excluded from synchronization and cache eviction.
Restoring or purging operates on all versions of the selected conversation and
keeps other accounts/conversations separate. Local-only data stays in that browser.

Archive cards calculate one responsive column width for the whole archive,
including partially filled date groups. Preview aspect ratio and title/date slots
are consistent, so a single older item no longer expands to fill the row.

## Rollout

Apply migration `006_recycle_bin.sql` **before** deploying the updated backend:

```powershell
# From backend/, using the intended database configuration:
..\.venv\Scripts\python.exe -m studio.migrate
```

Then deploy the backend and rebuild/deploy the frontend. No existing assets are
deleted by the migration. Previously permanently deleted assets are not recoverable.
Backend `/ready` checks the Recycle Bin column before activation, so an unapplied
migration rejects the staged release before it replaces the running backend.
After rollout, verify authenticated History and Recycle Bin through the hosted
frontend; public `/health` alone does not exercise database-backed history.
Database integration tests require `STUDIO_TEST_DATABASE_URL` pointing at an
isolated test database; never run them against the production database.

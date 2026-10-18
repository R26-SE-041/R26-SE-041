"""Private quiz history with reversible deletion."""
from fastapi import APIRouter, Request, Query
from app.services.db_service import DbService

router = APIRouter()


@router.get("")
def list_history(request: Request, deleted: bool = False, limit: int = Query(100, ge=1, le=500)):
    db = DbService()
    try:
        return db.get_history(request.state.user["id"], deleted=deleted, limit=limit)
    finally:
        if not db.is_postgres:
            db.conn.close()


def _move(request, session_id, deleted):
    db = DbService()
    try:
        db.move_history(session_id, request.state.user["id"], deleted)
        return {"status": "trashed" if deleted else "restored"}
    finally:
        if not db.is_postgres:
            db.conn.close()


@router.post("/{session_id}/trash")
def trash(session_id: str, request: Request):
    return _move(request, session_id, True)


@router.post("/{session_id}/restore")
def restore(session_id: str, request: Request):
    return _move(request, session_id, False)

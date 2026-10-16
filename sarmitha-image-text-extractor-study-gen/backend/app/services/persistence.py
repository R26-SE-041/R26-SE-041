"""Server-side persistence. Supabase credentials never reach the browser."""

import base64
import binascii
import json
import logging
from pathlib import Path
from uuid import uuid4

import httpx

from app.core.config import settings
from app.core.http import SSL_CONTEXT
from app.core.auth import AuthUser, user_client

logger = logging.getLogger(__name__)
DATASET_DIR = Path(__file__).resolve().parents[2] / "dataset"


class PersistenceError(Exception):
    pass


def supabase_client() -> httpx.AsyncClient:
    key = settings.supabase_service_role_key.get_secret_value()
    if not settings.supabase_url.startswith("https://") or not key:
        raise PersistenceError("Supabase is not configured.")
    headers = {"apikey": key}
    if not key.startswith("sb_secret_"):
        headers["Authorization"] = f"Bearer {key}"
    return httpx.AsyncClient(
        base_url=settings.supabase_url.rstrip("/"),
        headers=headers,
        timeout=30.0, verify=SSL_CONTEXT,
    )


async def check_database() -> None:
    async with supabase_client() as client:
        response = await client.get("/rest/v1/ocr_runs", params={"select": "id,user_id,filename", "limit": "0"})
        response.raise_for_status()
        response = await client.get("/rest/v1/auth_events", params={"select": "id", "limit": "0"})
        response.raise_for_status()
        response = await client.get(f"/storage/v1/bucket/{settings.supabase_feedback_bucket}")
        response.raise_for_status()
        response = await client.get(f"/storage/v1/bucket/{settings.supabase_history_bucket}")
        response.raise_for_status()


def history_image_paths(user_id: str, run_id: str) -> dict[str, str]:
    return {kind: f"{user_id}/{run_id}/{kind}" for kind in ("original", "enhanced")}


def decode_history_image(value: str) -> tuple[bytes, str]:
    data = base64.b64decode(value, validate=True)
    if not data or len(data) > 50 * 1024 * 1024:
        raise ValueError("Invalid image size")
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return data, "image/png"
    if data.startswith(b"\xff\xd8\xff"):
        return data, "image/jpeg"
    if data.startswith(b"RIFF") and data[8:12] == b"WEBP":
        return data, "image/webp"
    if data.startswith(b"BM"):
        return data, "image/bmp"
    raise ValueError("Unsupported image format")


async def remove_run_images(user_id: str, run_id: str) -> None:
    """Use generated owner-scoped paths, never paths supplied by a browser or row."""
    async with supabase_client() as client:
        response = await client.request("DELETE", f"/storage/v1/object/{settings.supabase_history_bucket}",
                                        json={"prefixes": list(history_image_paths(user_id, run_id).values())})
        response.raise_for_status()


async def history_image_urls(row: dict, user: AuthUser) -> dict:
    urls = {}
    paths = history_image_paths(user.id, str(row["id"]))
    # Legacy text-only entries do not have image paths.
    if not any(row.get(f"{kind}_image_path") for kind in paths):
        return urls
    async with supabase_client() as client:
        for kind, path in paths.items():
            if row.get(f"{kind}_image_path") != path:
                continue
            response = await client.post(f"/storage/v1/object/sign/{settings.supabase_history_bucket}/{path}",
                                         json={"expiresIn": 3600})
            response.raise_for_status()
            signed = response.json()["signedURL"]
            urls[f"{kind}_image_url"] = settings.supabase_url.rstrip("/") + "/storage/v1" + signed
    return urls


async def save_run(result: dict, user: AuthUser | None = None, filename: str = "Untitled image") -> str | None:
    if settings.storage_backend != "supabase":
        return None
    if user is None:
        raise PersistenceError("Please sign in to save your document.")
    run_id = str(uuid4())
    paths = history_image_paths(user.id, run_id)
    row = {
        "id": run_id,
        "user_id": user.id,
        "filename": filename.replace("\\", "/").split("/")[-1][:255],
        "extracted_text": result["extracted_text"],
        "extracted_text_ta": result.get("extracted_text_ta", ""),
        "extracted_text_en": result.get("extracted_text_en", ""),
        "lines": [{k: v for k, v in line.items() if k != "crop_b64"}
                  for line in result.get("lines", [])],
    }
    uploaded = []
    try:
        images = {kind: decode_history_image(result[f"{kind}_b64"]) for kind in paths}
        async with supabase_client() as storage:
            for kind, (data, content_type) in images.items():
                # Include attempted uploads in cleanup if a network timeout occurs after storage accepted it.
                uploaded.append(paths[kind])
                response = await storage.post(f"/storage/v1/object/{settings.supabase_history_bucket}/{paths[kind]}",
                                              content=data, headers={"Content-Type": content_type, "x-upsert": "false"})
                response.raise_for_status()
                row[f"{kind}_image_path"] = paths[kind]
        async with user_client(user.access_token) as client:
            response = await client.post("/rest/v1/ocr_runs", json=row)
            response.raise_for_status()
    except (httpx.HTTPError, PersistenceError, ValueError, KeyError, binascii.Error) as exc:
        if uploaded:
            try:
                await remove_run_images(user.id, run_id)
            except (httpx.HTTPError, PersistenceError):
                logger.error("History image cleanup failed for %s", run_id)
        logger.error("OCR persistence failed (%s)", type(exc).__name__)
        raise PersistenceError("Could not save OCR results. Please try again.") from exc
    return run_id


async def save_feedback(image: bytes, text: str, user: AuthUser | None = None) -> str:
    feedback_id = str(uuid4())
    object_path = f"corrections/{feedback_id}.jpg"
    if settings.storage_backend == "local":
        images = DATASET_DIR / "images"
        images.mkdir(parents=True, exist_ok=True)
        filename = f"{feedback_id}.jpg"
        (images / filename).write_bytes(image)
        with (DATASET_DIR / "metadata.jsonl").open("a", encoding="utf-8") as metadata:
            metadata.write(json.dumps({"file_name": f"images/{filename}", "text": text}, ensure_ascii=False) + "\n")
        return feedback_id

    if user is None:
        raise PersistenceError("Please sign in to save feedback.")
    object_path = f"corrections/{user.id}/{feedback_id}.jpg"

    try:
        async with supabase_client() as client:
            bucket = settings.supabase_feedback_bucket
            response = await client.post(
                f"/storage/v1/object/{bucket}/{object_path}",
                content=image, headers={"Content-Type": "image/jpeg", "x-upsert": "false"},
            )
            response.raise_for_status()
            try:
                response = await client.post("/rest/v1/ocr_feedback", json={
                    "id": feedback_id, "user_id": user.id, "object_path": object_path, "corrected_text": text,
                })
                response.raise_for_status()
            except httpx.HTTPError:
                try:
                    cleanup = await client.request("DELETE", f"/storage/v1/object/{bucket}", json={"prefixes": [object_path]})
                    cleanup.raise_for_status()
                except httpx.HTTPError:
                    logger.error("Feedback image cleanup failed for %s", feedback_id)
                raise
    except (httpx.HTTPError, PersistenceError) as exc:
        logger.error("Feedback persistence failed (%s)", type(exc).__name__)
        raise PersistenceError("Could not save feedback. Please try again.") from exc
    return feedback_id


async def record_auth_event(user_id: str, event_type: str) -> None:
    if event_type not in {"sign_in", "sign_out"}:
        raise PersistenceError("Invalid account event.")
    try:
        async with supabase_client() as client:
            response = await client.post("/rest/v1/auth_events", json={"user_id": user_id, "event_type": event_type})
            response.raise_for_status()
    except httpx.HTTPError as exc:
        logger.error("Account event persistence failed (%s)", type(exc).__name__)
        raise PersistenceError("Could not record account activity.") from exc

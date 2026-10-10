"""Private Supabase objects; only stable paths are stored in Postgres."""
from __future__ import annotations
import base64
import os
from urllib.parse import quote
import requests

class Storage:
    def __init__(self):
        self.base = os.environ["SUPABASE_URL"].rstrip("/") + "/storage/v1"
        key = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
        self.headers = {"apikey": key, "Authorization": f"Bearer {key}"}
        self.bucket = os.getenv("STUDIO_STORAGE_BUCKET", "koji-generations")

    def object_url(self, path: str, authenticated: bool = False):
        prefix = "/object/authenticated/" if authenticated else "/object/"
        return self.base + prefix + quote(self.bucket, safe="") + "/" + quote(path, safe="/")

    def upload(self, path: str, encoded: str, content_type: str):
        data = base64.b64decode(encoded, validate=True)
        limit = min(100, int(os.getenv("STUDIO_MAX_ASSET_MB", "50")))
        if not data or len(data) > limit * 1024 * 1024:
            raise ValueError(f"Asset is empty or exceeds the configured {limit} MiB upload limit")
        # Deterministic job paths make upload retries idempotent.
        for attempt in range(3):
            try:
                response = requests.post(self.object_url(path), data=data,
                    headers={**self.headers, "Content-Type": content_type, "x-upsert": "true"}, timeout=(10, 180))
                response.raise_for_status()
                return path
            except requests.RequestException:
                if attempt == 2:
                    raise RuntimeError("Asset upload failed. Please retry the generation.") from None

    def download(self, path: str):
        response = requests.get(self.object_url(path, True), headers=self.headers, timeout=(10, 180))
        response.raise_for_status()
        return base64.b64encode(response.content).decode("ascii")

    def upload_thumbnail(self, path: str, encoded: str):
        from io import BytesIO
        from PIL import Image
        with Image.open(BytesIO(base64.b64decode(encoded, validate=True))) as source:
            thumbnail = source.convert("RGB")
            thumbnail.thumbnail((320, 320))
            output = BytesIO()
            thumbnail.save(output, format="PNG", optimize=True)
        return self.upload(path, base64.b64encode(output.getvalue()).decode("ascii"), "image/png")

    def signed_url(self, path: str):
        response = requests.post(self.base + "/object/sign/" + quote(self.bucket, safe="") + "/" + quote(path, safe="/"),
            headers=self.headers, json={"expiresIn": 3600}, timeout=20)
        response.raise_for_status()
        url = response.json()["signedURL"]
        return url if url.startswith("https://") else os.environ["SUPABASE_URL"].rstrip("/") + "/storage/v1" + url

    def remove(self, paths: list[str]):
        if not paths:
            return
        for offset in range(0, len(paths), 100):
            response = requests.delete(self.base + "/object/" + quote(self.bucket, safe=""),
                headers=self.headers, json={"prefixes": paths[offset:offset + 100]}, timeout=30)
            response.raise_for_status()

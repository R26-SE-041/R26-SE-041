"""Validate deployment settings before accepting traffic."""
import os
from urllib.parse import urlsplit


def production():
    return os.getenv("APP_ENV", "development").lower() == "production"


def allowed_origins():
    configured = os.getenv("ALLOWED_ORIGINS", os.getenv("FRONTEND_URL", ""))
    origins = list(dict.fromkeys(value.strip().rstrip("/") for value in configured.split(",") if value.strip()))
    if not production():
        return origins or [f"http://{host}:{port}" for host in ("localhost", "127.0.0.1") for port in range(3000, 3004)]
    if not origins:
        raise RuntimeError("ALLOWED_ORIGINS must contain the Vercel frontend HTTPS origin.")
    for origin in origins:
        parsed = urlsplit(origin)
        if (parsed.scheme != "https" or not parsed.hostname or "*" in parsed.netloc
                or parsed.path or parsed.query or parsed.fragment or parsed.username is not None):
            raise RuntimeError("Production ALLOWED_ORIGINS must contain exact HTTPS origins.")
    if not os.getenv("DATABASE_URL", "").strip():
        raise RuntimeError("DATABASE_URL is required in production; SQLite is development-only.")
    return origins

"""Package Expo output, including the configured same-origin Studio API route."""
import json
import os
from pathlib import Path
import re
import shutil
from urllib.parse import urlsplit
ROOT=Path(__file__).resolve().parents[1]
frontend=ROOT/"frontend"

def setting(name):
    if name in os.environ:
        return os.environ[name].strip()
    env_file=frontend/".env.local"
    if env_file.exists():
        for line in env_file.read_text(encoding="utf-8").splitlines():
            if line.startswith(name+"="):
                return line.split("=",1)[1].strip().strip("\"'")
    return ""

def api_routes():
    prefix=setting("EXPO_PUBLIC_STUDIO_PROXY_PATH").rstrip("/")
    origin=setting("EXPO_PUBLIC_STUDIO_API_URL").rstrip("/")
    if not prefix or not origin:
        return []
    if not re.fullmatch(r"/[A-Za-z0-9_-]+(?:/[A-Za-z0-9_-]+)*",prefix):
        raise ValueError("Studio proxy path must be a dedicated URL path")
    parsed=urlsplit(origin)
    if parsed.scheme!="https" or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ValueError("Studio origin must be an HTTPS URL without credentials or query parameters")
    return [{"src":re.escape(prefix)+"/(.*)","dest":origin+"/$1","headers":{"Cache-Control":"private, no-store"}}]

if __name__=="__main__":
    routes=api_routes()+[{"handle":"filesystem"},{"src":"/.*","dest":"/index.html"}]
    output=frontend/".vercel/output"
    output.mkdir(parents=True,exist_ok=True)
    shutil.copytree(frontend/"dist",output/"static",dirs_exist_ok=True)
    (output/"config.json").write_text(json.dumps({"version":3,"routes":routes}),encoding="utf-8")

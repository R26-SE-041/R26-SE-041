"""Server-only Supabase persistence. Object paths always include the owner UUID."""
import uuid
from functools import lru_cache
from urllib.parse import quote

import httpx

from app.core.config import get_settings


def enabled():
    return get_settings().cloud_user_storage


@lru_cache(maxsize=1)
def _client():
    # Share the connection pool across API threads instead of paying a TLS
    # handshake for each action status update or migrated artifact.
    return httpx.Client(timeout=60, limits=httpx.Limits(max_connections=20, max_keepalive_connections=10))


def request(method, path, *, params=None, json=None, content=None, headers=None):
    settings = get_settings()
    auth = {"apikey": settings.supabase_service_role_key,
            "Authorization": "Bearer " + settings.supabase_service_role_key,
            "Prefer": "return=representation"}
    auth.update(headers or {})
    response = _client().request(method, settings.supabase_url.rstrip('/') + path,
                                 params=params, json=json, content=content, headers=auth)
    response.raise_for_status()
    if not response.content:
        return None
    return response.json()


def owner_path(user_id, filename):
    owner = str(uuid.UUID(user_id))
    if '/' in filename or '\\' in filename or filename.startswith('.'):
        raise ValueError('Invalid storage filename')
    return owner + '/' + filename


def upload(bucket, path, data, mime):
    return request('POST', '/storage/v1/object/' + bucket + '/' + quote(path, safe='/'),
                   content=data, headers={'Content-Type': mime, 'x-upsert': 'true'})


def download(bucket, path):
    settings = get_settings()
    response = _client().get(settings.supabase_url.rstrip('/') + '/storage/v1/object/' + bucket + '/' + quote(path, safe='/'),
                             headers={'apikey': settings.supabase_service_role_key,
                                      'Authorization': 'Bearer ' + settings.supabase_service_role_key})
    response.raise_for_status()
    return response.content


def remove(bucket, paths):
    if paths:
        request('DELETE', '/storage/v1/object/' + bucket, json={'prefixes': paths})

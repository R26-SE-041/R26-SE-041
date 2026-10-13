from types import SimpleNamespace
import time
import jwt
import pytest
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials
from app.core import security


@pytest.fixture
def production(monkeypatch):
    config = SimpleNamespace(require_auth=True, supabase_url='https://example.supabase.co',
                             supabase_jwt_secret='test-only-secret-at-least-32-characters')
    monkeypatch.setattr(security, 'get_settings', lambda: config)
    return config


def claims():
    return {'sub':'abc', 'exp':time.time()+60, 'iss':'https://example.supabase.co/auth/v1', 'aud':'authenticated'}


def test_public_deployment_rejects_guest(production):
    with pytest.raises(HTTPException) as caught:
        security.get_current_user(None)
    assert caught.value.status_code == 401


def test_local_demo_keeps_optional_auth(production):
    production.require_auth = False
    assert security.get_current_user(None) is None


def test_valid_signed_supabase_token(production):
    token = jwt.encode(claims(), production.supabase_jwt_secret, algorithm='HS256')
    assert security.get_current_user(HTTPAuthorizationCredentials(scheme='Bearer', credentials=token))['sub'] == 'abc'


@pytest.mark.parametrize('override', [{'iss':'https://wrong.supabase.co/auth/v1'}, {'exp':1}, {'aud':'wrong'}])
def test_wrong_issuer_expiry_and_audience_are_rejected(production, override):
    token = jwt.encode({**claims(), **override}, production.supabase_jwt_secret, algorithm='HS256')
    with pytest.raises(HTTPException) as caught:
        security.verify_token(token)
    assert caught.value.status_code == 401


def test_unsigned_tokens_are_rejected(production):
    token = jwt.encode(claims(), '', algorithm='none')
    with pytest.raises(HTTPException) as caught:
        security.verify_token(token)
    assert caught.value.status_code == 401


@pytest.mark.parametrize('algorithm', ['RS256', 'ES256'])
def test_asymmetric_signing_uses_verified_jwks_key(production, monkeypatch, algorithm):
    from cryptography.hazmat.primitives.asymmetric import rsa, ec
    key = (rsa.generate_private_key(public_exponent=65537, key_size=2048)
           if algorithm == 'RS256' else ec.generate_private_key(ec.SECP256R1()))
    token = jwt.encode(claims(), key, algorithm=algorithm, headers={'kid':'test-key'})
    monkeypatch.setattr(security, '_jwks', lambda url: SimpleNamespace(get_signing_key_from_jwt=lambda value: SimpleNamespace(key=key.public_key())))
    assert security.verify_token(token)['sub'] == 'abc'

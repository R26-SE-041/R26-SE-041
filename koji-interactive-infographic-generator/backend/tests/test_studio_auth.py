import os
from unittest.mock import Mock, patch
import requests
from fastapi.testclient import TestClient
from studio.main import app

OWNER='a3062c4e-d5df-4015-a803-b7b2017b9b87'
ENV={'SUPABASE_URL':'https://auth.example','SUPABASE_ANON_KEY':'public-key'}

def test_missing_and_empty_tokens_do_not_call_auth_or_database():
    with patch('studio.main.requests.get') as auth, patch('studio.main.repo') as repo:
        for headers in ({},{'Authorization':'Bearer '},{'Authorization':'Basic abc'}):
            assert TestClient(app).get('/studio/history',headers=headers).status_code==401
        auth.assert_not_called();repo.list_history.assert_not_called()

def test_verified_supabase_identity_owns_history_and_account_returns_minimal_profile():
    response=Mock(status_code=200)
    response.json.return_value={'id':OWNER,'email':'test@example.com','user_metadata':{'full_name':'Koji'},'email_confirmed_at':'2026-01-01','identities':['private']}
    with patch.dict(os.environ,ENV), patch('studio.main.requests.get',return_value=response) as auth, patch('studio.main.repo') as repo:
        repo.list_history.return_value=[]
        client=TestClient(app)
        headers={'Authorization':'Bearer opaque-valid-token'}
        assert client.get('/studio/history',headers=headers).status_code==200
        repo.list_history.assert_called_once_with(OWNER,None)
        profile=client.get('/studio/account',headers=headers).json()
        assert profile=={'id':OWNER,'email':'test@example.com','name':'Koji','emailVerified':True}
        assert auth.call_args.kwargs['headers']['Authorization']==headers['Authorization']

def test_revoked_tokens_cannot_read_history():
    with patch.dict(os.environ,ENV),patch('studio.main.requests.get',return_value=Mock(status_code=401)),patch('studio.main.repo') as repo:
        result=TestClient(app).get('/studio/history',headers={'Authorization':'Bearer revoked'})
        assert result.status_code==401
        repo.list_history.assert_not_called()

def test_auth_outage_does_not_leak_credentials_or_upstream_error():
    with patch.dict(os.environ,ENV),patch('studio.main.requests.get',side_effect=requests.ConnectionError('private upstream credential')):
        result=TestClient(app).get('/studio/account',headers={'Authorization':'Bearer token'})
        assert result.status_code==503
        assert 'private' not in result.text

def test_invalid_auth_identity_cannot_reach_history():
    response=Mock(status_code=200);response.json.return_value={'id':'malformed'}
    with patch.dict(os.environ,ENV),patch('studio.main.requests.get',return_value=response),patch('studio.main.repo') as repo:
        assert TestClient(app).get('/studio/history',headers={'Authorization':'Bearer token'}).status_code==503
        repo.list_history.assert_not_called()

def test_authenticated_api_responses_are_not_cached():
    result=TestClient(app).get("/studio/account")
    assert result.status_code==401
    assert result.headers["cache-control"]=="private, no-store"

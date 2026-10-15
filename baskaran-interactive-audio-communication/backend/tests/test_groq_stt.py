from types import SimpleNamespace
from unittest.mock import AsyncMock
import httpx
import pytest
from fastapi import HTTPException
from pydantic import SecretStr
from app.services import groq_stt
from app.agents import stt_agent

@pytest.fixture
def setup(tmp_path,monkeypatch):
    settings=SimpleNamespace(stt_provider='groq',groq_api_key=SecretStr('test-not-a-real-key'),groq_stt_model='whisper-large-v3-turbo',groq_stt_requests_per_minute=10,groq_stt_requests_per_day=100,groq_stt_quota_path=str(tmp_path/'quota.sqlite3'),actions_store_path=str(tmp_path/'actions'))
    monkeypatch.setattr(groq_stt,'get_settings',lambda:settings)
    monkeypatch.setattr(stt_agent,'get_settings',lambda:settings)
    monkeypatch.setattr(groq_stt,'audio_duration',AsyncMock(return_value=4.2))
    return settings

@pytest.mark.asyncio
@pytest.mark.parametrize('language,code',[('english','en'),('tamil','ta'),('sinhala','si')])
async def test_groq_language_mapping_and_no_modal_fallback(setup,monkeypatch,language,code):
    post=AsyncMock(return_value=httpx.Response(200,json={'text':'Spoken words','language':language}))
    monkeypatch.setattr(groq_stt._http,'post',post)
    modal=AsyncMock()
    monkeypatch.setattr(stt_agent,'call_whisper',modal)
    result=await stt_agent.stt_node({'audio_bytes':b'fake','audio_filename':'clip.webm','language':language})
    assert result['transcript']=='Spoken words' and result['detected_language']==code and result['duration_ms']==4200
    assert post.call_args.kwargs['data']['language']==code
    assert post.await_count==1
    modal.assert_not_awaited()

@pytest.mark.asyncio
async def test_missing_key_never_sends_audio(setup,monkeypatch):
    setup.groq_api_key=SecretStr('')
    post=AsyncMock();monkeypatch.setattr(groq_stt._http,'post',post)
    with pytest.raises(HTTPException) as caught:await groq_stt.transcribe(b'a','clip.webm','english')
    assert caught.value.status_code==503
    post.assert_not_awaited()

@pytest.mark.asyncio
@pytest.mark.parametrize('status,expected',[(429,429),(401,503),(500,503)])
async def test_provider_failure_has_no_retry_or_fallback(setup,monkeypatch,status,expected):
    post=AsyncMock(return_value=httpx.Response(status,json={'error':'private-provider-detail'}))
    monkeypatch.setattr(groq_stt._http,'post',post)
    with pytest.raises(HTTPException) as caught:await groq_stt.transcribe(b'a','clip.webm','english')
    assert caught.value.status_code==expected
    assert 'private-provider-detail' not in caught.value.detail
    assert post.await_count==1

@pytest.mark.asyncio
async def test_persistent_local_quota_blocks_before_http(setup,monkeypatch):
    setup.groq_stt_requests_per_minute=1
    post=AsyncMock(return_value=httpx.Response(200,json={'text':'hello'}));monkeypatch.setattr(groq_stt._http,'post',post)
    await groq_stt.transcribe(b'a','clip.webm','english')
    with pytest.raises(HTTPException) as caught:await groq_stt.transcribe(b'a','clip.webm','english')
    assert caught.value.status_code==429 and post.await_count==1

@pytest.mark.asyncio
async def test_timeout_and_empty_response(setup,monkeypatch):
    post=AsyncMock(side_effect=httpx.ReadTimeout('test timeout'));monkeypatch.setattr(groq_stt._http,'post',post)
    with pytest.raises(HTTPException) as caught:await groq_stt.transcribe(b'a','clip.webm','english')
    assert caught.value.status_code==504
    post.side_effect=None;post.return_value=httpx.Response(200,json={'text':''})
    with pytest.raises(HTTPException) as caught:await groq_stt.transcribe(b'a','clip.webm','english')
    assert caught.value.status_code==422

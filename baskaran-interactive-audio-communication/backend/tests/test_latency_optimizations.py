import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock
import pytest
from app.services.latency_cache import AsyncCache
from app.services import model_warmup


@pytest.mark.asyncio
async def test_cache_shares_inflight_without_cancellation_or_owner_leak():
    cache = AsyncCache()
    gate = asyncio.Event()
    calls = 0
    async def generate():
        nonlocal calls
        calls += 1
        await gate.wait()
        return b'audio'
    first = asyncio.create_task(cache.get(('alice', 'text'), generate))
    await asyncio.sleep(0)
    second = asyncio.create_task(cache.get(('alice', 'text'), generate))
    first.cancel()
    gate.set()
    assert await second == b'audio'
    assert calls == 1
    assert await cache.get(('bob', 'text'), generate) == b'audio'
    assert calls == 2


@pytest.mark.asyncio
async def test_cache_retries_failure_and_bounds_memory():
    cache = AsyncCache(max_bytes=6, max_entries=2)
    broken = AsyncMock(side_effect=ValueError('unavailable'))
    with pytest.raises(ValueError): await cache.get('a', broken)
    healthy = AsyncMock(return_value=b'1234')
    assert await cache.get('a', healthy) == b'1234'
    assert await cache.get('b', healthy) == b'1234'
    assert cache.size == 4 and len(cache.entries) == 1
    assert await cache.get('a', healthy) == b'1234'
    assert healthy.await_count == 3


@pytest.mark.asyncio
async def test_cache_expiry_and_endpoint_changes_force_fresh_work(monkeypatch):
    clock = [0]
    monkeypatch.setattr('app.services.latency_cache.time.monotonic', lambda: clock[0])
    cache = AsyncCache(ttl=10)
    generate = AsyncMock(return_value=b'audio')
    await cache.get(('workspace-a', 'text'), generate)
    await cache.get(('workspace-a', 'text'), generate)
    await cache.get(('workspace-b', 'text'), generate)
    clock[0] = 11
    await cache.get(('workspace-a', 'text'), generate)
    assert generate.await_count == 3


@pytest.mark.asyncio
@pytest.mark.parametrize('language,voice,audio', [('english', True, True), ('sinhala', True, True), ('tamil', False, False)])
async def test_preparation_is_scoped_throttled_and_never_uses_unused_audio(monkeypatch, language, voice, audio):
    from app.services import modal_client
    names = ['BASE_GEMMA', 'BGE_EMBED', 'BGE_RERANK', 'WHISPER', 'INDIC_STT', 'SINHALA_ASR', 'LOCALIZER', 'ENGLISH_KOKORO_TTS', 'INDIC_PARLER_MIXED_TTS', 'SINHALA_VITS_TTS']
    endpoints = {'MODAL_'+n+'_URL':'https://'+n.lower()+'.modal.run' for n in names}
    warmups = {k:v+'/prepare' for k,v in endpoints.items()}
    settings = SimpleNamespace(**{k.lower():v for k,v in endpoints.items()})
    monkeypatch.setattr(model_warmup, 'get_settings', lambda: settings)
    monkeypatch.setattr(model_warmup, 'manifests', lambda: [{'endpoints':endpoints, 'warmups':warmups}])
    monkeypatch.setattr(model_warmup, '_started', {})
    client = SimpleNamespace(get=AsyncMock(return_value=SimpleNamespace(raise_for_status=lambda:None)))
    monkeypatch.setattr(modal_client, '_http', client)
    model_warmup.start(language, voice=voice, audio=audio)
    model_warmup.start(language, voice=voice, audio=audio)
    await asyncio.gather(*list(model_warmup._tasks))
    urls = [call.args[0] for call in client.get.await_args_list]
    assert len(urls) == len(set(urls))
    assert warmups['MODAL_BASE_GEMMA_URL'] in urls
    if language == 'sinhala' or not audio:
        assert not any('_tts' in url for url in urls)
    if not voice:
        assert not any('bge_' in url or '_asr' in url or 'whisper' in url for url in urls)

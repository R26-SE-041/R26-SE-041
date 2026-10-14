"""Overlap cold starts only when a user begins an actual voice/action workflow."""
import asyncio
import json
import logging
import time
from functools import lru_cache
from pathlib import Path
from app.core.config import get_settings

logger = logging.getLogger(__name__)
_started = {}
_tasks = set()


@lru_cache(maxsize=1)
def manifests():
    folder = Path(__file__).resolve().parents[2] / 'modal_workspaces'
    return [json.loads(p.read_text(encoding='utf-8')) for p in folder.glob('*.json')]


def start(language, *, voice=True, audio=True):
    settings = get_settings()
    keys = ['MODAL_BASE_GEMMA_URL']
    if voice:
        keys += ['MODAL_BGE_EMBED_URL', 'MODAL_BGE_RERANK_URL',
                 {'english':'MODAL_WHISPER_URL','tamil':'MODAL_INDIC_STT_URL','sinhala':'MODAL_SINHALA_ASR_URL'}[language]]
    else:
        if language != 'english' and audio:
            keys.append('MODAL_LOCALIZER_URL')
    # Sinhala question audio requires later approval. Flashcards have no audio.
    if audio and not (voice and language == 'sinhala'):
        keys.append({'english':'MODAL_ENGLISH_KOKORO_TTS_URL','tamil':'MODAL_INDIC_PARLER_MIXED_TTS_URL','sinhala':'MODAL_SINHALA_VITS_TTS_URL'}[language])
    for key in keys:
        endpoint = getattr(settings, key.lower(), '')
        for manifest in manifests():
            if endpoint and manifest['endpoints'].get(key) == endpoint:
                url = manifest.get('warmups', {}).get(key)
                cooldown = 60 if key in {'MODAL_BASE_GEMMA_URL', 'MODAL_SINHALA_ASR_URL'} else 300
                if not url or not url.startswith('https://') or time.monotonic() - _started.get(url, -1000) < cooldown:
                    continue
                _started[url] = time.monotonic()
                async def prepare(target=url):
                    from app.services.modal_client import _http
                    try:
                        response = await asyncio.wait_for(_http.get(target, timeout=180), timeout=180)
                        response.raise_for_status()
                    except Exception:
                        logger.info('Optional model preparation failed; normal inference remains available.')
                task = asyncio.create_task(prepare())
                _tasks.add(task)
                task.add_done_callback(_tasks.discard)
                break

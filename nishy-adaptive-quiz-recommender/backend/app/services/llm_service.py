"""LLM and embedding services used by the assessment agents.

Text generation runs on the deployed Modal GPU endpoint. Embeddings remain
local because MiniLM is small and is also used by ChromaDB/RAG.
"""

import json
import logging
import os
import re
import time
from collections import OrderedDict
from threading import Lock
import httpx
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)

DEFAULT_MODAL_ENDPOINT_URL = "https://nisharahtheva--nishy-qwen-adaptive-quiz-web-endpoint.modal.run/generate"
MODAL_ENDPOINT_URL = os.getenv(
    "MODAL_ENDPOINT_URL", DEFAULT_MODAL_ENDPOINT_URL
).strip()
MODAL_API_KEY = os.getenv("MODAL_API_KEY", "").strip()
MODAL_REQUEST_TIMEOUT_SEC = float(os.getenv("MODAL_REQUEST_TIMEOUT_SEC", "120"))
MAX_NEW_TOKENS = int(os.getenv("MODAL_MAX_NEW_TOKENS", "180"))
MODAL_HEALTH_CACHE_SEC = float(os.getenv("MODAL_HEALTH_CACHE_SEC", "30"))
MODAL_FAILURE_COOLDOWN_SEC = float(os.getenv("MODAL_FAILURE_COOLDOWN_SEC", "30"))
EMBEDDING_CACHE_SIZE = max(0, int(os.getenv("EMBEDDING_CACHE_SIZE", "2048")))


class QwenModalService:
    """HTTP client for the Modal-hosted Qwen + LoRA inference service."""

    # Process-local, endpoint-specific state. A web health response establishes
    # reachability only; inference failures must override that positive result.
    _endpoint_status: dict[str, tuple[float, bool]] = {}
    _status_lock = Lock()

    @classmethod
    def _remember_status(cls, healthy: bool) -> None:
        ttl = MODAL_HEALTH_CACHE_SEC if healthy else MODAL_FAILURE_COOLDOWN_SEC
        with cls._status_lock:
            cls._endpoint_status[MODAL_ENDPOINT_URL] = (time.monotonic() + ttl, healthy)

    def __init__(self, generation_budget_sec: float | None = None):
        # Quiz retries share one deadline; other callers retain their timeout.
        self._deadline = (
            time.monotonic() + generation_budget_sec
            if generation_budget_sec is not None else None
        )
        if not MODAL_ENDPOINT_URL:
            logger.error("MODAL_ENDPOINT_URL is not configured")
        else:
            logger.info("QwenModalService initialized | endpoint=%s", MODAL_ENDPOINT_URL)

    @staticmethod
    def _headers() -> dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if MODAL_API_KEY and MODAL_API_KEY != "your-api-key":
            headers["Authorization"] = f"Bearer {MODAL_API_KEY}"
        return headers

    @staticmethod
    def _require_endpoint() -> str:
        if not MODAL_ENDPOINT_URL:
            raise RuntimeError(
                "MODAL_ENDPOINT_URL is missing. Add the deployed Modal web endpoint "
                "URL to backend/.env and restart the backend."
            )
        return MODAL_ENDPOINT_URL

    def check_health(self) -> bool:
        """Check API reachability, respecting a short inference-failure cooldown."""
        with self._status_lock:
            cached = self._endpoint_status.get(MODAL_ENDPOINT_URL)
            if cached is not None and time.monotonic() < cached[0]:
                return cached[1]
        try:
            endpoint = self._require_endpoint()
            health_endpoint = (
                endpoint[:-len("/generate")] + "/health"
                if endpoint.rstrip("/").endswith("/generate")
                else endpoint
            )
            response = httpx.get(
                health_endpoint,
                headers=self._headers(),
                timeout=httpx.Timeout(3.0, connect=2.0),
            )
            response.raise_for_status()
            payload = response.json()
            healthy = payload.get("status") == "ok" or bool(str(payload.get("response", "")).strip())
            self._remember_status(healthy)
            return healthy
        except Exception as exc:
            self._remember_status(False)
            logger.error("[ModalHealthCheck] %s", exc)
            return False

    def call(self, prompt: str, max_new_tokens: int | None = None, *, json_mode: bool = False) -> str:
        """Generate text through Modal, allowing enough time for a GPU cold start."""
        endpoint = self._require_endpoint()
        start = time.time()
        deadline = time.monotonic() + MODAL_REQUEST_TIMEOUT_SEC
        if self._deadline is not None:
            deadline = min(deadline, self._deadline)
        request_url = endpoint
        request_method = "POST"
        payload = {
            "prompt": prompt,
            "max_new_tokens": max_new_tokens or MAX_NEW_TOKENS,
        }
        if json_mode:
            payload["response_format"] = "json"
        try:
            # Modal may return HTTP 303 with a signed __modal_attempt_token
            # after a long-running web request. The signed continuation URL
            # must be fetched with GET, following standard HTTP 303 semantics.
            # Handle the redirect explicitly so the continuation uses GET.
            for attempt in range(6):
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise httpx.ReadTimeout("Modal inference deadline exceeded")

                request_timeout = httpx.Timeout(
                    remaining,
                    connect=min(30.0, remaining),
                )
                if request_method == "POST":
                    response = httpx.post(
                        request_url,
                        headers=self._headers(),
                        json=payload,
                        timeout=request_timeout,
                    )
                else:
                    response = httpx.get(
                        request_url,
                        headers=self._headers(),
                        timeout=request_timeout,
                    )
                if response.status_code != 303:
                    break

                location = response.headers.get("location", "")
                if not location:
                    raise RuntimeError("Modal returned an invalid retry redirect")
                request_url = location
                request_method = "GET"
                logger.info("Modal requested inference continuation | attempt=%d", attempt + 1)
            else:
                raise RuntimeError("Modal inference exceeded the retry redirect limit")

            response.raise_for_status()
            payload = response.json()
        except httpx.TimeoutException as exc:
            self._remember_status(False)
            raise RuntimeError(
                f"Modal inference timed out after {time.time() - start:.0f}s. "
                "Check the Modal app logs and container status."
            ) from exc
        except httpx.HTTPStatusError as exc:
            self._remember_status(False)
            detail = exc.response.text[:500]
            raise RuntimeError(
                f"Modal inference returned HTTP {exc.response.status_code}: {detail}"
            ) from exc
        except (httpx.HTTPError, ValueError) as exc:
            self._remember_status(False)
            raise RuntimeError(f"Could not call Modal inference endpoint: {exc}") from exc

        text = payload.get("response")
        if not isinstance(text, str) or not text.strip():
            self._remember_status(False)
            raise RuntimeError("Modal inference returned an empty or invalid 'response' value")

        self._remember_status(True)
        logger.info(
            "Modal inference completed in %.1fs | len=%d",
            time.time() - start,
            len(text),
        )
        return text.strip()

    def call_json(self, prompt: str, max_new_tokens: int | None = None) -> dict:
        """Call Modal and parse a JSON response, stripping markdown fences."""
        full_prompt = (
            prompt
            + "\n\nCRITICAL: Return ONLY valid JSON. "
            "No markdown, no code fences, no explanation."
        )
        # JSON includes five choices and an explanation (or a full written
        # answer). The short free-text default truncates that schema.
        budget = max_new_tokens if max_new_tokens is not None else max(MAX_NEW_TOKENS, 1024)
        raw = self.call(full_prompt, max_new_tokens=budget, json_mode=True)
        return self._extract_json(raw)

    @staticmethod
    def _extract_json(text: str) -> dict:
        """Robustly extract JSON even from messy LLM output."""
        try:
            parsed = json.loads(text.strip())
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError:
            pass

        clean = re.sub(r"```(?:json)?\n?", "", text).strip().rstrip("`")
        try:
            parsed = json.loads(clean)
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError:
            pass

        # Small instruction-tuned models sometimes produce one complete JSON
        # object and then append an extra closing brace or a short epilogue.
        # Decode the first complete object prefix; downstream schema, MCQ and
        # grounding validation still decide whether its contents are usable.
        decoder = json.JSONDecoder()
        for candidate in (text.strip(), clean):
            # Do not mistake a complete nested options object for a complete
            # question when the outer response was truncated.
            opening = candidate.find("{")
            if opening >= 0:
                try:
                    parsed, _ = decoder.raw_decode(candidate[opening:])
                except json.JSONDecodeError:
                    continue
                if isinstance(parsed, dict):
                    return parsed

        match = re.search(r"\{[\s\S]+\}", text)
        if match:
            try:
                return json.loads(match.group())
            except json.JSONDecodeError:
                pass

            # Small instruction-tuned models commonly emit JavaScript-style
            # object keys (options:{1:"..."}) while keeping all values valid.
            # Quote only bare keys; do not guess or rewrite factual values.
            repaired = re.sub(
                r'([\{,]\s*)([A-Za-z_][A-Za-z0-9_]*|[0-9]+)\s*:',
                r'\1"\2":',
                match.group(),
            )
            try:
                return json.loads(repaired)
            except json.JSONDecodeError:
                pass

        raise ValueError(f"Could not extract JSON from model output: {text[:300]}")


class EmbeddingService:
    """Local sentence-transformers embeddings for RAG and grounding."""

    _models: dict = {}
    _models_lock = Lock()
    _vectors: OrderedDict = OrderedDict()
    _vectors_lock = Lock()

    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        self._model = None
        self._model_name = model_name
        logger.info("EmbeddingService initialized (lazy) | model=%s", model_name)

    def _load(self):
        if self._model is None:
            # RAG and grounding create short-lived services on every question.
            # Load each model once per process, including concurrent sessions.
            with self._models_lock:
                if self._model_name not in self._models:
                    from sentence_transformers import SentenceTransformer

                    self._models[self._model_name] = SentenceTransformer(self._model_name)
                    logger.info("sentence-transformers model loaded: %s", self._model_name)
                self._model = self._models[self._model_name]

    def get_embedding(self, text: str) -> list[float]:
        return self.get_batch_embeddings([text])[0]

    def get_query_embedding(self, text: str) -> list[float]:
        return self.get_embedding(text)

    def get_batch_embeddings(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        # Include the model in the key; copy vectors on return so callers cannot
        # mutate a cached value. Cache only embeddings, never generated quizzes.
        found = {}
        with self._vectors_lock:
            for text in dict.fromkeys(texts):
                key = (self._model_name, text)
                if key in self._vectors:
                    found[text] = self._vectors[key]
                    self._vectors.move_to_end(key)
        missing = [text for text in dict.fromkeys(texts) if text not in found]
        if not missing:
            return [list(found[text]) for text in texts]
        self._load()
        vecs = self._model.encode(
            missing,
            normalize_embeddings=True,
            batch_size=32,
            show_progress_bar=False,
        )
        with self._vectors_lock:
            for text, vector in zip(missing, vecs):
                value = tuple(vector.tolist())
                found[text] = value
                self._vectors[(self._model_name, text)] = value
            while len(self._vectors) > EMBEDDING_CACHE_SIZE:
                self._vectors.popitem(last=False)
        return [list(found[text]) for text in texts]


LlmService = QwenModalService

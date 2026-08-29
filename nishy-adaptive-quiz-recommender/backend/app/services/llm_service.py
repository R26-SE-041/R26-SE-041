"""LLM and embedding services used by the assessment agents.

Text generation runs on the deployed Modal GPU endpoint. Embeddings remain
local because MiniLM is small and is also used by ChromaDB/RAG.
"""

import json
import logging
import os
import re
import time
import httpx
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)

DEFAULT_MODAL_ENDPOINT_URL = "https://nisharahtheva--nishy-qwen-api-generate.modal.run"
MODAL_ENDPOINT_URL = os.getenv(
    "MODAL_ENDPOINT_URL", DEFAULT_MODAL_ENDPOINT_URL
).strip()
MODAL_API_KEY = os.getenv("MODAL_API_KEY", "").strip()
MODAL_REQUEST_TIMEOUT_SEC = float(os.getenv("MODAL_REQUEST_TIMEOUT_SEC", "45"))
MAX_NEW_TOKENS = int(os.getenv("MODAL_MAX_NEW_TOKENS", "180"))


class QwenModalService:
    """HTTP client for the Modal-hosted Qwen + LoRA inference service."""

    def __init__(self):
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
        """Return whether the configured Modal generation endpoint is reachable."""
        try:
            endpoint = self._require_endpoint()
            response = httpx.post(
                endpoint,
                headers=self._headers(),
                json={"prompt": "Reply with OK.", "max_new_tokens": 8},
                # This is a circuit-breaker probe, not a cold-start request.
                # If a warm endpoint cannot answer quickly, callers should use
                # their deterministic source-grounded fallback immediately.
                timeout=httpx.Timeout(3.0, connect=2.0),
            )
            response.raise_for_status()
            return bool(str(response.json().get("response", "")).strip())
        except Exception as exc:
            logger.error("[ModalHealthCheck] %s", exc)
            return False

    def call(self, prompt: str, max_new_tokens: int | None = None) -> str:
        """Generate text through Modal, allowing enough time for a GPU cold start."""
        endpoint = self._require_endpoint()
        start = time.time()
        deadline = time.monotonic() + MODAL_REQUEST_TIMEOUT_SEC
        request_url = endpoint
        request_method = "POST"
        payload = {
            "prompt": prompt,
            "max_new_tokens": max_new_tokens or MAX_NEW_TOKENS,
        }
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
            raise RuntimeError(
                f"Modal inference timed out after {MODAL_REQUEST_TIMEOUT_SEC:.0f}s. "
                "Check the Modal app logs and container status."
            ) from exc
        except httpx.HTTPStatusError as exc:
            detail = exc.response.text[:500]
            raise RuntimeError(
                f"Modal inference returned HTTP {exc.response.status_code}: {detail}"
            ) from exc
        except (httpx.HTTPError, ValueError) as exc:
            raise RuntimeError(f"Could not call Modal inference endpoint: {exc}") from exc

        text = payload.get("response")
        if not isinstance(text, str) or not text.strip():
            raise RuntimeError("Modal inference returned an empty or invalid 'response' value")

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
        raw = self.call(full_prompt, max_new_tokens=max_new_tokens)
        return self._extract_json(raw)

    @staticmethod
    def _extract_json(text: str) -> dict:
        """Robustly extract JSON even from messy LLM output."""
        try:
            return json.loads(text.strip())
        except json.JSONDecodeError:
            pass

        clean = re.sub(r"```(?:json)?\n?", "", text).strip().rstrip("`")
        try:
            return json.loads(clean)
        except json.JSONDecodeError:
            pass

        # Small instruction-tuned models sometimes produce one complete JSON
        # object and then append an extra closing brace or a short epilogue.
        # Decode the first complete object prefix; downstream schema, MCQ and
        # grounding validation still decide whether its contents are usable.
        decoder = json.JSONDecoder()
        for candidate in (text.strip(), clean):
            for opening in (match.start() for match in re.finditer(r"\{", candidate)):
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

    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        self._model = None
        self._model_name = model_name
        logger.info("EmbeddingService initialized (lazy) | model=%s", model_name)

    def _load(self):
        if self._model is None:
            from sentence_transformers import SentenceTransformer

            self._model = SentenceTransformer(self._model_name)
            logger.info("sentence-transformers model loaded: %s", self._model_name)

    def get_embedding(self, text: str) -> list[float]:
        self._load()
        return self._model.encode(text, normalize_embeddings=True).tolist()

    def get_query_embedding(self, text: str) -> list[float]:
        return self.get_embedding(text)

    def get_batch_embeddings(self, texts: list[str]) -> list[list[float]]:
        self._load()
        vecs = self._model.encode(
            texts,
            normalize_embeddings=True,
            batch_size=32,
            show_progress_bar=False,
        )
        return [v.tolist() for v in vecs]


LlmService = QwenModalService

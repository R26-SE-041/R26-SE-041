import base64
import unittest
from unittest.mock import patch

import httpx

from app.services import srcnn_client


class FakeClient:
    def __init__(self, failures):
        self.failures = failures
        self.calls = 0

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, traceback):
        return False

    async def post(self, url, json):
        self.calls += 1
        if self.calls <= self.failures:
            raise httpx.ConnectError("temporary DNS failure")
        request = httpx.Request("POST", url)
        return httpx.Response(
            200,
            request=request,
            json={"enhanced_b64": base64.b64encode(b"enhanced").decode("utf-8")},
        )


class SrcnnClientTests(unittest.IsolatedAsyncioTestCase):
    async def test_retries_temporary_connect_errors(self):
        client = FakeClient(failures=2)
        with (
            patch.object(srcnn_client.settings, "srcnn_modal_url", "https://modal.test"),
            patch.object(srcnn_client, "modal_client", return_value=client),
            patch.object(srcnn_client.asyncio, "sleep", return_value=None),
        ):
            result = await srcnn_client.enhance_image(b"original")

        self.assertEqual(result, b"enhanced")
        self.assertEqual(client.calls, 3)

    async def test_raises_after_connect_retries_are_exhausted(self):
        client = FakeClient(failures=3)
        with (
            patch.object(srcnn_client.settings, "srcnn_modal_url", "https://modal.test"),
            patch.object(srcnn_client, "modal_client", return_value=client),
            patch.object(srcnn_client.asyncio, "sleep", return_value=None),
        ):
            with self.assertRaises(httpx.ConnectError):
                await srcnn_client.enhance_image(b"original")

        self.assertEqual(client.calls, 3)

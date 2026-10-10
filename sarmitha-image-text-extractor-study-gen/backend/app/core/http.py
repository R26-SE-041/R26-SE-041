"""Shared HTTPS client configuration for outbound Modal requests."""

import ssl

import httpx

try:
    import truststore
except ImportError:
    # pip bundles truststore on modern Python installations. This fallback
    # keeps local development working before requirements are reinstalled.
    from pip._vendor import truststore


# Use the operating system trust store. On Windows this includes certificates
# installed by managed networks, proxies, and antivirus HTTPS inspection.
SSL_CONTEXT = truststore.SSLContext(ssl.PROTOCOL_TLS_CLIENT)


def modal_client(timeout: float) -> httpx.AsyncClient:
    return httpx.AsyncClient(timeout=timeout, verify=SSL_CONTEXT)

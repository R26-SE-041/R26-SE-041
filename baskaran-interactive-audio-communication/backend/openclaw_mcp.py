"""Optional stdio MCP adapter. Run from backend: python openclaw_mcp.py.

Requires requirements-actions.txt. Secrets are environment variables, never CLI args.
"""

import os
from uuid import uuid4

import httpx
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("voicelearn-actions")


async def call_tool(name: str, action_id: str):
    secret = os.environ.get("ACTIONS_BRIDGE_SECRET", "")
    if not secret:
        raise ValueError("ACTIONS_BRIDGE_SECRET is required.")
    base = os.environ.get("VOICELEARN_BACKEND_URL", "http://127.0.0.1:8000")
    async with httpx.AsyncClient(timeout=float(os.environ.get("ACTIONS_SECTIONED_TIMEOUT_SECONDS", "1800"))) as client:
        response = await client.post(f"{base.rstrip('/')}/api/v1/actions/tools/{name}",
            headers={"X-Action-Bridge-Secret": secret}, json={"action_id": action_id})
        if not response.is_success:
            raise ValueError("VoiceLearn tool failed; inspect the application's action status.")
        return response.json()


@mcp.tool()
async def summarize_document(action_id: str) -> dict:
    """Prepare transcript once. Result is metadata only; follow next_tool, never request text."""
    return await call_tool("summarize_document", action_id)


@mcp.tool()
async def save_summary(action_id: str) -> dict:
    """Save the existing summary bound to this ticket. Summarize first when needed."""
    return await call_tool("save_summary", action_id)


@mcp.tool()
async def create_revision_audio(action_id: str) -> dict:
    """Synthesize with the ticket's English/Tamil/Sinhala TTS. Summarize first."""
    return await call_tool("create_revision_audio", action_id)


@mcp.tool()
async def save_audio_revision(action_id: str) -> dict:
    """Save and verify transcript plus WAV audio. Create revision audio first."""
    return await call_tool("save_audio_revision", action_id)


if os.environ.get("VOICELEARN_MCP_ENABLE_PING") == "true":
    @mcp.tool()
    def ping_tool() -> dict:
        """Feasibility test only: generate a fresh execution ID server-side."""
        result = uuid4().hex
        import sys
        print(f"ping_tool execution_id={result}", file=sys.stderr, flush=True)
        return {"execution_id": result}


if __name__ == "__main__":
    mcp.run(transport="stdio")

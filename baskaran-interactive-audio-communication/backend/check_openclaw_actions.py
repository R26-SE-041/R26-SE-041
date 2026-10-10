"""Gateway -> MCP ping feasibility check; run from backend after configuring OpenClaw."""

import asyncio
import json

import httpx

from app.core.config import get_settings


async def main():
    settings = get_settings()
    if not settings.openclaw_gateway_token:
        raise SystemExit("Configure OPENCLAW_GATEWAY_TOKEN in backend/.env first.")
    async with httpx.AsyncClient(timeout=120) as client:
        response = await client.post(settings.openclaw_gateway_url.rstrip("/") + "/v1/chat/completions",
            headers={"Authorization": f"Bearer {settings.openclaw_gateway_token}"},
            json={"model": f"openclaw/{settings.openclaw_agent_id}", "stream": False,
                  "messages": [{"role": "user", "content": "Call the connected VoiceLearn ping_tool exactly once. "
                      "Return only its server-generated execution_id. Do not invent an ID."}]})
        if not response.is_success:
            raise SystemExit(f"Gateway request failed (HTTP {response.status_code}). Check endpoint enablement, token and agent.")
        data = response.json()
        print(json.dumps({"gateway_content": data["choices"][0]["message"].get("content")}, indent=2))
        print("Compare the returned ID with the MCP stderr log. A response alone does not prove tool execution.")


if __name__ == "__main__":
    asyncio.run(main())

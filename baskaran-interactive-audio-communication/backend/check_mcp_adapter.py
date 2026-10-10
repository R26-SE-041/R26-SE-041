"""Verify real stdio tool discovery and optional ping execution, without a model.

python check_mcp_adapter.py --ping
python check_mcp_adapter.py
This is adapter verification, not proof of Gateway/agent execution.
"""

import argparse
import asyncio
import json
import os
from pathlib import Path
import sys
import site
from uuid import UUID

dependencies = Path(__file__).resolve().parent / ".actions-runtime" / "python"
if dependencies.is_dir():
    site.addsitedir(str(dependencies))
    sys.path.remove(str(dependencies))
    sys.path.insert(0, str(dependencies))

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


async def check(ping):
    env = {key: os.environ[key] for key in (
        "PYTHONPATH", "ACTIONS_BRIDGE_SECRET", "VOICELEARN_BACKEND_URL", "ACTIONS_TIMEOUT_SECONDS"
    ) if key in os.environ}
    env["VOICELEARN_MCP_ENABLE_PING"] = "true" if ping else "false"
    params = StdioServerParameters(command=sys.executable,
        args=[str(Path(__file__).with_name("run_actions_mcp.py"))], env=env)
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            tools = await session.list_tools()
            names = {tool.name for tool in tools.tools}
            expected = {"summarize_document", "save_summary", "create_revision_audio", "save_audio_revision"}
            if ping:
                expected.add("ping_tool")
            if names != expected:
                raise RuntimeError("Unexpected MCP tool inventory.")
            print("Tool discovery passed: " + ", ".join(sorted(names)))
            if ping:
                results = []
                for _ in range(2):
                    response = await session.call_tool("ping_tool", {})
                    if response.isError:
                        raise RuntimeError("Ping execution failed.")
                    payload = response.structuredContent or json.loads(response.content[0].text)
                    execution_id = payload["execution_id"]
                    UUID(hex=execution_id)
                    results.append(execution_id)
                if results[0] == results[1]:
                    raise RuntimeError("Ping execution IDs must be fresh.")
                print("Real stdio ping execution passed (two fresh server-generated IDs).")
            else:
                response = await session.call_tool("ping_tool", {})
                if not response.isError:
                    raise RuntimeError("Ping must not execute when disabled.")
                print("Disabled ping check passed; only the four production tools are exposed.")
    print("Gateway/model feasibility is a separate check: check_openclaw_actions.py")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--ping", action="store_true")
    args = parser.parse_args()
    asyncio.run(check(args.ping))

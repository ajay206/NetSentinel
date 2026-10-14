"""Write contracts/mcp/netsentinel-tools.json (tools, resource templates, prompts) from mcp-server.

Usage: uv run python scripts/gen_mcp_contract.py   (or: make mcp-contract)
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

from mcp_server.server import mcp

OUT = Path(__file__).resolve().parents[1] / "contracts/mcp/netsentinel-tools.json"


async def describe() -> dict:
    tools = await mcp.list_tools()
    templates = await mcp.list_resource_templates()
    prompts = await mcp.list_prompts()
    return {
        "server": "netsentinel",
        "transport": "streamable-http at /mcp, Authorization: Bearer <MCP_SERVICE_TOKEN>",
        "tools": [
            {"name": t.name, "inputSchema": t.inputSchema, "outputSchema": t.outputSchema}
            for t in sorted(tools, key=lambda t: t.name)
        ],
        "resourceTemplates": [
            {"uriTemplate": r.uriTemplate, "mimeType": r.mimeType} for r in templates
        ],
        "prompts": [
            {
                "name": p.name,
                "arguments": [a.model_dump(exclude_none=True) for a in p.arguments or []],
            }
            for p in prompts
        ],
    }


def main() -> None:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(asyncio.run(describe()), indent=2) + "\n")
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()

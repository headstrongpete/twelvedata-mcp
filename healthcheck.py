"""Standalone health check for the Twelve Data MCP server.

Launches td_mcp_server.py over stdio exactly like Claude Desktop does, performs
the MCP handshake, lists tools, and makes one live API call. Reports OK/FAIL.

    ./.venv/bin/python healthcheck.py

Note: this spawns its OWN server instance to verify the server *code* and API
key. To confirm Claude Desktop's live connection instead, check
  ~/Library/Logs/Claude/mcp-server-twelvedata.log
or `ps aux | grep td_mcp_server`.
"""

import asyncio
import sys
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

HERE = Path(__file__).resolve().parent


async def main() -> int:
    params = StdioServerParameters(
        command=str(HERE / ".venv" / "bin" / "python"),
        args=[str(HERE / "td_mcp_server.py")],
    )
    try:
        async with stdio_client(params) as (read, write):
            async with ClientSession(read, write) as session:
                init = await session.initialize()
                tools = await session.list_tools()
                print(f"✅ server started: {init.serverInfo.name} "
                      f"v{init.serverInfo.version}")
                print(f"✅ {len(tools.tools)} tools exposed")

                probe = await session.call_tool("get_price", {"symbol": "AAPL"})
                text = (probe.structuredContent
                        or (probe.content[0].text if probe.content else "?"))
                if probe.isError:
                    print(f"⚠️  API call returned an error: {text}")
                    return 1
                print(f"✅ live API call OK: get_price(AAPL) -> {text}")
        print("\nHEALTHY")
        return 0
    except Exception as exc:  # noqa: BLE001
        print(f"❌ FAILED: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))

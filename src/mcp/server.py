# src/mcp/server.py
# RUN: python -m src.mcp.server


import asyncio

from src.mcp.core import MCPServer
from src.mcp.resources import register_resources
from src.mcp.tools import register_tools


async def main():
    server = MCPServer(name="LedgerMCP")

    # Register tools (commands)
    register_tools(server)

    # Register resources (queries)
    register_resources(server)

    await server.start()


if __name__ == "__main__":
    asyncio.run(main())

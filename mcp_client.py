"""MCP Client for interacting with Teradata MCP Server"""
import asyncio
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client
from config import Config

# Cache for MCP tools
cached_tools = []


async def get_mcp_tools():
    """Get available tools from MCP server using SDK"""
    global cached_tools

    url = Config.get_mcp_url()
    print(f"[MCP] Connecting to {url}")

    async with streamablehttp_client(url) as (read_stream, write_stream, _):
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()
            print("[MCP] Session initialized")

            tools_result = await session.list_tools()
            cached_tools = [
                {
                    "name": t.name,
                    "description": t.description,
                    "inputSchema": t.inputSchema
                }
                for t in tools_result.tools
            ]
            print(f"[MCP] Got {len(cached_tools)} tools")
            return cached_tools


async def call_mcp_tool(tool_name, arguments=None):
    """Call a specific MCP tool"""
    url = Config.get_mcp_url()
    print(f"[MCP] Calling tool: {tool_name}")

    async with streamablehttp_client(url) as (read_stream, write_stream, _):
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()

            result = await session.call_tool(tool_name, arguments or {})
            print(f"[MCP] Tool result received")

            # Extract text content from result
            if result.content:
                texts = [c.text for c in result.content if hasattr(c, 'text')]
                return {"content": texts}
            return {"content": []}


def run_async(coro):
    """Run async function in sync context"""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()

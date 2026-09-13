"""MCP client: connects to every enabled server in the registry (see
mcp_registry.py), aggregates their tools, and routes tool calls back to
whichever server actually owns them."""
import asyncio
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

import mcp_registry

# Display name (as shown to the LLM / UI) -> {"server": server_dict, "real_name": str}.
# Rebuilt on every get_mcp_tools() call, which chat_handler.py always does
# before any call_mcp_tool() in the same turn - see process_chat_request().
tool_routing = {}


async def _fetch_server_tools(server):
    """Return (server, tools, error) for one server - tools is None on
    failure, so one dead server can't blank out the others' tools."""
    try:
        async with streamablehttp_client(server["url"], headers=server.get("headers") or None) as (read_stream, write_stream, _):
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()
                tools_result = await session.list_tools()
                tools = [
                    {"name": t.name, "description": t.description, "inputSchema": t.inputSchema}
                    for t in tools_result.tools
                ]
                return server, tools, None
    except Exception as e:
        return server, None, str(e)


async def get_server_statuses():
    """Per-server health + tool count, for /api/mcp/health and the settings UI."""
    servers = [s for s in mcp_registry.list_servers() if s.get("enabled", True)]
    if not servers:
        return []

    results = await asyncio.gather(*(_fetch_server_tools(s) for s in servers))
    statuses = []
    for server, tools, error in results:
        if error:
            statuses.append({"id": server["id"], "name": server["name"], "status": "error", "error": error})
        else:
            statuses.append({"id": server["id"], "name": server["name"], "status": "ok", "tools_count": len(tools)})
    return statuses


async def get_mcp_tools():
    """Aggregate tools from every enabled server.

    A tool name is only qualified with a "ServerName::" prefix when two
    servers actually expose the same bare name - the common single-server
    case is byte-for-byte the same as before this registry existed, since
    chat_handler.py and prompts.py just consume whatever names come back.
    """
    global tool_routing

    servers = [s for s in mcp_registry.list_servers() if s.get("enabled", True)]
    results = await asyncio.gather(*(_fetch_server_tools(s) for s in servers))

    name_counts = {}
    per_server_tools = []
    for server, tools, error in results:
        if error:
            print(f"[MCP] {server['name']} ({server['url']}) unreachable: {error}")
            continue
        per_server_tools.append((server, tools))
        for t in tools:
            name_counts[t["name"]] = name_counts.get(t["name"], 0) + 1

    tool_routing = {}
    aggregated = []
    for server, tools in per_server_tools:
        for t in tools:
            collision = name_counts[t["name"]] > 1
            display_name = f"{server['name']}::{t['name']}" if collision else t["name"]
            tool_routing[display_name] = {"server": server, "real_name": t["name"]}
            aggregated.append({**t, "name": display_name})

    print(f"[MCP] Got {len(aggregated)} tools across {len(per_server_tools)}/{len(servers)} enabled servers")
    return aggregated


async def call_mcp_tool(tool_name, arguments=None):
    """Call a tool by the display name get_mcp_tools() returned, routed to
    whichever server actually owns it."""
    route = tool_routing.get(tool_name)
    if route is None:
        raise ValueError(f"Unknown tool: {tool_name} (not in the last-fetched tool list)")

    server = route["server"]
    real_name = route["real_name"]
    print(f"[MCP] Calling tool: {real_name} on {server['name']}")

    async with streamablehttp_client(server["url"], headers=server.get("headers") or None) as (read_stream, write_stream, _):
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()

            result = await session.call_tool(real_name, arguments or {})
            print(f"[MCP] Tool result received")

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

"""Per-agent database knowledge sync: crawls a persona's bound database via
the existing MCP plumbing (mcp_client.py, the same tool-calling path
/api/chat uses) and writes what it finds as a skill in deepagents' own
SKILL.md format (agent_skill_store.py) - the data-agent picks it up
automatically via progressive disclosure (skills=[f"/{persona_id}/"] in
agent_orchestrator.py), no new loading wiring needed.

Real result shapes verified live against teradata-mcp-server (not assumed):
base_tableList -> {"status": "success", "results": [{"TableName": "..."}]}
base_tableDDL  -> {"status": "success", "results": [{"Request Text": "CREATE ..."}]}
"""
import json

import cache
import mcp_client
import agent_skill_store
import agent_persona_store

KNOWLEDGE_SKILL_SLUG = "database-knowledge"
MAX_TABLES = 25  # caps how many DDLs get pulled per sync, so one sync of a
# huge database doesn't take minutes or blow the skill body past what's
# useful as context - the index still lists every table name found.


def _parse_results(mcp_result):
    """Best-effort JSON parse of an MCP tool's text content, matching the
    {"status", "results": [...]} shape these particular tools return."""
    for text in mcp_result.get("content", []):
        try:
            parsed = json.loads(text)
        except (json.JSONDecodeError, TypeError):
            continue
        if isinstance(parsed, dict):
            return parsed.get("results", [])
    return []


async def _sync_async(database_name):
    tools = await mcp_client.get_mcp_tools()  # also populates mcp_client.tool_routing
    tool_names = {t["name"] for t in tools}
    if "base_tableList" not in tool_names:
        raise ValueError("base_tableList tool is not available from any enabled MCP server")

    table_result = await mcp_client.call_mcp_tool("base_tableList", {"database_name": database_name})
    table_names = [row.get("TableName") for row in _parse_results(table_result) if row.get("TableName")]

    ddls = []
    if "base_tableDDL" in tool_names:
        for table_name in table_names[:MAX_TABLES]:
            try:
                # Cached 10 minutes: schema rarely changes mid-session, and
                # this guards repeated syncs of the same database (e.g. a
                # user re-syncing to tune knowledge) from re-fetching
                # identical DDL over the network every time.
                ddl_result = await cache.cached(
                    f"ddl:{database_name}:{table_name}", 600,
                    lambda db=database_name, tn=table_name: mcp_client.call_mcp_tool("base_tableDDL", {"database_name": db, "table_name": tn}),
                )
                rows = _parse_results(ddl_result)
                ddl_text = rows[0].get("Request Text", "").strip() if rows else ""
            except Exception as e:
                ddl_text = f"(failed to fetch DDL: {e})"
            if ddl_text:
                ddls.append((table_name, ddl_text))

    return table_names, ddls


def sync(persona_id, database_name):
    """Run a sync and save/overwrite the persona's "database-knowledge"
    skill. Returns the resulting skill record."""
    table_names, ddls = mcp_client.run_async(_sync_async(database_name))

    body_parts = [
        f"# Database: {database_name}\n",
        f"This database has {len(table_names)} tables. Consult this before writing SQL against it - use the EXACT names below.\n",
        "## Table list\n" + "\n".join(f"- {t}" for t in table_names),
    ]
    if ddls:
        body_parts.append(
            f"\n## Table definitions (first {len(ddls)} tables)\n" +
            "\n\n".join(f"### {name}\n```sql\n{ddl}\n```" for name, ddl in ddls)
        )
    body = "\n".join(body_parts)

    existing = agent_skill_store.get_skill(persona_id, KNOWLEDGE_SKILL_SLUG)
    description = f"Schema knowledge for the {database_name} database ({len(table_names)} tables) - auto-generated, re-sync to refresh."
    if existing:
        skill = agent_skill_store.update_skill(persona_id, KNOWLEDGE_SKILL_SLUG, description=description, body=body)
    else:
        skill = agent_skill_store.create_skill(persona_id, "Database Knowledge", description, body)

    agent_persona_store.mark_synced(persona_id)
    return skill


async def _fetch_databases():
    tools = await mcp_client.get_mcp_tools()
    if "base_databaseList" not in {t["name"] for t in tools}:
        return []
    result = await mcp_client.call_mcp_tool("base_databaseList", {})
    return [row.get("DatabaseName") for row in _parse_results(result) if row.get("DatabaseName")]


async def _list_databases_async():
    # Real MCP round trip each time otherwise (unlike get_mcp_tools, which
    # mcp_client.py already caches) - worth a short cache since the
    # database-binding dropdown re-fetches this every time a persona's
    # Knowledge tab opens, and the list rarely changes minute to minute.
    return await cache.cached("mcp:database-list", 60, _fetch_databases)


def list_databases():
    """Every database name visible through the enabled MCP server(s) - feeds
    the persona editor's database-binding dropdown."""
    return mcp_client.run_async(_list_databases_async())

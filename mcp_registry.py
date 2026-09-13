"""MCP server registry: persists the list of configured MCP servers to
data/mcp_servers.json (one file, mirrors conversation_store.py's style).

Chatterbase used to hardcode exactly one MCP server via Config.MCP_SERVER_URL
+ Config.MCP_ENDPOINT. This registry replaces that with a list, each entry a
single full URL (e.g. http://127.0.0.1:8001/mcp) rather than the old split
base-URL/endpoint pair - simpler, and matches how MCP client configs (Claude
Desktop, Cursor, ...) actually write URLs.
"""
import json
import os
import uuid

from config import Config


def _data_dir():
    path = os.path.join(os.getcwd(), Config.DATA_DIR)
    os.makedirs(path, exist_ok=True)
    return path


def _servers_path():
    return os.path.join(_data_dir(), "mcp_servers.json")


def _seed_default():
    """Build the initial registry from today's single-server .env config,
    so an existing deployment (like the live teradata-mcp-server setup)
    keeps working with zero manual migration."""
    return [{
        "id": str(uuid.uuid4()),
        "name": "Default",
        "url": Config.get_mcp_url(),
        "enabled": True,
        "headers": {},
    }]


def _load():
    path = _servers_path()
    if not os.path.exists(path):
        servers = _seed_default()
        _save(servers)
        return servers
    with open(path) as f:
        return json.load(f)


def _save(servers):
    with open(_servers_path(), "w") as f:
        json.dump(servers, f, indent=2)


def list_servers():
    """Return all configured servers, enabled and disabled."""
    return _load()


def get_server(server_id):
    """Return one server dict, or None if it doesn't exist."""
    for s in _load():
        if s["id"] == server_id:
            return s
    return None


def add_server(name, url, headers=None, enabled=True):
    """Add a new server and return it."""
    servers = _load()
    server = {
        "id": str(uuid.uuid4()),
        "name": name,
        "url": url,
        "enabled": enabled,
        "headers": headers or {},
    }
    servers.append(server)
    _save(servers)
    return server


def update_server(server_id, **fields):
    """Update one server's fields (name/url/enabled/headers). Raises
    FileNotFoundError-style KeyError if the id doesn't exist."""
    servers = _load()
    for s in servers:
        if s["id"] == server_id:
            for key in ("name", "url", "enabled", "headers"):
                if key in fields and fields[key] is not None:
                    s[key] = fields[key]
            _save(servers)
            return s
    raise KeyError(f"MCP server {server_id} not found")


def delete_server(server_id):
    """Delete a server. Returns True if it existed."""
    servers = _load()
    remaining = [s for s in servers if s["id"] != server_id]
    if len(remaining) == len(servers):
        return False
    _save(remaining)
    return True


def import_mcp_servers_json(raw_text):
    """Import servers from a pasted Claude-Desktop-style config:

        {"mcpServers": {"name": {"url": "http://host:port/mcp"}, ...}}

    Only url-based (remote, HTTP) entries are supported - this client talks
    streamable-HTTP only. command-based (stdio-launched local server) entries
    are reported back as skipped rather than silently dropped, since actually
    supporting those would mean managing a subprocess's lifecycle - a
    different, bigger feature.

    Returns {"added": [server, ...], "skipped": [{"name", "reason"}, ...]}.
    """
    try:
        parsed = json.loads(raw_text)
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON: {e}")

    # Tolerate either the full {"mcpServers": {...}} wrapper or a bare
    # {"name": {...}} map, since people paste fragments too.
    entries = parsed.get("mcpServers", parsed) if isinstance(parsed, dict) else {}
    if not isinstance(entries, dict):
        raise ValueError("Expected an object of {\"name\": {\"url\": ...}} entries")

    existing_urls = {s["url"] for s in _load()}
    added = []
    skipped = []

    for name, cfg in entries.items():
        if not isinstance(cfg, dict):
            skipped.append({"name": name, "reason": "not a valid server config object"})
            continue
        url = cfg.get("url")
        if not url:
            reason = ("local stdio (command-based) servers aren't supported by this "
                       "HTTP-only client" if "command" in cfg else "missing a \"url\" field")
            skipped.append({"name": name, "reason": reason})
            continue
        if url in existing_urls:
            skipped.append({"name": name, "reason": "already configured (same URL)"})
            continue
        server = add_server(name, url, headers=cfg.get("headers"))
        existing_urls.add(url)
        added.append(server)

    return {"added": added, "skipped": skipped}

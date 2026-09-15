"""Tiny async JSON cache over Redis (the same instance the Langfuse stack
uses - see docker-compose.yml), with an in-process TTL-dict fallback when
REDIS_URL is unset or the server is unreachable - `uv run` local dev needs
nothing, and a Redis outage degrades to "every call is a cache miss," not
a broken app.

Async-only: every real caching target in this app (MCP tool/health fetches
in mcp_client.py, agent_orchestrator.py, knowledge_sync.py) is already an
async function reached via run_async() from sync Flask routes, so one
implementation covers everything - no separate sync client needed.
"""
import json
import os
import time

_redis_client = None
_redis_checked_at = 0
_RECHECK_INTERVAL = 30  # seconds - if Redis was down, retry occasionally
# rather than assuming it's down forever for the life of the process.

_local_cache = {}  # key -> (expires_at, json-serializable value)


async def _get_redis():
    global _redis_client, _redis_checked_at
    now = time.monotonic()
    if _redis_client is not None:
        return _redis_client
    if now - _redis_checked_at < _RECHECK_INTERVAL:
        return None
    _redis_checked_at = now
    url = os.environ.get("REDIS_URL")
    if not url:
        return None
    try:
        import redis.asyncio as redis
        client = redis.from_url(url, socket_connect_timeout=1, socket_timeout=1)
        await client.ping()
        _redis_client = client
        return client
    except Exception as e:
        print(f"[Cache] Redis unavailable, using in-process cache: {e}")
        return None


async def get(key):
    client = await _get_redis()
    if client is not None:
        try:
            raw = await client.get(key)
            return json.loads(raw) if raw is not None else None
        except Exception:
            return None
    entry = _local_cache.get(key)
    if not entry:
        return None
    expires_at, value = entry
    if time.time() > expires_at:
        _local_cache.pop(key, None)
        return None
    return value


async def set(key, value, ttl_seconds):
    client = await _get_redis()
    if client is not None:
        try:
            await client.set(key, json.dumps(value), ex=ttl_seconds)
            return
        except Exception:
            pass
    _local_cache[key] = (time.time() + ttl_seconds, value)


async def cached(key, ttl_seconds, compute_coro_fn):
    """Get-or-compute: return the cached value if present, else await
    compute_coro_fn(), cache the result, and return it."""
    value = await get(key)
    if value is not None:
        return value
    value = await compute_coro_fn()
    await set(key, value, ttl_seconds)
    return value

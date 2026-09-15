"""Observability: Langfuse tracing (deep LLM/tool spans, self-hosted - see
docker-compose.yml) plus a lightweight in-app SQLite activity log, both fed
via LangChain callback handlers attached to every agent invoke
(agent_orchestrator.py passes get_callbacks()'s result as config["callbacks"]).

Langfuse is optional at the call site, not just at startup: get_callbacks()
never raises - if LANGFUSE_PUBLIC_KEY/SECRET_KEY aren't set, or the service
is unreachable, it's silently omitted so a Langfuse outage never blocks a
run (verified: LangChain callback handler construction from env vars alone
does not itself contact the server - only flush/export calls do, and those
happen async in the SDK's own background thread, not on the request path).
"""
import datetime
import os
import sqlite3
import time

from langchain_core.callbacks import BaseCallbackHandler

from config import Config

_SCHEMA = """
CREATE TABLE IF NOT EXISTS activity (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts TEXT NOT NULL,
    thread_id TEXT,
    persona_id TEXT,
    kind TEXT NOT NULL,
    label TEXT,
    duration_ms INTEGER,
    status TEXT
)
"""


def _db_path():
    data_dir = os.path.join(os.getcwd(), Config.DATA_DIR)
    os.makedirs(data_dir, exist_ok=True)
    return os.path.join(data_dir, "activity.sqlite")


def _connect():
    conn = sqlite3.connect(_db_path())
    conn.execute(_SCHEMA)
    return conn


def log_event(thread_id=None, persona_id=None, kind="event", label="", duration_ms=None, status="ok"):
    conn = _connect()
    with conn:
        conn.execute(
            "INSERT INTO activity (ts, thread_id, persona_id, kind, label, duration_ms, status) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (datetime.datetime.utcnow().isoformat() + "Z", thread_id, persona_id, kind, (label or "")[:500], duration_ms, status),
        )
    conn.close()


def list_events(persona_id=None, kind=None, limit=100):
    conn = _connect()
    query = "SELECT id, ts, thread_id, persona_id, kind, label, duration_ms, status FROM activity"
    clauses, params = [], []
    if persona_id:
        clauses.append("persona_id = ?")
        params.append(persona_id)
    if kind:
        clauses.append("kind = ?")
        params.append(kind)
    if clauses:
        query += " WHERE " + " AND ".join(clauses)
    query += " ORDER BY id DESC LIMIT ?"
    params.append(min(limit, 500))
    rows = conn.execute(query, params).fetchall()
    conn.close()
    cols = ["id", "ts", "thread_id", "persona_id", "kind", "label", "duration_ms", "status"]
    return [dict(zip(cols, r)) for r in rows]


def stats():
    conn = _connect()
    today = datetime.datetime.utcnow().date().isoformat()
    total_runs = conn.execute("SELECT COUNT(*) FROM activity WHERE kind = 'run_start'").fetchone()[0]
    runs_today = conn.execute("SELECT COUNT(*) FROM activity WHERE kind = 'run_start' AND ts >= ?", (today,)).fetchone()[0]
    tool_calls = conn.execute("SELECT COUNT(*) FROM activity WHERE kind = 'tool_call'").fetchone()[0]
    errors = conn.execute("SELECT COUNT(*) FROM activity WHERE status = 'error'").fetchone()[0]
    avg_duration = conn.execute("SELECT AVG(duration_ms) FROM activity WHERE kind = 'tool_call' AND duration_ms IS NOT NULL").fetchone()[0]
    conn.close()
    return {
        "total_runs": total_runs,
        "runs_today": runs_today,
        "tool_calls": tool_calls,
        "errors": errors,
        "avg_tool_duration_ms": round(avg_duration) if avg_duration else 0,
    }


def _is_control_flow(error):
    """True for LangGraph's interrupt()/control-flow exceptions (verified
    live: raises langgraph.errors.GraphInterrupt, a GraphBubbleUp subclass)
    - these aren't failures, just how a paused-for-approval run is
    implemented under the hood, so callback handlers shouldn't record them
    as errors."""
    try:
        from langgraph.errors import GraphBubbleUp
        return isinstance(error, GraphBubbleUp)
    except ImportError:
        return False


class ActivityCallbackHandler(BaseCallbackHandler):
    """Real BaseCallbackHandler subclass (not just duck-typed - the base
    class supplies attributes like run_inline the callback manager's
    internals require, confirmed live: a plain duck-typed class raised
    AttributeError as soon as a tool call fired) that writes tool-call and
    error events to the SQLite activity log as they happen. thread_id/
    persona_id are bound per run via a small factory below rather than read
    from LangChain's run metadata, since that's simpler and exactly what
    agent_orchestrator.py already has in hand at call time."""

    def __init__(self, thread_id, persona_id):
        super().__init__()
        self.thread_id = thread_id
        self.persona_id = persona_id
        self._tool_starts = {}

    def on_tool_start(self, serialized, input_str, *, run_id, **kwargs):
        self._tool_starts[run_id] = time.monotonic()
        name = (serialized or {}).get("name", "tool")
        log_event(self.thread_id, self.persona_id, "tool_call", label=f"{name} started", status="running")

    def on_tool_end(self, output, *, run_id, **kwargs):
        started = self._tool_starts.pop(run_id, None)
        duration_ms = int((time.monotonic() - started) * 1000) if started else None
        log_event(self.thread_id, self.persona_id, "tool_call", label="tool finished", duration_ms=duration_ms, status="ok")

    def on_tool_error(self, error, *, run_id, **kwargs):
        started = self._tool_starts.pop(run_id, None)
        duration_ms = int((time.monotonic() - started) * 1000) if started else None
        if _is_control_flow(error):
            log_event(self.thread_id, self.persona_id, "tool_call", label="paused for approval", duration_ms=duration_ms, status="ok")
            return
        log_event(self.thread_id, self.persona_id, "tool_call", label=str(error)[:300], duration_ms=duration_ms, status="error")

    def on_llm_error(self, error, *, run_id, **kwargs):
        if _is_control_flow(error):
            return
        log_event(self.thread_id, self.persona_id, "llm_call", label=str(error)[:300], status="error")

    def on_chain_error(self, error, *, run_id, **kwargs):
        # LangGraph implements interrupt() as a GraphInterrupt exception that
        # bubbles up through every enclosing chain's on_*_error callback
        # before the top-level Pregel loop catches it and turns it into the
        # normal __interrupt__ result key (verified live: approving a
        # pending dispatch logged a spurious "run ... error" event here even
        # though the run was actually paused successfully, not failed) - a
        # paused-for-approval run is expected control flow, not a failure.
        if _is_control_flow(error):
            return
        log_event(self.thread_id, self.persona_id, "run", label=str(error)[:300], status="error")


_langfuse_checked = False
_langfuse_available = False


def _langfuse_configured():
    """True once, cheaply, without a network call - real availability is
    proven per-call by the handler construction below, which is itself
    wrapped in try/except so a misconfigured or unreachable Langfuse never
    breaks a run."""
    global _langfuse_checked, _langfuse_available
    if not _langfuse_checked:
        _langfuse_checked = True
        _langfuse_available = bool(os.environ.get("LANGFUSE_PUBLIC_KEY") and os.environ.get("LANGFUSE_SECRET_KEY"))
    return _langfuse_available


def get_callbacks(thread_id, persona_id):
    """LangChain callback list for one agent invoke: the in-app activity
    logger always included, plus a Langfuse CallbackHandler when configured
    - construction is guarded so an unreachable/misconfigured Langfuse
    degrades to "just the local activity log" instead of failing the run."""
    callbacks = [ActivityCallbackHandler(thread_id, persona_id)]
    if _langfuse_configured():
        try:
            from langfuse.langchain import CallbackHandler
            callbacks.append(CallbackHandler())
        except Exception as e:
            print(f"[Observability] Langfuse callback unavailable, continuing without it: {e}")
    return callbacks


def langfuse_ui_url():
    """The self-hosted Langfuse UI's base URL, for a UI "open in Langfuse"
    link - None if not configured (see /api/config)."""
    if not _langfuse_configured():
        return None
    host = os.environ.get("LANGFUSE_HOST", "")
    # The browser reaches Langfuse via the host-published port (docker-
    # compose.yml maps 3001->3000), not the container-internal DNS name/port
    # the SDK itself uses server-side - swap that in for the UI link.
    if "langfuse-web:3000" in host:
        return "http://localhost:3001"
    return host or None

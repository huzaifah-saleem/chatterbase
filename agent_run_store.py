"""Agent run history index: one file per run under data/agent_runs/, mirrors
conversation_store.py's pattern. Holds only enough to list past runs in the
sidebar (id/request/status/timestamps) - the actual paused/resumable
execution state lives in the LangGraph checkpointer (see agent_orchestrator.py
and data/agent_checkpoints.sqlite), not here. Replaces plan_store.py, which
held full step results because it WAS the execution state; that job now
belongs to the checkpointer.
"""
import json
import os
import re
import uuid
import datetime

from config import Config


def _runs_dir():
    path = os.path.join(os.getcwd(), Config.DATA_DIR, "agent_runs")
    os.makedirs(path, exist_ok=True)
    return path


def _path_for(run_id):
    safe_id = re.sub(r'[^a-fA-F0-9-]', '', run_id)
    return os.path.join(_runs_dir(), f"{safe_id}.json")


def create_run(request, persona_id=None):
    """Start a new run record. The id doubles as the LangGraph thread_id."""
    now = datetime.datetime.utcnow().isoformat() + "Z"
    run = {
        "id": str(uuid.uuid4()),
        "request": request,
        "persona_id": persona_id,
        "status": "running",
        "created_at": now,
        "updated_at": now,
    }
    with open(_path_for(run["id"]), "w") as f:
        json.dump(run, f, indent=2)
    return run


def get_run(run_id):
    path = _path_for(run_id)
    if not os.path.exists(path):
        return None
    with open(path) as f:
        return json.load(f)


def list_runs(persona_id=None):
    """Summaries, newest first. persona_id=None lists every run (used for
    "General"'s catch-all history); pass a persona's id to filter to it, or
    the sentinel "__none__" to list only runs with no persona (kept distinct
    from "list everything" for the "General" tab's own feed)."""
    summaries = []
    for filename in os.listdir(_runs_dir()):
        if not filename.endswith('.json'):
            continue
        try:
            with open(os.path.join(_runs_dir(), filename)) as f:
                data = json.load(f)
            run_persona_id = data.get("persona_id")
            if persona_id == "__none__" and run_persona_id is not None:
                continue
            if persona_id not in (None, "__none__") and run_persona_id != persona_id:
                continue
            summaries.append({
                "id": data["id"],
                "request": data.get("request", ""),
                "status": data.get("status", ""),
                "updated_at": data.get("updated_at", ""),
            })
        except (json.JSONDecodeError, KeyError, OSError):
            continue
    summaries.sort(key=lambda r: r["updated_at"], reverse=True)
    return summaries


def delete_run(run_id):
    """Remove the run's index entry only - its checkpointed execution state
    stays in data/agent_checkpoints.sqlite, orphaned but not destroyed, same
    trade-off agent_chat_store.delete_chat makes for chats."""
    path = _path_for(run_id)
    if not os.path.exists(path):
        return False
    os.remove(path)
    return True


def set_status(run_id, status):
    run = get_run(run_id)
    if run is None:
        raise FileNotFoundError(f"Run {run_id} not found")
    run["status"] = status
    run["updated_at"] = datetime.datetime.utcnow().isoformat() + "Z"
    with open(_path_for(run_id), "w") as f:
        json.dump(run, f, indent=2)
    return run

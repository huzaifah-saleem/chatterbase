"""Agent plans: a user request decomposed into steps, each dispatched to a
sub-agent, gated on approval before executing. One file per plan under
data/plans/ - mirrors conversation_store.py's pattern exactly.

A step's "agent_type" determines which handler in agent_orchestrator.py runs
it. Results are stored per-step as generic UI blocks (see agent_orchestrator.py
and the renderBlocks() dispatcher in templates/index.html) rather than plain
text, so the frontend can render tables/charts/nested plans generically
instead of every new agent type needing new frontend code.
"""
import json
import os
import re
import uuid
import datetime

from config import Config


def _plans_dir():
    path = os.path.join(os.getcwd(), Config.DATA_DIR, "plans")
    os.makedirs(path, exist_ok=True)
    return path


def _path_for(plan_id):
    safe_id = re.sub(r'[^a-fA-F0-9-]', '', plan_id)
    return os.path.join(_plans_dir(), f"{safe_id}.json")


def create_plan(request, steps):
    """steps: [{"id", "description", "agent_type"}, ...] - already normalized
    by agent_orchestrator.plan_request()."""
    now = datetime.datetime.utcnow().isoformat() + "Z"
    plan = {
        "id": str(uuid.uuid4()),
        "request": request,
        "steps": steps,
        "status": "pending_approval",
        "results": [],
        "created_at": now,
        "updated_at": now,
    }
    with open(_path_for(plan["id"]), "w") as f:
        json.dump(plan, f, indent=2)
    return plan


def get_plan(plan_id):
    path = _path_for(plan_id)
    if not os.path.exists(path):
        return None
    with open(path) as f:
        return json.load(f)


def list_plans():
    """Summaries (id, request, status, updated_at), newest first."""
    summaries = []
    for filename in os.listdir(_plans_dir()):
        if not filename.endswith('.json'):
            continue
        try:
            with open(os.path.join(_plans_dir(), filename)) as f:
                data = json.load(f)
            summaries.append({
                "id": data["id"],
                "request": data.get("request", ""),
                "status": data.get("status", ""),
                "updated_at": data.get("updated_at", ""),
            })
        except (json.JSONDecodeError, KeyError, OSError):
            continue
    summaries.sort(key=lambda p: p["updated_at"], reverse=True)
    return summaries


def _save(plan):
    plan["updated_at"] = datetime.datetime.utcnow().isoformat() + "Z"
    with open(_path_for(plan["id"]), "w") as f:
        json.dump(plan, f, indent=2)


def set_status(plan_id, status):
    plan = get_plan(plan_id)
    if plan is None:
        raise FileNotFoundError(f"Plan {plan_id} not found")
    plan["status"] = status
    _save(plan)
    return plan


def append_result(plan_id, step_id, blocks):
    """Record one step's output blocks. Safe to call once per step, in order."""
    plan = get_plan(plan_id)
    if plan is None:
        raise FileNotFoundError(f"Plan {plan_id} not found")
    plan["results"].append({"step_id": step_id, "blocks": blocks})
    _save(plan)
    return plan

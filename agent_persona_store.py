"""Agent personas: named, saved domain-expertise definitions (e.g. "Telecom
Analyst") that flavor the data-agent's system prompt for a given run - see
agent_orchestrator.py's _build_agent(). One file per persona under
data/agent_personas/, mirrors dashboard_store.py's file-per-record pattern,
but with full CRUD (mirrors llm_registry.py's update_profile) rather than
dashboard_store's create/delete-only shape, since a persona's name and
expertise prompt are meant to be revised in place.
"""
import json
import os
import re
import uuid
import datetime

from config import Config


def _personas_dir():
    path = os.path.join(os.getcwd(), Config.DATA_DIR, "agent_personas")
    os.makedirs(path, exist_ok=True)
    return path


def _path_for(persona_id):
    safe_id = re.sub(r'[^a-fA-F0-9-]', '', persona_id)
    return os.path.join(_personas_dir(), f"{safe_id}.json")


def list_personas():
    """Summaries, newest first."""
    summaries = []
    for filename in os.listdir(_personas_dir()):
        if not filename.endswith('.json'):
            continue
        try:
            with open(os.path.join(_personas_dir(), filename)) as f:
                data = json.load(f)
            summaries.append({
                "id": data["id"],
                "name": data.get("name", "Untitled"),
                "expertise_prompt": data.get("expertise_prompt", ""),
                "tagline": data.get("tagline", ""),
                "emoji": data.get("emoji", ""),
                "color": data.get("color", ""),
                "database": data.get("database", ""),
                "last_synced": data.get("last_synced", ""),
                "updated_at": data.get("updated_at", ""),
            })
        except (json.JSONDecodeError, KeyError, OSError):
            continue
    summaries.sort(key=lambda p: p["updated_at"], reverse=True)
    return summaries


def get_persona(persona_id):
    path = _path_for(persona_id)
    if not os.path.exists(path):
        return None
    with open(path) as f:
        return json.load(f)


def create_persona(name, expertise_prompt, tagline="", emoji="", color="", database=""):
    now = datetime.datetime.utcnow().isoformat() + "Z"
    persona = {
        "id": str(uuid.uuid4()),
        "name": name,
        "expertise_prompt": expertise_prompt,
        "tagline": tagline,
        "emoji": emoji,
        "color": color,
        "database": database,
        "last_synced": "",
        "created_at": now,
        "updated_at": now,
    }
    with open(_path_for(persona["id"]), "w") as f:
        json.dump(persona, f, indent=2)
    return persona


def update_persona(persona_id, name=None, expertise_prompt=None, tagline=None, emoji=None, color=None, database=None):
    """Update a persona's fields in place. database is the schema/database
    name this agent is bound to for knowledge sync (see knowledge_sync.py) -
    unset it (empty string) to unbind."""
    persona = get_persona(persona_id)
    if persona is None:
        raise KeyError(f"Persona {persona_id} not found")
    for field, value in (("name", name), ("expertise_prompt", expertise_prompt), ("tagline", tagline), ("emoji", emoji), ("color", color)):
        if value is not None:
            persona[field] = value
    if database is not None and database != persona.get("database", ""):
        persona["database"] = database
        persona["last_synced"] = ""  # binding changed - any prior sync is now stale
    persona["updated_at"] = datetime.datetime.utcnow().isoformat() + "Z"
    with open(_path_for(persona_id), "w") as f:
        json.dump(persona, f, indent=2)
    return persona


def mark_synced(persona_id):
    persona = get_persona(persona_id)
    if persona is None:
        raise KeyError(f"Persona {persona_id} not found")
    persona["last_synced"] = datetime.datetime.utcnow().isoformat() + "Z"
    with open(_path_for(persona_id), "w") as f:
        json.dump(persona, f, indent=2)
    return persona


def delete_persona(persona_id):
    """Delete a persona. Its past runs (agent_run_store) are left untouched,
    same as deleting a dashboard doesn't delete the conversations that fed it."""
    path = _path_for(persona_id)
    if not os.path.exists(path):
        return False
    os.remove(path)
    return True

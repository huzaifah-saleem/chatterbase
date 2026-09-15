"""Agent chat threads: an index of multi-turn conversations per persona,
mirroring conversation_store.py's pattern exactly. The messages themselves
live in the LangGraph checkpointer (data/agent_checkpoints.sqlite, keyed by
thread_id = this chat's id) - see agent_orchestrator.py's chat_message()/
get_chat_history(). This store only tracks id/title/timestamps, same
"index vs. execution state" split as agent_run_store.py.

Layout: data/agent_chats/<persona_id>/<chat_id>.json. Chat mode is
persona-only (not available under "General" - see AgentWorkspace.jsx), so
unlike agent_run_store there's no "__none__" persona case to handle.

Deleting a persona does NOT cascade-delete its chats (matches
agent_run_store's runs, not agent_skill_store's skills) - chats are history,
not configuration; they're left on disk, orphaned but not destroyed, same
as a deleted persona's task runs.
"""
import json
import os
import re
import uuid
import datetime

from config import Config


def _chats_dir(persona_id):
    safe_id = re.sub(r'[^a-fA-F0-9-]', '', persona_id)
    path = os.path.join(os.getcwd(), Config.DATA_DIR, "agent_chats", safe_id)
    os.makedirs(path, exist_ok=True)
    return path


def _path_for(persona_id, chat_id):
    safe_id = re.sub(r'[^a-fA-F0-9-]', '', chat_id)
    return os.path.join(_chats_dir(persona_id), f"{safe_id}.json")


def _make_title(first_message):
    title = first_message.strip().replace('\n', ' ')
    return title[:50] + ('...' if len(title) > 50 else '')


def list_chats(persona_id):
    """Summaries (id, title, updated_at), newest first."""
    summaries = []
    for filename in os.listdir(_chats_dir(persona_id)):
        if not filename.endswith('.json'):
            continue
        try:
            with open(os.path.join(_chats_dir(persona_id), filename)) as f:
                data = json.load(f)
            summaries.append({
                "id": data["id"],
                "title": data.get("title", "Untitled"),
                "updated_at": data.get("updated_at", ""),
            })
        except (json.JSONDecodeError, KeyError, OSError):
            continue
    summaries.sort(key=lambda c: c["updated_at"], reverse=True)
    return summaries


def create_chat(persona_id, first_message):
    now = datetime.datetime.utcnow().isoformat() + "Z"
    chat = {
        "id": str(uuid.uuid4()),
        "persona_id": persona_id,
        "title": _make_title(first_message),
        "created_at": now,
        "updated_at": now,
    }
    with open(_path_for(persona_id, chat["id"]), "w") as f:
        json.dump(chat, f, indent=2)
    return chat


def touch(persona_id, chat_id):
    """Bump updated_at after a new message, so the sidebar list re-sorts by
    recency (mirrors conversation_store.update_messages' side effect)."""
    path = _path_for(persona_id, chat_id)
    if not os.path.exists(path):
        raise FileNotFoundError(f"Chat {chat_id} not found")
    with open(path) as f:
        chat = json.load(f)
    chat["updated_at"] = datetime.datetime.utcnow().isoformat() + "Z"
    with open(path, "w") as f:
        json.dump(chat, f, indent=2)
    return chat


def delete_chat(persona_id, chat_id):
    path = _path_for(persona_id, chat_id)
    if not os.path.exists(path):
        return False
    os.remove(path)
    return True

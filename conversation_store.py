"""Conversation persistence: one JSON file per conversation under Config.CONVERSATIONS_DIR.

Each file is self-contained (id, title, timestamps, full message list), which
keeps the format simple and makes each conversation trivially batch-loadable
into an external store (e.g. a vector store) later without a migration step.
"""
import json
import os
import re
import uuid
import datetime

from config import Config


def _conversations_dir():
    path = os.path.join(os.getcwd(), Config.CONVERSATIONS_DIR)
    os.makedirs(path, exist_ok=True)
    return path


def _path_for(conversation_id):
    # conversation_id is always a uuid4 we generated - safe to use directly,
    # but strip anything that isn't hex/hyphen as a defensive measure against
    # path traversal from a malformed id reaching here.
    safe_id = re.sub(r'[^a-fA-F0-9-]', '', conversation_id)
    return os.path.join(_conversations_dir(), f"{safe_id}.json")


def _make_title(first_message):
    title = first_message.strip().replace('\n', ' ')
    return title[:50] + ('...' if len(title) > 50 else '')


def list_conversations():
    """Return summaries (id, title, updated_at) of all conversations, newest first."""
    summaries = []
    for filename in os.listdir(_conversations_dir()):
        if not filename.endswith('.json'):
            continue
        try:
            with open(os.path.join(_conversations_dir(), filename)) as f:
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


def get_conversation(conversation_id):
    """Return the full conversation dict, or None if it doesn't exist."""
    path = _path_for(conversation_id)
    if not os.path.exists(path):
        return None
    with open(path) as f:
        return json.load(f)


def create_conversation(first_message):
    """Create a new conversation seeded with a title derived from the first message."""
    now = datetime.datetime.utcnow().isoformat() + "Z"
    conversation = {
        "id": str(uuid.uuid4()),
        "title": _make_title(first_message),
        "created_at": now,
        "updated_at": now,
        "messages": [],
    }
    with open(_path_for(conversation["id"]), "w") as f:
        json.dump(conversation, f, indent=2)
    return conversation


def update_messages(conversation_id, messages):
    """Overwrite a conversation's message list and bump updated_at."""
    conversation = get_conversation(conversation_id)
    if conversation is None:
        raise FileNotFoundError(f"Conversation {conversation_id} not found")

    conversation["messages"] = messages
    conversation["updated_at"] = datetime.datetime.utcnow().isoformat() + "Z"
    with open(_path_for(conversation_id), "w") as f:
        json.dump(conversation, f, indent=2)
    return conversation


def delete_conversation(conversation_id):
    """Delete a conversation file. Returns True if it existed."""
    path = _path_for(conversation_id)
    if not os.path.exists(path):
        return False
    os.remove(path)
    return True

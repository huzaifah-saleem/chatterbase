"""Portable agent export/import: a persona's definition (name, tagline,
emoji, color, database-binding hint, expertise prompt) plus its
user-authored skills, as one importable JSON file - a real marketplace
across installs/teammates (see the phase-5 roadmap's "Agent import/export"
item). A single JSON file, not a zip: everything here is already plain
text, so a zip would only add complexity without adding capability.

The auto-generated database-knowledge skill (knowledge_sync.py) is
deliberately EXCLUDED from export: its body is a schema snapshot (table
list + DDL) of one specific live database, and importing that into a
different environment/instance would present someone else's schema as
settled fact instead of what it actually is - stale or simply wrong. The
persona's own `database` name string still travels (a cheap, honest hint
of what it was bound to), but re-syncing knowledge against the importing
environment's own database is left to whoever imports it.
"""
import agent_persona_store
import agent_skill_store
from knowledge_sync import KNOWLEDGE_SKILL_SLUG

EXPORT_KIND = "persona"
EXPORT_VERSION = 1


def export_persona(persona_id):
    persona = agent_persona_store.get_persona(persona_id)
    if persona is None:
        raise KeyError(f"Persona {persona_id} not found")
    skills = [
        agent_skill_store.get_skill(persona_id, s["slug"])
        for s in agent_skill_store.list_skills(persona_id)
        if s["slug"] != KNOWLEDGE_SKILL_SLUG
    ]
    return {
        "chatterbase_export": EXPORT_KIND,
        "version": EXPORT_VERSION,
        "persona": {
            "name": persona["name"],
            "expertise_prompt": persona.get("expertise_prompt", ""),
            "tagline": persona.get("tagline", ""),
            "emoji": persona.get("emoji", ""),
            "color": persona.get("color", ""),
            "database": persona.get("database", ""),
        },
        "skills": [{"name": s["name"], "description": s["description"], "body": s["body"]} for s in skills],
    }


def import_persona(payload):
    """Create a brand-new persona (fresh id, never overwrites an existing
    one) from an exported blob. A skill name that collides with another
    already in the same payload just keeps the first and skips the rest -
    acceptable since this is importing someone else's already-curated set,
    not merging into an existing persona's own skills."""
    if not isinstance(payload, dict) or payload.get("chatterbase_export") != EXPORT_KIND:
        raise ValueError("Not a Chatterbase agent export file")
    p = payload.get("persona") or {}
    name = (p.get("name") or "").strip()
    if not name:
        raise ValueError("Export is missing a persona name")
    persona = agent_persona_store.create_persona(
        name=name,
        expertise_prompt=p.get("expertise_prompt", ""),
        tagline=p.get("tagline", ""),
        emoji=p.get("emoji", ""),
        color=p.get("color", ""),
        database=p.get("database", ""),
    )
    for skill in payload.get("skills") or []:
        skill_name = (skill.get("name") or "").strip()
        if not skill_name:
            continue
        try:
            agent_skill_store.create_skill(persona["id"], skill_name, skill.get("description", ""), skill.get("body", ""))
        except FileExistsError:
            pass
    return persona

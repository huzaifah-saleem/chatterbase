"""Agent skills: markdown playbooks scoped to one persona, written directly
in the on-disk shape deepagents' own SkillsMiddleware expects - a directory
per skill containing a SKILL.md with YAML frontmatter (name, description)
plus a markdown body - so agent_orchestrator.py's FilesystemBackend can load
them with no translation layer. See deepagents/middleware/skills.py for the
format this mirrors.

Layout: data/agent_skills/<persona_id>/<slug>/SKILL.md
"""
import os
import re
import shutil

import yaml

from config import Config

_FRONTMATTER_RE = re.compile(r'^---\s*\n(.*?)\n---\s*\n?(.*)$', re.DOTALL)


def _skills_root():
    path = os.path.join(os.getcwd(), Config.DATA_DIR, "agent_skills")
    os.makedirs(path, exist_ok=True)
    return path


def _persona_dir(persona_id):
    safe_id = re.sub(r'[^a-fA-F0-9-]', '', persona_id)
    path = os.path.join(_skills_root(), safe_id)
    os.makedirs(path, exist_ok=True)
    return path


def _slugify(name):
    """Lowercase alphanumeric-and-hyphens, matching the Agent Skills spec's
    name rule (max 64 chars)."""
    slug = re.sub(r'[^a-z0-9]+', '-', name.lower()).strip('-')
    return slug[:64] or "skill"


def _skill_path(persona_id, slug):
    safe_slug = re.sub(r'[^a-z0-9-]', '', slug)
    return os.path.join(_persona_dir(persona_id), safe_slug, "SKILL.md")


def _parse(raw_markdown):
    match = _FRONTMATTER_RE.match(raw_markdown)
    if not match:
        return {"name": "", "description": ""}, raw_markdown
    frontmatter = yaml.safe_load(match.group(1)) or {}
    body = match.group(2)
    return frontmatter, body


def list_skills(persona_id):
    """Summaries (slug, name, description), by directory name."""
    persona_dir = _persona_dir(persona_id)
    summaries = []
    for slug in sorted(os.listdir(persona_dir)):
        skill_md = os.path.join(persona_dir, slug, "SKILL.md")
        if not os.path.isfile(skill_md):
            continue
        try:
            with open(skill_md) as f:
                frontmatter, _ = _parse(f.read())
            summaries.append({
                "slug": slug,
                "name": frontmatter.get("name", slug),
                "description": frontmatter.get("description", ""),
            })
        except (OSError, yaml.YAMLError):
            continue
    return summaries


def get_skill(persona_id, slug):
    """Full record: {slug, name, description, body}, or None if missing."""
    path = _skill_path(persona_id, slug)
    if not os.path.exists(path):
        return None
    with open(path) as f:
        frontmatter, body = _parse(f.read())
    return {
        "slug": slug,
        "name": frontmatter.get("name", slug),
        "description": frontmatter.get("description", ""),
        "body": body.strip(),
    }


def _write(persona_id, slug, description, body):
    path = _skill_path(persona_id, slug)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    frontmatter = yaml.safe_dump({"name": slug, "description": description}, sort_keys=False).strip()
    with open(path, "w") as f:
        f.write(f"---\n{frontmatter}\n---\n\n{body.strip()}\n")
    return get_skill(persona_id, slug)


def create_skill(persona_id, name, description, body):
    """Create a new skill. The Agent Skills spec requires frontmatter "name"
    itself to be lowercase-alphanumeric-with-hyphens (deepagents warns
    otherwise), so a human-typed "Churn Playbook" is normalized to
    "churn-playbook" and used as both the slug and the stored name - this
    becomes the skill's permanent identifier, not just its directory name."""
    slug = _slugify(name)
    if os.path.exists(os.path.dirname(_skill_path(persona_id, slug))):
        raise FileExistsError(f'A skill named "{slug}" already exists for this agent')
    return _write(persona_id, slug, description, body)


def update_skill(persona_id, slug, description=None, body=None):
    """Update a skill's description and/or body in place. The identifier
    (slug/name) is immutable once created - matches how personas and other
    records in this app keep a stable id while their other fields change."""
    existing = get_skill(persona_id, slug)
    if existing is None:
        raise KeyError(f"Skill {slug} not found")
    return _write(
        persona_id, slug,
        description if description is not None else existing["description"],
        body if body is not None else existing["body"],
    )


def delete_skill(persona_id, slug):
    path = _skill_path(persona_id, slug)
    skill_dir = os.path.dirname(path)
    if not os.path.exists(skill_dir):
        return False
    shutil.rmtree(skill_dir)
    return True


def delete_all_for_persona(persona_id):
    """Called when a persona itself is deleted, so its skill files don't
    linger unreachable on disk."""
    persona_dir = _persona_dir(persona_id)
    if os.path.exists(persona_dir):
        shutil.rmtree(persona_dir)

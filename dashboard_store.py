"""Dashboards: named collections of pinned charts, one file per dashboard
under data/dashboards/ - mirrors conversation_store.py's pattern exactly, so
dashboards behave as a genuinely separate module alongside chats rather than
a single global list.

A pinned chart stores exactly what renderChart() in index.html needs to
redraw it (type/title/labels/data/colors) - it's a snapshot of that one
result, not a live query, so it keeps working even if the source
conversation is later deleted or the underlying data changes.
"""
import json
import os
import re
import uuid
import datetime

from config import Config


def _dashboards_dir():
    path = os.path.join(os.getcwd(), Config.DATA_DIR, "dashboards")
    os.makedirs(path, exist_ok=True)
    return path


def _path_for(dashboard_id):
    # dashboard_id is always a uuid4 we generated - safe to use directly, but
    # strip anything that isn't hex/hyphen as a defensive measure against
    # path traversal from a malformed id reaching here.
    safe_id = re.sub(r'[^a-fA-F0-9-]', '', dashboard_id)
    return os.path.join(_dashboards_dir(), f"{safe_id}.json")


def _migrate_legacy_flat_file():
    """One-time migration: the first version of this feature kept a single
    flat data/dashboard.json list of charts with no concept of separate
    named dashboards. If that file exists and nothing has been migrated yet,
    fold it into one "Default" dashboard, then rename it out of the way so
    this doesn't re-run."""
    legacy_path = os.path.join(os.getcwd(), Config.DATA_DIR, "dashboard.json")
    if not os.path.exists(legacy_path):
        return
    try:
        with open(legacy_path) as f:
            legacy_charts = json.load(f)
    except (json.JSONDecodeError, OSError):
        legacy_charts = []

    if legacy_charts:
        create_dashboard("Default", charts=legacy_charts)
    os.rename(legacy_path, legacy_path + ".migrated")


def list_dashboards():
    """Summaries (id, name, updated_at, chart_count), newest first."""
    _migrate_legacy_flat_file()
    summaries = []
    for filename in os.listdir(_dashboards_dir()):
        if not filename.endswith('.json'):
            continue
        try:
            with open(os.path.join(_dashboards_dir(), filename)) as f:
                data = json.load(f)
            summaries.append({
                "id": data["id"],
                "name": data.get("name", "Untitled"),
                "updated_at": data.get("updated_at", ""),
                "chart_count": len(data.get("charts", [])),
            })
        except (json.JSONDecodeError, KeyError, OSError):
            continue
    summaries.sort(key=lambda d: d["updated_at"], reverse=True)
    return summaries


def get_dashboard(dashboard_id):
    """Full dashboard record including its charts, or None if it doesn't exist."""
    path = _path_for(dashboard_id)
    if not os.path.exists(path):
        return None
    with open(path) as f:
        return json.load(f)


def create_dashboard(name, charts=None):
    now = datetime.datetime.utcnow().isoformat() + "Z"
    dashboard = {
        "id": str(uuid.uuid4()),
        "name": name,
        "created_at": now,
        "updated_at": now,
        "charts": charts or [],
    }
    with open(_path_for(dashboard["id"]), "w") as f:
        json.dump(dashboard, f, indent=2)
    return dashboard


def delete_dashboard(dashboard_id):
    path = _path_for(dashboard_id)
    if not os.path.exists(path):
        return False
    os.remove(path)
    return True


def _save(dashboard):
    dashboard["updated_at"] = datetime.datetime.utcnow().isoformat() + "Z"
    with open(_path_for(dashboard["id"]), "w") as f:
        json.dump(dashboard, f, indent=2)


def pin_chart(dashboard_id, title, chart_type, labels, data, colors=None):
    dashboard = get_dashboard(dashboard_id)
    if dashboard is None:
        raise FileNotFoundError(f"Dashboard {dashboard_id} not found")
    entry = {
        "id": str(uuid.uuid4()),
        "title": title,
        "type": chart_type,
        "labels": labels,
        "data": data,
        "colors": colors,
    }
    dashboard["charts"].append(entry)
    _save(dashboard)
    return entry


def update_chart_type(dashboard_id, chart_id, new_type):
    """Persist a type switch made from the dashboard view, so it doesn't
    reset back to the originally-pinned type next time it's opened."""
    dashboard = get_dashboard(dashboard_id)
    if dashboard is None:
        raise FileNotFoundError(f"Dashboard {dashboard_id} not found")
    for c in dashboard["charts"]:
        if c["id"] == chart_id:
            c["type"] = new_type
            _save(dashboard)
            return c
    raise KeyError(f"Chart {chart_id} not found in dashboard {dashboard_id}")


def unpin_chart(dashboard_id, chart_id):
    dashboard = get_dashboard(dashboard_id)
    if dashboard is None:
        raise FileNotFoundError(f"Dashboard {dashboard_id} not found")
    remaining = [c for c in dashboard["charts"] if c["id"] != chart_id]
    if len(remaining) == len(dashboard["charts"]):
        return False
    dashboard["charts"] = remaining
    _save(dashboard)
    return True

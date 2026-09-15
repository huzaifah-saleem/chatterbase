"""Agent-authored reports: a title plus an ordered list of blocks, saved for
later - mirrors dashboard_store.py's file-per-record pattern. A report's
blocks reuse the exact {type: "text"|"table"|"chart"} shape Blocks.jsx
already renders everywhere else (chat turns, task results, dashboards), so
no new frontend rendering code is needed to display one - only a new place
to save/list/view/export them (see report_export.py for export).
"""
import json
import os
import re
import uuid
import datetime

from config import Config


def _reports_dir():
    path = os.path.join(os.getcwd(), Config.DATA_DIR, "reports")
    os.makedirs(path, exist_ok=True)
    return path


def _path_for(report_id):
    safe_id = re.sub(r'[^a-fA-F0-9-]', '', report_id)
    return os.path.join(_reports_dir(), f"{safe_id}.json")


def list_reports(persona_id=None):
    """Summaries (id, title, persona_id, chart_count, updated_at), newest
    first. persona_id filters to reports authored by that persona when
    given; omit it to list every report."""
    summaries = []
    for filename in os.listdir(_reports_dir()):
        if not filename.endswith('.json'):
            continue
        try:
            with open(os.path.join(_reports_dir(), filename)) as f:
                data = json.load(f)
            if persona_id is not None and data.get("persona_id") != persona_id:
                continue
            blocks = data.get("blocks", [])
            summaries.append({
                "id": data["id"],
                "title": data.get("title", "Untitled"),
                "persona_id": data.get("persona_id"),
                "chart_count": sum(1 for b in blocks if b.get("type") == "chart"),
                "updated_at": data.get("updated_at", ""),
            })
        except (json.JSONDecodeError, KeyError, OSError):
            continue
    summaries.sort(key=lambda r: r["updated_at"], reverse=True)
    return summaries


def get_report(report_id):
    """Full report record including its blocks, or None if it doesn't exist."""
    path = _path_for(report_id)
    if not os.path.exists(path):
        return None
    with open(path) as f:
        return json.load(f)


def create_report(title, blocks, persona_id=None):
    now = datetime.datetime.utcnow().isoformat() + "Z"
    report = {
        "id": str(uuid.uuid4()),
        "title": title,
        "persona_id": persona_id,
        "blocks": blocks,
        "created_at": now,
        "updated_at": now,
    }
    with open(_path_for(report["id"]), "w") as f:
        json.dump(report, f, indent=2)
    return report


def rename_report(report_id, title):
    report = get_report(report_id)
    if report is None:
        raise FileNotFoundError(f"Report {report_id} not found")
    report["title"] = title
    report["updated_at"] = datetime.datetime.utcnow().isoformat() + "Z"
    with open(_path_for(report_id), "w") as f:
        json.dump(report, f, indent=2)
    return report


def delete_report(report_id):
    path = _path_for(report_id)
    if not os.path.exists(path):
        return False
    os.remove(path)
    return True

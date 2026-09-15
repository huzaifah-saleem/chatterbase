"""
Chatterbase - Chat with Your Data
A Flask-based web interface for interacting with Teradata via MCP using LLMs
"""
from flask import Flask, request, jsonify, send_from_directory, Response
from werkzeug.utils import safe_join
from flask_cors import CORS
import base64
import datetime
import json
import os
import re

from config import Config
from mcp_client import run_async, get_mcp_tools, get_server_statuses
from llm_providers import LLMProvider, LocalLLMProvider, GeminiProvider, OpenAIProvider, NvidiaNIMProvider, LMStudioProvider
from chat_handler import process_chat_request
import conversation_store
import mcp_registry
import llm_registry
import dashboard_store
import agent_run_store
import agent_persona_store
import agent_skill_store
import agent_chat_store
import agent_orchestrator
import knowledge_sync
import observability
import report_store
import report_export
import agent_export

# Initialize Flask app. Static assets now come from the built React SPA
# (frontend/dist, see frontend/vite.config.js + Dockerfile's node build
# stage) rather than templates/index.html - that file and static/ are kept
# on disk, unused, until the Phase-5 parity gate passes (see the phase-5
# plan), at which point they're deleted outright.
#
# static_folder=None disables Flask's automatic static route - it would
# otherwise register /<path:filename> itself (since static_url_path=''),
# which 404s directly on any non-existent path instead of falling through
# to the spa() catch-all below. Both static assets (JS/CSS bundles) and the
# index.html fallback for client-side routes are served from spa() instead.
app = Flask(__name__, static_folder=None)
CORS(app)

# Apply the persisted active LLM profile on top of .env's defaults, so a
# restart honors whatever was last activated/edited in the UI rather than
# silently reverting to .env every time.
llm_registry.apply_active_profile()


# ============ API Routes ============


@app.route("/api/llm/profiles", methods=["GET"])
def list_llm_profiles():
    """List all saved LLM profiles and which one is active"""
    try:
        return jsonify({"profiles": llm_registry.list_profiles(), "active_id": llm_registry.get_active_id()})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/llm/profiles", methods=["POST"])
def add_llm_profile():
    """Add a new LLM profile"""
    try:
        data = request.json
        name = (data.get("name") or "").strip()
        provider_type = data.get("provider_type")
        if not name or provider_type not in ("local_llm", "gemini", "openai", "nvidia_nim", "lm_studio"):
            return jsonify({"error": "A name and a valid provider_type are required"}), 400
        profile = llm_registry.add_profile(
            name, provider_type,
            url=data.get("url", ""), model=data.get("model", ""), api_key=data.get("api_key", "")
        )
        return jsonify(profile)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/llm/profiles/<profile_id>", methods=["PUT"])
def update_llm_profile(profile_id):
    """Update a profile's fields (re-applied immediately if it's the active one)"""
    try:
        data = request.json
        profile = llm_registry.update_profile(
            profile_id,
            name=data.get("name"), provider_type=data.get("provider_type"),
            url=data.get("url"), model=data.get("model"), api_key=data.get("api_key"),
        )
        return jsonify(profile)
    except KeyError as e:
        return jsonify({"error": str(e)}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/llm/profiles/<profile_id>", methods=["DELETE"])
def delete_llm_profile(profile_id):
    """Delete a saved LLM profile"""
    try:
        existed = llm_registry.delete_profile(profile_id)
        if not existed:
            return jsonify({"error": "Profile not found"}), 404
        return jsonify({"status": "ok"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/llm/profiles/<profile_id>/activate", methods=["POST"])
def activate_llm_profile(profile_id):
    """Make a profile the active one used for chat calls"""
    try:
        profile = llm_registry.set_active(profile_id)
        return jsonify(profile)
    except KeyError as e:
        return jsonify({"error": str(e)}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/mcp/health")
def mcp_health():
    """Per-server MCP health, plus an aggregate tool count across all of them"""
    try:
        servers = run_async(get_server_statuses())
        total_tools = sum(s.get("tools_count", 0) for s in servers)
        return jsonify({"servers": servers, "total_tools": total_tools})
    except Exception as e:
        print(f"[MCP Health] Error: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/api/mcp/tools")
def get_tools():
    """Get available MCP tools, aggregated across all enabled servers"""
    try:
        tools = run_async(get_mcp_tools())
        return jsonify({"tools": tools})
    except Exception as e:
        print(f"[MCP Tools] Error: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/api/mcp/servers", methods=["GET"])
def list_mcp_servers():
    """List all configured MCP servers"""
    try:
        return jsonify({"servers": mcp_registry.list_servers()})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/mcp/servers", methods=["POST"])
def add_mcp_server():
    """Add a new MCP server"""
    try:
        data = request.json
        name = (data.get("name") or "").strip()
        url = (data.get("url") or "").strip()
        if not name or not url:
            return jsonify({"error": "Both name and url are required"}), 400
        server = mcp_registry.add_server(name, url)
        return jsonify(server)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/mcp/servers/<server_id>", methods=["PUT"])
def update_mcp_server(server_id):
    """Update a server's name/url/enabled state"""
    try:
        data = request.json
        server = mcp_registry.update_server(
            server_id,
            name=data.get("name"),
            url=data.get("url"),
            enabled=data.get("enabled"),
        )
        return jsonify(server)
    except KeyError as e:
        return jsonify({"error": str(e)}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/mcp/servers/<server_id>", methods=["DELETE"])
def delete_mcp_server(server_id):
    """Delete a configured MCP server"""
    try:
        existed = mcp_registry.delete_server(server_id)
        if not existed:
            return jsonify({"error": "Server not found"}), 404
        return jsonify({"status": "ok"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/mcp/servers/import", methods=["POST"])
def import_mcp_servers():
    """Bulk-import servers from a pasted Claude-Desktop-style mcpServers JSON blob"""
    try:
        raw_text = request.json.get("json", "")
        result = mcp_registry.import_mcp_servers_json(raw_text)
        return jsonify(result)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/llm/health")
def llm_health():
    """Check LLM provider health"""
    try:
        if Config.LLM_PROVIDER == "local_llm":
            return jsonify(LocalLLMProvider.health_check())
        elif Config.LLM_PROVIDER == "gemini":
            return jsonify(GeminiProvider.health_check())
        elif Config.LLM_PROVIDER == "openai":
            return jsonify(OpenAIProvider.health_check())
        elif Config.LLM_PROVIDER == "nvidia_nim":
            return jsonify(NvidiaNIMProvider.health_check())
        elif Config.LLM_PROVIDER == "lm_studio":
            return jsonify(LMStudioProvider.health_check())
        else:
            return jsonify({"error": f"Unknown provider: {Config.LLM_PROVIDER}"}), 500
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/llm/models")
def llm_models():
    """List models available from an OpenAI-compatible local server (LM Studio, etc.)"""
    try:
        url = request.args.get("url")
        models = LMStudioProvider.list_models(url)
        return jsonify({"models": models})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/conversations", methods=["GET"])
def list_conversations():
    """List all saved conversations (summary only), newest first"""
    try:
        return jsonify({"conversations": conversation_store.list_conversations()})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/conversations", methods=["POST"])
def create_conversation():
    """Create a new conversation, titled from the first message"""
    try:
        data = request.json
        first_message = data.get("first_message", "New Conversation")
        conversation = conversation_store.create_conversation(first_message)
        return jsonify(conversation)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/conversations/<conversation_id>", methods=["GET"])
def get_conversation(conversation_id):
    """Get a single conversation's full message history"""
    try:
        conversation = conversation_store.get_conversation(conversation_id)
        if conversation is None:
            return jsonify({"error": "Conversation not found"}), 404
        return jsonify(conversation)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/conversations/<conversation_id>", methods=["PUT"])
def update_conversation(conversation_id):
    """Replace a conversation's message list (called after each exchange)"""
    try:
        data = request.json
        messages = data.get("messages", [])
        conversation = conversation_store.update_messages(conversation_id, messages)
        return jsonify(conversation)
    except FileNotFoundError as e:
        return jsonify({"error": str(e)}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/conversations/<conversation_id>/rename", methods=["PUT"])
def rename_conversation(conversation_id):
    try:
        title = (request.json.get("title") or "").strip()
        if not title:
            return jsonify({"error": "title is required"}), 400
        return jsonify(conversation_store.rename_conversation(conversation_id, title))
    except FileNotFoundError as e:
        return jsonify({"error": str(e)}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/conversations/<conversation_id>", methods=["DELETE"])
def delete_conversation(conversation_id):
    """Delete a conversation"""
    try:
        existed = conversation_store.delete_conversation(conversation_id)
        if not existed:
            return jsonify({"error": "Conversation not found"}), 404
        return jsonify({"status": "ok"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/dashboards", methods=["GET"])
def list_dashboards():
    """List all dashboards (summary only), newest first"""
    try:
        return jsonify({"dashboards": dashboard_store.list_dashboards()})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/dashboards", methods=["POST"])
def create_dashboard():
    """Create a new, empty, named dashboard"""
    try:
        name = (request.json.get("name") or "").strip()
        if not name:
            return jsonify({"error": "A name is required"}), 400
        return jsonify(dashboard_store.create_dashboard(name))
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/dashboards/<dashboard_id>", methods=["GET"])
def get_dashboard(dashboard_id):
    """Get one dashboard's full record, including its charts"""
    try:
        dashboard = dashboard_store.get_dashboard(dashboard_id)
        if dashboard is None:
            return jsonify({"error": "Dashboard not found"}), 404
        return jsonify(dashboard)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/dashboards/<dashboard_id>/rename", methods=["PUT"])
def rename_dashboard(dashboard_id):
    try:
        name = (request.json.get("name") or "").strip()
        if not name:
            return jsonify({"error": "name is required"}), 400
        return jsonify(dashboard_store.rename_dashboard(dashboard_id, name))
    except FileNotFoundError as e:
        return jsonify({"error": str(e)}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/dashboards/<dashboard_id>", methods=["DELETE"])
def delete_dashboard(dashboard_id):
    """Delete a dashboard and everything pinned to it"""
    try:
        existed = dashboard_store.delete_dashboard(dashboard_id)
        if not existed:
            return jsonify({"error": "Dashboard not found"}), 404
        return jsonify({"status": "ok"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/dashboards/<dashboard_id>/layout", methods=["PUT"])
def update_dashboard_layout(dashboard_id):
    """Persist the chart grid arrangement after a drag/resize in edit mode."""
    try:
        layout = request.json.get("layout")
        if not isinstance(layout, list):
            return jsonify({"error": "layout must be a list"}), 400
        return jsonify(dashboard_store.update_layout(dashboard_id, layout))
    except FileNotFoundError as e:
        return jsonify({"error": str(e)}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/dashboards/<dashboard_id>/comments", methods=["POST"])
def add_dashboard_comment(dashboard_id):
    try:
        text = (request.json.get("text") or "").strip()
        if not text:
            return jsonify({"error": "text is required"}), 400
        author = request.json.get("author") or ""
        return jsonify(dashboard_store.add_comment(dashboard_id, text, author))
    except FileNotFoundError as e:
        return jsonify({"error": str(e)}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/dashboards/<dashboard_id>/comments/<comment_id>", methods=["DELETE"])
def delete_dashboard_comment(dashboard_id, comment_id):
    try:
        existed = dashboard_store.delete_comment(dashboard_id, comment_id)
        if not existed:
            return jsonify({"error": "Comment not found"}), 404
        return jsonify({"status": "ok"})
    except FileNotFoundError as e:
        return jsonify({"error": str(e)}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/dashboards/<dashboard_id>/charts", methods=["POST"])
def pin_dashboard_chart(dashboard_id):
    """Pin a chart into this dashboard (a snapshot of type/labels/data/colors, not a live query)"""
    try:
        data = request.json
        entry = dashboard_store.pin_chart(
            dashboard_id,
            title=data.get("title", "Chart"),
            chart_type=data.get("type", "bar"),
            labels=data.get("labels"),
            data=data.get("data"),
            colors=data.get("colors"),
            points=data.get("points"),
            flows=data.get("flows"),
        )
        return jsonify(entry)
    except FileNotFoundError as e:
        return jsonify({"error": str(e)}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/dashboards/<dashboard_id>/charts/<chart_id>", methods=["PUT"])
def update_dashboard_chart(dashboard_id, chart_id):
    """Persist a type switch made from the dashboard view"""
    try:
        new_type = request.json.get("type")
        if not new_type:
            return jsonify({"error": "type is required"}), 400
        entry = dashboard_store.update_chart_type(dashboard_id, chart_id, new_type)
        return jsonify(entry)
    except (FileNotFoundError, KeyError) as e:
        return jsonify({"error": str(e)}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/dashboards/<dashboard_id>/charts/<chart_id>", methods=["DELETE"])
def unpin_dashboard_chart(dashboard_id, chart_id):
    """Unpin a chart from this dashboard"""
    try:
        existed = dashboard_store.unpin_chart(dashboard_id, chart_id)
        if not existed:
            return jsonify({"error": "Chart not found"}), 404
        return jsonify({"status": "ok"})
    except FileNotFoundError as e:
        return jsonify({"error": str(e)}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/reports", methods=["GET"])
def list_reports():
    """List saved reports (summary only), newest first. ?persona_id= filters
    to reports authored by one persona."""
    try:
        return jsonify({"reports": report_store.list_reports(request.args.get("persona_id"))})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/reports/<report_id>", methods=["GET"])
def get_report(report_id):
    try:
        report = report_store.get_report(report_id)
        if report is None:
            return jsonify({"error": "Report not found"}), 404
        return jsonify(report)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/reports/<report_id>/rename", methods=["PUT"])
def rename_report(report_id):
    try:
        title = (request.json.get("title") or "").strip()
        if not title:
            return jsonify({"error": "title is required"}), 400
        return jsonify(report_store.rename_report(report_id, title))
    except FileNotFoundError as e:
        return jsonify({"error": str(e)}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/reports/<report_id>", methods=["DELETE"])
def delete_report(report_id):
    try:
        existed = report_store.delete_report(report_id)
        if not existed:
            return jsonify({"error": "Report not found"}), 404
        return jsonify({"status": "ok"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/reports/<report_id>/export", methods=["GET"])
def export_report(report_id):
    """Download the report as a standalone file - ?format=html (default,
    genuinely interactive - Chart.js/Leaflet load from CDN) or ?format=md
    (plain data, charts become a small table instead of an image)."""
    try:
        report = report_store.get_report(report_id)
        if report is None:
            return jsonify({"error": "Report not found"}), 404
        fmt = request.args.get("format", "html")
        safe_name = re.sub(r'[^A-Za-z0-9_-]+', '-', report.get("title", "report")).strip('-') or "report"
        if fmt == "md":
            body, mimetype, filename = report_export.to_markdown(report), "text/markdown", f"{safe_name}.md"
        else:
            body, mimetype, filename = report_export.to_html(report), "text/html", f"{safe_name}.html"
        return Response(body, mimetype=mimetype, headers={"Content-Disposition": f'attachment; filename="{filename}"'})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/agent/personas", methods=["GET"])
def list_agent_personas():
    """List all saved agent personas, newest first"""
    try:
        return jsonify({"personas": agent_persona_store.list_personas()})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/agent/personas", methods=["POST"])
def create_agent_persona():
    """Create a new agent persona: a name plus a standing domain-expertise
    prompt that flavors the data-agent for any run started under it. tagline/
    emoji/color are display-only card fields for the marketplace grid;
    database optionally binds it for knowledge sync (see knowledge_sync.py)."""
    try:
        data = request.json
        name = (data.get("name") or "").strip()
        expertise_prompt = (data.get("expertise_prompt") or "").strip()
        if not name or not expertise_prompt:
            return jsonify({"error": "Both name and expertise_prompt are required"}), 400
        return jsonify(agent_persona_store.create_persona(
            name, expertise_prompt,
            tagline=(data.get("tagline") or "").strip(),
            emoji=(data.get("emoji") or "").strip(),
            color=(data.get("color") or "").strip(),
            database=(data.get("database") or "").strip(),
        ))
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/agent/personas/<persona_id>", methods=["PUT"])
def update_agent_persona(persona_id):
    """Rename a persona and/or edit its expertise prompt, card fields, or
    database binding in place."""
    try:
        data = request.json
        name = data.get("name")
        expertise_prompt = data.get("expertise_prompt")
        if name is not None:
            name = name.strip()
            if not name:
                return jsonify({"error": "name cannot be blank"}), 400
        if expertise_prompt is not None:
            expertise_prompt = expertise_prompt.strip()
            if not expertise_prompt:
                return jsonify({"error": "expertise_prompt cannot be blank"}), 400
        return jsonify(agent_persona_store.update_persona(
            persona_id, name=name, expertise_prompt=expertise_prompt,
            tagline=data.get("tagline"), emoji=data.get("emoji"), color=data.get("color"),
            database=data.get("database"),
        ))
    except KeyError as e:
        return jsonify({"error": str(e)}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/agent/personas/<persona_id>", methods=["DELETE"])
def delete_agent_persona(persona_id):
    """Delete a persona and its skills. Its past runs are left untouched
    (same as deleting a dashboard doesn't delete the conversations that fed
    it) - but skills are persona-owned configuration, not history, so they
    cascade-delete (matches how deleting a dashboard removes its charts)."""
    try:
        existed = agent_persona_store.delete_persona(persona_id)
        if not existed:
            return jsonify({"error": "Persona not found"}), 404
        agent_skill_store.delete_all_for_persona(persona_id)
        return jsonify({"status": "ok"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/agent/personas/<persona_id>/export", methods=["GET"])
def export_agent_persona(persona_id):
    """Download this agent as a portable JSON file - name/tagline/emoji/
    color/database hint plus its user-authored skills (not the
    auto-generated database-knowledge skill, and not its chat/run history -
    see agent_export.py for why). Importable into any Chatterbase instance."""
    try:
        payload = agent_export.export_persona(persona_id)
        safe_name = re.sub(r'[^A-Za-z0-9_-]+', '-', payload["persona"]["name"]).strip('-') or "agent"
        return Response(
            json.dumps(payload, indent=2),
            mimetype="application/json",
            headers={"Content-Disposition": f'attachment; filename="{safe_name}.chatterbase-agent.json"'},
        )
    except KeyError as e:
        return jsonify({"error": str(e)}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/agent/personas/import", methods=["POST"])
def import_agent_persona():
    """Create a new agent from a previously exported JSON file - always a
    fresh persona (new id), never overwrites an existing one."""
    try:
        persona = agent_export.import_persona(request.json)
        return jsonify(persona)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/agent/personas/<persona_id>/skills", methods=["GET"])
def list_agent_skills(persona_id):
    """List a persona's skills (name/description only, not the full body)"""
    try:
        return jsonify({"skills": agent_skill_store.list_skills(persona_id)})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/agent/personas/<persona_id>/skills", methods=["POST"])
def create_agent_skill(persona_id):
    """Create a new skill (markdown playbook) for a persona"""
    try:
        data = request.json
        name = (data.get("name") or "").strip()
        description = (data.get("description") or "").strip()
        body = data.get("body") or ""
        if not name or not description or not body.strip():
            return jsonify({"error": "name, description, and body are all required"}), 400
        return jsonify(agent_skill_store.create_skill(persona_id, name, description, body))
    except FileExistsError as e:
        return jsonify({"error": str(e)}), 409
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/agent/personas/<persona_id>/skills/<slug>", methods=["GET"])
def get_agent_skill(persona_id, slug):
    """Get one skill's full record (including body) for editing"""
    try:
        skill = agent_skill_store.get_skill(persona_id, slug)
        if skill is None:
            return jsonify({"error": "Skill not found"}), 404
        return jsonify(skill)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/agent/personas/<persona_id>/skills/<slug>", methods=["PUT"])
def update_agent_skill(persona_id, slug):
    """Update a skill's description and/or body. Its name/slug is immutable
    once created (see agent_skill_store.update_skill)."""
    try:
        data = request.json
        description = data.get("description")
        body = data.get("body")
        return jsonify(agent_skill_store.update_skill(persona_id, slug, description=description, body=body))
    except KeyError as e:
        return jsonify({"error": str(e)}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/agent/personas/<persona_id>/skills/<slug>", methods=["DELETE"])
def delete_agent_skill(persona_id, slug):
    try:
        existed = agent_skill_store.delete_skill(persona_id, slug)
        if not existed:
            return jsonify({"error": "Skill not found"}), 404
        return jsonify({"status": "ok"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/agent/personas/<persona_id>/chats", methods=["GET"])
def list_agent_chats(persona_id):
    """List a persona's chat threads (summary only), newest first"""
    try:
        return jsonify({"chats": agent_chat_store.list_chats(persona_id)})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/agent/personas/<persona_id>/chats", methods=["POST"])
def create_agent_chat(persona_id):
    """Start a new chat thread, titled from the first message, and get the
    agent's reply to it - multi-turn, ungated (see agent_orchestrator.chat_message)."""
    try:
        first_message = (request.json.get("first_message") or "").strip()
        if not first_message:
            return jsonify({"error": "first_message is required"}), 400
        chat = agent_chat_store.create_chat(persona_id, first_message)
        reply = agent_orchestrator.chat_message(chat["id"], first_message, persona_id)
        return jsonify({**chat, **reply})
    except Exception as e:
        print(f"[Agent Chat] Start error: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/api/agent/personas/<persona_id>/chats/<chat_id>", methods=["GET"])
def get_agent_chat(persona_id, chat_id):
    """Full turn-by-turn history of a chat thread, reconstructed from the
    LangGraph checkpointer - includes whether it's currently paused on a
    pending tool approval (see agent_orchestrator.get_chat_history)."""
    try:
        return jsonify(agent_orchestrator.get_chat_history(chat_id, persona_id))
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/agent/personas/<persona_id>/chats/<chat_id>/message", methods=["POST"])
def send_agent_chat_message(persona_id, chat_id):
    """Send one message in an existing chat thread and get the agent's reply
    - may come back "interrupted" (e.g. a run_python call pending approval)."""
    try:
        message = (request.json.get("message") or "").strip()
        if not message:
            return jsonify({"error": "message is required"}), 400
        reply = agent_orchestrator.chat_message(chat_id, message, persona_id)
        agent_chat_store.touch(persona_id, chat_id)
        return jsonify(reply)
    except FileNotFoundError as e:
        return jsonify({"error": str(e)}), 404
    except Exception as e:
        print(f"[Agent Chat] Message error: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/api/agent/personas/<persona_id>/chats/<chat_id>/resume", methods=["POST"])
def resume_agent_chat(persona_id, chat_id):
    """Resume a chat turn paused on a pending tool approval (e.g. run_python)."""
    try:
        decision = request.json.get("decision")
        if decision not in ("approve", "reject"):
            return jsonify({"error": "decision must be \"approve\" or \"reject\""}), 400
        reply = agent_orchestrator.resume_chat(chat_id, decision, persona_id)
        agent_chat_store.touch(persona_id, chat_id)
        return jsonify(reply)
    except Exception as e:
        print(f"[Agent Chat] Resume error: {e}")
        return jsonify({"error": str(e)}), 500


def _agent_chat_sse(work_fn):
    """SSE response wrapper for the streaming agent-chat routes below -
    mirrors chat_stream()'s thread+queue bridge (a background thread runs
    the async work and pushes events into a queue; this generator drains
    it as SSE frames), generalized for token/result event streams instead
    of just progress labels. work_fn(emit) does the real work, calling
    emit(event) for each event; any exception becomes one final "error"
    event, since the HTTP response is already committed to 200 by the time
    real processing starts - there's no way to report failure via status
    code once streaming has begun."""
    from flask import Response, stream_with_context
    import json as json_lib
    import queue
    import threading

    event_queue = queue.Queue()

    def run_processing():
        try:
            work_fn(event_queue.put)
            event_queue.put({"type": "done"})
        except Exception as e:
            print(f"[Agent Chat Stream] Error: {e}")
            event_queue.put({"type": "error", "message": str(e)})

    def generate():
        thread = threading.Thread(target=run_processing)
        thread.start()
        while True:
            event = event_queue.get()
            if event["type"] == "done":
                yield "data: [DONE]\n\n"
                break
            if event["type"] == "error":
                yield f"data: {json_lib.dumps({'type': 'error', 'data': {'error': event['message']}})}\n\n"
                break
            yield f"data: {json_lib.dumps(event)}\n\n"
        thread.join()

    return Response(
        stream_with_context(generate()),
        mimetype='text/event-stream',
        headers={'Cache-Control': 'no-cache', 'X-Accel-Buffering': 'no'},
    )


@app.route("/api/agent/personas/<persona_id>/chats/stream", methods=["POST"])
def create_agent_chat_stream(persona_id):
    """Streaming variant of create_agent_chat: same effect (new chat thread,
    titled from the first message), but the reply arrives as SSE token/
    result events instead of one blocking JSON response."""
    first_message = (request.json.get("first_message") or "").strip()
    if not first_message:
        return jsonify({"error": "first_message is required"}), 400
    chat = agent_chat_store.create_chat(persona_id, first_message)

    def work(emit):
        emit({"type": "chat", "data": chat})
        agent_orchestrator.chat_message_stream(chat["id"], first_message, persona_id, emit)

    return _agent_chat_sse(work)


@app.route("/api/agent/personas/<persona_id>/chats/<chat_id>/message/stream", methods=["POST"])
def send_agent_chat_message_stream(persona_id, chat_id):
    """Streaming variant of send_agent_chat_message."""
    message = (request.json.get("message") or "").strip()
    if not message:
        return jsonify({"error": "message is required"}), 400

    def work(emit):
        agent_orchestrator.chat_message_stream(chat_id, message, persona_id, emit)
        agent_chat_store.touch(persona_id, chat_id)

    return _agent_chat_sse(work)


@app.route("/api/agent/personas/<persona_id>/chats/<chat_id>/resume/stream", methods=["POST"])
def resume_agent_chat_stream(persona_id, chat_id):
    """Streaming variant of resume_agent_chat."""
    decision = request.json.get("decision")
    if decision not in ("approve", "reject"):
        return jsonify({"error": "decision must be \"approve\" or \"reject\""}), 400

    def work(emit):
        agent_orchestrator.resume_chat_stream(chat_id, decision, persona_id, emit)
        agent_chat_store.touch(persona_id, chat_id)

    return _agent_chat_sse(work)


@app.route("/api/agent/personas/<persona_id>/chats/<chat_id>/rename", methods=["PUT"])
def rename_agent_chat(persona_id, chat_id):
    try:
        title = (request.json.get("title") or "").strip()
        if not title:
            return jsonify({"error": "title is required"}), 400
        return jsonify(agent_chat_store.rename_chat(persona_id, chat_id, title))
    except FileNotFoundError as e:
        return jsonify({"error": str(e)}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/agent/personas/<persona_id>/chats/<chat_id>", methods=["DELETE"])
def delete_agent_chat(persona_id, chat_id):
    try:
        existed = agent_chat_store.delete_chat(persona_id, chat_id)
        if not existed:
            return jsonify({"error": "Chat not found"}), 404
        return jsonify({"status": "ok"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/databases", methods=["GET"])
def list_databases():
    """Every database name visible through the enabled MCP server(s) - feeds
    the persona editor's database-binding dropdown (see knowledge_sync.py)."""
    try:
        return jsonify({"databases": knowledge_sync.list_databases()})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/agent/personas/<persona_id>/knowledge", methods=["GET"])
def get_agent_knowledge(persona_id):
    """The persona's auto-generated database-knowledge skill, if it's been
    synced at least once."""
    try:
        skill = agent_skill_store.get_skill(persona_id, knowledge_sync.KNOWLEDGE_SKILL_SLUG)
        return jsonify(skill or {})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/agent/personas/<persona_id>/knowledge/sync", methods=["POST"])
def sync_agent_knowledge(persona_id):
    """Crawl the given database's schema and (re)write the persona's
    database-knowledge skill from it (see knowledge_sync.sync)."""
    try:
        database = (request.json.get("database") or "").strip()
        if not database:
            return jsonify({"error": "database is required"}), 400
        persona = agent_persona_store.update_persona(persona_id, database=database)
        skill = knowledge_sync.sync(persona_id, database)
        return jsonify({**skill, "persona": persona})
    except KeyError as e:
        return jsonify({"error": str(e)}), 404
    except Exception as e:
        print(f"[Knowledge Sync] Error: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/api/activity", methods=["GET"])
def get_activity():
    """Recent activity log events (tool calls, run starts/finishes, errors -
    see observability.py). ?persona_id=, ?kind=, ?limit= all optional filters."""
    try:
        limit = int(request.args.get("limit", 100))
        return jsonify({"events": observability.list_events(
            persona_id=request.args.get("persona_id"),
            kind=request.args.get("kind"),
            limit=limit,
        )})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/activity/stats", methods=["GET"])
def get_activity_stats():
    try:
        return jsonify(observability.stats())
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/config", methods=["GET"])
def get_config():
    """Frontend-facing config: currently just the Langfuse UI link (None if
    not configured), for the Activity view's "Open in Langfuse" button."""
    try:
        return jsonify({"langfuse_url": observability.langfuse_ui_url()})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/agent/runs", methods=["GET"])
def list_agent_runs():
    """List past agent runs (summary only), newest first. ?persona_id=
    filters to one persona's runs, or "__none__" for "General"'s runs."""
    try:
        persona_id = request.args.get("persona_id")
        return jsonify({"runs": agent_run_store.list_runs(persona_id)})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/agent/run", methods=["POST"])
def start_agent_run():
    """Start a new agent run. Runs the deepagents graph to its first
    interrupt (a proposed sub-agent dispatch) or straight to completion if
    none is needed - see agent_orchestrator.start_run."""
    try:
        request_text = (request.json.get("request") or "").strip()
        if not request_text:
            return jsonify({"error": "request is required"}), 400
        persona_id = request.json.get("persona_id")
        run = agent_run_store.create_run(request_text, persona_id)
        state = agent_orchestrator.start_run(run["id"], request_text, persona_id)
        agent_run_store.set_status(run["id"], state["status"])
        return jsonify({**run, **state})
    except Exception as e:
        print(f"[Agent] Run start error: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/api/agent/run/<thread_id>", methods=["GET"])
def get_agent_run(thread_id):
    """Re-derive the current state of a run from checkpointed state - for
    reloading or replaying a run without resuming it."""
    try:
        run = agent_run_store.get_run(thread_id)
        if run is None:
            return jsonify({"error": "Run not found"}), 404
        state = agent_orchestrator.get_run_state(thread_id, run.get("persona_id"))
        if state is None:
            return jsonify({"error": "Run has no checkpointed state"}), 404
        return jsonify({**run, **state})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/agent/run/<thread_id>/rename", methods=["PUT"])
def rename_agent_run(thread_id):
    try:
        title = (request.json.get("title") or "").strip()
        if not title:
            return jsonify({"error": "title is required"}), 400
        return jsonify(agent_run_store.rename_run(thread_id, title))
    except FileNotFoundError as e:
        return jsonify({"error": str(e)}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/agent/run/<thread_id>", methods=["DELETE"])
def delete_agent_run(thread_id):
    try:
        existed = agent_run_store.delete_run(thread_id)
        if not existed:
            return jsonify({"error": "Run not found"}), 404
        return jsonify({"status": "ok"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/agent/run/<thread_id>/resume", methods=["POST"])
def resume_agent_run(thread_id):
    """Resume a paused run with an approve/reject decision for the pending
    sub-agent dispatch, running to the next interrupt or completion."""
    try:
        run = agent_run_store.get_run(thread_id)
        if run is None:
            return jsonify({"error": "Run not found"}), 404
        decision = request.json.get("decision")
        if decision not in ("approve", "reject"):
            return jsonify({"error": "decision must be \"approve\" or \"reject\""}), 400
        state = agent_orchestrator.resume_run(thread_id, decision, run.get("persona_id"))
        run = agent_run_store.set_status(thread_id, state["status"])
        return jsonify({**run, **state})
    except Exception as e:
        print(f"[Agent] Resume error: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/api/chart/save", methods=["POST"])
def save_chart():
    """Save chart as PNG"""
    try:
        data = request.json
        image_data = data["image"]
        chart_name = data.get("name", "chart")

        # Decode base64 image
        if "," in image_data:
            image_data = image_data.split(",")[1]
        image_bytes = base64.b64decode(image_data)

        # Save to charts directory
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{chart_name}_{timestamp}.png"
        filepath = os.path.join(os.getcwd(), Config.CHARTS_DIR, filename)

        os.makedirs(os.path.dirname(filepath), exist_ok=True)

        with open(filepath, "wb") as f:
            f.write(image_bytes)

        return jsonify({"status": "ok", "path": filepath, "filename": filename})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/chat", methods=["POST"])
def chat():
    """Process chat request with multi-step execution"""
    try:
        data = request.json
        user_message = data["message"]
        history = data.get("history", [])

        result = process_chat_request(user_message, history)
        return jsonify(result)

    except Exception as e:
        print(f"[Chat] Error: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/api/chat/stream", methods=["POST"])
def chat_stream():
    """Process chat request with real-time progress updates"""
    from flask import Response, stream_with_context
    import json as json_lib
    import queue
    import threading

    data = request.json
    user_message = data["message"]
    history = data.get("history", [])

    # Use a queue to communicate between threads
    progress_queue = queue.Queue()
    result_container = {}

    def progress_callback(status, detail):
        """Callback to send progress updates"""
        progress_queue.put({'type': 'progress', 'status': status, 'detail': detail})

    def run_processing():
        """Run the chat processing in a separate thread"""
        try:
            result = process_chat_request(user_message, history, progress_callback)
            result_container['result'] = result
            progress_queue.put({'type': 'done'})
        except Exception as e:
            import traceback
            tb = traceback.format_exc()
            print(f"[Chat Stream] Unhandled error in run_processing:\n{tb}")
            result_container['error'] = f"{type(e).__name__}: {e}"
            progress_queue.put({'type': 'error', 'message': f"{type(e).__name__}: {e}"})

    def generate():
        """Generator function for Server-Sent Events"""
        # Start processing in background thread
        thread = threading.Thread(target=run_processing)
        thread.start()

        # Stream progress updates
        while True:
            try:
                event = progress_queue.get(timeout=0.1)

                if event['type'] == 'progress':
                    data = {'type': 'progress', 'data': {'status': event['status'], 'detail': event['detail']}}
                    yield f"data: {json_lib.dumps(data)}\n\n"

                elif event['type'] == 'done':
                    if 'result' in result_container:
                        try:
                            data = {'type': 'result', 'data': result_container['result']}
                            yield f"data: {json_lib.dumps(data)}\n\n"
                        except (TypeError, ValueError) as e:
                            print(f"[Chat Stream] Failed to serialize result: {e}")
                            error_data = {'type': 'error', 'data': {'error': f"Result serialization failed: {e}"}}
                            yield f"data: {json_lib.dumps(error_data)}\n\n"
                    yield "data: [DONE]\n\n"
                    break

                elif event['type'] == 'error':
                    data = {'type': 'error', 'data': {'error': event['message']}}
                    yield f"data: {json_lib.dumps(data)}\n\n"
                    break

            except queue.Empty:
                continue

        thread.join()

    return Response(
        stream_with_context(generate()),
        mimetype='text/event-stream',
        headers={
            'Cache-Control': 'no-cache',
            'X-Accel-Buffering': 'no'
        }
    )


# ============ SPA catch-all ============
# Any non-API path serves the React app's index.html so client-side routing
# (react-router's BrowserRouter) resolves deep links like /agents/<id> on a
# hard refresh. Static asset paths (e.g. /assets/index-*.js) are served
# directly from frontend/dist by Flask's static handling above this route -
# Werkzeug matches those literal/static rules before this catch-all
# regardless of definition order, so /api/* is never at risk of landing here.

@app.route("/", defaults={"path": ""})
@app.route("/<path:path>")
def spa(path):
    dist_dir = os.path.join(os.getcwd(), "frontend", "dist")
    safe_path = path and safe_join(dist_dir, path)
    if safe_path and os.path.isfile(safe_path):
        return send_from_directory(dist_dir, path)
    return send_from_directory(dist_dir, "index.html")


# ============ Main Entry Point ============

if __name__ == "__main__":
    server_count = len(mcp_registry.list_servers())
    print(f"""
╔════════════════════════════════════════════════════════════╗
║             Chatterbase - Chat with Your Data              ║
╠════════════════════════════════════════════════════════════╣
║  Server:  http://localhost:{Config.PORT:<44}║
╠════════════════════════════════════════════════════════════╣
║  MCP servers:  {server_count:<43}║
║  LLM Provider: {Config.LLM_PROVIDER:<43}║
╚════════════════════════════════════════════════════════════╝
""")
    app.run(host=Config.HOST, debug=Config.DEBUG, port=Config.PORT)

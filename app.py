"""
Chatterbase - Chat with Your Data
A Flask-based web interface for interacting with Teradata via MCP using LLMs
"""
from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
import base64
import datetime
import os

from config import Config
from mcp_client import run_async, get_mcp_tools, get_server_statuses
from llm_providers import LLMProvider, LocalLLMProvider, GeminiProvider, OpenAIProvider, NvidiaNIMProvider, LMStudioProvider
from chat_handler import process_chat_request
import conversation_store
import mcp_registry
import llm_registry
import dashboard_store
import plan_store
import agent_orchestrator

# Initialize Flask app
app = Flask(__name__, static_folder='static', static_url_path='/static', template_folder='templates')
CORS(app)

# Apply the persisted active LLM profile on top of .env's defaults, so a
# restart honors whatever was last activated/edited in the UI rather than
# silently reverting to .env every time.
llm_registry.apply_active_profile()


# ============ API Routes ============

@app.route("/")
def index():
    """Serve the main web interface"""
    return render_template('index.html')


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


@app.route("/api/dashboards/<dashboard_id>/charts", methods=["POST"])
def pin_dashboard_chart(dashboard_id):
    """Pin a chart into this dashboard (a snapshot of type/labels/data/colors, not a live query)"""
    try:
        data = request.json
        entry = dashboard_store.pin_chart(
            dashboard_id,
            title=data.get("title", "Chart"),
            chart_type=data.get("type", "bar"),
            labels=data.get("labels", []),
            data=data.get("data", []),
            colors=data.get("colors"),
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


@app.route("/api/agent/plan", methods=["POST"])
def create_agent_plan():
    """Decompose a request into steps and persist as pending_approval - does
    not execute anything yet."""
    try:
        request_text = (request.json.get("request") or "").strip()
        if not request_text:
            return jsonify({"error": "request is required"}), 400
        steps = agent_orchestrator.plan_request(request_text)
        plan = plan_store.create_plan(request_text, steps)
        return jsonify(plan)
    except Exception as e:
        print(f"[Agent] Planning error: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/api/agent/plan/<plan_id>", methods=["GET"])
def get_agent_plan(plan_id):
    try:
        plan = plan_store.get_plan(plan_id)
        if plan is None:
            return jsonify({"error": "Plan not found"}), 404
        return jsonify(plan)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/agent/plan/<plan_id>/approve", methods=["POST"])
def approve_agent_plan(plan_id):
    """Executes every step synchronously and returns the completed plan.
    v0 has no streaming - a multi-step plan can take tens of seconds since
    each step is its own LLM call (and possibly MCP tool calls)."""
    try:
        plan = plan_store.get_plan(plan_id)
        if plan is None:
            return jsonify({"error": "Plan not found"}), 404
        plan_store.set_status(plan_id, "approved")
        completed = agent_orchestrator.execute_plan(plan_id)
        return jsonify(completed)
    except Exception as e:
        print(f"[Agent] Execution error: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/api/agent/plan/<plan_id>/reject", methods=["POST"])
def reject_agent_plan(plan_id):
    try:
        plan = plan_store.set_status(plan_id, "rejected")
        return jsonify(plan)
    except FileNotFoundError as e:
        return jsonify({"error": str(e)}), 404
    except Exception as e:
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

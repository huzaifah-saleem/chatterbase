"""
Teradata MCP Agent
A Flask-based web interface for interacting with Teradata via MCP using LLMs
"""
from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
import base64
import datetime
import os

from config import Config
from mcp_client import run_async, get_mcp_tools
from llm_providers import LLMProvider, LocalLLMProvider, GeminiProvider, OpenAIProvider, NvidiaNIMProvider
from chat_handler import process_chat_request

# Initialize Flask app
app = Flask(__name__, static_folder='static', static_url_path='/static', template_folder='templates')
CORS(app)


# ============ API Routes ============

@app.route("/")
def index():
    """Serve the main web interface"""
    return render_template('index.html')


@app.route("/api/status")
def status():
    """Get current configuration status"""
    return jsonify({
        "mcp_url": Config.get_mcp_url(),
        "llm_provider": Config.LLM_PROVIDER,
        "local_llm_url": Config.LOCAL_LLM_URL,
        "local_llm_model": Config.LOCAL_LLM_MODEL,
        "gemini_api_key": Config.GEMINI_API_KEY[:10] + "..." if Config.GEMINI_API_KEY else "",
        "gemini_model": Config.GEMINI_MODEL,
        "openai_api_key": Config.OPENAI_API_KEY[:10] + "..." if Config.OPENAI_API_KEY else "",
        "openai_model": Config.OPENAI_MODEL,
    })


@app.route("/api/mcp/health")
def mcp_health():
    """Check MCP server health"""
    try:
        tools = run_async(get_mcp_tools())
        return jsonify({"status": "ok", "tools_count": len(tools)})
    except Exception as e:
        print(f"[MCP Health] Error: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/api/mcp/tools")
def get_tools():
    """Get available MCP tools"""
    try:
        tools = run_async(get_mcp_tools())
        return jsonify({"tools": tools})
    except Exception as e:
        print(f"[MCP Tools] Error: {e}")
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
        else:
            return jsonify({"error": f"Unknown provider: {Config.LLM_PROVIDER}"}), 500
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/config/update", methods=["POST"])
def update_config():
    """Update configuration settings"""
    try:
        data = request.json
        Config.update(
            llm_provider=data.get("llm_provider"),
            local_llm_url=data.get("local_llm_url"),
            local_llm_model=data.get("local_llm_model"),
            gemini_api_key=data.get("gemini_api_key"),
            gemini_model=data.get("gemini_model"),
            openai_api_key=data.get("openai_api_key"),
            openai_model=data.get("openai_model"),
            mcp_server_url=data.get("mcp_url"),
            mcp_endpoint=data.get("mcp_endpoint")
        )
        return jsonify({"status": "ok", "message": "Configuration updated"})
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
            result_container['error'] = str(e)
            progress_queue.put({'type': 'error', 'message': str(e)})

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
                        data = {'type': 'result', 'data': result_container['result']}
                        yield f"data: {json_lib.dumps(data)}\n\n"
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
    print(f"""
╔════════════════════════════════════════════════════════════╗
║         Teradata MCP Chatbot                               ║
╠════════════════════════════════════════════════════════════╣
║  Server:  http://localhost:{Config.PORT:<44}║
╠════════════════════════════════════════════════════════════╣
║  MCP URL:      {Config.get_mcp_url():<43}║
║  LLM Provider: {Config.LLM_PROVIDER:<43}║
╚════════════════════════════════════════════════════════════╝
""")
    app.run(debug=Config.DEBUG, port=Config.PORT)

# MCP UI - Teradata MCP Agent

A Flask-based web interface for interacting with Teradata databases via the Model Context Protocol (MCP) using various LLM providers.

## Features

- **Multi-LLM Support**: Works with multiple LLM providers:
  - Local LLM (Ollama)
  - Google Gemini
  - OpenAI
  - NVIDIA NIM

- **MCP Integration**: Seamlessly connects to MCP servers for tool execution
- **Real-time Chat**: Interactive chat interface with streaming responses
- **Chart Generation**: Create and save data visualizations
- **Dynamic Configuration**: Update settings on-the-fly through the web interface

## Prerequisites

- Python 3.11 or above
- MCP Server running (typically on `http://127.0.0.1:8001`)
- API keys for your chosen LLM provider (Gemini, OpenAI, etc.)

## Getting Started

### 1. Clone the Repository

```bash
git clone <repository-url>
cd "MCP UI"
```

### 2. Set Up Python Environment

Create a virtual environment using Python 3.11+:

```bash
python3.11 -m venv venv
```

Activate the virtual environment:

**On macOS/Linux:**
```bash
source venv/bin/activate
```

**On Windows:**
```bash
venv\Scripts\activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure Environment Variables

**Option A: Manual Setup (Recommended for Production)**

1. Copy the example environment file:
   ```bash
   cp env.example .env
   ```

2. Edit `.env` and add your credentials:
   ```bash
   # MCP Server
   MCP_SERVER_URL=http://127.0.0.1:8001
   MCP_ENDPOINT=/mcp

   # Choose your LLM provider: "local_llm", "gemini", "openai", or "nvidia_nim"
   LLM_PROVIDER=nvidia_nim

   # Local LLM Configuration (for Ollama or NVIDIA NIM)
   LOCAL_LLM_URL=http://127.0.0.1:11434
   LOCAL_LLM_MODEL=llama2

   # Google Gemini Configuration
   GEMINI_API_KEY=your_actual_api_key_here
   GEMINI_MODEL=gemini-pro

   # OpenAI Configuration
   OPENAI_API_KEY=your_actual_api_key_here
   OPENAI_MODEL=gpt-4
   ```

**Option B: Configure via Web Interface**

You can also configure all settings (including API keys and LLM providers) directly from the web interface Settings panel after starting the application. This is convenient for quick setup and testing.

### 5. Run the Application

```bash
python app.py
```

The application will start on `http://localhost:5000` by default.

## Usage

1. Open your browser and navigate to `http://localhost:5000`
2. If you didn't set up `.env`, go to Settings (gear icon) and configure:
   - MCP Server URL
   - LLM Provider and credentials
3. Start chatting with your Teradata database through the MCP interface
4. Use the chat to query data, generate charts, and perform database operations

## Project Structure

```
MCP UI/
├── app.py              # Main Flask application
├── chat_handler.py     # Chat processing logic
├── config.py           # Configuration management
├── llm_providers.py    # LLM provider implementations
├── mcp_client.py       # MCP client interface
├── prompts.py          # System prompts and templates
├── requirements.txt    # Python dependencies
├── env.example         # Environment variables template
├── static/             # Static assets (CSS, JS)
└── templates/          # HTML templates
```

## Configuration Options

### LLM Providers

- **local_llm**: Ollama or other local LLM servers
- **gemini**: Google's Gemini API
- **openai**: OpenAI's GPT models
- **nvidia_nim**: NVIDIA NIM endpoints

### MCP Server

Ensure your MCP server is running before starting the application. The default configuration expects it at `http://127.0.0.1:8001/mcp`.

## Troubleshooting

**MCP Connection Issues:**
- Verify your MCP server is running
- Check the MCP_SERVER_URL in your configuration
- Use the `/api/mcp/health` endpoint to test connectivity

**LLM Provider Errors:**
- Verify API keys are correctly set
- Check the `/api/llm/health` endpoint for provider status
- Ensure you have sufficient API credits/quota

## License

[Add your license here]

## Contributing

[Add contribution guidelines here]

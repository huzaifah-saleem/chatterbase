"""Configuration management for Teradata MCP Agent"""
import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    """Application configuration"""
    # MCP Server Configuration
    MCP_SERVER_URL = os.getenv("MCP_SERVER_URL", "http://127.0.0.1:8001")
    MCP_ENDPOINT = os.getenv("MCP_ENDPOINT", "/mcp")

    # LLM Provider Configuration
    LLM_PROVIDER = os.getenv("LLM_PROVIDER", "local_llm")

    # Local LLM Configuration (used by Local LLM and NVIDIA NIM providers)
    LOCAL_LLM_URL = os.getenv("LOCAL_LLM_URL", "http://127.0.0.1:11434")
    LOCAL_LLM_MODEL = os.getenv("LOCAL_LLM_MODEL", "deepseek-r1:32b")

    # Google Gemini Configuration
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
    GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-pro")

    # OpenAI Configuration
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
    OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4")

    # Application Configuration
    DEBUG = os.getenv("DEBUG", "True").lower() == "true"
    PORT = int(os.getenv("PORT", 5000))
    CHARTS_DIR = "charts"
    MAX_ITERATIONS = 10  # Safety limit for multi-step execution
    TIMEOUT = 300  # 5 minutes timeout for LLM calls

    @classmethod
    def get_mcp_url(cls):
        """Get full MCP URL"""
        endpoint = cls.MCP_ENDPOINT if cls.MCP_ENDPOINT.endswith('/') else cls.MCP_ENDPOINT + '/'
        return f"{cls.MCP_SERVER_URL}{endpoint}"

    @classmethod
    def update(cls, **kwargs):
        """Update configuration values dynamically"""
        for key, value in kwargs.items():
            if hasattr(cls, key.upper()):
                setattr(cls, key.upper(), value)

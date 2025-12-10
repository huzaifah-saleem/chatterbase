"""LLM Provider implementations for Local LLM, Gemini, OpenAI, and NVIDIA NIM"""
from config import Config


class LLMProvider:
    """Base class for LLM providers"""

    @staticmethod
    def call(system_prompt, user_message, history=None):
        """Call the configured LLM provider"""
        provider = Config.LLM_PROVIDER.lower()

        if provider == "local_llm":
            return LocalLLMProvider.call(system_prompt, user_message, history)
        elif provider == "gemini":
            return GeminiProvider.call(system_prompt, user_message, history)
        elif provider == "openai":
            return OpenAIProvider.call(system_prompt, user_message, history)
        elif provider == "nvidia_nim":
            return NvidiaNIMProvider.call(system_prompt, user_message, history)
        else:
            raise ValueError(f"Unknown LLM provider: {Config.LLM_PROVIDER}")


class LocalLLMProvider:
    """Local LLM provider (Ollama, etc.)"""

    @staticmethod
    def call(system_prompt, user_message, history=None):
        """Call Local LLM API (native Ollama-style API)"""
        import requests

        messages = [{"role": "system", "content": system_prompt}]
        if history:
            messages.extend(history)
        messages.append({"role": "user", "content": user_message})

        response = requests.post(
            f"{Config.LOCAL_LLM_URL}/api/chat",
            json={
                "model": Config.LOCAL_LLM_MODEL,
                "messages": messages,
                "stream": False,
                "options": {
                    "temperature": 0.1,
                    "top_p": 0.9,
                    "top_k": 40
                }
            },
            timeout=Config.TIMEOUT
        )
        response.raise_for_status()
        return response.json().get("message", {}).get("content", "")

    @staticmethod
    def health_check():
        """Check if Local LLM is available"""
        import requests
        response = requests.get(f"{Config.LOCAL_LLM_URL}/api/tags", timeout=5)
        response.raise_for_status()
        return {"status": "ok", "provider": Config.LOCAL_LLM_MODEL}


class GeminiProvider:
    """Google Gemini LLM provider"""

    @staticmethod
    def call(system_prompt, user_message, history=None):
        """Call Google Gemini API using chat interface"""
        import google.generativeai as genai

        genai.configure(api_key=Config.GEMINI_API_KEY)

        # Use system_instruction parameter for better system prompt handling
        model = genai.GenerativeModel(
            Config.GEMINI_MODEL,
            system_instruction=system_prompt
        )

        # Convert history to Gemini format (role must be "user" or "model")
        gemini_history = []
        if history:
            for msg in history:
                gemini_history.append({
                    "role": "user" if msg["role"] == "user" else "model",
                    "parts": [msg["content"]]
                })

        print(f"[Gemini] History items: {len(gemini_history)}, Current message: {user_message[:100]}...")

        # Start chat with history and send message
        chat = model.start_chat(history=gemini_history)
        response = chat.send_message(user_message)
        print(f"[Gemini] Response: {response.text[:200]}...")
        return response.text

    @staticmethod
    def health_check():
        """Check if Gemini API key is configured"""
        if not Config.GEMINI_API_KEY:
            raise ValueError("Gemini API key not configured")
        return {"status": "ok", "provider": Config.GEMINI_MODEL}


class OpenAIProvider:
    """OpenAI LLM provider"""

    @staticmethod
    def call(system_prompt, user_message, history=None):
        """Call OpenAI API"""
        from openai import OpenAI

        client = OpenAI(api_key=Config.OPENAI_API_KEY)

        messages = [{"role": "system", "content": system_prompt}]
        if history:
            messages.extend(history)
        messages.append({"role": "user", "content": user_message})

        response = client.chat.completions.create(
            model=Config.OPENAI_MODEL,
            messages=messages
        )
        return response.choices[0].message.content

    @staticmethod
    def health_check():
        """Check if OpenAI API key is configured"""
        if not Config.OPENAI_API_KEY:
            raise ValueError("OpenAI API key not configured")
        return {"status": "ok", "provider": Config.OPENAI_MODEL}


class NvidiaNIMProvider:
    """NVIDIA NIM LLM provider (OpenAI-compatible API, reuses Local LLM config)"""

    @staticmethod
    def call(system_prompt, user_message, history=None):
        """Call NVIDIA NIM API using OpenAI-compatible interface"""
        from openai import OpenAI

        # Reuse Local LLM URL and model config for NIM (same pattern: URL + model, no API key)
        client = OpenAI(
            base_url=Config.LOCAL_LLM_URL,
            api_key="not-needed"  # NIM doesn't require API key
        )

        messages = [{"role": "system", "content": system_prompt}]
        if history:
            messages.extend(history)
        messages.append({"role": "user", "content": user_message})

        print(f"[NVIDIA NIM] Calling {Config.LOCAL_LLM_URL} with model {Config.LOCAL_LLM_MODEL}")

        response = client.chat.completions.create(
            model=Config.LOCAL_LLM_MODEL,
            messages=messages,
            temperature=0.1,
            max_tokens=4096
        )

        result = response.choices[0].message.content
        print(f"[NVIDIA NIM] Response: {result[:200]}...")
        return result

    @staticmethod
    def health_check():
        """Check if NVIDIA NIM is available"""
        import requests
        try:
            # Try to hit the models endpoint (OpenAI-compatible)
            response = requests.get(f"{Config.LOCAL_LLM_URL}/models", timeout=5)
            response.raise_for_status()
            return {"status": "ok", "provider": Config.LOCAL_LLM_MODEL}
        except Exception as e:
            raise ValueError(f"NVIDIA NIM not available at {Config.LOCAL_LLM_URL}: {str(e)}")

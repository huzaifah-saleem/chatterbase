"""LLM provider profile registry: persists named LLM connection profiles to
data/llm_profiles.json, plus which one is active.

Chatterbase used to hold exactly one live-edited config per provider type on
Config's class attributes (Config.LLM_PROVIDER + per-type fields), with no
way to save more than one connection of the same type (e.g. two different
LM Studio endpoints) and no persistence across a restart. This registry
replaces that with named, saved profiles - activating one pushes its fields
onto Config, so llm_providers.py and chat_handler.py need no changes at all;
they still just read Config.* like before.
"""
import json
import os
import uuid

from config import Config

# Which fields each provider type actually uses.
URL_MODEL_TYPES = ("local_llm", "nvidia_nim", "lm_studio")
API_KEY_TYPES = ("gemini", "openai")


def _data_dir():
    path = os.path.join(os.getcwd(), Config.DATA_DIR)
    os.makedirs(path, exist_ok=True)
    return path


def _profiles_path():
    return os.path.join(_data_dir(), "llm_profiles.json")


def _seed_default():
    """Build the initial registry from today's single-profile .env config, so
    an existing deployment keeps working with zero manual migration."""
    provider = Config.LLM_PROVIDER
    if provider in URL_MODEL_TYPES:
        url, model, api_key = Config.LOCAL_LLM_URL, Config.LOCAL_LLM_MODEL, ""
    elif provider == "gemini":
        url, model, api_key = "", Config.GEMINI_MODEL, Config.GEMINI_API_KEY
    else:  # openai
        url, model, api_key = "", Config.OPENAI_MODEL, Config.OPENAI_API_KEY

    profile = {
        "id": str(uuid.uuid4()),
        "name": "Default",
        "provider_type": provider,
        "url": url,
        "model": model,
        "api_key": api_key,
    }
    return {"profiles": [profile], "active_id": profile["id"]}


def _load():
    path = _profiles_path()
    if not os.path.exists(path):
        data = _seed_default()
        _save(data)
        return data
    with open(path) as f:
        return json.load(f)


def _save(data):
    with open(_profiles_path(), "w") as f:
        json.dump(data, f, indent=2)


def list_profiles():
    return _load()["profiles"]


def get_active_id():
    return _load()["active_id"]


def get_active_profile():
    data = _load()
    for p in data["profiles"]:
        if p["id"] == data["active_id"]:
            return p
    return data["profiles"][0] if data["profiles"] else None


def add_profile(name, provider_type, url="", model="", api_key=""):
    data = _load()
    profile = {
        "id": str(uuid.uuid4()),
        "name": name,
        "provider_type": provider_type,
        "url": url,
        "model": model,
        "api_key": api_key,
    }
    data["profiles"].append(profile)
    _save(data)
    return profile


def update_profile(profile_id, **fields):
    """Update one profile's fields. Re-applies it to Config if it's the
    active one, so an in-place edit (e.g. fixing a typo'd API key) takes
    effect immediately without a separate activate step."""
    data = _load()
    for p in data["profiles"]:
        if p["id"] == profile_id:
            for key in ("name", "provider_type", "url", "model", "api_key"):
                if key in fields and fields[key] is not None:
                    p[key] = fields[key]
            _save(data)
            if data["active_id"] == profile_id:
                apply_active_profile()
            return p
    raise KeyError(f"LLM profile {profile_id} not found")


def delete_profile(profile_id):
    """Delete a profile. If it was active, falls back to the first remaining
    profile (or none). Returns True if it existed."""
    data = _load()
    remaining = [p for p in data["profiles"] if p["id"] != profile_id]
    if len(remaining) == len(data["profiles"]):
        return False
    data["profiles"] = remaining
    if data["active_id"] == profile_id:
        data["active_id"] = remaining[0]["id"] if remaining else None
    _save(data)
    if data["active_id"]:
        apply_active_profile()
    return True


def set_active(profile_id):
    data = _load()
    if not any(p["id"] == profile_id for p in data["profiles"]):
        raise KeyError(f"LLM profile {profile_id} not found")
    data["active_id"] = profile_id
    _save(data)
    apply_active_profile()
    return get_active_profile()


def apply_active_profile():
    """Push the active profile's fields onto Config, so llm_providers.py
    (which reads Config.* directly, unchanged) picks it up. Call this once
    at startup too, so a restart honors the persisted active profile instead
    of falling back to .env's defaults."""
    profile = get_active_profile()
    if profile is None:
        return
    updates = {"llm_provider": profile["provider_type"]}
    if profile["provider_type"] in URL_MODEL_TYPES:
        updates["local_llm_url"] = profile["url"]
        updates["local_llm_model"] = profile["model"]
    elif profile["provider_type"] == "gemini":
        updates["gemini_api_key"] = profile["api_key"]
        updates["gemini_model"] = profile["model"]
    elif profile["provider_type"] == "openai":
        updates["openai_api_key"] = profile["api_key"]
        updates["openai_model"] = profile["model"]
    Config.update(**updates)

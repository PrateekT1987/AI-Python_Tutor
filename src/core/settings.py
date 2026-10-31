"""Session and settings persistence for Python Tutor."""

from __future__ import annotations

import json
import os
from pathlib import Path

APP_NAME = "python-tutor"

DEFAULT_SETTINGS = {
    "level": "Intermediate",
    "model": "",
    "temperature": 0.4,
    "max_tokens": 2000,
    "geometry": "",
    "sandbox_memory_mb": 512,
    "sandbox_allow_network": False,
}


def _app_dir(env_var: str, default: str) -> Path:
    base = os.environ.get(env_var) or os.path.expanduser(default)
    path = Path(base) / APP_NAME
    path.mkdir(parents=True, exist_ok=True)
    return path


def config_dir() -> Path:
    return _app_dir("XDG_CONFIG_HOME", "~/.config")


def data_dir() -> Path:
    return _app_dir("XDG_DATA_HOME", "~/.local/share")


def settings_path() -> Path:
    return config_dir() / "settings.json"


def session_path() -> Path:
    return data_dir() / "session.json"


def load_settings() -> dict:
    path = settings_path()
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            return DEFAULT_SETTINGS.copy()
        return {**DEFAULT_SETTINGS, **data}
    except (OSError, json.JSONDecodeError):
        return DEFAULT_SETTINGS.copy()


def save_settings(settings: dict) -> None:
    path = settings_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(settings, f, indent=2, sort_keys=True)
    except OSError:
        pass


def load_session() -> list[dict]:
    path = session_path()
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, list):
            return []
        cleaned = []
        for msg in data:
            if (
                isinstance(msg, dict)
                and msg.get("role") in ("user", "assistant")
                and isinstance(msg.get("content"), str)
            ):
                cleaned.append({"role": msg["role"], "content": msg["content"]})
        return cleaned
    except (OSError, json.JSONDecodeError):
        return []


def save_session(history: list[dict]) -> None:
    path = session_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(history, f, indent=2, ensure_ascii=False)
    except OSError:
        pass


def clear_session() -> None:
    try:
        os.remove(session_path())
    except OSError:
        pass


def fit_messages(messages: list[dict], max_chars: int | None = None) -> list[dict]:
    """Trim the oldest turns so the request fits a char-based context budget."""
    from src.core.config import config
    
    limit = max_chars or config.MAX_CONTEXT_CHARS
    system = [m for m in messages if m.get("role") == "system"]
    rest = [m for m in messages if m.get("role") != "system"]

    def size(items: list[dict]) -> int:
        return sum(len(str(m.get("content", ""))) for m in items)

    if size(system) > limit // 2:
        system = [dict(system[0])]
        system[0]["content"] = str(system[0].get("content", ""))[: limit // 2]

    if size(system) + size(rest) <= limit:
        return list(system) + list(rest)

    total = size(system)
    kept: list[dict] = []
    for message in reversed(rest):
        content = str(message.get("content", ""))
        if kept and total + len(content) > limit:
            break
        if not kept and total + len(content) > limit:
            allowed = max(0, limit - total)
            message = {**message, "content": content[:allowed]}
            content = message["content"]
        kept.append(message)
        total += len(content)

    kept.reverse()
    return list(system) + kept
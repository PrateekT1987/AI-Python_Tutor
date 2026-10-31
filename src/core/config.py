"""Configuration management for Python Tutor."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field, asdict
from pathlib import Path

from dotenv import load_dotenv

from .settings import config_dir


@dataclass
class Config:
    """Application configuration with persistence."""
    
    # OpenRouter settings (loaded in __post_init__ after load_dotenv)
    openrouter_api_key: str = ""
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    model: str = "nvidia/nemotron-3-ultra-550b-a55b:free"
    
    # Generation settings
    temperature: float = 0.4
    max_tokens: int = 2000
    
    # UI settings
    level: str = "Intermediate"
    geometry: str = ""
    window_state: str = ""
    
    # Sandbox settings
    sandbox_memory_mb: int = 512
    sandbox_allow_network: bool = False
    
    # Runtime
    _config_path: Path = field(
        default_factory=lambda: config_dir() / "config.json",
        repr=False,
    )
    MAX_CONTEXT_CHARS: int = 24000
    
    def __post_init__(self):
        # Load .env file first
        load_dotenv()
        # Load from environment
        self.openrouter_api_key = os.getenv("OPENROUTER_API_KEY", "")
        self.openrouter_base_url = os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
        self.model = os.getenv("MODEL", "nvidia/nemotron-3-ultra-550b-a55b:free")
        # Load saved settings
        self.load()
    
    @property
    def config_path(self) -> Path:
        return self._config_path
    
    def load(self) -> None:
        """Load saved settings.

        Saved values are treated as the user's explicit choices and win over
        ``.env`` values, which only seed the defaults. This keeps edits made in
        Settings (API key, model, endpoint) from silently reverting on restart.
        """
        if not self.config_path.exists():
            return

        try:
            with open(self.config_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (json.JSONDecodeError, OSError):
            return

        if not isinstance(data, dict):
            return

        saved_model = data.get("model")
        if isinstance(saved_model, str) and saved_model.strip():
            self.model = saved_model.strip()

        saved_key = data.get("openrouter_api_key")
        if isinstance(saved_key, str) and saved_key.strip():
            self.openrouter_api_key = saved_key.strip()

        saved_url = data.get("openrouter_base_url")
        if isinstance(saved_url, str) and saved_url.strip():
            self.openrouter_base_url = saved_url.strip()

        skip = {"openrouter_api_key", "openrouter_base_url", "model", "_config_path"}
        for key, value in data.items():
            if key in skip or not hasattr(self, key):
                continue
            if key in ("geometry", "window_state") and isinstance(value, str):
                from PyQt6.QtCore import QByteArray
                value = QByteArray.fromHex(value.encode("ascii"))
            setattr(self, key, value)

    def save(self) -> None:
        """Save configuration to file (atomically, owner-readable only)."""
        try:
            self.config_path.parent.mkdir(parents=True, exist_ok=True)
            data = {}
            for key, value in asdict(self).items():
                if key.startswith("_") or callable(value):
                    continue
                if hasattr(value, "toHex"):
                    data[key] = bytes(value.toHex().data()).decode("ascii")
                else:
                    data[key] = value

            # The file can contain an API key, so write it 0600 and replace
            # atomically to avoid a truncated config on a crash.
            tmp_path = self.config_path.with_name(self.config_path.name + ".tmp")
            with open(tmp_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
            os.chmod(tmp_path, 0o600)
            os.replace(tmp_path, self.config_path)
        except OSError:
            pass
    
    @property
    def headers(self) -> dict[str, str]:
        """HTTP headers for OpenRouter requests."""
        return {
            "Authorization": f"Bearer {self.openrouter_api_key}",
            "Content-Type": "application/json; charset=utf-8",
            "Accept": "text/event-stream; charset=utf-8",
            "HTTP-Referer": "https://github.com/PrateekT1987/AI-Python-tutor",
            "X-Title": "Python Tutor",
        }
    
    @property
    def chat_completions_url(self) -> str:
        return f"{self.openrouter_base_url.rstrip('/')}/chat/completions"


# Global config instance
config = Config()
"""Runtime settings resolved with precedence: env vars → persisted JSON → defaults.

Environment variables take precedence at startup. Any field the user saves via
the Settings tab is written to ``settings.json`` under ``AICOMIC_CONFIG_DIR``
and is read on subsequent runs (but still overridable by env vars).
"""

from __future__ import annotations

import os
from dataclasses import asdict, dataclass, field
from pathlib import Path
from threading import RLock

from config.persist import read_json, write_json_atomic

_SETTINGS_FILE_NAME = "settings.json"
_ENV_PREFIX = "AICOMIC_"

# Fields the user can edit from the Settings tab. Other fields (paths, bind
# host/port) are deploy-time concerns driven purely by env vars.
_USER_EDITABLE = {
    "comfy_base_url",
    "comfy_auth_token",
    "comfy_verify_tls",
    "default_checkpoint",
    "default_seed_mode",
}


@dataclass
class Settings:
    # Remote ComfyUI
    comfy_base_url: str = ""
    comfy_auth_token: str = ""
    comfy_verify_tls: bool = True
    default_checkpoint: str = ""
    default_seed_mode: str = "random"  # "random" | "fixed"

    # Deploy-time (env only)
    bind_host: str = "0.0.0.0"
    bind_port: int = 7860
    config_dir: str = "/config"
    assets_dir: str = "/config/assets"

    # ---- derived helpers ----
    @property
    def config_path(self) -> Path:
        return Path(self.config_dir)

    @property
    def assets_path(self) -> Path:
        return Path(self.assets_dir)

    @property
    def settings_file(self) -> Path:
        return self.config_path / _SETTINGS_FILE_NAME

    @property
    def db_path(self) -> Path:
        return self.config_path / "ai-comic.db"

    @property
    def comfy_ws_url(self) -> str:
        """Derive ws(s) URL from the http(s) base URL."""
        base = self.comfy_base_url.rstrip("/")
        if not base:
            return ""
        if base.startswith("https://"):
            return "wss://" + base[len("https://") :] + "/ws"
        if base.startswith("http://"):
            return "ws://" + base[len("http://") :] + "/ws"
        # Fallback — assume http.
        return "ws://" + base + "/ws"

    def is_configured(self) -> bool:
        return bool(self.comfy_base_url)

    def to_user_dict(self) -> dict:
        """Only the fields the user edits from the UI — goes to settings.json."""
        d = asdict(self)
        return {k: d[k] for k in _USER_EDITABLE}


_ENV_COERCERS = {
    "bind_port": int,
    "comfy_verify_tls": lambda v: str(v).lower() not in {"0", "false", "no"},
}


def _env_overrides() -> dict:
    out: dict = {}
    field_names = {f.name for f in Settings.__dataclass_fields__.values()}
    # Map AICOMIC_COMFY_URL → comfy_base_url (historical alias we advertise).
    alias = {"comfy_url": "comfy_base_url", "comfy_token": "comfy_auth_token"}
    for key, value in os.environ.items():
        if not key.startswith(_ENV_PREFIX):
            continue
        name = key[len(_ENV_PREFIX) :].lower()
        name = alias.get(name, name)
        if name not in field_names:
            continue
        coerce = _ENV_COERCERS.get(name, lambda v: v)
        try:
            out[name] = coerce(value)
        except ValueError:
            pass
    return out


_lock = RLock()
_cache: Settings | None = None


def _build() -> Settings:
    # 1. defaults
    settings = Settings()
    # 2. deploy-time env for paths so we know where to read JSON from
    env = _env_overrides()
    for name in ("config_dir", "assets_dir", "bind_host", "bind_port"):
        if name in env:
            setattr(settings, name, env[name])
    # 3. persisted JSON (user-editable fields only)
    persisted = read_json(settings.settings_file)
    for name, value in persisted.items():
        if name in _USER_EDITABLE and hasattr(settings, name):
            setattr(settings, name, value)
    # 4. remaining env overrides win over JSON
    for name, value in env.items():
        setattr(settings, name, value)
    return settings


def get_settings(refresh: bool = False) -> Settings:
    global _cache
    with _lock:
        if _cache is None or refresh:
            _cache = _build()
        return _cache


def save_settings(**updates) -> Settings:
    """Update user-editable fields and persist them. Returns the new Settings."""
    with _lock:
        current = get_settings()
        for name, value in updates.items():
            if name in _USER_EDITABLE and hasattr(current, name):
                setattr(current, name, value)
        write_json_atomic(current.settings_file, current.to_user_dict())
        # force rebuild so env re-applies any overrides
        return get_settings(refresh=True)

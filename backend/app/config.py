"""Application settings, read from environment variables (see .env.example)."""
from __future__ import annotations

import os
import secrets
from dataclasses import dataclass, field
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent


def _load_dotenv(path: Path) -> None:
    """Minimal .env loader so the app runs without extra dependencies.
    Existing environment variables always win."""
    if not path.is_file():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key, value = key.strip(), value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)


def _env(name: str, default: str = "") -> str:
    """Read an environment variable; empty values count as "not set"."""
    value = os.environ.get(name, "").strip()
    return value if value else default


def _int(name: str, default: int) -> int:
    try:
        return int(_env(name, str(default)))
    except ValueError:
        raise RuntimeError(f"Environment variable {name} must be an integer")


@dataclass
class Settings:
    app_env: str = "development"
    data_dir: Path = BACKEND_DIR / "data"
    secret_key: str = ""
    token_ttl_minutes: int = 720
    max_upload_mb: int = 20
    max_media_upload_mb: int = 50
    cors_origins: list[str] = field(default_factory=list)

    # Email: "console" writes mail to the server log + dev outbox; "smtp" sends it.
    email_mode: str = "console"
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from: str = "HAQ <no-reply@haq.local>"

    # AI provider: "local" (deterministic template), "watsonx" or "ollama".
    ai_provider: str = "local"
    ai_timeout_seconds: int = 60
    watsonx_url: str = "https://us-south.ml.cloud.ibm.com"
    watsonx_apikey: str = ""
    watsonx_project_id: str = ""
    watsonx_model_id: str = "ibm/granite-3-8b-instruct"
    ollama_url: str = "http://127.0.0.1:11434"
    ollama_model: str = "granite3.3:2b"

    ocr_languages: str = "eng"
    stt_model: str = "off"  # offline speech-to-text (faster-whisper): off, tiny, base, small

    @property
    def is_dev(self) -> bool:
        return self.app_env == "development"

    @property
    def db_path(self) -> Path:
        return self.data_dir / "haq.sqlite3"

    @property
    def storage_dir(self) -> Path:
        return self.data_dir / "private_files"


def load_settings() -> Settings:
    _load_dotenv(BACKEND_DIR / ".env")
    s = Settings()
    s.app_env = _env("APP_ENV", "development").lower()
    if s.app_env not in {"development", "production", "test"}:
        raise RuntimeError("APP_ENV must be development, production or test")
    s.data_dir = Path(_env("HAQ_DATA_DIR", str(BACKEND_DIR / "data"))).resolve()
    s.token_ttl_minutes = _int("TOKEN_TTL_MINUTES", 720)
    s.max_upload_mb = _int("MAX_UPLOAD_MB", 20)
    s.max_media_upload_mb = _int("MAX_MEDIA_UPLOAD_MB", 50)
    s.cors_origins = [o.strip() for o in _env("CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173").split(",") if o.strip()]

    s.email_mode = _env("EMAIL_MODE", "console").strip().lower()
    s.smtp_host = _env("SMTP_HOST", "")
    s.smtp_port = _int("SMTP_PORT", 587)
    s.smtp_user = _env("SMTP_USER", "")
    s.smtp_password = _env("SMTP_PASSWORD", "")
    s.smtp_from = _env("SMTP_FROM", s.smtp_from)

    s.ai_provider = _env("AI_PROVIDER", "local").strip().lower()
    s.ai_timeout_seconds = _int("AI_TIMEOUT_SECONDS", 60)
    s.watsonx_url = _env("WATSONX_URL", s.watsonx_url).rstrip("/")
    s.watsonx_apikey = _env("WATSONX_APIKEY", "")
    s.watsonx_project_id = _env("WATSONX_PROJECT_ID", "")
    s.watsonx_model_id = _env("WATSONX_MODEL_ID", s.watsonx_model_id)
    s.ollama_url = _env("OLLAMA_URL", s.ollama_url).rstrip("/")
    s.ollama_model = _env("OLLAMA_MODEL", s.ollama_model)
    s.ocr_languages = _env("OCR_LANGUAGES", "eng")
    s.stt_model = _env("STT_MODEL", "base").strip().lower() or "off"

    s.data_dir.mkdir(parents=True, exist_ok=True)
    s.storage_dir.mkdir(parents=True, exist_ok=True)

    key = _env("SECRET_KEY", "").strip()
    if not key:
        if s.app_env == "production":
            raise RuntimeError("SECRET_KEY must be set in production")
        # Development convenience: persist a random key inside the private data folder.
        key_file = s.data_dir / ".dev_secret_key"
        if key_file.is_file():
            key = key_file.read_text().strip()
        else:
            key = secrets.token_urlsafe(48)
            key_file.write_text(key)
    if len(key) < 32:
        raise RuntimeError("SECRET_KEY must be at least 32 characters")
    s.secret_key = key
    if s.email_mode == "smtp" and not s.smtp_host:
        raise RuntimeError("EMAIL_MODE=smtp requires SMTP_HOST")
    return s

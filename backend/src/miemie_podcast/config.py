from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def _load_env_file() -> None:
    root_dir = Path(__file__).resolve().parents[3]
    env_path = root_dir / ".env"
    if not env_path.exists():
        return
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip("'").strip('"')
        os.environ.setdefault(key, value)


def _get_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    app_env: str
    app_host: str
    app_port: int
    app_domain: str
    api_host: str
    api_port: int
    web_origin: str
    next_public_api_base_url: str
    data_dir: Path
    database_url: str
    queue_backend: str
    storage_backend: str
    auth_mode: str
    admin_password: str
    cookie_name: str
    cookie_secure: bool
    cookie_samesite: str
    dashscope_api_key: str
    dashscope_base_url: str
    dashscope_compatible_base_url: str
    worker_poll_interval_seconds: int
    worker_process_count: int
    analysis_chunk_extract_concurrency: int
    mindmap_renderer_command: str

    @property
    def sqlite_path(self) -> Path:
        if not self.database_url.startswith("sqlite:///"):
            raise ValueError("Only sqlite DATABASE_URL is supported in v1.")
        return Path(self.database_url.replace("sqlite:///", "", 1)).resolve()

    @classmethod
    def from_env(cls) -> "Settings":
        data_dir = Path(os.getenv("DATA_DIR", "./data")).resolve()
        database_url = os.getenv("DATABASE_URL", f"sqlite:///{data_dir / 'miemie.db'}")
        api_host = os.getenv("API_HOST", "127.0.0.1")
        api_port = int(os.getenv("API_PORT", "8000"))
        return cls(
            app_env=os.getenv("APP_ENV", "development"),
            app_host=os.getenv("APP_HOST", "0.0.0.0"),
            app_port=int(os.getenv("APP_PORT", "3000")),
            app_domain=os.getenv("APP_DOMAIN", ""),
            api_host=api_host,
            api_port=api_port,
            web_origin=os.getenv("WEB_ORIGIN", "http://127.0.0.1:3000"),
            next_public_api_base_url=os.getenv(
                "NEXT_PUBLIC_API_BASE_URL", f"http://{api_host}:{api_port}"
            ),
            data_dir=data_dir,
            database_url=database_url,
            queue_backend=os.getenv("QUEUE_BACKEND", "db_polling"),
            storage_backend=os.getenv("STORAGE_BACKEND", "local"),
            auth_mode=os.getenv("AUTH_MODE", "password_single_user"),
            admin_password=os.getenv("APP_ADMIN_PASSWORD", "change-me"),
            cookie_name=os.getenv("COOKIE_NAME", "miemie_session"),
            cookie_secure=_get_bool("COOKIE_SECURE", False),
            cookie_samesite=os.getenv("COOKIE_SAMESITE", "lax"),
            dashscope_api_key=os.getenv("DASHSCOPE_API_KEY", ""),
            dashscope_base_url=os.getenv("DASHSCOPE_BASE_URL", "https://dashscope.aliyuncs.com"),
            dashscope_compatible_base_url=os.getenv(
                "DASHSCOPE_COMPATIBLE_BASE_URL",
                "https://dashscope.aliyuncs.com/compatible-mode/v1",
            ),
            worker_poll_interval_seconds=int(os.getenv("WORKER_POLL_INTERVAL_SECONDS", "5")),
            worker_process_count=max(1, int(os.getenv("WORKER_PROCESS_COUNT", "2"))),
            analysis_chunk_extract_concurrency=max(1, int(os.getenv("ANALYSIS_CHUNK_EXTRACT_CONCURRENCY", "4"))),
            mindmap_renderer_command=os.getenv(
                "MINDMAP_RENDERER_COMMAND", "node scripts/render-mindmap.mjs"
            ),
        )


_load_env_file()
settings = Settings.from_env()

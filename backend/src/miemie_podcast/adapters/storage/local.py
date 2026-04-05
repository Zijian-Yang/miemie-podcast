from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

from miemie_podcast.config import Settings
from miemie_podcast.ports.repositories import ObjectStorage


class LocalFileStorage(ObjectStorage):
    def __init__(self, settings: Settings) -> None:
        self.root = settings.data_dir.resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def save_text(self, relative_path: str, content: str) -> Dict[str, Any]:
        path = self.resolve_path(relative_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return {"relative_path": relative_path, "size_bytes": path.stat().st_size}

    def save_bytes(self, relative_path: str, content: bytes) -> Dict[str, Any]:
        path = self.resolve_path(relative_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
        return {"relative_path": relative_path, "size_bytes": path.stat().st_size}

    def resolve_path(self, relative_path: str) -> Path:
        return (self.root / relative_path).resolve()

    def delete_prefix(self, relative_prefix: str) -> None:
        target = self.resolve_path(relative_prefix)
        if not target.exists():
            return
        if target.is_file():
            target.unlink()
            return
        for path in sorted(target.rglob("*"), reverse=True):
            if path.is_file():
                path.unlink()
            elif path.is_dir():
                path.rmdir()
        target.rmdir()


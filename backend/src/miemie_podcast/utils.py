from __future__ import annotations

import hashlib
import json
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def minutes_from_now(minutes: int) -> str:
    return (datetime.now(timezone.utc) + timedelta(minutes=minutes)).isoformat()


def seconds_from_now(seconds: int) -> str:
    return (datetime.now(timezone.utc) + timedelta(seconds=seconds)).isoformat()


def new_id(prefix: str) -> str:
    return f"{prefix}_{secrets.token_hex(8)}"


def json_dumps(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def json_loads(value: Optional[str], default: Any = None) -> Any:
    if not value:
        return default
    return json.loads(value)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def timestamp_to_mmss(ms: int) -> str:
    seconds = int(ms / 1000)
    minutes = seconds // 60
    remain = seconds % 60
    return f"{minutes:02d}:{remain:02d}"


def chunk_dict(
    chunk_id: str,
    start_ms: int,
    end_ms: int,
    text: str,
    extra: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    payload = {
        "chunk_id": chunk_id,
        "start_ms": start_ms,
        "end_ms": end_ms,
        "timestamp": timestamp_to_mmss(start_ms),
        "text": text,
    }
    if extra:
        payload.update(extra)
    return payload


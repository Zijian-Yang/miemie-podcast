from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class EpisodeStatus(str, Enum):
    QUEUED = "queued"
    SOURCE_RESOLVED = "source_resolved"
    TRANSCRIBING = "transcribing"
    TRANSCRIBED = "transcribed"
    ANALYZING = "analyzing"
    READY = "ready"
    FAILED = "failed"
    DELETED = "deleted"


class JobStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class ModuleStatus(str, Enum):
    PENDING = "pending"
    READY = "ready"
    FAILED = "failed"


@dataclass(frozen=True)
class RequestContext:
    workspace_id: str
    user_id: str
    role: str
    auth_mode: str


@dataclass
class Workspace:
    id: str
    slug: str
    name: str
    owner_user_id: str
    visibility: str
    created_at: str
    updated_at: str
    deleted_at: Optional[str] = None


@dataclass
class User:
    id: str
    workspace_id: str
    email: str
    display_name: str
    role: str
    created_at: str
    updated_at: str
    deleted_at: Optional[str] = None


@dataclass
class Session:
    id: str
    workspace_id: str
    user_id: str
    token_hash: str
    expires_at: str
    created_at: str
    updated_at: str
    deleted_at: Optional[str] = None


@dataclass
class Episode:
    id: str
    workspace_id: str
    owner_user_id: str
    created_by: str
    visibility: str
    source_type: str
    source_url: str
    source_episode_id: str
    podcast_title: str
    episode_title: str
    cover_image_url: str
    audio_url: str
    published_at: Optional[str]
    duration_seconds: Optional[int]
    status: EpisodeStatus
    processing_stage: str
    transcription_task_id: Optional[str]
    transcription_provider: Optional[str]
    failure_code: Optional[str]
    failure_message: Optional[str]
    created_at: str
    updated_at: str
    deleted_at: Optional[str] = None


@dataclass
class EpisodeSourceRecord:
    id: str
    workspace_id: str
    episode_id: str
    source_type: str
    normalized_source: str
    raw_payload_json: str
    created_at: str
    updated_at: str
    deleted_at: Optional[str] = None


@dataclass
class Job:
    id: str
    workspace_id: str
    episode_id: Optional[str]
    job_type: str
    stage: str
    status: JobStatus
    payload_json: str
    result_json: Optional[str]
    error_json: Optional[str]
    attempt_count: int
    max_attempts: int
    dedupe_key: Optional[str]
    available_at: str
    locked_by: Optional[str]
    locked_at: Optional[str]
    heartbeat_at: Optional[str]
    created_at: str
    updated_at: str
    deleted_at: Optional[str] = None


@dataclass
class TranscriptChunk:
    id: str
    workspace_id: str
    episode_id: str
    chunk_index: int
    start_ms: int
    end_ms: int
    text: str
    metadata_json: str
    created_at: str
    updated_at: str
    deleted_at: Optional[str] = None


@dataclass
class ModuleOutput:
    id: str
    workspace_id: str
    episode_id: str
    module_key: str
    version: str
    format: str
    status: ModuleStatus
    content_json: str
    rendered_markdown: Optional[str]
    rendered_html: Optional[str]
    citations_json: Optional[str]
    created_at: str
    updated_at: str
    deleted_at: Optional[str] = None


@dataclass
class SearchDocument:
    id: str
    workspace_id: str
    episode_id: str
    source_kind: str
    title: str
    body: str
    metadata_json: str
    created_at: str
    updated_at: str
    deleted_at: Optional[str] = None


@dataclass
class Artifact:
    id: str
    workspace_id: str
    episode_id: str
    artifact_key: str
    format: str
    mime_type: str
    relative_path: str
    size_bytes: int
    metadata_json: str
    created_at: str
    updated_at: str
    deleted_at: Optional[str] = None


@dataclass
class Citation:
    source_kind: str
    chunk_id: Optional[str]
    start_ms: Optional[int]
    end_ms: Optional[int]
    excerpt: str


@dataclass
class QAAnswer:
    answer: str
    citations: List[Citation] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SourceAdapterResult:
    normalized_source: str
    episode_metadata: Dict[str, Any]
    audio_locator: Dict[str, Any]
    raw_snapshot: Dict[str, Any]


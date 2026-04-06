from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    password: Optional[str] = None


class LoginResponse(BaseModel):
    success: bool


class MeResponse(BaseModel):
    workspace_id: str
    user_id: str
    role: str
    auth_mode: str


class ImportEpisodeRequest(BaseModel):
    source_url: str = Field(min_length=1)


class QuestionRequest(BaseModel):
    question: str = Field(min_length=1)


class CitationResponse(BaseModel):
    source_kind: str
    chunk_id: Optional[str] = None
    start_ms: Optional[int] = None
    end_ms: Optional[int] = None
    excerpt: str


class QAResponse(BaseModel):
    answer: str
    citations: List[CitationResponse]


class JobResponse(BaseModel):
    id: str
    workspace_id: str
    episode_id: Optional[str] = None
    job_type: str
    stage: str
    status: str
    attempt_count: int
    max_attempts: int
    available_at: str
    updated_at: str
    current_stage: str
    current_stage_label: str
    progress_percent: int
    retryable: bool
    last_error: Optional[Dict[str, Any]] = None
    payload: Dict[str, Any]
    result: Optional[Dict[str, Any]] = None
    error: Optional[Dict[str, Any]] = None


class EpisodeListItem(BaseModel):
    id: str
    source_url: str
    source_type: str
    source_episode_id: str
    podcast_title: str
    episode_title: str
    cover_image_url: str
    audio_url: str
    published_at: Optional[str] = None
    duration_seconds: Optional[int] = None
    status: str
    processing_stage: str
    current_stage: str
    current_stage_label: str
    progress_percent: int
    last_error: Optional[str] = None
    failure_code: Optional[str] = None
    failure_message: Optional[str] = None
    updated_at: str


class EpisodeListResponse(BaseModel):
    items: List[EpisodeListItem]
    total: int
    page: int
    page_size: int


class ModuleManifestResponse(BaseModel):
    module_key: str
    display_name: str
    description: str
    copy_markdown: bool
    viewable: bool
    supports_html_view: bool
    supports_png_export: bool
    transcript_fidelity: Optional[str] = None


class ModuleOutputResponse(BaseModel):
    module_key: str
    display_name: str
    version: str
    format: str
    status: str
    content_json: Dict[str, Any]
    rendered_markdown: Optional[str] = None
    rendered_html: Optional[str] = None
    manifest: ModuleManifestResponse
    artifacts: List["ArtifactResponse"] = Field(default_factory=list)
    citations_json: List[Dict[str, Any]] = Field(default_factory=list)


class ArtifactResponse(BaseModel):
    artifact_key: str
    format: str
    mime_type: str
    download_url: str
    size_bytes: int


class TranscriptChunkResponse(BaseModel):
    id: str
    chunk_index: int
    start_ms: int
    end_ms: int
    text: str
    metadata: Dict[str, Any]


class EpisodeDetailResponse(BaseModel):
    episode: EpisodeListItem
    modules: List[ModuleOutputResponse]
    transcript_chunks: List[TranscriptChunkResponse]
    artifacts: List[ArtifactResponse]


ModuleOutputResponse.model_rebuild()

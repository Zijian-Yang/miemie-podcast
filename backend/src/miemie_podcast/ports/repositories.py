from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

from miemie_podcast.domain.models import (
    Artifact,
    Episode,
    Job,
    ModuleOutput,
    RequestContext,
    SearchDocument,
    Session,
    TranscriptChunk,
    User,
    Workspace,
)


class WorkspaceRepository(ABC):
    @abstractmethod
    def ensure_default_workspace(self) -> Workspace:
        raise NotImplementedError

    @abstractmethod
    def get_by_id(self, workspace_id: str) -> Optional[Workspace]:
        raise NotImplementedError


class UserRepository(ABC):
    @abstractmethod
    def ensure_default_admin(self, workspace_id: str) -> User:
        raise NotImplementedError

    @abstractmethod
    def get_by_id(self, workspace_id: str, user_id: str) -> Optional[User]:
        raise NotImplementedError


class SessionRepository(ABC):
    @abstractmethod
    def create(self, workspace_id: str, user_id: str, token_hash: str, expires_at: str) -> Session:
        raise NotImplementedError

    @abstractmethod
    def get_by_token_hash(self, token_hash: str) -> Optional[Session]:
        raise NotImplementedError

    @abstractmethod
    def delete(self, session_id: str) -> None:
        raise NotImplementedError


class EpisodeRepository(ABC):
    @abstractmethod
    def create(self, context: RequestContext, source_type: str, source_url: str, source_episode_id: str) -> Episode:
        raise NotImplementedError

    @abstractmethod
    def find_active_by_source_url(self, workspace_id: str, source_url: str) -> Optional[Episode]:
        raise NotImplementedError

    @abstractmethod
    def get_by_id(self, workspace_id: str, episode_id: str) -> Optional[Episode]:
        raise NotImplementedError

    @abstractmethod
    def list(
        self,
        workspace_id: str,
        query: Optional[str],
        status: Optional[str],
        podcast_title: Optional[str],
        sort: str,
        page: int,
        page_size: int,
    ) -> Dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    def update_fields(self, workspace_id: str, episode_id: str, fields: Dict[str, Any]) -> None:
        raise NotImplementedError

    @abstractmethod
    def soft_delete(self, workspace_id: str, episode_id: str) -> None:
        raise NotImplementedError


class EpisodeSourceRepository(ABC):
    @abstractmethod
    def upsert(self, workspace_id: str, episode_id: str, source_type: str, normalized_source: str, raw_payload_json: str) -> None:
        raise NotImplementedError


class JobRepository(ABC):
    @abstractmethod
    def create(
        self,
        workspace_id: str,
        episode_id: Optional[str],
        job_type: str,
        stage: str,
        payload_json: str,
        dedupe_key: Optional[str],
        available_at: str,
        max_attempts: int,
    ) -> Job:
        raise NotImplementedError

    @abstractmethod
    def claim(self, worker_id: str, supported_types: Sequence[str], limit: int) -> List[Job]:
        raise NotImplementedError

    @abstractmethod
    def get_by_id(self, workspace_id: str, job_id: str) -> Optional[Job]:
        raise NotImplementedError

    @abstractmethod
    def heartbeat(self, job_id: str, stage: str) -> None:
        raise NotImplementedError

    @abstractmethod
    def complete(self, job_id: str, result_json: str) -> None:
        raise NotImplementedError

    @abstractmethod
    def fail(self, job_id: str, error_json: str, retryable: bool, next_available_at: Optional[str]) -> None:
        raise NotImplementedError


class TranscriptRepository(ABC):
    @abstractmethod
    def replace_for_episode(self, workspace_id: str, episode_id: str, chunks: Sequence[TranscriptChunk]) -> None:
        raise NotImplementedError

    @abstractmethod
    def list_by_episode(self, workspace_id: str, episode_id: str) -> List[TranscriptChunk]:
        raise NotImplementedError


class ModuleOutputRepository(ABC):
    @abstractmethod
    def upsert(self, workspace_id: str, episode_id: str, module_output: ModuleOutput) -> None:
        raise NotImplementedError

    @abstractmethod
    def list_by_episode(self, workspace_id: str, episode_id: str) -> List[ModuleOutput]:
        raise NotImplementedError


class SearchRepository(ABC):
    @abstractmethod
    def replace_for_episode(self, workspace_id: str, episode_id: str, documents: Sequence[SearchDocument]) -> None:
        raise NotImplementedError

    @abstractmethod
    def search_episode(self, workspace_id: str, episode_id: str, query: str, limit: int) -> List[SearchDocument]:
        raise NotImplementedError


class ArtifactRepository(ABC):
    @abstractmethod
    def upsert(self, workspace_id: str, episode_id: str, artifact: Artifact) -> None:
        raise NotImplementedError

    @abstractmethod
    def list_by_episode(self, workspace_id: str, episode_id: str) -> List[Artifact]:
        raise NotImplementedError

    @abstractmethod
    def get_by_key(self, workspace_id: str, episode_id: str, artifact_key: str) -> Optional[Artifact]:
        raise NotImplementedError


class ObjectStorage(ABC):
    @abstractmethod
    def save_text(self, relative_path: str, content: str) -> Dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    def save_bytes(self, relative_path: str, content: bytes) -> Dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    def resolve_path(self, relative_path: str) -> Path:
        raise NotImplementedError

    @abstractmethod
    def delete_prefix(self, relative_prefix: str) -> None:
        raise NotImplementedError


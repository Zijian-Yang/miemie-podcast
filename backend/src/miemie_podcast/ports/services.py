from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Sequence

from miemie_podcast.domain.models import Citation, QAAnswer, SourceAdapterResult


class JobQueue(ABC):
    @abstractmethod
    def enqueue(
        self,
        workspace_id: str,
        episode_id: Optional[str],
        job_type: str,
        payload: Dict[str, Any],
        dedupe_key: Optional[str],
        run_after: Optional[str],
        max_attempts: int = 10,
        stage: Optional[str] = None,
    ) -> Dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    def claim(self, worker_id: str, supported_types: Sequence[str], limit: int) -> List[Dict[str, Any]]:
        raise NotImplementedError

    @abstractmethod
    def heartbeat(self, job_id: str, progress: Optional[float], stage: str) -> None:
        raise NotImplementedError

    @abstractmethod
    def complete(self, job_id: str, result: Dict[str, Any]) -> None:
        raise NotImplementedError

    @abstractmethod
    def fail(self, job_id: str, error: Dict[str, Any], retryable: bool) -> None:
        raise NotImplementedError


class SourceAdapter(ABC):
    @abstractmethod
    def supports(self, source_url: str) -> bool:
        raise NotImplementedError

    @abstractmethod
    def parse(self, source_url: str) -> SourceAdapterResult:
        raise NotImplementedError


class SpeechToTextProvider(ABC):
    @abstractmethod
    def submit_file(self, url: str, metadata: Dict[str, Any]) -> Dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    def get_result(self, task_id: str) -> Dict[str, Any]:
        raise NotImplementedError


class LanguageModelProvider(ABC):
    @abstractmethod
    def generate_json(
        self,
        task: str,
        schema: Dict[str, Any],
        input_parts: Sequence[Dict[str, Any]],
        cache_strategy: Optional[Dict[str, Any]] = None,
        temperature: float = 0.2,
        model: Optional[str] = None,
    ) -> Dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    def answer_with_citations(
        self,
        question: str,
        evidence_set: Sequence[Dict[str, Any]],
        output_schema: Dict[str, Any],
        cache_strategy: Optional[Dict[str, Any]] = None,
    ) -> QAAnswer:
        raise NotImplementedError


from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence

from miemie_podcast.domain.models import Job
from miemie_podcast.ports.repositories import JobRepository
from miemie_podcast.ports.services import JobQueue
from miemie_podcast.utils import json_dumps, json_loads, now_iso, seconds_from_now


class DatabasePollingQueue(JobQueue):
    def __init__(self, job_repository: JobRepository) -> None:
        self.job_repository = job_repository

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
        job = self.job_repository.create(
            workspace_id=workspace_id,
            episode_id=episode_id,
            job_type=job_type,
            stage=stage or job_type,
            payload_json=json_dumps(payload),
            dedupe_key=dedupe_key,
            available_at=run_after or now_iso(),
            max_attempts=max_attempts,
        )
        return {"job_id": job.id}

    def claim(self, worker_id: str, supported_types: Sequence[str], limit: int) -> List[Dict[str, Any]]:
        jobs = self.job_repository.claim(worker_id, supported_types, limit)
        return [
            {
                "job_id": job.id,
                "workspace_id": job.workspace_id,
                "episode_id": job.episode_id,
                "job_type": job.job_type,
                "stage": job.stage,
                "attempt_count": job.attempt_count,
                "payload": json_loads(job.payload_json, {}),
            }
            for job in jobs
        ]

    def heartbeat(self, job_id: str, progress: Optional[float], stage: str) -> None:
        _ = progress
        self.job_repository.heartbeat(job_id, stage)

    def complete(self, job_id: str, result: Dict[str, Any]) -> None:
        self.job_repository.complete(job_id, json_dumps(result))

    def fail(self, job_id: str, error: Dict[str, Any], retryable: bool) -> None:
        next_available_at = seconds_from_now(30) if retryable else None
        payload = {**error, "retryable": retryable}
        self.job_repository.fail(job_id, json_dumps(payload), retryable, next_available_at)


from __future__ import annotations

import logging
from typing import Any, Dict

from miemie_podcast.application.container import Container


logger = logging.getLogger(__name__)


class WorkerRunner:
    SUPPORTED_JOB_TYPES = ["import_episode", "poll_transcription", "analyze_episode"]

    def __init__(self, container: Container) -> None:
        self.container = container

    def run_once(self, worker_id: str) -> int:
        claimed_jobs = self.container.job_queue.claim(worker_id, self.SUPPORTED_JOB_TYPES, limit=1)
        if not claimed_jobs:
            return 0
        logger.info("Worker claimed %s job(s): %s", len(claimed_jobs), [job["job_id"] for job in claimed_jobs])
        for job in claimed_jobs:
            self._process_job(job)
        return len(claimed_jobs)

    def _process_job(self, job: Dict[str, Any]) -> None:
        job_id = job["job_id"]
        workspace_id = job["workspace_id"]
        job_type = job["job_type"]
        payload = job["payload"]
        self.container.job_queue.heartbeat(job_id, progress=None, stage=job_type)
        logger.info(
            "Worker processing job: job_id=%s, job_type=%s, workspace_id=%s, episode_id=%s",
            job_id,
            job_type,
            workspace_id,
            payload.get("episode_id"),
        )
        try:
            if job_type == "import_episode":
                result = self.container.episode_service.process_import_job(
                    workspace_id=workspace_id,
                    episode_id=payload["episode_id"],
                    source_url=payload["source_url"],
                )
            elif job_type == "poll_transcription":
                result = self.container.episode_service.process_poll_transcription_job(
                    workspace_id=workspace_id,
                    episode_id=payload["episode_id"],
                    task_id=payload["task_id"],
                )
            elif job_type == "analyze_episode":
                result = self.container.episode_service.process_analyze_episode_job(
                    workspace_id=workspace_id,
                    episode_id=payload["episode_id"],
                )
            else:
                raise RuntimeError(f"Unsupported job type: {job_type}")
            self.container.job_queue.complete(job_id, result)
            logger.info("Worker completed job: job_id=%s, job_type=%s, result=%s", job_id, job_type, result)
        except Exception as exc:  # noqa: BLE001
            logger.exception("Worker failed job: job_id=%s, job_type=%s", job_id, job_type)
            self.container.job_queue.fail(
                job_id,
                {"message": str(exc), "job_type": job_type},
                retryable=job_type == "poll_transcription",
            )

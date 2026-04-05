from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from miemie_podcast.api.deps import get_request_context
from miemie_podcast.api.schemas import JobResponse
from miemie_podcast.application.presentation import get_job_progress_payload
from miemie_podcast.application.container import Container, get_container
from miemie_podcast.domain.models import RequestContext
from miemie_podcast.utils import json_loads

router = APIRouter(prefix="/api/v1/jobs", tags=["jobs"])


@router.get("/{job_id}", response_model=JobResponse)
def get_job(
    job_id: str,
    context: RequestContext = Depends(get_request_context),
    container: Container = Depends(get_container),
) -> JobResponse:
    job = container.job_repository.get_by_id(context.workspace_id, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found.")
    progress = get_job_progress_payload(job)
    return JobResponse(
        id=job.id,
        workspace_id=job.workspace_id,
        episode_id=job.episode_id,
        job_type=job.job_type,
        stage=job.stage,
        status=job.status.value,
        attempt_count=job.attempt_count,
        max_attempts=job.max_attempts,
        available_at=job.available_at,
        updated_at=job.updated_at,
        current_stage=progress["current_stage"],
        current_stage_label=progress["current_stage_label"],
        progress_percent=progress["progress_percent"],
        retryable=progress["retryable"],
        last_error=progress["last_error"],
        payload=json_loads(job.payload_json, {}),
        result=json_loads(job.result_json, None),
        error=json_loads(job.error_json, None),
    )

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse

from miemie_podcast.api.deps import get_request_context
from miemie_podcast.api.schemas import (
    ArtifactResponse,
    EpisodeDetailResponse,
    EpisodeListItem,
    EpisodeListResponse,
    ImportEpisodeRequest,
    ModuleManifestResponse,
    ModuleOutputResponse,
    QAResponse,
    QuestionRequest,
    TranscriptChunkResponse,
)
from miemie_podcast.application.container import Container, get_container
from miemie_podcast.application.presentation import (
    get_episode_progress_payload,
    get_module_manifest,
    group_artifacts_by_module,
)
from miemie_podcast.domain.models import RequestContext
from miemie_podcast.utils import json_loads

router = APIRouter(prefix="/api/v1/episodes", tags=["episodes"])


def _serialize_episode(item) -> EpisodeListItem:
    progress = get_episode_progress_payload(item)
    return EpisodeListItem(
        id=item.id,
        source_url=item.source_url,
        source_type=item.source_type,
        source_episode_id=item.source_episode_id,
        podcast_title=item.podcast_title,
        episode_title=item.episode_title,
        cover_image_url=item.cover_image_url,
        audio_url=item.audio_url,
        published_at=item.published_at,
        duration_seconds=item.duration_seconds,
        status=item.status.value,
        processing_stage=item.processing_stage,
        current_stage=progress["current_stage"],
        current_stage_label=progress["current_stage_label"],
        progress_percent=progress["progress_percent"],
        last_error=progress["last_error"],
        failure_code=item.failure_code,
        failure_message=item.failure_message,
        updated_at=item.updated_at,
    )


@router.post("/import")
def import_episode(
    payload: ImportEpisodeRequest,
    context: RequestContext = Depends(get_request_context),
    container: Container = Depends(get_container),
):
    try:
        result = container.episode_service.import_episode(context, payload.source_url)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    episode = _serialize_episode(result["episode"])
    return {
        "episode": episode.model_dump(),
        "job": result.get("job"),
        "reused": result["reused"],
    }


@router.get("", response_model=EpisodeListResponse)
def list_episodes(
    query: Optional[str] = Query(default=None),
    status: Optional[str] = Query(default=None),
    podcast_title: Optional[str] = Query(default=None),
    sort: str = Query(default="latest"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    context: RequestContext = Depends(get_request_context),
    container: Container = Depends(get_container),
) -> EpisodeListResponse:
    result = container.episode_service.list_episodes(context, query, status, podcast_title, sort, page, page_size)
    return EpisodeListResponse(
        items=[_serialize_episode(item) for item in result["items"]],
        total=result["total"],
        page=result["page"],
        page_size=result["page_size"],
    )


@router.get("/{episode_id}", response_model=EpisodeDetailResponse)
def get_episode(
    episode_id: str,
    context: RequestContext = Depends(get_request_context),
    container: Container = Depends(get_container),
) -> EpisodeDetailResponse:
    try:
        result = container.episode_service.get_episode_detail(context, episode_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    artifacts = [
        ArtifactResponse(
            artifact_key=item.artifact_key,
            format=item.format,
            mime_type=item.mime_type,
            download_url=f"/api/v1/episodes/{episode_id}/exports/{item.artifact_key}",
            size_bytes=item.size_bytes,
        )
        for item in result["artifacts"]
    ]
    artifacts_by_module = group_artifacts_by_module(result["artifacts"])
    modules = [
        ModuleOutputResponse(
            module_key=item.module_key,
            display_name=get_module_manifest(item.module_key)["display_name"],
            version=item.version,
            format=item.format,
            status=item.status.value,
            content_json=json_loads(item.content_json, {}),
            rendered_markdown=item.rendered_markdown,
            rendered_html=item.rendered_html,
            manifest=ModuleManifestResponse(**get_module_manifest(item.module_key)),
            artifacts=[
                ArtifactResponse(
                    artifact_key=artifact.artifact_key,
                    format=artifact.format,
                    mime_type=artifact.mime_type,
                    download_url=f"/api/v1/episodes/{episode_id}/exports/{artifact.artifact_key}",
                    size_bytes=artifact.size_bytes,
                )
                for artifact in artifacts_by_module.get(item.module_key, [])
            ],
            citations_json=json_loads(item.citations_json, []),
        )
        for item in result["modules"]
    ]
    transcript_chunks = [
        TranscriptChunkResponse(
            id=item.id,
            chunk_index=item.chunk_index,
            start_ms=item.start_ms,
            end_ms=item.end_ms,
            text=item.text,
            metadata=json_loads(item.metadata_json, {}),
        )
        for item in result["transcript_chunks"]
    ]
    return EpisodeDetailResponse(
        episode=_serialize_episode(result["episode"]),
        modules=modules,
        transcript_chunks=transcript_chunks,
        artifacts=artifacts,
    )


@router.delete("/{episode_id}")
def delete_episode(
    episode_id: str,
    context: RequestContext = Depends(get_request_context),
    container: Container = Depends(get_container),
):
    try:
        container.episode_service.delete_episode(context, episode_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"success": True}


@router.post("/{episode_id}/qa", response_model=QAResponse)
def ask_episode(
    episode_id: str,
    payload: QuestionRequest,
    context: RequestContext = Depends(get_request_context),
    container: Container = Depends(get_container),
) -> QAResponse:
    try:
        result = container.episode_service.answer_question(context, episode_id, payload.question)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return QAResponse(**result)


@router.get("/{episode_id}/exports/{artifact_key}")
def export_episode_artifact(
    episode_id: str,
    artifact_key: str,
    context: RequestContext = Depends(get_request_context),
    container: Container = Depends(get_container),
):
    try:
        path = container.episode_service.export_artifact_path(context, episode_id, artifact_key)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return FileResponse(path)

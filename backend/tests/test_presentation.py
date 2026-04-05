from miemie_podcast.application.presentation import (
    get_episode_progress_payload,
    get_job_progress_payload,
    get_module_manifest,
)
from miemie_podcast.domain.models import Episode, EpisodeStatus, Job, JobStatus
from miemie_podcast.utils import json_dumps


def test_episode_progress_payload_uses_human_label():
    episode = Episode(
        id="ep_1",
        workspace_id="ws_1",
        owner_user_id="user_1",
        created_by="user_1",
        visibility="private",
        source_type="XiaoyuzhouEpisodeSourceAdapter",
        source_url="https://example.com",
        source_episode_id="69b1645e9b893f69c739b82a",
        podcast_title="节目",
        episode_title="标题",
        cover_image_url="",
        audio_url="",
        published_at=None,
        duration_seconds=None,
        status=EpisodeStatus.ANALYZING,
        processing_stage="analyzing",
        transcription_task_id=None,
        transcription_provider=None,
        failure_code=None,
        failure_message=None,
        created_at="2026-01-01T00:00:00Z",
        updated_at="2026-01-01T00:00:00Z",
    )
    payload = get_episode_progress_payload(episode)
    assert payload["current_stage_label"]
    assert payload["progress_percent"] > 0


def test_job_progress_payload_exposes_retryability():
    job = Job(
        id="job_1",
        workspace_id="ws_1",
        episode_id="ep_1",
        job_type="poll_transcription",
        stage="poll_transcription",
        status=JobStatus.PENDING,
        payload_json=json_dumps({"task_id": "task_1"}),
        result_json=None,
        error_json=json_dumps({"message": "temporary failure", "retryable": True}),
        attempt_count=1,
        max_attempts=10,
        dedupe_key="ws_1:ep_1:poll_transcription",
        available_at="2026-01-01T00:00:00Z",
        locked_by=None,
        locked_at=None,
        heartbeat_at=None,
        created_at="2026-01-01T00:00:00Z",
        updated_at="2026-01-01T00:00:00Z",
    )
    payload = get_job_progress_payload(job)
    assert payload["retryable"] is True
    assert payload["last_error"]["message"] == "temporary failure"


def test_module_manifest_marks_transcript_as_verbatim():
    manifest = get_module_manifest("transcript")
    assert manifest["copy_markdown"] is True
    assert manifest["transcript_fidelity"] == "verbatim_asr"


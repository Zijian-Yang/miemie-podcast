from __future__ import annotations

import json
import threading
import time
from pathlib import Path
from types import SimpleNamespace

from miemie_podcast.application import services
from miemie_podcast.application.services import EpisodeService
from miemie_podcast.domain.models import Episode, EpisodeStatus, TranscriptChunk


class StubEpisodeRepository:
    def __init__(self, episode: Episode) -> None:
        self.episode = episode
        self.updated_fields = []

    def get_by_id(self, workspace_id: str, episode_id: str):
        _ = workspace_id, episode_id
        return self.episode

    def update_fields(self, workspace_id: str, episode_id: str, fields):
        _ = workspace_id, episode_id
        self.updated_fields.append(fields)


class StubTranscriptRepository:
    def __init__(self, chunks):
        self.chunks = list(chunks)

    def list_by_episode(self, workspace_id: str, episode_id: str):
        _ = workspace_id, episode_id
        return list(self.chunks)


class StubModuleOutputRepository:
    def __init__(self) -> None:
        self.modules = []

    def upsert(self, workspace_id: str, episode_id: str, module):
        _ = workspace_id, episode_id
        self.modules.append(module)


class StubSearchRepository:
    def __init__(self) -> None:
        self.documents = []

    def replace_for_episode(self, workspace_id: str, episode_id: str, documents):
        _ = workspace_id, episode_id
        self.documents = list(documents)


class StubArtifactRepository:
    def __init__(self) -> None:
        self.artifacts = []

    def upsert(self, workspace_id: str, episode_id: str, artifact):
        _ = workspace_id, episode_id
        self.artifacts.append(artifact)


class StubStorage:
    def __init__(self, root: Path) -> None:
        self.root = root

    def save_text(self, relative_path: str, content: str):
        path = self.root / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return {"relative_path": relative_path, "size_bytes": len(content.encode("utf-8"))}

    def resolve_path(self, relative_path: str) -> Path:
        return self.root / relative_path


class TrackingLLMProvider:
    def __init__(self) -> None:
        self.lock = threading.Lock()
        self.active_chunk_extracts = 0
        self.max_active_chunk_extracts = 0
        self.section_merge_chunk_ids = []
        self.summary_started = threading.Event()
        self.knowledge_started = threading.Event()
        self.summary_overlapped = False
        self.knowledge_overlapped = False

    def generate_json(self, task, schema, input_parts, cache_strategy=None, temperature=0.2, model=None):
        _ = schema, cache_strategy, temperature, model
        prompt = input_parts[0]["text"]
        if task == "chunk_extract":
            chunk_label = prompt.rsplit("\n", 1)[-1]
            chunk_index = int(chunk_label.rsplit("-", 1)[-1])
            with self.lock:
                self.active_chunk_extracts += 1
                self.max_active_chunk_extracts = max(self.max_active_chunk_extracts, self.active_chunk_extracts)
            time.sleep(0.02 * (4 - chunk_index))
            with self.lock:
                self.active_chunk_extracts -= 1
            return {
                "summary": f"summary-{chunk_index}",
                "facts": [f"fact-{chunk_index}"],
                "insights": [f"insight-{chunk_index}"],
                "quotes": [f"quote-{chunk_index}"],
                "outline_nodes": [f"node-{chunk_index}"],
                "open_questions": [f"question-{chunk_index}"],
            }
        if task == "section_merge":
            payload = json.loads(prompt.split("输入：\n", 1)[1])
            self.section_merge_chunk_ids.append([item["chunk_id"] for item in payload])
            return {
                "section_title": "section-1",
                "summary": "section summary",
                "takeaways": ["takeaway"],
                "evidence_points": ["evidence"],
                "open_questions": ["open question"],
            }
        if task == "episode_summary":
            self.summary_started.set()
            self.summary_overlapped = self.knowledge_started.wait(timeout=0.2)
            return {
                "overview": "overview",
                "topic": "topic",
                "core_question": "core question",
                "themes": ["theme-a", "theme-b", "theme-c"],
                "argument_structure": ["argument"],
                "key_evidence": ["evidence"],
                "conclusions": ["conclusion"],
                "actionable_insights": ["insight"],
                "open_questions": ["question"],
            }
        if task == "episode_knowledge":
            self.knowledge_started.set()
            self.knowledge_overlapped = self.summary_started.wait(timeout=0.2)
            return {
                "conclusions": ["conclusion"],
                "principles": ["principle"],
                "quotes": ["quote"],
                "signals": ["signal"],
                "concepts": ["concept"],
                "research_questions": ["question"],
            }
        if task == "mindmap_spec_build":
            return {"root": {"title": "root", "children": []}}
        raise AssertionError(f"Unexpected task: {task}")


def test_process_analyze_episode_job_parallelizes_chunk_extracts_and_module_builds(tmp_path, monkeypatch):
    monkeypatch.setattr(services, "render_mindmap_png", lambda command, html_path, png_path: False)

    episode = Episode(
        id="ep_1",
        workspace_id="ws_1",
        owner_user_id="user_1",
        created_by="user_1",
        visibility="private",
        source_type="source",
        source_url="https://example.com/ep",
        source_episode_id="source_ep_1",
        podcast_title="podcast",
        episode_title="episode",
        cover_image_url="",
        audio_url="",
        published_at="2026-04-06T00:00:00Z",
        duration_seconds=3600,
        status=EpisodeStatus.TRANSCRIBED,
        processing_stage="transcribed",
        transcription_task_id=None,
        transcription_provider=None,
        failure_code=None,
        failure_message=None,
        created_at="2026-04-06T00:00:00Z",
        updated_at="2026-04-06T00:00:00Z",
    )
    chunks = [
        TranscriptChunk(
            id=f"chunk-{index}",
            workspace_id="ws_1",
            episode_id="ep_1",
            chunk_index=index,
            start_ms=index * 1000,
            end_ms=index * 1000 + 900,
            text=f"chunk-{index}",
            metadata_json="{}",
            created_at="2026-04-06T00:00:00Z",
            updated_at="2026-04-06T00:00:00Z",
        )
        for index in range(4)
    ]
    llm_provider = TrackingLLMProvider()
    service = EpisodeService.__new__(EpisodeService)
    service.settings = SimpleNamespace(
        analysis_chunk_extract_concurrency=4,
        mindmap_renderer_command="node scripts/render-mindmap.mjs",
    )
    service.episode_repository = StubEpisodeRepository(episode)
    service.transcript_repository = StubTranscriptRepository(chunks)
    service.module_output_repository = StubModuleOutputRepository()
    service.search_repository = StubSearchRepository()
    service.artifact_repository = StubArtifactRepository()
    service.storage = StubStorage(tmp_path)
    service.llm_provider = llm_provider
    service.source_adapters = []

    result = service.process_analyze_episode_job("ws_1", "ep_1")

    assert result["status"] == "ready"
    assert llm_provider.max_active_chunk_extracts >= 2
    assert llm_provider.section_merge_chunk_ids == [["chunk-0", "chunk-1", "chunk-2", "chunk-3"]]
    assert llm_provider.summary_overlapped is True
    assert llm_provider.knowledge_overlapped is True

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

from miemie_podcast.adapters.providers.qwen import render_mindmap_png
from miemie_podcast.application.prompts import (
    build_chunk_extract_prompt,
    build_episode_knowledge_prompt,
    build_episode_summary_prompt,
    build_mindmap_prompt,
    build_section_merge_prompt,
)
from miemie_podcast.config import Settings
from miemie_podcast.domain.models import Artifact, Citation, EpisodeStatus, RequestContext
from miemie_podcast.ports.repositories import (
    ArtifactRepository,
    EpisodeRepository,
    EpisodeSourceRepository,
    ModuleOutputRepository,
    ObjectStorage,
    SearchRepository,
    TranscriptRepository,
)
from miemie_podcast.ports.services import JobQueue, LanguageModelProvider, SourceAdapter, SpeechToTextProvider
from miemie_podcast.application.pipeline import (
    build_search_documents,
    build_transcript_chunks,
    make_chunk_evidence,
    make_module_output,
    normalize_asr_sentences,
    render_knowledge_markdown,
    render_mindmap_html,
    render_summary_markdown,
    render_transcript_markdown,
)
from miemie_podcast.utils import json_dumps, json_loads, new_id, now_iso, seconds_from_now


SUMMARY_SCHEMA = {
    "overview": "string",
    "topic": "string",
    "core_question": "string",
    "themes": ["string"],
    "argument_structure": ["string"],
    "key_evidence": ["string"],
    "conclusions": ["string"],
    "actionable_insights": ["string"],
    "open_questions": ["string"],
}

KNOWLEDGE_SCHEMA = {
    "conclusions": ["string"],
    "principles": ["string"],
    "quotes": ["string"],
    "signals": ["string"],
    "concepts": ["string"],
    "research_questions": ["string"],
}

CHUNK_EXTRACT_SCHEMA = {
    "summary": "string",
    "facts": ["string"],
    "insights": ["string"],
    "quotes": ["string"],
    "outline_nodes": ["string"],
    "open_questions": ["string"],
}

SECTION_SCHEMA = {
    "section_title": "string",
    "summary": "string",
    "takeaways": ["string"],
    "evidence_points": ["string"],
    "open_questions": ["string"],
}

MINDMAP_SCHEMA = {
    "root": {
        "title": "string",
        "children": [{"title": "string", "children": []}],
    }
}

QA_SCHEMA = {
    "answer": "string",
    "citations": [
        {
            "source_kind": "string",
            "chunk_id": "string",
            "start_ms": 0,
            "end_ms": 0,
            "excerpt": "string",
        }
    ],
}


def _string_list(value: Any) -> List[str]:
    if not isinstance(value, list):
        return []
    items: List[str] = []
    for item in value:
        text = str(item).strip()
        if text:
            items.append(text)
    return items


def _unique(values: Sequence[str], limit: int = 8) -> List[str]:
    seen = set()
    output: List[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        output.append(value)
        if len(output) >= limit:
            break
    return output


def _flatten(items: Sequence[Dict[str, Any]], field: str) -> List[str]:
    values: List[str] = []
    for item in items:
        values.extend(_string_list(item.get(field)))
    return values


def normalize_summary_data(data: Dict[str, Any], sections: Sequence[Dict[str, Any]], chunk_extracts: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    section_titles = [str(item.get("section_title", "")).strip() for item in sections if str(item.get("section_title", "")).strip()]
    section_summaries = [str(item.get("summary", "")).strip() for item in sections if str(item.get("summary", "")).strip()]
    section_takeaways = _flatten(sections, "takeaways")
    section_evidence = _flatten(sections, "evidence_points")
    section_questions = _flatten(sections, "open_questions")
    chunk_facts = _flatten(chunk_extracts, "facts")
    chunk_quotes = _flatten(chunk_extracts, "quotes")

    themes = _unique(_string_list(data.get("themes")) or section_titles, limit=6)
    argument_structure = _unique(_string_list(data.get("argument_structure")) or section_takeaways or section_summaries, limit=6)
    key_evidence = _unique(_string_list(data.get("key_evidence")) or section_evidence or chunk_facts or chunk_quotes, limit=6)
    conclusions = _unique(_string_list(data.get("conclusions")) or section_takeaways or argument_structure, limit=6)
    actionable_insights = _unique(_string_list(data.get("actionable_insights")) or conclusions[:3], limit=6)
    open_questions = _unique(_string_list(data.get("open_questions")) or section_questions, limit=6)
    topic = str(data.get("topic") or (themes[0] if themes else "")).strip()
    core_question = str(data.get("core_question") or (open_questions[0] if open_questions else "")).strip()

    return {
        "overview": str(data.get("overview") or "本期播客围绕关键议题展开了多层次讨论。").strip(),
        "topic": topic,
        "core_question": core_question,
        "themes": themes,
        "argument_structure": argument_structure,
        "key_evidence": key_evidence,
        "conclusions": conclusions,
        "actionable_insights": actionable_insights,
        "open_questions": open_questions,
    }


def normalize_knowledge_data(data: Dict[str, Any], sections: Sequence[Dict[str, Any]], chunk_extracts: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    section_takeaways = _flatten(sections, "takeaways")
    section_questions = _flatten(sections, "open_questions")
    chunk_insights = _flatten(chunk_extracts, "insights")
    chunk_quotes = _flatten(chunk_extracts, "quotes")
    chunk_nodes = _flatten(chunk_extracts, "outline_nodes")

    conclusions = _unique(_string_list(data.get("conclusions")) or section_takeaways or chunk_insights, limit=8)
    principles = _unique(_string_list(data.get("principles")) or chunk_insights or conclusions, limit=8)
    quotes = _unique(_string_list(data.get("quotes")) or chunk_quotes, limit=8)
    signals = _unique(_string_list(data.get("signals")) or conclusions[:4], limit=6)
    concepts = _unique(_string_list(data.get("concepts")) or chunk_nodes, limit=8)
    research_questions = _unique(_string_list(data.get("research_questions")) or section_questions, limit=6)

    return {
        "conclusions": conclusions,
        "principles": principles,
        "quotes": quotes,
        "signals": signals,
        "concepts": concepts,
        "research_questions": research_questions,
    }


class EpisodeService:
    def __init__(
        self,
        settings: Settings,
        episode_repository: EpisodeRepository,
        episode_source_repository: EpisodeSourceRepository,
        transcript_repository: TranscriptRepository,
        module_output_repository: ModuleOutputRepository,
        search_repository: SearchRepository,
        artifact_repository: ArtifactRepository,
        storage: ObjectStorage,
        queue: JobQueue,
        llm_provider: LanguageModelProvider,
        stt_provider: SpeechToTextProvider,
        source_adapters: Sequence[SourceAdapter],
    ) -> None:
        self.settings = settings
        self.episode_repository = episode_repository
        self.episode_source_repository = episode_source_repository
        self.transcript_repository = transcript_repository
        self.module_output_repository = module_output_repository
        self.search_repository = search_repository
        self.artifact_repository = artifact_repository
        self.storage = storage
        self.queue = queue
        self.llm_provider = llm_provider
        self.stt_provider = stt_provider
        self.source_adapters = list(source_adapters)

    def import_episode(self, context: RequestContext, source_url: str) -> Dict[str, Any]:
        existing = self.episode_repository.find_active_by_source_url(context.workspace_id, source_url)
        if existing:
            return {"episode": existing, "reused": True}
        adapter = self._get_adapter(source_url)
        source_episode_id = source_url.rstrip("/").split("/")[-1]
        episode = self.episode_repository.create(
            context=context,
            source_type=adapter.__class__.__name__,
            source_url=source_url,
            source_episode_id=source_episode_id,
        )
        job = self.queue.enqueue(
            workspace_id=context.workspace_id,
            episode_id=episode.id,
            job_type="import_episode",
            payload={"episode_id": episode.id, "source_url": source_url},
            dedupe_key=f"{context.workspace_id}:{source_url}",
            run_after=None,
            stage="import_episode",
        )
        return {"episode": episode, "job": job, "reused": False}

    def list_episodes(
        self,
        context: RequestContext,
        query: Optional[str],
        status: Optional[str],
        podcast_title: Optional[str],
        sort: str,
        page: int,
        page_size: int,
    ) -> Dict[str, Any]:
        return self.episode_repository.list(
            workspace_id=context.workspace_id,
            query=query,
            status=status,
            podcast_title=podcast_title,
            sort=sort,
            page=page,
            page_size=page_size,
        )

    def get_episode_detail(self, context: RequestContext, episode_id: str) -> Dict[str, Any]:
        episode = self._get_episode_or_raise(context.workspace_id, episode_id)
        modules = self.module_output_repository.list_by_episode(context.workspace_id, episode_id)
        chunks = self.transcript_repository.list_by_episode(context.workspace_id, episode_id)
        artifacts = self.artifact_repository.list_by_episode(context.workspace_id, episode_id)
        return {
            "episode": episode,
            "modules": modules,
            "transcript_chunks": chunks,
            "artifacts": artifacts,
        }

    def delete_episode(self, context: RequestContext, episode_id: str) -> None:
        self._get_episode_or_raise(context.workspace_id, episode_id)
        self.episode_repository.soft_delete(context.workspace_id, episode_id)
        self.storage.delete_prefix(f"workspaces/{context.workspace_id}/episodes/{episode_id}")

    def answer_question(self, context: RequestContext, episode_id: str, question: str) -> Dict[str, Any]:
        self._get_episode_or_raise(context.workspace_id, episode_id)
        evidence_docs = self.search_repository.search_episode(context.workspace_id, episode_id, question, limit=8)
        evidence_payload = [
            {
                "source_kind": doc.source_kind,
                "chunk_id": doc.id,
                "start_ms": None,
                "end_ms": None,
                "excerpt": doc.body[:800],
                "title": doc.title,
            }
            for doc in evidence_docs
        ]
        qa_answer = self.llm_provider.answer_with_citations(
            question=question,
            evidence_set=evidence_payload,
            output_schema=QA_SCHEMA,
            cache_strategy={"enabled": True},
        )
        return {
            "answer": qa_answer.answer,
            "citations": [
                {
                    "source_kind": item.source_kind,
                    "chunk_id": item.chunk_id,
                    "start_ms": item.start_ms,
                    "end_ms": item.end_ms,
                    "excerpt": item.excerpt,
                }
                for item in qa_answer.citations
            ],
        }

    def export_artifact_path(self, context: RequestContext, episode_id: str, artifact_key: str) -> Path:
        artifact = self.artifact_repository.get_by_key(context.workspace_id, episode_id, artifact_key)
        if not artifact:
            raise KeyError(f"Artifact not found: {artifact_key}")
        return self.storage.resolve_path(artifact.relative_path)

    def process_import_job(self, workspace_id: str, episode_id: str, source_url: str) -> Dict[str, Any]:
        adapter = self._get_adapter(source_url)
        result = adapter.parse(source_url)
        episode = self._get_episode_or_raise(workspace_id, episode_id)
        html_relative_path = f"workspaces/{workspace_id}/episodes/{episode_id}/source/source_snapshot.html"
        html_save_result = self.storage.save_text(html_relative_path, result.raw_snapshot.get("html", ""))
        self.artifact_repository.upsert(
            workspace_id,
            episode_id,
            Artifact(
                id=new_id("artifact"),
                workspace_id=workspace_id,
                episode_id=episode_id,
                artifact_key="source_snapshot.html",
                format="html",
                mime_type="text/html",
                relative_path=html_save_result["relative_path"],
                size_bytes=html_save_result["size_bytes"],
                metadata_json=json_dumps({"kind": "source_snapshot"}),
                created_at=now_iso(),
                updated_at=now_iso(),
            ),
        )
        self.episode_source_repository.upsert(
            workspace_id=workspace_id,
            episode_id=episode_id,
            source_type=adapter.__class__.__name__,
            normalized_source=result.normalized_source,
            raw_payload_json=json_dumps(result.raw_snapshot),
        )
        metadata = result.episode_metadata
        audio_url = result.audio_locator["audio_url"]
        self.episode_repository.update_fields(
            workspace_id,
            episode_id,
            {
                "source_url": result.normalized_source,
                "source_episode_id": metadata.get("source_episode_id") or episode.source_episode_id,
                "podcast_title": metadata.get("podcast_title") or episode.podcast_title,
                "episode_title": metadata.get("episode_title") or episode.episode_title,
                "cover_image_url": metadata.get("cover_image_url") or episode.cover_image_url,
                "audio_url": audio_url,
                "published_at": metadata.get("published_at"),
                "duration_seconds": metadata.get("duration_seconds"),
                "status": EpisodeStatus.SOURCE_RESOLVED,
                "processing_stage": "source_resolved",
                "failure_code": None,
                "failure_message": None,
            },
        )
        transcription_submit = self.stt_provider.submit_file(audio_url, metadata)
        self.episode_repository.update_fields(
            workspace_id,
            episode_id,
            {
                "status": EpisodeStatus.TRANSCRIBING,
                "processing_stage": "transcribing",
                "transcription_task_id": transcription_submit["task_id"],
                "transcription_provider": "qwen3-asr-flash-filetrans",
            },
        )
        self.queue.enqueue(
            workspace_id=workspace_id,
            episode_id=episode_id,
            job_type="poll_transcription",
            payload={"episode_id": episode_id, "task_id": transcription_submit["task_id"]},
            dedupe_key=f"{workspace_id}:{episode_id}:poll_transcription",
            run_after=seconds_from_now(20),
            stage="poll_transcription",
        )
        return {"status": "submitted", "task_id": transcription_submit["task_id"]}

    def process_poll_transcription_job(self, workspace_id: str, episode_id: str, task_id: str) -> Dict[str, Any]:
        result = self.stt_provider.get_result(task_id)
        if result["status"] in {"PENDING", "RUNNING"}:
            self.queue.enqueue(
                workspace_id=workspace_id,
                episode_id=episode_id,
                job_type="poll_transcription",
                payload={"episode_id": episode_id, "task_id": task_id},
                dedupe_key=f"{workspace_id}:{episode_id}:poll_transcription",
                run_after=seconds_from_now(20),
                stage="poll_transcription",
            )
            return {"status": result["status"].lower(), "task_id": task_id}
        if result["status"] != "SUCCEEDED":
            self.episode_repository.update_fields(
                workspace_id,
                episode_id,
                {
                    "status": EpisodeStatus.FAILED,
                    "processing_stage": "transcription_failed",
                    "failure_code": result.get("code"),
                    "failure_message": result.get("message"),
                },
            )
            raise RuntimeError(result.get("message") or "Transcription failed.")
        transcript_json = result["transcript_json"]
        raw_relative_path = f"workspaces/{workspace_id}/episodes/{episode_id}/transcript/raw_asr.json"
        raw_save_result = self.storage.save_text(raw_relative_path, json_dumps(transcript_json))
        self.artifact_repository.upsert(
            workspace_id,
            episode_id,
            Artifact(
                id=new_id("artifact"),
                workspace_id=workspace_id,
                episode_id=episode_id,
                artifact_key="raw_asr.json",
                format="json",
                mime_type="application/json",
                relative_path=raw_save_result["relative_path"],
                size_bytes=raw_save_result["size_bytes"],
                metadata_json=json_dumps({"kind": "raw_asr"}),
                created_at=now_iso(),
                updated_at=now_iso(),
            ),
        )
        sentences = normalize_asr_sentences(transcript_json)
        chunks = build_transcript_chunks(workspace_id, episode_id, sentences)
        self.transcript_repository.replace_for_episode(workspace_id, episode_id, chunks)
        transcript_markdown = render_transcript_markdown(sentences)
        transcript_relative_path = f"workspaces/{workspace_id}/episodes/{episode_id}/modules/transcript.md"
        transcript_save_result = self.storage.save_text(transcript_relative_path, transcript_markdown)
        self.artifact_repository.upsert(
            workspace_id,
            episode_id,
            Artifact(
                id=new_id("artifact"),
                workspace_id=workspace_id,
                episode_id=episode_id,
                artifact_key="transcript.md",
                format="md",
                mime_type="text/markdown",
                relative_path=transcript_save_result["relative_path"],
                size_bytes=transcript_save_result["size_bytes"],
                metadata_json=json_dumps({"module_key": "transcript"}),
                created_at=now_iso(),
                updated_at=now_iso(),
            ),
        )
        module = make_module_output(
            workspace_id=workspace_id,
            episode_id=episode_id,
            module_key="transcript",
            content={
                "sentence_count": len(sentences),
                "chunk_count": len(chunks),
                "fidelity_mode": "verbatim_asr",
                "export_assets": ["transcript.md", "raw_asr.json"],
            },
            rendered_markdown=transcript_markdown,
        )
        self.module_output_repository.upsert(workspace_id, episode_id, module)
        self.episode_repository.update_fields(
            workspace_id,
            episode_id,
            {
                "status": EpisodeStatus.TRANSCRIBED,
                "processing_stage": "transcribed",
                "failure_code": None,
                "failure_message": None,
            },
        )
        self.queue.enqueue(
            workspace_id=workspace_id,
            episode_id=episode_id,
            job_type="analyze_episode",
            payload={"episode_id": episode_id},
            dedupe_key=f"{workspace_id}:{episode_id}:analyze_episode",
            run_after=seconds_from_now(2),
            stage="analyze_episode",
        )
        return {"status": "transcribed", "chunk_count": len(chunks)}

    def process_analyze_episode_job(self, workspace_id: str, episode_id: str) -> Dict[str, Any]:
        episode = self._get_episode_or_raise(workspace_id, episode_id)
        chunks = self.transcript_repository.list_by_episode(workspace_id, episode_id)
        if not chunks:
            raise RuntimeError("No transcript chunks found for analysis.")
        self.episode_repository.update_fields(
            workspace_id,
            episode_id,
            {"status": EpisodeStatus.ANALYZING, "processing_stage": "analyzing"},
        )
        chunk_extracts = []
        for chunk in chunks:
            extraction = self.llm_provider.generate_json(
                task="chunk_extract",
                schema=CHUNK_EXTRACT_SCHEMA,
                input_parts=[
                    {
                        "role": "user",
                        "text": build_chunk_extract_prompt(chunk.text),
                        "cacheable": False,
                    }
                ],
                cache_strategy={"enabled": True},
            )
            chunk_extracts.append(
                {
                    "chunk_id": chunk.id,
                    "start_ms": chunk.start_ms,
                    "end_ms": chunk.end_ms,
                    **extraction,
                }
            )
        sections = []
        bucket_size = 4
        for start in range(0, len(chunk_extracts), bucket_size):
            part = chunk_extracts[start : start + bucket_size]
            section = self.llm_provider.generate_json(
                task="section_merge",
                schema=SECTION_SCHEMA,
                input_parts=[
                    {
                        "role": "user",
                        "text": build_section_merge_prompt(part),
                        "cacheable": False,
                    }
                ],
                cache_strategy={"enabled": True},
            )
            sections.append(section)
        summary_data = self.llm_provider.generate_json(
            task="episode_summary",
            schema=SUMMARY_SCHEMA,
            input_parts=[
                {
                    "role": "user",
                    "text": build_episode_summary_prompt(
                        {
                            "episode_title": episode.episode_title,
                            "podcast_title": episode.podcast_title,
                            "published_at": episode.published_at,
                            "duration_seconds": episode.duration_seconds,
                        },
                        sections,
                    ),
                    "cacheable": True,
                }
            ],
            cache_strategy={"enabled": True},
        )
        summary_data = normalize_summary_data(summary_data, sections, chunk_extracts)
        knowledge_data = self.llm_provider.generate_json(
            task="episode_knowledge",
            schema=KNOWLEDGE_SCHEMA,
            input_parts=[
                {
                    "role": "user",
                    "text": build_episode_knowledge_prompt(
                        {
                            "episode_title": episode.episode_title,
                            "podcast_title": episode.podcast_title,
                            "published_at": episode.published_at,
                            "duration_seconds": episode.duration_seconds,
                        },
                        sections,
                        chunk_extracts[:12],
                    ),
                    "cacheable": True,
                }
            ],
            cache_strategy={"enabled": True},
        )
        knowledge_data = normalize_knowledge_data(knowledge_data, sections, chunk_extracts)
        mindmap_spec = self.llm_provider.generate_json(
            task="mindmap_spec_build",
            schema=MINDMAP_SCHEMA,
            input_parts=[
                {
                    "role": "user",
                    "text": build_mindmap_prompt(episode.episode_title, summary_data, knowledge_data),
                    "cacheable": True,
                }
            ],
            cache_strategy={"enabled": True},
        )
        summary_markdown = render_summary_markdown(summary_data)
        knowledge_markdown = render_knowledge_markdown(knowledge_data)
        mindmap_html = render_mindmap_html(episode.episode_title, mindmap_spec)
        summary_artifact = self.storage.save_text(
            f"workspaces/{workspace_id}/episodes/{episode_id}/modules/summary.md",
            summary_markdown,
        )
        knowledge_artifact = self.storage.save_text(
            f"workspaces/{workspace_id}/episodes/{episode_id}/modules/knowledge.md",
            knowledge_markdown,
        )
        mindmap_html_artifact = self.storage.save_text(
            f"workspaces/{workspace_id}/episodes/{episode_id}/modules/mindmap.html",
            mindmap_html,
        )
        self.artifact_repository.upsert(
            workspace_id,
            episode_id,
            Artifact(
                id=new_id("artifact"),
                workspace_id=workspace_id,
                episode_id=episode_id,
                artifact_key="summary.md",
                format="md",
                mime_type="text/markdown",
                relative_path=summary_artifact["relative_path"],
                size_bytes=summary_artifact["size_bytes"],
                metadata_json=json_dumps({"module_key": "summary"}),
                created_at=now_iso(),
                updated_at=now_iso(),
            ),
        )
        self.artifact_repository.upsert(
            workspace_id,
            episode_id,
            Artifact(
                id=new_id("artifact"),
                workspace_id=workspace_id,
                episode_id=episode_id,
                artifact_key="knowledge.md",
                format="md",
                mime_type="text/markdown",
                relative_path=knowledge_artifact["relative_path"],
                size_bytes=knowledge_artifact["size_bytes"],
                metadata_json=json_dumps({"module_key": "knowledge"}),
                created_at=now_iso(),
                updated_at=now_iso(),
            ),
        )
        self.artifact_repository.upsert(
            workspace_id,
            episode_id,
            Artifact(
                id=new_id("artifact"),
                workspace_id=workspace_id,
                episode_id=episode_id,
                artifact_key="mindmap.html",
                format="html",
                mime_type="text/html",
                relative_path=mindmap_html_artifact["relative_path"],
                size_bytes=mindmap_html_artifact["size_bytes"],
                metadata_json=json_dumps({"module_key": "mindmap"}),
                created_at=now_iso(),
                updated_at=now_iso(),
            ),
        )
        mindmap_png_path = self.storage.resolve_path(
            f"workspaces/{workspace_id}/episodes/{episode_id}/modules/mindmap.png"
        )
        html_path = self.storage.resolve_path(mindmap_html_artifact["relative_path"])
        png_ready = render_mindmap_png(self.settings.mindmap_renderer_command, html_path, mindmap_png_path)
        if png_ready:
            self.artifact_repository.upsert(
                workspace_id,
                episode_id,
                Artifact(
                    id=new_id("artifact"),
                    workspace_id=workspace_id,
                    episode_id=episode_id,
                    artifact_key="mindmap.png",
                    format="png",
                    mime_type="image/png",
                    relative_path=f"workspaces/{workspace_id}/episodes/{episode_id}/modules/mindmap.png",
                    size_bytes=mindmap_png_path.stat().st_size,
                    metadata_json=json_dumps({"module_key": "mindmap"}),
                    created_at=now_iso(),
                    updated_at=now_iso(),
                ),
            )
        summary_module = make_module_output(
            workspace_id=workspace_id,
            episode_id=episode_id,
            module_key="summary",
            content={**summary_data, "export_assets": ["summary.md"]},
            rendered_markdown=summary_markdown,
        )
        knowledge_module = make_module_output(
            workspace_id=workspace_id,
            episode_id=episode_id,
            module_key="knowledge",
            content={**knowledge_data, "export_assets": ["knowledge.md"]},
            rendered_markdown=knowledge_markdown,
        )
        mindmap_module = make_module_output(
            workspace_id=workspace_id,
            episode_id=episode_id,
            module_key="mindmap",
            content={
                **mindmap_spec,
                "_delivery": {
                    "html_preview_available": True,
                    "html_export_key": "mindmap.html",
                    "png_export_key": "mindmap.png",
                    "png_render_status": "ready" if png_ready else "failed",
                    "fallback_outline_available": True,
                },
            },
            rendered_html=mindmap_html,
        )
        self.module_output_repository.upsert(workspace_id, episode_id, summary_module)
        self.module_output_repository.upsert(workspace_id, episode_id, knowledge_module)
        self.module_output_repository.upsert(workspace_id, episode_id, mindmap_module)
        search_documents = build_search_documents(
            workspace_id=workspace_id,
            episode_id=episode_id,
            episode_title=episode.episode_title,
            podcast_title=episode.podcast_title,
            summary_data=summary_data,
            knowledge_data=knowledge_data,
            transcript_chunks=chunks,
        )
        self.search_repository.replace_for_episode(workspace_id, episode_id, search_documents)
        self.episode_repository.update_fields(
            workspace_id,
            episode_id,
            {
                "status": EpisodeStatus.READY,
                "processing_stage": "ready",
                "failure_code": None,
                "failure_message": None,
            },
        )
        return {"status": "ready", "summary_theme_count": len(summary_data.get("themes", []))}

    def _get_adapter(self, source_url: str) -> SourceAdapter:
        for adapter in self.source_adapters:
            if adapter.supports(source_url):
                return adapter
        raise ValueError("No source adapter supports this URL.")

    def _get_episode_or_raise(self, workspace_id: str, episode_id: str):
        episode = self.episode_repository.get_by_id(workspace_id, episode_id)
        if not episode:
            raise KeyError(f"Episode not found: {episode_id}")
        return episode

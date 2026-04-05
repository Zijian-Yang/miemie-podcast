from __future__ import annotations

import sqlite3
from typing import Any, Dict, List, Optional, Sequence

from miemie_podcast.adapters.db.sqlite import SQLiteDatabase
from miemie_podcast.domain.models import (
    Artifact,
    Episode,
    EpisodeSourceRecord,
    EpisodeStatus,
    Job,
    JobStatus,
    ModuleOutput,
    ModuleStatus,
    RequestContext,
    SearchDocument,
    Session,
    TranscriptChunk,
    User,
    Workspace,
)
from miemie_podcast.ports.repositories import (
    ArtifactRepository,
    EpisodeRepository,
    EpisodeSourceRepository,
    JobRepository,
    ModuleOutputRepository,
    SearchRepository,
    SessionRepository,
    TranscriptRepository,
    UserRepository,
    WorkspaceRepository,
)
from miemie_podcast.utils import json_dumps, json_loads, new_id, now_iso


def _row_to_workspace(row: sqlite3.Row) -> Workspace:
    return Workspace(**dict(row))


def _row_to_user(row: sqlite3.Row) -> User:
    return User(**dict(row))


def _row_to_session(row: sqlite3.Row) -> Session:
    return Session(**dict(row))


def _row_to_episode(row: sqlite3.Row) -> Episode:
    payload = dict(row)
    payload["status"] = EpisodeStatus(payload["status"])
    return Episode(**payload)


def _row_to_job(row: sqlite3.Row) -> Job:
    payload = dict(row)
    payload["status"] = JobStatus(payload["status"])
    return Job(**payload)


def _row_to_chunk(row: sqlite3.Row) -> TranscriptChunk:
    return TranscriptChunk(**dict(row))


def _row_to_module(row: sqlite3.Row) -> ModuleOutput:
    payload = dict(row)
    payload["status"] = ModuleStatus(payload["status"])
    return ModuleOutput(**payload)


def _row_to_search_document(row: sqlite3.Row) -> SearchDocument:
    return SearchDocument(**dict(row))


def _row_to_artifact(row: sqlite3.Row) -> Artifact:
    return Artifact(**dict(row))


class SQLiteWorkspaceRepository(WorkspaceRepository):
    def __init__(self, database: SQLiteDatabase) -> None:
        self.database = database

    def ensure_default_workspace(self) -> Workspace:
        with self.database.connect() as connection:
            row = connection.execute(
                "SELECT * FROM workspaces WHERE slug = ? AND deleted_at IS NULL",
                ("default-workspace",),
            ).fetchone()
            if row:
                return _row_to_workspace(row)
            timestamp = now_iso()
            workspace = Workspace(
                id=new_id("ws"),
                slug="default-workspace",
                name="Default Workspace",
                owner_user_id="pending-admin",
                visibility="private",
                created_at=timestamp,
                updated_at=timestamp,
            )
            connection.execute(
                """
                INSERT INTO workspaces (id, slug, name, owner_user_id, visibility, created_at, updated_at, deleted_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, NULL)
                """,
                (
                    workspace.id,
                    workspace.slug,
                    workspace.name,
                    workspace.owner_user_id,
                    workspace.visibility,
                    workspace.created_at,
                    workspace.updated_at,
                ),
            )
            connection.commit()
            return workspace

    def update_owner(self, workspace_id: str, owner_user_id: str) -> None:
        with self.database.connect() as connection:
            connection.execute(
                "UPDATE workspaces SET owner_user_id = ?, updated_at = ? WHERE id = ?",
                (owner_user_id, now_iso(), workspace_id),
            )
            connection.commit()

    def get_by_id(self, workspace_id: str) -> Optional[Workspace]:
        with self.database.connect() as connection:
            row = connection.execute(
                "SELECT * FROM workspaces WHERE id = ? AND deleted_at IS NULL",
                (workspace_id,),
            ).fetchone()
            return _row_to_workspace(row) if row else None


class SQLiteUserRepository(UserRepository):
    def __init__(self, database: SQLiteDatabase, workspace_repository: SQLiteWorkspaceRepository) -> None:
        self.database = database
        self.workspace_repository = workspace_repository

    def ensure_default_admin(self, workspace_id: str) -> User:
        with self.database.connect() as connection:
            row = connection.execute(
                "SELECT * FROM users WHERE workspace_id = ? AND email = ? AND deleted_at IS NULL",
                (workspace_id, "admin@miemie.local"),
            ).fetchone()
            if row:
                return _row_to_user(row)
            timestamp = now_iso()
            user = User(
                id=new_id("user"),
                workspace_id=workspace_id,
                email="admin@miemie.local",
                display_name="Admin",
                role="admin",
                created_at=timestamp,
                updated_at=timestamp,
            )
            connection.execute(
                """
                INSERT INTO users (id, workspace_id, email, display_name, role, created_at, updated_at, deleted_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, NULL)
                """,
                (
                    user.id,
                    user.workspace_id,
                    user.email,
                    user.display_name,
                    user.role,
                    user.created_at,
                    user.updated_at,
                ),
            )
            connection.commit()
            self.workspace_repository.update_owner(workspace_id, user.id)
            return user

    def get_by_id(self, workspace_id: str, user_id: str) -> Optional[User]:
        with self.database.connect() as connection:
            row = connection.execute(
                "SELECT * FROM users WHERE workspace_id = ? AND id = ? AND deleted_at IS NULL",
                (workspace_id, user_id),
            ).fetchone()
            return _row_to_user(row) if row else None


class SQLiteSessionRepository(SessionRepository):
    def __init__(self, database: SQLiteDatabase) -> None:
        self.database = database

    def create(self, workspace_id: str, user_id: str, token_hash: str, expires_at: str) -> Session:
        timestamp = now_iso()
        session = Session(
            id=new_id("sess"),
            workspace_id=workspace_id,
            user_id=user_id,
            token_hash=token_hash,
            expires_at=expires_at,
            created_at=timestamp,
            updated_at=timestamp,
        )
        with self.database.connect() as connection:
            connection.execute(
                """
                INSERT INTO sessions (id, workspace_id, user_id, token_hash, expires_at, created_at, updated_at, deleted_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, NULL)
                """,
                (
                    session.id,
                    session.workspace_id,
                    session.user_id,
                    session.token_hash,
                    session.expires_at,
                    session.created_at,
                    session.updated_at,
                ),
            )
            connection.commit()
        return session

    def get_by_token_hash(self, token_hash: str) -> Optional[Session]:
        with self.database.connect() as connection:
            row = connection.execute(
                """
                SELECT * FROM sessions
                WHERE token_hash = ? AND deleted_at IS NULL AND expires_at > ?
                """,
                (token_hash, now_iso()),
            ).fetchone()
            return _row_to_session(row) if row else None

    def delete(self, session_id: str) -> None:
        with self.database.connect() as connection:
            connection.execute(
                "UPDATE sessions SET deleted_at = ?, updated_at = ? WHERE id = ?",
                (now_iso(), now_iso(), session_id),
                )
            connection.commit()


class SQLiteEpisodeRepository(EpisodeRepository):
    def __init__(self, database: SQLiteDatabase) -> None:
        self.database = database

    def create(self, context: RequestContext, source_type: str, source_url: str, source_episode_id: str) -> Episode:
        timestamp = now_iso()
        episode = Episode(
            id=new_id("ep"),
            workspace_id=context.workspace_id,
            owner_user_id=context.user_id,
            created_by=context.user_id,
            visibility="private",
            source_type=source_type,
            source_url=source_url,
            source_episode_id=source_episode_id,
            podcast_title="",
            episode_title="",
            cover_image_url="",
            audio_url="",
            published_at=None,
            duration_seconds=None,
            status=EpisodeStatus.QUEUED,
            processing_stage="queued",
            transcription_task_id=None,
            transcription_provider=None,
            failure_code=None,
            failure_message=None,
            created_at=timestamp,
            updated_at=timestamp,
        )
        with self.database.connect() as connection:
            connection.execute(
                """
                INSERT INTO episodes (
                    id, workspace_id, owner_user_id, created_by, visibility, source_type, source_url,
                    source_episode_id, podcast_title, episode_title, cover_image_url, audio_url, published_at,
                    duration_seconds, status, processing_stage, transcription_task_id, transcription_provider,
                    failure_code, failure_message, created_at, updated_at, deleted_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL)
                """,
                (
                    episode.id,
                    episode.workspace_id,
                    episode.owner_user_id,
                    episode.created_by,
                    episode.visibility,
                    episode.source_type,
                    episode.source_url,
                    episode.source_episode_id,
                    episode.podcast_title,
                    episode.episode_title,
                    episode.cover_image_url,
                    episode.audio_url,
                    episode.published_at,
                    episode.duration_seconds,
                    episode.status.value,
                    episode.processing_stage,
                    episode.transcription_task_id,
                    episode.transcription_provider,
                    episode.failure_code,
                    episode.failure_message,
                    episode.created_at,
                    episode.updated_at,
                ),
            )
            connection.commit()
        return episode

    def find_active_by_source_url(self, workspace_id: str, source_url: str) -> Optional[Episode]:
        with self.database.connect() as connection:
            row = connection.execute(
                """
                SELECT * FROM episodes
                WHERE workspace_id = ? AND source_url = ? AND deleted_at IS NULL
                ORDER BY created_at DESC
                LIMIT 1
                """,
                (workspace_id, source_url),
            ).fetchone()
            return _row_to_episode(row) if row else None

    def get_by_id(self, workspace_id: str, episode_id: str) -> Optional[Episode]:
        with self.database.connect() as connection:
            row = connection.execute(
                "SELECT * FROM episodes WHERE workspace_id = ? AND id = ? AND deleted_at IS NULL",
                (workspace_id, episode_id),
            ).fetchone()
            return _row_to_episode(row) if row else None

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
        clauses = ["workspace_id = ?", "deleted_at IS NULL"]
        params: List[Any] = [workspace_id]
        if status:
            clauses.append("status = ?")
            params.append(status)
        if podcast_title:
            clauses.append("podcast_title = ?")
            params.append(podcast_title)
        if query:
            clauses.append("(episode_title LIKE ? OR podcast_title LIKE ?)")
            keyword = f"%{query}%"
            params.extend([keyword, keyword])
        order_by = "updated_at DESC" if sort != "oldest" else "updated_at ASC"
        offset = (page - 1) * page_size
        with self.database.connect() as connection:
            total_row = connection.execute(
                f"SELECT COUNT(*) AS count FROM episodes WHERE {' AND '.join(clauses)}",
                params,
            ).fetchone()
            rows = connection.execute(
                f"""
                SELECT * FROM episodes
                WHERE {' AND '.join(clauses)}
                ORDER BY {order_by}
                LIMIT ? OFFSET ?
                """,
                [*params, page_size, offset],
            ).fetchall()
            return {
                "items": [_row_to_episode(row) for row in rows],
                "total": total_row["count"] if total_row else 0,
                "page": page,
                "page_size": page_size,
            }

    def update_fields(self, workspace_id: str, episode_id: str, fields: Dict[str, Any]) -> None:
        if not fields:
            return
        parts = []
        params: List[Any] = []
        for key, value in fields.items():
            parts.append(f"{key} = ?")
            params.append(value.value if isinstance(value, (EpisodeStatus, ModuleStatus)) else value)
        parts.append("updated_at = ?")
        params.append(now_iso())
        params.extend([workspace_id, episode_id])
        with self.database.connect() as connection:
            connection.execute(
                f"""
                UPDATE episodes SET {', '.join(parts)}
                WHERE workspace_id = ? AND id = ?
                """,
                params,
            )
            connection.commit()

    def soft_delete(self, workspace_id: str, episode_id: str) -> None:
        with self.database.connect() as connection:
            timestamp = now_iso()
            connection.execute(
                """
                UPDATE episodes
                SET deleted_at = ?, updated_at = ?, status = ?, processing_stage = ?
                WHERE workspace_id = ? AND id = ?
                """,
                (timestamp, timestamp, EpisodeStatus.DELETED.value, "deleted", workspace_id, episode_id),
            )
            connection.commit()


class SQLiteEpisodeSourceRepository(EpisodeSourceRepository):
    def __init__(self, database: SQLiteDatabase) -> None:
        self.database = database

    def upsert(
        self,
        workspace_id: str,
        episode_id: str,
        source_type: str,
        normalized_source: str,
        raw_payload_json: str,
    ) -> None:
        with self.database.connect() as connection:
            row = connection.execute(
                "SELECT id FROM episode_sources WHERE workspace_id = ? AND episode_id = ?",
                (workspace_id, episode_id),
            ).fetchone()
            timestamp = now_iso()
            if row:
                connection.execute(
                    """
                    UPDATE episode_sources
                    SET source_type = ?, normalized_source = ?, raw_payload_json = ?, updated_at = ?, deleted_at = NULL
                    WHERE id = ?
                    """,
                    (source_type, normalized_source, raw_payload_json, timestamp, row["id"]),
                )
            else:
                record = EpisodeSourceRecord(
                    id=new_id("src"),
                    workspace_id=workspace_id,
                    episode_id=episode_id,
                    source_type=source_type,
                    normalized_source=normalized_source,
                    raw_payload_json=raw_payload_json,
                    created_at=timestamp,
                    updated_at=timestamp,
                )
                connection.execute(
                    """
                    INSERT INTO episode_sources (id, workspace_id, episode_id, source_type, normalized_source, raw_payload_json, created_at, updated_at, deleted_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, NULL)
                    """,
                    (
                        record.id,
                        record.workspace_id,
                        record.episode_id,
                        record.source_type,
                        record.normalized_source,
                        record.raw_payload_json,
                        record.created_at,
                        record.updated_at,
                    ),
                )
            connection.commit()


class SQLiteJobRepository(JobRepository):
    def __init__(self, database: SQLiteDatabase) -> None:
        self.database = database

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
        timestamp = now_iso()
        job = Job(
            id=new_id("job"),
            workspace_id=workspace_id,
            episode_id=episode_id,
            job_type=job_type,
            stage=stage,
            status=JobStatus.PENDING,
            payload_json=payload_json,
            result_json=None,
            error_json=None,
            attempt_count=0,
            max_attempts=max_attempts,
            dedupe_key=dedupe_key,
            available_at=available_at,
            locked_by=None,
            locked_at=None,
            heartbeat_at=None,
            created_at=timestamp,
            updated_at=timestamp,
        )
        with self.database.connect() as connection:
            connection.execute(
                """
                INSERT INTO jobs (
                    id, workspace_id, episode_id, job_type, stage, status, payload_json,
                    result_json, error_json, attempt_count, max_attempts, dedupe_key,
                    available_at, locked_by, locked_at, heartbeat_at, created_at, updated_at, deleted_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL)
                """,
                (
                    job.id,
                    job.workspace_id,
                    job.episode_id,
                    job.job_type,
                    job.stage,
                    job.status.value,
                    job.payload_json,
                    job.result_json,
                    job.error_json,
                    job.attempt_count,
                    job.max_attempts,
                    job.dedupe_key,
                    job.available_at,
                    job.locked_by,
                    job.locked_at,
                    job.heartbeat_at,
                    job.created_at,
                    job.updated_at,
                ),
            )
            connection.commit()
        return job

    def claim(self, worker_id: str, supported_types: Sequence[str], limit: int) -> List[Job]:
        if not supported_types:
            return []
        placeholders = ",".join(["?"] * len(supported_types))
        now = now_iso()
        claimed: List[Job] = []
        with self.database.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            rows = connection.execute(
                f"""
                SELECT * FROM jobs
                WHERE status = ? AND available_at <= ? AND deleted_at IS NULL AND job_type IN ({placeholders})
                ORDER BY available_at ASC
                LIMIT ?
                """,
                [JobStatus.PENDING.value, now, *supported_types, limit],
            ).fetchall()
            for row in rows:
                connection.execute(
                    """
                    UPDATE jobs
                    SET status = ?, locked_by = ?, locked_at = ?, heartbeat_at = ?, attempt_count = attempt_count + 1, updated_at = ?
                    WHERE id = ? AND status = ?
                    """,
                    (JobStatus.PROCESSING.value, worker_id, now, now, now, row["id"], JobStatus.PENDING.value),
                )
            connection.commit()
        for row in rows:
            refreshed = self.get_by_id(row["workspace_id"], row["id"])
            if refreshed:
                claimed.append(refreshed)
        return claimed

    def get_by_id(self, workspace_id: str, job_id: str) -> Optional[Job]:
        with self.database.connect() as connection:
            row = connection.execute(
                "SELECT * FROM jobs WHERE workspace_id = ? AND id = ? AND deleted_at IS NULL",
                (workspace_id, job_id),
            ).fetchone()
            return _row_to_job(row) if row else None

    def cancel_pending_for_episode(self, workspace_id: str, episode_id: str, reason: str) -> None:
        with self.database.connect() as connection:
            connection.execute(
                """
                UPDATE jobs
                SET status = ?, error_json = ?, updated_at = ?
                WHERE workspace_id = ? AND episode_id = ? AND status IN (?, ?)
                """,
                (
                    JobStatus.FAILED.value,
                    json_dumps({"message": reason, "retryable": False}),
                    now_iso(),
                    workspace_id,
                    episode_id,
                    JobStatus.PENDING.value,
                    JobStatus.PROCESSING.value,
                ),
            )
            connection.commit()

    def heartbeat(self, job_id: str, stage: str) -> None:
        with self.database.connect() as connection:
            connection.execute(
                "UPDATE jobs SET heartbeat_at = ?, stage = ?, updated_at = ? WHERE id = ?",
                (now_iso(), stage, now_iso(), job_id),
            )
            connection.commit()

    def complete(self, job_id: str, result_json: str) -> None:
        with self.database.connect() as connection:
            connection.execute(
                """
                UPDATE jobs
                SET status = ?, result_json = ?, error_json = NULL, updated_at = ?
                WHERE id = ?
                """,
                (JobStatus.COMPLETED.value, result_json, now_iso(), job_id),
            )
            connection.commit()

    def fail(self, job_id: str, error_json: str, retryable: bool, next_available_at: Optional[str]) -> None:
        with self.database.connect() as connection:
            if retryable and next_available_at:
                connection.execute(
                    """
                    UPDATE jobs
                    SET status = ?, error_json = ?, available_at = ?, locked_by = NULL, locked_at = NULL, heartbeat_at = NULL, updated_at = ?
                    WHERE id = ?
                    """,
                    (JobStatus.PENDING.value, error_json, next_available_at, now_iso(), job_id),
                )
            else:
                connection.execute(
                    """
                    UPDATE jobs
                    SET status = ?, error_json = ?, updated_at = ?
                    WHERE id = ?
                    """,
                    (JobStatus.FAILED.value, error_json, now_iso(), job_id),
                )
            connection.commit()


class SQLiteTranscriptRepository(TranscriptRepository):
    def __init__(self, database: SQLiteDatabase) -> None:
        self.database = database

    def replace_for_episode(self, workspace_id: str, episode_id: str, chunks: Sequence[TranscriptChunk]) -> None:
        with self.database.connect() as connection:
            connection.execute(
                "DELETE FROM transcript_chunks WHERE workspace_id = ? AND episode_id = ?",
                (workspace_id, episode_id),
            )
            for chunk in chunks:
                connection.execute(
                    """
                    INSERT INTO transcript_chunks (
                        id, workspace_id, episode_id, chunk_index, start_ms, end_ms, text,
                        metadata_json, created_at, updated_at, deleted_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL)
                    """,
                    (
                        chunk.id,
                        chunk.workspace_id,
                        chunk.episode_id,
                        chunk.chunk_index,
                        chunk.start_ms,
                        chunk.end_ms,
                        chunk.text,
                        chunk.metadata_json,
                        chunk.created_at,
                        chunk.updated_at,
                    ),
                )
            connection.commit()

    def list_by_episode(self, workspace_id: str, episode_id: str) -> List[TranscriptChunk]:
        with self.database.connect() as connection:
            rows = connection.execute(
                """
                SELECT * FROM transcript_chunks
                WHERE workspace_id = ? AND episode_id = ? AND deleted_at IS NULL
                ORDER BY chunk_index ASC
                """,
                (workspace_id, episode_id),
            ).fetchall()
            return [_row_to_chunk(row) for row in rows]


class SQLiteModuleOutputRepository(ModuleOutputRepository):
    def __init__(self, database: SQLiteDatabase) -> None:
        self.database = database

    def upsert(self, workspace_id: str, episode_id: str, module_output: ModuleOutput) -> None:
        with self.database.connect() as connection:
            row = connection.execute(
                """
                SELECT id FROM module_outputs
                WHERE workspace_id = ? AND episode_id = ? AND module_key = ?
                """,
                (workspace_id, episode_id, module_output.module_key),
            ).fetchone()
            if row:
                connection.execute(
                    """
                    UPDATE module_outputs
                    SET version = ?, format = ?, status = ?, content_json = ?, rendered_markdown = ?, rendered_html = ?, citations_json = ?, updated_at = ?, deleted_at = NULL
                    WHERE id = ?
                    """,
                    (
                        module_output.version,
                        module_output.format,
                        module_output.status.value,
                        module_output.content_json,
                        module_output.rendered_markdown,
                        module_output.rendered_html,
                        module_output.citations_json,
                        now_iso(),
                        row["id"],
                    ),
                )
            else:
                connection.execute(
                    """
                    INSERT INTO module_outputs (
                        id, workspace_id, episode_id, module_key, version, format, status,
                        content_json, rendered_markdown, rendered_html, citations_json,
                        created_at, updated_at, deleted_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL)
                    """,
                    (
                        module_output.id,
                        module_output.workspace_id,
                        module_output.episode_id,
                        module_output.module_key,
                        module_output.version,
                        module_output.format,
                        module_output.status.value,
                        module_output.content_json,
                        module_output.rendered_markdown,
                        module_output.rendered_html,
                        module_output.citations_json,
                        module_output.created_at,
                        module_output.updated_at,
                    ),
                )
            connection.commit()

    def list_by_episode(self, workspace_id: str, episode_id: str) -> List[ModuleOutput]:
        with self.database.connect() as connection:
            rows = connection.execute(
                """
                SELECT * FROM module_outputs
                WHERE workspace_id = ? AND episode_id = ? AND deleted_at IS NULL
                ORDER BY module_key ASC
                """,
                (workspace_id, episode_id),
            ).fetchall()
            return [_row_to_module(row) for row in rows]


class SQLiteSearchRepository(SearchRepository):
    def __init__(self, database: SQLiteDatabase) -> None:
        self.database = database

    def replace_for_episode(self, workspace_id: str, episode_id: str, documents: Sequence[SearchDocument]) -> None:
        with self.database.connect() as connection:
            old_rows = connection.execute(
                "SELECT id FROM search_documents WHERE workspace_id = ? AND episode_id = ?",
                (workspace_id, episode_id),
            ).fetchall()
            for row in old_rows:
                connection.execute("DELETE FROM search_documents_fts WHERE id = ?", (row["id"],))
            connection.execute(
                "DELETE FROM search_documents WHERE workspace_id = ? AND episode_id = ?",
                (workspace_id, episode_id),
            )
            for doc in documents:
                connection.execute(
                    """
                    INSERT INTO search_documents (
                        id, workspace_id, episode_id, source_kind, title, body, metadata_json,
                        created_at, updated_at, deleted_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, NULL)
                    """,
                    (
                        doc.id,
                        doc.workspace_id,
                        doc.episode_id,
                        doc.source_kind,
                        doc.title,
                        doc.body,
                        doc.metadata_json,
                        doc.created_at,
                        doc.updated_at,
                    ),
                )
                connection.execute(
                    """
                    INSERT INTO search_documents_fts (id, workspace_id, episode_id, source_kind, title, body)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (doc.id, doc.workspace_id, doc.episode_id, doc.source_kind, doc.title, doc.body),
                )
            connection.commit()

    def search_episode(self, workspace_id: str, episode_id: str, query: str, limit: int) -> List[SearchDocument]:
        with self.database.connect() as connection:
            rows = connection.execute(
                """
                SELECT sd.*
                FROM search_documents_fts fts
                JOIN search_documents sd ON sd.id = fts.id
                WHERE fts.workspace_id = ? AND fts.episode_id = ? AND search_documents_fts MATCH ?
                ORDER BY bm25(search_documents_fts)
                LIMIT ?
                """,
                (workspace_id, episode_id, query, limit),
            ).fetchall()
            return [_row_to_search_document(row) for row in rows]


class SQLiteArtifactRepository(ArtifactRepository):
    def __init__(self, database: SQLiteDatabase) -> None:
        self.database = database

    def upsert(self, workspace_id: str, episode_id: str, artifact: Artifact) -> None:
        with self.database.connect() as connection:
            row = connection.execute(
                "SELECT id FROM artifacts WHERE workspace_id = ? AND episode_id = ? AND artifact_key = ?",
                (workspace_id, episode_id, artifact.artifact_key),
            ).fetchone()
            if row:
                connection.execute(
                    """
                    UPDATE artifacts
                    SET format = ?, mime_type = ?, relative_path = ?, size_bytes = ?, metadata_json = ?, updated_at = ?, deleted_at = NULL
                    WHERE id = ?
                    """,
                    (
                        artifact.format,
                        artifact.mime_type,
                        artifact.relative_path,
                        artifact.size_bytes,
                        artifact.metadata_json,
                        now_iso(),
                        row["id"],
                    ),
                )
            else:
                connection.execute(
                    """
                    INSERT INTO artifacts (
                        id, workspace_id, episode_id, artifact_key, format, mime_type, relative_path,
                        size_bytes, metadata_json, created_at, updated_at, deleted_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL)
                    """,
                    (
                        artifact.id,
                        artifact.workspace_id,
                        artifact.episode_id,
                        artifact.artifact_key,
                        artifact.format,
                        artifact.mime_type,
                        artifact.relative_path,
                        artifact.size_bytes,
                        artifact.metadata_json,
                        artifact.created_at,
                        artifact.updated_at,
                    ),
                )
            connection.commit()

    def list_by_episode(self, workspace_id: str, episode_id: str) -> List[Artifact]:
        with self.database.connect() as connection:
            rows = connection.execute(
                """
                SELECT * FROM artifacts
                WHERE workspace_id = ? AND episode_id = ? AND deleted_at IS NULL
                ORDER BY artifact_key ASC
                """,
                (workspace_id, episode_id),
            ).fetchall()
            return [_row_to_artifact(row) for row in rows]

    def get_by_key(self, workspace_id: str, episode_id: str, artifact_key: str) -> Optional[Artifact]:
        with self.database.connect() as connection:
            row = connection.execute(
                """
                SELECT * FROM artifacts
                WHERE workspace_id = ? AND episode_id = ? AND artifact_key = ? AND deleted_at IS NULL
                """,
                (workspace_id, episode_id, artifact_key),
            ).fetchone()
            return _row_to_artifact(row) if row else None

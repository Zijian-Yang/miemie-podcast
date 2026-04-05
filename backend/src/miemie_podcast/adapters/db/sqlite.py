from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from miemie_podcast.config import Settings


SCHEMA_SQL = """
PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;

CREATE TABLE IF NOT EXISTS workspaces (
  id TEXT PRIMARY KEY,
  slug TEXT NOT NULL UNIQUE,
  name TEXT NOT NULL,
  owner_user_id TEXT NOT NULL,
  visibility TEXT NOT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  deleted_at TEXT
);

CREATE TABLE IF NOT EXISTS users (
  id TEXT PRIMARY KEY,
  workspace_id TEXT NOT NULL,
  email TEXT NOT NULL,
  display_name TEXT NOT NULL,
  role TEXT NOT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  deleted_at TEXT,
  FOREIGN KEY(workspace_id) REFERENCES workspaces(id)
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_users_workspace_email ON users(workspace_id, email);

CREATE TABLE IF NOT EXISTS sessions (
  id TEXT PRIMARY KEY,
  workspace_id TEXT NOT NULL,
  user_id TEXT NOT NULL,
  token_hash TEXT NOT NULL UNIQUE,
  expires_at TEXT NOT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  deleted_at TEXT,
  FOREIGN KEY(workspace_id) REFERENCES workspaces(id),
  FOREIGN KEY(user_id) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS episodes (
  id TEXT PRIMARY KEY,
  workspace_id TEXT NOT NULL,
  owner_user_id TEXT NOT NULL,
  created_by TEXT NOT NULL,
  visibility TEXT NOT NULL,
  source_type TEXT NOT NULL,
  source_url TEXT NOT NULL,
  source_episode_id TEXT NOT NULL,
  podcast_title TEXT NOT NULL DEFAULT '',
  episode_title TEXT NOT NULL DEFAULT '',
  cover_image_url TEXT NOT NULL DEFAULT '',
  audio_url TEXT NOT NULL DEFAULT '',
  published_at TEXT,
  duration_seconds INTEGER,
  status TEXT NOT NULL,
  processing_stage TEXT NOT NULL DEFAULT 'queued',
  transcription_task_id TEXT,
  transcription_provider TEXT,
  failure_code TEXT,
  failure_message TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  deleted_at TEXT,
  FOREIGN KEY(workspace_id) REFERENCES workspaces(id),
  FOREIGN KEY(owner_user_id) REFERENCES users(id),
  FOREIGN KEY(created_by) REFERENCES users(id)
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_episodes_workspace_source_url ON episodes(workspace_id, source_url);
CREATE INDEX IF NOT EXISTS idx_episodes_workspace_status ON episodes(workspace_id, status);

CREATE TABLE IF NOT EXISTS episode_sources (
  id TEXT PRIMARY KEY,
  workspace_id TEXT NOT NULL,
  episode_id TEXT NOT NULL,
  source_type TEXT NOT NULL,
  normalized_source TEXT NOT NULL,
  raw_payload_json TEXT NOT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  deleted_at TEXT,
  FOREIGN KEY(workspace_id) REFERENCES workspaces(id),
  FOREIGN KEY(episode_id) REFERENCES episodes(id)
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_episode_sources_workspace_episode ON episode_sources(workspace_id, episode_id);

CREATE TABLE IF NOT EXISTS jobs (
  id TEXT PRIMARY KEY,
  workspace_id TEXT NOT NULL,
  episode_id TEXT,
  job_type TEXT NOT NULL,
  stage TEXT NOT NULL,
  status TEXT NOT NULL,
  payload_json TEXT NOT NULL,
  result_json TEXT,
  error_json TEXT,
  attempt_count INTEGER NOT NULL DEFAULT 0,
  max_attempts INTEGER NOT NULL DEFAULT 10,
  dedupe_key TEXT,
  available_at TEXT NOT NULL,
  locked_by TEXT,
  locked_at TEXT,
  heartbeat_at TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  deleted_at TEXT,
  FOREIGN KEY(workspace_id) REFERENCES workspaces(id),
  FOREIGN KEY(episode_id) REFERENCES episodes(id)
);

CREATE INDEX IF NOT EXISTS idx_jobs_status_available ON jobs(status, available_at);
CREATE INDEX IF NOT EXISTS idx_jobs_workspace ON jobs(workspace_id, created_at DESC);

CREATE TABLE IF NOT EXISTS transcript_chunks (
  id TEXT PRIMARY KEY,
  workspace_id TEXT NOT NULL,
  episode_id TEXT NOT NULL,
  chunk_index INTEGER NOT NULL,
  start_ms INTEGER NOT NULL,
  end_ms INTEGER NOT NULL,
  text TEXT NOT NULL,
  metadata_json TEXT NOT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  deleted_at TEXT,
  FOREIGN KEY(workspace_id) REFERENCES workspaces(id),
  FOREIGN KEY(episode_id) REFERENCES episodes(id)
);

CREATE INDEX IF NOT EXISTS idx_transcript_workspace_episode ON transcript_chunks(workspace_id, episode_id, chunk_index);

CREATE TABLE IF NOT EXISTS module_outputs (
  id TEXT PRIMARY KEY,
  workspace_id TEXT NOT NULL,
  episode_id TEXT NOT NULL,
  module_key TEXT NOT NULL,
  version TEXT NOT NULL,
  format TEXT NOT NULL,
  status TEXT NOT NULL,
  content_json TEXT NOT NULL,
  rendered_markdown TEXT,
  rendered_html TEXT,
  citations_json TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  deleted_at TEXT,
  FOREIGN KEY(workspace_id) REFERENCES workspaces(id),
  FOREIGN KEY(episode_id) REFERENCES episodes(id)
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_module_workspace_episode_key ON module_outputs(workspace_id, episode_id, module_key);

CREATE TABLE IF NOT EXISTS search_documents (
  id TEXT PRIMARY KEY,
  workspace_id TEXT NOT NULL,
  episode_id TEXT NOT NULL,
  source_kind TEXT NOT NULL,
  title TEXT NOT NULL,
  body TEXT NOT NULL,
  metadata_json TEXT NOT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  deleted_at TEXT,
  FOREIGN KEY(workspace_id) REFERENCES workspaces(id),
  FOREIGN KEY(episode_id) REFERENCES episodes(id)
);

CREATE INDEX IF NOT EXISTS idx_search_workspace_episode ON search_documents(workspace_id, episode_id);

CREATE VIRTUAL TABLE IF NOT EXISTS search_documents_fts USING fts5(
  id UNINDEXED,
  workspace_id UNINDEXED,
  episode_id UNINDEXED,
  source_kind,
  title,
  body,
  tokenize = 'unicode61'
);

CREATE TABLE IF NOT EXISTS qa_logs (
  id TEXT PRIMARY KEY,
  workspace_id TEXT NOT NULL,
  episode_id TEXT NOT NULL,
  user_id TEXT NOT NULL,
  question TEXT NOT NULL,
  answer_json TEXT NOT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  deleted_at TEXT,
  FOREIGN KEY(workspace_id) REFERENCES workspaces(id),
  FOREIGN KEY(episode_id) REFERENCES episodes(id),
  FOREIGN KEY(user_id) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS artifacts (
  id TEXT PRIMARY KEY,
  workspace_id TEXT NOT NULL,
  episode_id TEXT NOT NULL,
  artifact_key TEXT NOT NULL,
  format TEXT NOT NULL,
  mime_type TEXT NOT NULL,
  relative_path TEXT NOT NULL,
  size_bytes INTEGER NOT NULL,
  metadata_json TEXT NOT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  deleted_at TEXT,
  FOREIGN KEY(workspace_id) REFERENCES workspaces(id),
  FOREIGN KEY(episode_id) REFERENCES episodes(id)
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_artifacts_workspace_episode_key ON artifacts(workspace_id, episode_id, artifact_key);
"""


class SQLiteDatabase:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.path = settings.sqlite_path

    def initialize(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        settings_dir = self.settings.data_dir
        settings_dir.mkdir(parents=True, exist_ok=True)
        with self.connect() as connection:
            connection.executescript(SCHEMA_SQL)
            connection.commit()

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.path, check_same_thread=False)
        connection.row_factory = sqlite3.Row
        try:
            connection.execute("PRAGMA foreign_keys=ON")
            yield connection
        finally:
            connection.close()


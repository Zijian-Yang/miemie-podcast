from __future__ import annotations

from functools import lru_cache

from miemie_podcast.adapters.auth.password import PasswordAuthService
from miemie_podcast.adapters.db.repositories import (
    SQLiteArtifactRepository,
    SQLiteEpisodeRepository,
    SQLiteEpisodeSourceRepository,
    SQLiteJobRepository,
    SQLiteModuleOutputRepository,
    SQLiteSearchRepository,
    SQLiteSessionRepository,
    SQLiteTranscriptRepository,
    SQLiteUserRepository,
    SQLiteWorkspaceRepository,
)
from miemie_podcast.adapters.db.sqlite import SQLiteDatabase
from miemie_podcast.adapters.providers.qwen import Qwen35PlusProvider, QwenAsrFlashFiletransProvider
from miemie_podcast.adapters.queue.db_polling import DatabasePollingQueue
from miemie_podcast.adapters.sources.xiaoyuzhou import XiaoyuzhouEpisodeSourceAdapter
from miemie_podcast.adapters.storage.local import LocalFileStorage
from miemie_podcast.application.services import EpisodeService
from miemie_podcast.config import settings


class Container:
    def __init__(self) -> None:
        self.settings = settings
        self.database = SQLiteDatabase(self.settings)
        self.workspace_repository = SQLiteWorkspaceRepository(self.database)
        self.user_repository = SQLiteUserRepository(self.database, self.workspace_repository)
        self.session_repository = SQLiteSessionRepository(self.database)
        self.episode_repository = SQLiteEpisodeRepository(self.database)
        self.episode_source_repository = SQLiteEpisodeSourceRepository(self.database)
        self.job_repository = SQLiteJobRepository(self.database)
        self.transcript_repository = SQLiteTranscriptRepository(self.database)
        self.module_output_repository = SQLiteModuleOutputRepository(self.database)
        self.search_repository = SQLiteSearchRepository(self.database)
        self.artifact_repository = SQLiteArtifactRepository(self.database)
        self.storage = LocalFileStorage(self.settings)
        self.auth_service = PasswordAuthService(
            settings=self.settings,
            workspace_repository=self.workspace_repository,
            user_repository=self.user_repository,
            session_repository=self.session_repository,
        )
        self.job_queue = DatabasePollingQueue(self.job_repository)
        self.llm_provider = Qwen35PlusProvider(self.settings)
        self.stt_provider = QwenAsrFlashFiletransProvider(self.settings)
        self.source_adapters = [XiaoyuzhouEpisodeSourceAdapter()]
        self.episode_service = EpisodeService(
            settings=self.settings,
            episode_repository=self.episode_repository,
            episode_source_repository=self.episode_source_repository,
            transcript_repository=self.transcript_repository,
            module_output_repository=self.module_output_repository,
            search_repository=self.search_repository,
            artifact_repository=self.artifact_repository,
            storage=self.storage,
            queue=self.job_queue,
            llm_provider=self.llm_provider,
            stt_provider=self.stt_provider,
            source_adapters=self.source_adapters,
        )

    def initialize(self) -> None:
        self.database.initialize()
        self.auth_service.bootstrap()


@lru_cache
def get_container() -> Container:
    container = Container()
    container.initialize()
    return container


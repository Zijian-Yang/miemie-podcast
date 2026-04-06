from __future__ import annotations

import hmac
import secrets
from typing import Optional

from miemie_podcast.config import Settings
from miemie_podcast.domain.models import RequestContext
from miemie_podcast.ports.repositories import SessionRepository, UserRepository, WorkspaceRepository
from miemie_podcast.utils import hash_token, minutes_from_now


class PasswordAuthService:
    def __init__(
        self,
        settings: Settings,
        workspace_repository: WorkspaceRepository,
        user_repository: UserRepository,
        session_repository: SessionRepository,
    ) -> None:
        self.settings = settings
        self.workspace_repository = workspace_repository
        self.user_repository = user_repository
        self.session_repository = session_repository

    def bootstrap(self) -> RequestContext:
        workspace = self.workspace_repository.ensure_default_workspace()
        user = self.user_repository.ensure_default_admin(workspace.id)
        return RequestContext(
            workspace_id=workspace.id,
            user_id=user.id,
            role=user.role,
            auth_mode=self.settings.auth_mode,
        )

    def _create_session(self, context: RequestContext) -> str:
        raw_token = secrets.token_urlsafe(32)
        self.session_repository.create(
            workspace_id=context.workspace_id,
            user_id=context.user_id,
            token_hash=hash_token(raw_token),
            expires_at=minutes_from_now(60 * 24 * 30),
        )
        return raw_token

    def login(self, password: Optional[str] = None) -> Optional[str]:
        if self.settings.auth_mode == "password_single_user_strict":
            if not password or not hmac.compare_digest(password, self.settings.admin_password):
                return None
        context = self.bootstrap()
        return self._create_session(context)

    def authenticate(self, token: str) -> Optional[RequestContext]:
        session = self.session_repository.get_by_token_hash(hash_token(token))
        if not session:
            return None
        user = self.user_repository.get_by_id(session.workspace_id, session.user_id)
        if not user:
            return None
        return RequestContext(
            workspace_id=session.workspace_id,
            user_id=session.user_id,
            role=user.role,
            auth_mode=self.settings.auth_mode,
        )

    def logout(self, token: str) -> None:
        session = self.session_repository.get_by_token_hash(hash_token(token))
        if session:
            self.session_repository.delete(session.id)

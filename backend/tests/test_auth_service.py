from __future__ import annotations

from types import SimpleNamespace

from miemie_podcast.adapters.auth.password import PasswordAuthService
from miemie_podcast.domain.models import User, Workspace


class StubWorkspaceRepository:
    def ensure_default_workspace(self) -> Workspace:
        return Workspace(
            id="ws_1",
            slug="default-workspace",
            name="Default Workspace",
            owner_user_id="user_1",
            visibility="private",
            created_at="2026-04-06T00:00:00Z",
            updated_at="2026-04-06T00:00:00Z",
        )


class StubUserRepository:
    def __init__(self) -> None:
        self.user = User(
            id="user_1",
            workspace_id="ws_1",
            email="admin@miemie.local",
            display_name="Admin",
            role="admin",
            created_at="2026-04-06T00:00:00Z",
            updated_at="2026-04-06T00:00:00Z",
        )

    def ensure_default_admin(self, workspace_id: str) -> User:
        assert workspace_id == self.user.workspace_id
        return self.user

    def get_by_id(self, workspace_id: str, user_id: str) -> User | None:
        if workspace_id == self.user.workspace_id and user_id == self.user.id:
            return self.user
        return None


class StubSessionRepository:
    def __init__(self) -> None:
        self.sessions_by_hash: dict[str, SimpleNamespace] = {}

    def create(self, workspace_id: str, user_id: str, token_hash: str, expires_at: str) -> SimpleNamespace:
        session = SimpleNamespace(
            id="sess_1",
            workspace_id=workspace_id,
            user_id=user_id,
            token_hash=token_hash,
            expires_at=expires_at,
        )
        self.sessions_by_hash[token_hash] = session
        return session

    def get_by_token_hash(self, token_hash: str) -> SimpleNamespace | None:
        return self.sessions_by_hash.get(token_hash)

    def delete(self, session_id: str) -> None:
        for token_hash, session in list(self.sessions_by_hash.items()):
            if session.id == session_id:
                del self.sessions_by_hash[token_hash]


def test_login_creates_session_without_password():
    service = PasswordAuthService(
        settings=SimpleNamespace(auth_mode="session_single_user", admin_password="unused"),
        workspace_repository=StubWorkspaceRepository(),
        user_repository=StubUserRepository(),
        session_repository=StubSessionRepository(),
    )

    token = service.login()

    assert token
    context = service.authenticate(token)
    assert context is not None
    assert context.workspace_id == "ws_1"
    assert context.user_id == "user_1"
    assert context.role == "admin"
    assert context.auth_mode == "session_single_user"

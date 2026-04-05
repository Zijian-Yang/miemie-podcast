from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Cookie, Depends, HTTPException, Response, status

from miemie_podcast.api.schemas import LoginRequest, LoginResponse, MeResponse
from miemie_podcast.application.container import Container, get_container
from miemie_podcast.config import settings
from miemie_podcast.api.deps import get_request_context
from miemie_podcast.domain.models import RequestContext

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


@router.post("/login", response_model=LoginResponse)
def login(payload: LoginRequest, response: Response, container: Container = Depends(get_container)) -> LoginResponse:
    token = container.auth_service.login(payload.password)
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Incorrect password.")
    response.set_cookie(
        key=settings.cookie_name,
        value=token,
        httponly=True,
        secure=settings.cookie_secure,
        samesite=settings.cookie_samesite,
        max_age=60 * 60 * 24 * 30,
        path="/",
    )
    return LoginResponse(success=True)


@router.post("/logout", response_model=LoginResponse)
def logout(
    response: Response,
    context: RequestContext = Depends(get_request_context),
    container: Container = Depends(get_container),
    session_token: Optional[str] = Cookie(default=None, alias=settings.cookie_name),
) -> LoginResponse:
    _ = context
    if session_token:
        container.auth_service.logout(session_token)
    response.delete_cookie(settings.cookie_name, path="/")
    return LoginResponse(success=True)


@router.get("/me", response_model=MeResponse)
def me(context: RequestContext = Depends(get_request_context)) -> MeResponse:
    return MeResponse(
        workspace_id=context.workspace_id,
        user_id=context.user_id,
        role=context.role,
        auth_mode=context.auth_mode,
    )

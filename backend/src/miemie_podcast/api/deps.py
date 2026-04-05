from __future__ import annotations

from typing import Optional

from fastapi import Cookie, Depends, HTTPException, status

from miemie_podcast.application.container import Container, get_container
from miemie_podcast.config import settings
from miemie_podcast.domain.models import RequestContext


def get_request_context(
    session_token: Optional[str] = Cookie(default=None, alias=settings.cookie_name),
    container: Container = Depends(get_container),
) -> RequestContext:
    if not session_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required.")
    context = container.auth_service.authenticate(session_token)
    if not context:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid session.")
    return context

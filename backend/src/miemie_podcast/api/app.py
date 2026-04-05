from __future__ import annotations

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from miemie_podcast.api.routes import auth, episodes, jobs
from miemie_podcast.config import settings

app = FastAPI(title="Miemie Podcast API", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.web_origin],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(auth.router)
app.include_router(episodes.router)
app.include_router(jobs.router)


@app.get("/healthz")
def healthz():
    return {"status": "ok"}


def main() -> None:
    uvicorn.run(
        "miemie_podcast.api.app:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=settings.app_env == "development",
    )


if __name__ == "__main__":
    main()


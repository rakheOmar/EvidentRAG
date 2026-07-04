from pathlib import Path

from fastapi import FastAPI

from app.core.config import Settings


def mount_frontend(app: FastAPI, settings: Settings) -> None:
    if settings.app.environment != "production":
        return

    dist_path = Path(settings.app.client_dist_path)
    if not dist_path.is_absolute():
        dist_path = Path(__file__).resolve().parent.parent / dist_path

    dist_path = dist_path.resolve()

    if not dist_path.is_dir():
        return

    app.frontend("/", directory=str(dist_path), fallback="index.html")

from __future__ import annotations

from dataclasses import dataclass
from importlib.metadata import PackageNotFoundError, version
import os
import subprocess
from typing import TYPE_CHECKING
import uuid

if TYPE_CHECKING:
    from app.core.config import Settings


_GENERATED_INSTANCE_ID = str(uuid.uuid4())


@dataclass(frozen=True)
class RuntimeContext:
    service_name: str
    environment: str
    version: str
    commit_hash: str
    instance_id: str
    region: str

    def otel_resource_attributes(self) -> dict[str, str]:
        return {
            "service.name": self.service_name,
            "service.version": self.version,
            "service.instance.id": self.instance_id,
            "deployment.environment.name": self.environment,
            "evidentrag.commit.sha": self.commit_hash,
            "cloud.region": self.region,
        }


def get_runtime_context(settings: Settings) -> RuntimeContext:
    return RuntimeContext(
        service_name=settings.otel.service_name,
        environment=settings.app.environment,
        version=_service_version(),
        commit_hash=_commit_hash(),
        instance_id=os.getenv("SERVICE_INSTANCE_ID") or _GENERATED_INSTANCE_ID,
        region=os.getenv("REGION") or os.getenv("AWS_REGION") or "unknown",
    )


def _commit_hash() -> str:
    env_hash = os.getenv("COMMIT_SHA") or os.getenv("COMMIT_HASH")
    if env_hash:
        return env_hash
    try:
        return (
            subprocess.check_output(
                ["git", "rev-parse", "--short", "HEAD"],
                stderr=subprocess.DEVNULL,
                timeout=2,
            )
            .decode("utf-8")
            .strip()
        )
    except Exception:
        return "unknown"


def _service_version() -> str:
    configured_version = os.getenv("SERVICE_VERSION")
    if configured_version:
        return configured_version
    try:
        return version("server")
    except PackageNotFoundError:
        return "unknown"

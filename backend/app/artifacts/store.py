"""Persist artifacts with sanitization applied exactly once, at write time.
Both engines call this; the viewer only ever receives sanitized_content."""

from uuid import UUID

from app.artifacts.sanitizer import sanitize_artifact
from app.db.repos import ArtifactRepo
from app.logging import EVT_ARTIFACT_SANITIZED, get_logger
from app.models.domain import Artifact

log = get_logger(__name__)


async def save_artifact(
    repo: ArtifactRepo, session_id: UUID, kind: str, title: str, content: str
) -> Artifact:
    sanitized = sanitize_artifact(kind, content)
    artifact = await repo.create(
        session_id=session_id,
        kind=kind,
        title=title or ("Untitled " + kind),
        content=content,
        sanitized_content=sanitized,
    )
    log.info(
        EVT_ARTIFACT_SANITIZED,
        artifact_id=str(artifact.id),
        kind=kind,
        removed_bytes=max(0, len(content) - len(sanitized)),
    )
    return artifact

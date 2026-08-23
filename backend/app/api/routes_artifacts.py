"""Artifact retrieval. The viewer receives sanitized content by default;
the raw (pre-sanitization) document is available explicitly for the Source
tab and for auditing what the sanitizer removed."""

from uuid import UUID

from fastapi import APIRouter, Query, Request

from app.api.errors import NotFoundError
from app.models.api import ArtifactResponse

router = APIRouter()


@router.get("/artifacts/{artifact_id}", response_model=ArtifactResponse)
async def get_artifact(
    artifact_id: UUID, request: Request, raw: bool = Query(default=False)
) -> ArtifactResponse:
    artifact = await request.app.state.artifact_repo.get(artifact_id)
    if not artifact:
        raise NotFoundError("Artifact not found.")
    return ArtifactResponse(
        id=artifact.id,
        session_id=artifact.session_id,
        kind=artifact.kind,
        title=artifact.title,
        content=artifact.content if raw else artifact.sanitized_content,
        created_at=artifact.created_at,
    )

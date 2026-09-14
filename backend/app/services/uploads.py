"""Server-controlled local source-video storage."""

from __future__ import annotations

import uuid
from pathlib import Path, PurePosixPath

from fastapi import UploadFile

from app.core.config import get_storage_root


UPLOAD_CHUNK_SIZE = 1024 * 1024


class UploadStorageError(Exception):
    """Raised when a source upload cannot be safely stored."""


def source_relative_path(project_id: uuid.UUID) -> PurePosixPath:
    """Return a deterministic path that never includes client-controlled input."""
    return PurePosixPath("projects") / str(project_id) / "source" / "video.mp4"


def resolve_storage_path(relative_path: PurePosixPath) -> Path:
    """Resolve a known internal path and reject escapes from server storage."""
    storage_root = get_storage_root().resolve()
    resolved_path = (storage_root / Path(relative_path)).resolve()
    if not resolved_path.is_relative_to(storage_root):
        raise UploadStorageError("The upload destination is outside server storage.")
    return resolved_path


async def save_source_upload(upload: UploadFile, project_id: uuid.UUID) -> PurePosixPath:
    """Write the upload to its UUID-controlled location and return a relative reference."""
    relative_path = source_relative_path(project_id)
    destination = resolve_storage_path(relative_path)

    try:
        destination.parent.mkdir(parents=True, exist_ok=False)
        with destination.open("xb") as stored_file:
            while chunk := await upload.read(UPLOAD_CHUNK_SIZE):
                stored_file.write(chunk)
    except (OSError, ValueError) as error:
        remove_source_upload(relative_path)
        raise UploadStorageError("Unable to store the uploaded source video.") from error

    return relative_path


def remove_source_upload(relative_path: PurePosixPath) -> None:
    """Remove only a known source file and its now-empty UUID-specific directories."""
    destination = resolve_storage_path(relative_path)
    try:
        destination.unlink(missing_ok=True)
    except OSError:
        return

    for directory in (destination.parent, destination.parent.parent):
        try:
            directory.rmdir()
        except OSError:
            break

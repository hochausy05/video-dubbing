"""Server-controlled local source-video storage."""

from __future__ import annotations

import asyncio
import json
import math
import subprocess
import uuid
from pathlib import Path, PurePosixPath

from fastapi import UploadFile

from app.core.config import (
    get_max_upload_size_bytes,
    get_max_video_duration_seconds,
    get_storage_root,
)


UPLOAD_CHUNK_SIZE = 1024 * 1024
FFPROBE_TIMEOUT_SECONDS = 30


class UploadStorageError(Exception):
    """Raised when a source upload cannot be safely stored."""


class UploadValidationError(Exception):
    """Raised for a safe, client-facing source-video validation failure."""

    def __init__(self, detail: str, status_code: int) -> None:
        super().__init__(detail)
        self.detail = detail
        self.status_code = status_code


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
    """Store and validate a bounded MP4 source before it can be persisted."""
    relative_path = source_relative_path(project_id)
    destination = resolve_storage_path(relative_path)
    maximum_size = get_max_upload_size_bytes()
    written_bytes = 0

    try:
        destination.parent.mkdir(parents=True, exist_ok=False)
        with destination.open("xb") as stored_file:
            while chunk := await upload.read(UPLOAD_CHUNK_SIZE):
                written_bytes += len(chunk)
                if written_bytes > maximum_size:
                    raise UploadValidationError(
                        "The uploaded file exceeds the maximum size of 100 MiB.", 413
                    )
                stored_file.write(chunk)
    except UploadValidationError:
        remove_source_upload(relative_path)
        raise
    except (OSError, ValueError) as error:
        remove_source_upload(relative_path)
        raise UploadStorageError("Unable to store the uploaded source video.") from error

    try:
        await asyncio.to_thread(validate_source_video, destination)
    except Exception:
        remove_source_upload(relative_path)
        raise

    return relative_path


def validate_source_video(path: Path) -> None:
    """Use ffprobe to verify a readable MP4 video and its duration without trusting metadata."""
    command = [
        "ffprobe",
        "-v",
        "error",
        "-show_entries",
        "format=format_name,duration:format_tags=major_brand:stream=codec_type",
        "-of",
        "json",
        str(path),
    ]
    try:
        completed_process = subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=FFPROBE_TIMEOUT_SECONDS,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        raise UploadValidationError("The uploaded file is not a readable MP4 video.", 422) from error

    if completed_process.returncode != 0:
        raise UploadValidationError("The uploaded file is not a readable MP4 video.", 422)

    try:
        probe_data = json.loads(completed_process.stdout)
        media_format = probe_data["format"]
        format_names = set(media_format["format_name"].split(","))
        duration = float(media_format["duration"])
        streams = probe_data["streams"]
    except (KeyError, TypeError, ValueError, json.JSONDecodeError) as error:
        raise UploadValidationError("The uploaded file is not a readable MP4 video.", 422) from error

    major_brand = media_format.get("tags", {}).get("major_brand", "").strip().lower()
    has_video_stream = any(stream.get("codec_type") == "video" for stream in streams)
    if "mp4" not in format_names or major_brand == "qt" or not has_video_stream:
        raise UploadValidationError("Only MP4 video uploads are supported.", 415)
    if not math.isfinite(duration) or duration < 0:
        raise UploadValidationError("The uploaded file is not a readable MP4 video.", 422)
    if duration > get_max_video_duration_seconds():
        raise UploadValidationError(
            "The uploaded video exceeds the maximum duration of 1800 seconds.", 422
        )


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

# AutoDub MVP Architecture

## Purpose and status

This file is authoritative for technical boundaries and data flow. It describes the agreed local MVP design; implementation exists only when `TASKS.md` records verified completion.

## Components

| Component | Owns | Must not own |
| --- | --- | --- |
| React + TypeScript + Vite | Upload UI, project list, job state, translation editing, artifact preview/download | Secrets or direct Whisper/FFmpeg execution |
| FastAPI | HTTP validation, persistence calls, job creation, status/result endpoints | Full media processing inside a web request |
| SQLite | `Project`, `Job`, `Segment`, translation revision, `Artifact`, persisted state/errors | Large video/audio binary content |
| Python worker | Sequential job claiming; Whisper, Gemini, Edge-TTS, FFmpeg; persisted stage/result updates | Dependence on an open browser tab |
| Local storage | Source, intermediate, and result files isolated by server-generated project/job IDs | Arbitrary client-selected filesystem paths |

Frontend calls FastAPI. FastAPI persists a queued job. A separate worker process on the same Windows machine claims one job at a time and writes state/results back to SQLite and local storage.

## Pipeline A — Transcribe and translate

1. FastAPI validates an uploaded source and creates a persisted job.
2. The worker reads the source and runs Whisper, initially targeting model `small`.
3. It validates ordered segments with stable IDs, timestamps, and source text.
4. It sends required segment text to Gemini and stores Vietnamese text separately.
5. It persists the result and finishes; it does not wait while the user reviews text.

GPU Whisper is an optimization only after `ASR-01` verifies compatibility. CPU remains the fallback.

## Pipeline B — Generate speech and render

1. The user edits and confirms a translation revision.
2. FastAPI creates a new TTS/render job for that exact revision.
3. The worker generates and validates per-segment Vietnamese audio with Edge-TTS.
4. The worker measures timing, creates SRT, and renders MP4 with FFmpeg.
5. It stores artifacts linked to the project, job, and confirmed revision.

Editing translation invalidates artifacts from older revisions. Retry uses a distinct run identity so stale files are not overwritten or reused as current output.

## State model

Worker job states: `queued`, `running`, `succeeded`, `failed`, `interrupted`.

- `stage` identifies detailed processing progress.
- Persisted error information must be safe to display and useful for diagnosis.
- Project business state such as `awaiting_review` or `ready` is separate from worker state.
- A restart/interruption policy must prevent jobs from remaining silently stuck.

## Planned data entities

| Entity | Minimum responsibilities |
| --- | --- |
| `Project` | ID, name, source media reference, languages, selected voice, business state, current revision, timestamps |
| `Job` | ID, project ID, operation type, input revision, state, stage, safe error, start/end timestamps |
| `Segment` | Stable ID, project ID, order, start/end, source text, translated text, revision, warnings |
| `Artifact` | ID, project/job ID, revision, media type, controlled internal path |

Field names and schemas are finalized in `DATA-01`, not by this planning document. Clients receive controlled IDs/URLs, never server absolute paths.

## Planned API groups

- Create/list/read projects.
- Upload and retrieve controlled source video.
- Create transcribe/translate jobs and read job status.
- Read/edit segments and confirm a translation revision.
- Create TTS/render jobs.
- Preview/download artifacts for the current project/revision.

Routes and payloads are finalized incrementally before frontend integration; do not prebuild every endpoint.

## Deployment and extension constraints

- Local Windows, one user, one worker, one video job at a time.
- Python 3.11 virtual environment for backend/worker.
- API keys remain in backend/worker configuration; examples contain placeholders only.
- Prefer `h264_nvenc` for rendering only when runtime checks pass; retain CPU encoding fallback.
- SQLite, storage, generated media, and sensitive logs remain outside Git.
- Redis/RQ, public deployment, accounts, and multi-user operation are excluded from the MVP unless scope is explicitly revised.


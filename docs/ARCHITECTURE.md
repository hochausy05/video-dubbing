# AutoDub MVP Architecture

## Purpose and status

This file is authoritative for technical boundaries and data flow. It describes the agreed local MVP design; implementation exists only when `TASKS.md` records verified completion.

## Components

| Component | Owns | Must not own |
| --- | --- | --- |
| React + TypeScript + Vite | Upload UI, project list, job state, translation editing, artifact preview/download | Secrets, direct access to application tables, or direct Whisper/FFmpeg execution |
| FastAPI | HTTP validation, SQLAlchemy persistence calls, job creation, status/result endpoints | Full media processing inside a web request |
| Supabase-hosted PostgreSQL | Metadata for `Project`, `Job`, `Segment`, translation revision, `Artifact`, and persisted state/errors | Large video/audio/output file contents |
| Python worker | Sequential job claiming; Whisper, Gemini, Edge-TTS, FFmpeg; persisted stage/result updates | Dependence on an open browser tab |
| Local storage | Source, intermediate, and result files isolated by server-generated project/job IDs | Arbitrary client-selected filesystem paths |

Frontend calls FastAPI only. FastAPI and the worker access Supabase-hosted PostgreSQL through SQLAlchemy with a PostgreSQL driver, using `DATABASE_URL` from uncommitted environment configuration. A separate worker process on the same Windows machine claims one job at a time and writes state/results back to PostgreSQL and local storage.

## Pipeline A — Transcribe and translate

1. FastAPI streams an uploaded source into UUID-controlled local storage, enforcing the configured byte limit, then uses `ffprobe` to validate an actual MP4 video and its configured duration limit before persisting the Project. The canonical limits are in `docs/PRD.md` and backend configuration.
2. The worker resolves only the Project's UUID-derived source path under managed storage and runs faster-whisper model `small`.
3. It validates and transactionally persists ordered Segments with stable IDs, timestamps, and source text. Re-transcription replaces only unedited Segments for the same Project revision; translated, revision-changed, or warning-bearing Segments are preserved and cause a safe failure.
4. For a non-empty transcript, the worker sends deterministic bounded batches of existing Segment IDs and source text to Gemini using a structured JSON schema. It validates the complete mapping before transactionally updating only `translated_text`; no-speech input skips Gemini.
5. After all translations persist, the combined Job finishes successfully. A no-speech transcript finishes with the truthful `no_speech` stage.

Gemini requests fail immediately on quota/rate-limit and permanent configuration/client errors. Transient network or provider 5xx failures retry the same request at most once after a 0.5-second bounded delay; malformed or incomplete structured output is also retried once, then rejected. No quota retry, model switch, fallback text, or partial persistence is allowed.

## Pre-TTS validation (EDIT-03)

`GET /projects/{project_id}/tts-readiness` reads the current Project, Jobs, and ordered persisted Segments without writing data or changing Job state. Readiness requires at least one Segment, no queued/running Job, and a latest Job that succeeded with `translation_ready` for the current Project revision. Historical terminal Jobs do not count as active. Segment checks require valid unique UUIDs, non-empty source text, current revision, timestamps convertible to non-negative integer milliseconds with end after start, and a non-empty Vietnamese translation no longer than the shared 10,000-character EDIT-02 limit. The database stores source timestamps in seconds as `Numeric(12,3)`; validation interprets that millisecond precision without modifying it.

Blocking validation issues make `ready` false. Timing concerns are warnings only: speaking windows shorter than 250 ms, translation density above 8 whitespace-delimited Vietnamese tokens per source second, and overlaps with earlier source timestamp windows. WPS is a pre-TTS heuristic, not measured speech duration; long translations are not rejected solely for their original window. The viewer separates errors from warnings, allows navigation to affected Segments, and clears previous results after a successful translation edit so the user must validate again.

EDIT-03 preserves the original Whisper timeline and creates no output timeline. It does not synthesize audio, measure TTS duration, adapt speaking rate, stretch video, shift timestamps, or create artifacts. Future TTS/Render work must measure generated audio and calculate any output timing separately.

The worker loads and reuses one Whisper model instance per process. It attempts CUDA `float16` inference, logs the reason if CUDA initialization/inference fails, and falls back to CPU `int8`. CPU inference is verified; GPU inference is not claimed unless the full inference succeeds.

## Pipeline B — Generate speech and render

TTS-01 adds a user-triggered `POST /projects/{project_id}/tts-jobs`. FastAPI locks the Project, re-runs EDIT-03 readiness, rejects blocking errors or another active Job, then returns a queued `tts` Job. The separate sequential worker revalidates readiness while excluding its own claimed Job, synthesizes each current persisted Vietnamese translation using Edge-TTS voice `vi-VN-HoaiMyNeural` by default, and stores MP3s below the Project/Job UUID path. `EDGE_TTS_VOICE` and `EDGE_TTS_CONCURRENCY` configure the Vietnamese voice and a maximum concurrency of five.

Adaptive pacing uses the legacy v3.4.1 whitespace-token WPS heuristic (Vietnamese syllables are counted as whitespace tokens): above 4.2 WPS use +20%, above 3.5 use +12%, above 2.8 use +6%, otherwise normal speed. Each Segment request has a 90-second timeout and at most three attempts with short bounded backoff for transient connection/service failures; client/configuration errors are not retried. FFprobe measures every synthesized MP3 and stores positive integer `duration_ms`. Original Whisper timestamps are unchanged.

The worker stages all audio under a job-specific temporary directory. Only after every Segment succeeds and its translation snapshot still matches does one database transaction insert the Artifact set, make prior TTS Artifacts non-current, and mark the Job `succeeded`/`tts_ready`. Artifact metadata associates a Segment and includes duration, voice, rate, and a SHA-256 fingerprint of exact translation text plus synthesis configuration. A changed translation or voice/rate makes old audio stale and unavailable for playback; failed regeneration leaves the last valid Artifact set intact. Audio is served only through the Project/Segment API after ownership, canonical relative path, and provenance checks. Translation readiness is based on the current successful `transcribe_translate` Job, so a later TTS Job does not invalidate EDIT-02 or EDIT-03.

TTS-01 creates Segment-level speech audio only; it does not create a final video or output timeline. The user confirmed real Project worker generation and browser playback on `demo2`, including persistence after refresh. Legacy v3.5.0 Dynamic Video Time-Stretching, cumulative timeline shifting, SRT generation, mixing, audio/video synchronization, and rendering remain future work.

## State model

Worker job states: `queued`, `running`, `succeeded`, `failed`, `interrupted`.

For JOB-01, FastAPI persists `queued` Jobs and returns their IDs immediately. The separate Python worker claims the oldest queued Job using a PostgreSQL advisory transaction lock plus `FOR UPDATE SKIP LOCKED`, and permits only one `running` Job at a time.

For JOB-02, enqueue and retry set both status and stage to `queued`. Claim sets status to `running`, stage to `claimed`, records `started_at`, and clears stale error/completion values. ASR sets `preparing_asr`, `transcribing`, and finally `transcript_ready` or `no_speech`. For a non-empty transcript, translation sets `translating`, validates complete batch responses, and transactionally writes the full translation set with stage `translation_ready`; only then does the combined `transcribe_translate` Job become `succeeded`. No-speech input skips Gemini and succeeds with stage `no_speech`. ASR or translation failures become `failed` with a bounded safe reason. The worker holds a PostgreSQL session advisory lock for its process lifetime; only after acquiring that lock does startup recovery change prior `running` Jobs to `interrupted`, set stage and `completed_at`, and store a safe reason. Interrupted work remains history and is never automatically requeued. Retry creates a new Job with the original Project, operation type, and input revision. `GET /jobs/{job_id}` returns persisted lifecycle fields; `GET /projects/{project_id}/jobs` returns that Project's persisted Jobs newest first for UI reload recovery. API `finished_at` maps to the existing timezone-aware `completed_at` column. Worker transition helpers set `succeeded`/`failed` only after real work or an explicit failure, record `completed_at`, clear success errors, and bound/redact failure summaries.

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
| `Artifact` | ID, project/job ID, optional Segment ID, revision, media type, controlled internal path, measured duration, translation/config fingerprint, voice and adaptive rate |

Persistent entities use UUID identifiers and timezone-aware timestamps where appropriate. The database stores metadata and controlled media references only; source, intermediate, and output file contents remain in server-managed storage. DATA-01 field definitions and constraints live in `backend/app/models/entities.py`; clients receive controlled IDs/URLs, never server absolute paths.

## Planned API groups

- Create/list/read projects.
- Upload and retrieve controlled source video.
- Read Project Segments in position order and stream the UUID-derived source video through `GET /projects/{project_id}/segments` and `GET /projects/{project_id}/video`; video responses support HTTP Range requests.
- Update only a Segment's Vietnamese translation through `PATCH /projects/{project_id}/segments/{segment_id}`. The API accepts a trimmed non-empty string up to 10,000 characters, returns the saved Segment, and allows edits only when the current revision's translation Job succeeded and no Job is queued/running. This follows the current single-user API convention; the application has no authentication layer.
- Read deterministic pre-TTS validation results through `GET /projects/{project_id}/tts-readiness`; errors block readiness while timing warnings remain informational.
- Create transcribe/translate jobs, read persisted job lifecycle state, and explicitly retry failed or interrupted Jobs as new records.
- Read/edit segments and confirm a translation revision.
- Create a readiness-gated TTS Job, list current per-Segment audio and measured durations, and stream audio through `GET /projects/{project_id}/segments/{segment_id}/audio`.
- Preview/download artifacts for the current project/revision.

Routes and payloads are finalized incrementally before frontend integration; do not prebuild every endpoint.

## Deployment and extension constraints

- Local Windows, one user, one worker, one video job at a time.
- Python 3.11 virtual environment for backend/worker.
- API keys and `DATABASE_URL` remain in backend/worker environment configuration; examples contain placeholders only and `DATABASE_URL` is never committed.
- Prefer `h264_nvenc` for rendering only when runtime checks pass; retain CPU encoding fallback.
- Server-managed storage, generated media, and sensitive logs remain outside Git; Supabase connection credentials are never committed.
- Supabase Auth, Storage, Realtime, and RLS; Redis/RQ; public deployment; accounts; and multi-user operation are excluded from the MVP unless scope is explicitly revised.

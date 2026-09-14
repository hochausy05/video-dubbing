# Product Requirements — AutoDub MVP

## 1. Product definition

AutoDub helps one local user translate spoken English or Chinese video content into Vietnamese, review each translated segment, generate Vietnamese speech, and export a dubbed MP4 plus SRT subtitles.

AI output is a draft. The user confirms the translation revision before speech generation or rendering. Planned behavior is not implemented behavior; consult `TASKS.md` for verified status.

## 2. Target user and operating scope

- User: a person with basic computer skills processing media they own or may use.
- Environment: local Windows demo; one user and one video job at a time.
- Input preference: MP4, English or Chinese speech.
- Target language: Vietnamese.
- Provisional limits: 3 minutes and 100 MB; enforce only after implementation tests confirm them.

## 3. MVP flow

1. Create a project and upload a video.
2. Validate actual media format, configured size, and duration.
3. Create a background transcribe/translate job.
4. Store stable timestamped source segments and Vietnamese drafts.
5. Let the user edit, persist, and confirm a translation revision.
6. Create a separate TTS/render job for that revision.
7. Generate valid segment audio, MP4, and SRT.
8. Preview/download artifacts for the current project and revision.

Failure must identify the affected stage. Missing translation, silent audio, incomplete output, or stale artifacts must never be presented as success.

## 4. User stories and acceptance

### `US-001` — Manage projects

Create, list, and open projects. Persist metadata so projects remain visible after application restart. Verify through the local browser UI.

### `US-002` — Upload and validate video

Accept supported valid media and clearly reject corrupt, unsupported, oversized, or over-duration input. Store it under server-generated identifiers; user filenames must not control server paths. Verify through the local browser UI.

### `US-003` — Request transcription and translation

Return a job ID while heavy work runs outside the HTTP request. Store each segment with stable ID, order, valid start/end, separate source/translation. Treat no-speech and malformed/incomplete provider output as non-success.

### `US-004` — Track jobs and errors

Persist `queued`, `running`, `succeeded`, `failed`, or `interrupted` state, detailed stage, and safe error information. Reload must not lose state. Show measured progress only; otherwise show stage or completed segment count.

### `US-005` — Review and confirm translation

Display aligned source, translation, timestamp, and stable segment ID. Persist edits across refresh. Require an explicit confirmed revision before output generation. Flag empty/error segments and make older-revision artifacts non-current.

### `US-006` — Generate speech and export

Use only a tested Vietnamese voice and the confirmed revision. Validate per-segment audio. Warn when speech exceeds its interval and never silently truncate sentences. Link successful MP4/SRT to the correct project, job, and revision. Verify by watching/listening through the local UI.

## 5. Functional requirements

| ID | Requirement |
| --- | --- |
| `FR-01` | Create/list/read persistent projects. |
| `FR-02` | Validate actual media format, configured size, and duration before processing. |
| `FR-03` | Use server-generated IDs and controlled storage paths/URLs. |
| `FR-04` | Run transcription/translation and TTS/render in background worker jobs. |
| `FR-05` | Process at most one video job concurrently in the MVP. |
| `FR-06` | Persist stable timestamped segments with separate source and Vietnamese text. |
| `FR-07` | Persist job state, stage, timestamps, and safe errors separately from project business state. |
| `FR-08` | Read, edit, save, and confirm translation by segment/revision. |
| `FR-09` | Invalidate stale artifacts and identify retry runs to prevent incorrect reuse/overwrite. |
| `FR-10` | Validate TTS audio and fail clearly instead of substituting silence. |
| `FR-11` | Produce/serve MP4 and SRT for the correct confirmed revision. |
| `FR-12` | Inform the user when text is sent to an external AI service. |

## 6. Non-functional requirements

| ID | Requirement |
| --- | --- |
| `NFR-01` | Local, single-user MVP; no public deployment requirement. |
| `NFR-02` | Never report invalid, missing, silent, incomplete, or stale results as complete. |
| `NFR-03` | Use bounded retry and avoid duplicate job/artifact execution. |
| `NFR-04` | Keep secrets, private media, runtime databases, artifacts, and sensitive logs out of Git. |
| `NFR-05` | Use safe argument-list process execution and release files/processes on every path. |
| `NFR-06` | Require reproducible real evidence before completing functional tasks; label mocks. |
| `NFR-07` | Make no performance promise before measurement on the demo machine; CPU fallback required. |
| `NFR-08` | Preserve component boundaries; avoid unnecessary services/abstractions. |
| `NFR-09` | Persist application metadata in Supabase-hosted PostgreSQL through FastAPI; React must not access application tables directly, file contents remain outside PostgreSQL, and `DATABASE_URL` is environment-only. |

## 7. MVP exclusions

- Authentication, authorization, multiple users, and payments.
- Public Internet deployment.
- Social-platform URL download or automatic posting.
- Voice cloning, lip sync, subtitle OCR, advanced voice/music separation.
- Batch/concurrent video processing or advanced timeline editing.
- Unmeasured guarantees for translation quality, voice quality, or processing time.
- Supabase Auth, Storage, Realtime, and RLS.

## 8. MVP acceptance

The MVP is accepted only after one permitted sample demonstrates:

1. Persistent project creation and safe video validation/upload.
2. Worker-based transcription/translation with valid segments and durable state/errors.
3. Persisted edits and explicit translation-revision confirmation.
4. Valid TTS plus MP4/SRT from the confirmed revision.
5. Human review of video, audio, subtitles, timing, and documented limitations.
6. No tracked secrets/private runtime data and reproducible setup/check instructions.

## 9. Open verification items

- Select permitted test media and confirm available Gemini/TTS access/quota.
- Verify faster-whisper GPU compatibility on the recorded machine; CPU is fallback.
- Test provisional 3-minute/100-MB limits and measure actual stage performance.
- Verify Edge-TTS voice availability/behavior and actual NVENC render commands.

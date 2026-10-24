# AI Usage Log

## Initial documentation (`INIT-01`, `INIT-02`)

- **AI assistance:** Proposed the initial project goals, scope, plan, backlog, engineering rules, and placeholder repository structure.
- **Developer decision:** Keep this stage documentation-only; product scope, stack, and demo machine required later review.
- **Verification:** Checked delivered files, structure, and internal links. No application test was claimed because no application existed.
- **Result/limits:** Initial document and directory foundation created; no repository commit or issue was recorded here.

## `INIT-03` — Confirm MVP direction and scope

- **AI assistance:** Normalized semester development direction, MVP scope, processing flow, architecture, exclusions, and phase order across project documents.
- **Developer decision:** Local single-user MVP; one video at a time; React/TypeScript/Vite, FastAPI, SQLite, and a Python worker; Redis/RQ only if future evidence justifies it.
- **Affected areas:** `README.md`, `PLAN.md`, `TASKS.md`, `docs/PRD.md`, and `docs/ARCHITECTURE.md`.
- **Verification:** Read relevant source documents, checked Markdown links, and ran `git diff --check` after editing.
- **Result/limits:** Documentation scope completed. Whisper, Gemini, Edge-TTS, FFmpeg, and input limits remained unverified.
- **Commit/issue:** None recorded by the AI assistant.

## `EDIT-01` — Video preview and bilingual transcript viewer

- **AI assistance:** Added read-only ordered Segment and controlled source-video endpoints, a typed response schema, Range-compatible video delivery, and a responsive React viewer with timestamps, seek, playback highlighting, and backend-driven transcript states.
- **Developer decision:** Keep transcript read-only, avoid schema changes and preserve all existing Projects and transcript rows.
- **Affected areas:** Project API/schema, React project viewer, focused API unit tests, architecture route notes, and audit logs.
- **Verification:** 18 backend unit tests, frontend TypeScript/Vite build, `compileall`, `pip check`, `git diff --check`, and secret/runtime/ignore checks passed. The configured SQLAlchemy connection could not connect to Supabase because its tenant/user was not recognized; no browser test against a real Project was performed.
- **Result/limits:** Partial; EDIT-01 remains pending until a real persisted Project is opened in the browser and playback, seek, highlighting, and reload are confirmed.
- **Commit/issue:** None recorded by the AI assistant.

## `EDIT-01` — Manual browser acceptance close-out

- **AI assistance:** Recorded the developer-provided manual acceptance and updated the task status; no EDIT-01 implementation changes were needed.
- **Developer decision:** Accept the confirmed video playback, Chinese/Vietnamese display, timestamp seeking, playback-synchronized highlighting, timestamp alignment, and refresh persistence.
- **Affected areas:** `TASKS.md` and append-only task audit records.
- **Verification:** The developer manually confirmed the six specified browser behaviors. No additional runtime check is claimed.
- **Result/limits:** EDIT-01 is complete based on developer-provided browser evidence.
- **Commit/issue:** None recorded by the AI assistant.

## `EDIT-02` — Editable Vietnamese Segment translations

- **AI assistance:** Added a typed Project/Segment PATCH route that updates only `translated_text`, state and ownership checks, bounded non-empty payload validation, and a React Save/Cancel editor that retains drafts on failure. Added API unit tests for persistence and transcript integrity.
- **Developer decision:** Reuse existing Segment fields and current single-user API conventions; require a succeeded current `translation_ready` Job; do not add schema metadata or migration. Existing translation preflight/transaction checks already reject non-null translations, protecting edits from retranslation overwrite.
- **Affected areas:** Project API and schemas, React viewer/editor, focused API tests, architecture and task records.
- **Verification:** 22 backend unit tests passed; frontend TypeScript/Vite production build, `compileall`, `pip check`, and `git diff --check` passed. Browser save/cancel/error/reload flow remains unverified.
- **Result/limits:** Partial; EDIT-02 remains pending manual browser acceptance. Authentication is not implemented anywhere in this single-user app.
- **Commit/issue:** None recorded by the AI assistant.

## `EDIT-03` — Pre-TTS translation readiness validation

- **AI assistance:** Added a read-only SQLAlchemy validation service/API, structured readiness issues, conservative centralized timing heuristics, and viewer UI for readiness, separated blocking errors/warnings, Segment navigation, and stale-result invalidation after saved edits.
- **Developer decision:** Preserve EDIT-02's shared 10,000-character limit and translation protection; treat short windows, estimated WPS, and overlaps as warnings; keep original Whisper timestamps unchanged and leave synthesis/output timing to later TTS/Render tasks.
- **Affected areas:** Backend config, Project API/schemas/service, React viewer/styles, focused readiness tests, task status, architecture and append-only logs. No schema migration or dependency added.
- **Verification:** 33 backend unit tests passed, including no-write verification; frontend production build, `compileall`, `pip check`, and `git diff --check` passed. Manual browser acceptance remains pending.
- **Result/limits:** Partial. The readiness result uses 250 ms and 8 whitespace-delimited Vietnamese tokens/second as warning-only heuristics. It does not measure synthesized duration or implement adaptive pacing, time-stretching, or output timeline changes.
- **Commit/issue:** None recorded by the AI assistant.

## `INIT-04` — Confirm development environment

- **AI assistance:** Analyzed developer-provided machine results and updated environment-related documentation without installing packages or writing application code.
- **Developer decision:** Python 3.11 virtual environment; worker directly on Windows; one job at a time; Whisper model `small` initially; prefer `h264_nvenc` when available; retain CPU fallback.
- **Affected areas:** `docs/ENVIRONMENT.md` and related environment references.
- **Verification:** Compared developer-provided command output with the recorded environment facts; checked documentation consistency.
- **Result/limits:** Environment documentation completed. Whisper GPU execution and provider/media performance were not claimed as verified.
- **Commit/issue:** None recorded by the AI assistant.

## `ENV-00` — Confirm disk capacity

- **AI assistance:** Reviewed the move to drive D and available capacity.
- **Developer decision:** Continue the MVP on drive D while keeping roughly 10 GB free during model download and media processing.
- **Verification:** Developer reported about 27 GB free on drive D.
- **Result/limits:** Disk prerequisite accepted. No virtual environment, dependencies, models, or application code were created in this task.

## `ENV-01` — Bootstrap minimal FastAPI

- **AI assistance:** Implemented a minimal FastAPI application and a JSON health endpoint.
- **Developer decision:** Use the selected Python 3.11 interpreter with an ignored local virtual environment; defer dependency pinning and all non-health API work to later tasks.
- **Affected areas:** `backend/app/main.py` and task completion records.
- **Verification:** Started Uvicorn with `app.main:app` and called `GET http://127.0.0.1:8000/health`; received HTTP 200 with `{"status":"ok"}`.
- **Result/limits:** ENV-01 is complete; no frontend, database, worker, AI, or media-pipeline functionality was added.
- **Commit/issue:** None recorded by the AI assistant.

## `ENV-02` — Bootstrap minimal React, TypeScript, and Vite

- **AI assistance:** Initialized the minimal React/TypeScript/Vite configuration and welcome page.
- **Developer decision:** Keep the existing frontend placeholder directories and add no routing, API integration, state management, or UI framework.
- **Affected areas:** `frontend/` bootstrap files and task completion records.
- **Verification:** `npm run build` passed; Vite served `http://127.0.0.1:5173/` and a local HTTP request returned 200 with `AutoDub` present.
- **Result/limits:** ENV-02 is complete; package/development configuration hardening remains for ENV-03.
- **Commit/issue:** None recorded by the AI assistant.

## `ENV-03` — Dependencies and safe example configuration

- **AI assistance:** Added the verified direct backend dependency pins, safe environment template, and reproducible Windows setup instructions.
- **Developer decision:** Keep only FastAPI and Uvicorn in the backend requirements; retain the existing frontend package manifest and lockfile as its dependency source of truth; add no runtime configuration library.
- **Affected areas:** `backend/requirements.txt`, `.env.example`, `README.md`, and task completion records.
- **Verification:** Python 3.11 created/refreshed the backend virtual environment and installed requirements; FastAPI returned HTTP 200 at `/health`; `npm ci` and `npm run build` passed; Vite returned HTTP 200 with `AutoDub`; `.env` was ignored while `.env.example` remained trackable. A stale Vite process was stopped before the successful `npm ci` retry.
- **Result/limits:** ENV-03 is complete. No secrets, API integration, database, worker, or media functionality was added.
- **Commit/issue:** None recorded by the AI assistant.

## `DATA-01` — Document Supabase PostgreSQL persistence decision

- **AI assistance:** Updated the database-related task, architecture, product, and environment documentation to replace the planned SQLite layer with Supabase-hosted PostgreSQL.
- **Developer decision:** Keep FastAPI as the only application backend; use SQLAlchemy with a PostgreSQL driver and an uncommitted `DATABASE_URL`; keep React away from application tables and media file contents outside PostgreSQL. Defer Supabase Auth, Storage, Realtime, and RLS.
- **Affected areas:** `TASKS.md`, `docs/ARCHITECTURE.md`, `docs/PRD.md`, and `docs/ENVIRONMENT.md`.
- **Verification:** Reviewed the revised database references and documentation consistency; no application code, schema, dependency, or database connection was created or tested.
- **Result/limits:** Documentation is ready to guide DATA-01 implementation. Connection configuration, driver installation, schema creation, and persistence verification remain outstanding.
- **Commit/issue:** None recorded by the AI assistant.

## `DATA-01` — Documentation consistency supplement

- **AI assistance:** Updated the active README stack summary and Phase 3 plan label after the consistency check found their former SQLite references.
- **Verification:** Searched active documentation for SQLite references after the update; only append-only historical/audit context remains.
- **Result/limits:** No code, schema, dependency, or database connection was added or tested.

## `DATA-01` — Supabase PostgreSQL persistence foundation

- **AI assistance:** Implemented backend-only SQLAlchemy models, configuration, PostgreSQL engine/session helpers, and idempotent table initialization.
- **Developer decision:** Use SQLAlchemy 2.0.52, psycopg 3.3.5, and python-dotenv 1.2.3; load only the ignored repository `.env` without overriding an existing OS environment variable. No API, worker, frontend, Auth, Storage, Realtime, RLS, or media binary implementation was added.
- **Affected areas:** `backend/app/core/`, `backend/app/models/`, `backend/requirements.txt`, `.env.example`, and the authoritative architecture/environment records.
- **Verification:** Installed the pinned dependencies; `compileall` and offline SQLAlchemy metadata/relationship checks passed; `.env` is ignored and `.env.example` is trackable. The real initializer correctly refused to run because no `DATABASE_URL` is configured.
- **Result/limits:** The code foundation is present, but no Supabase connection, table creation, transaction, reconnect readback, or test-record cleanup could be performed. DATA-01 remains incomplete.
- **Commit/issue:** None recorded by the AI assistant.

## `DATA-01` — Live Supabase verification attempt

- **AI assistance:** Ran the application's SQLAlchemy/psycopg initialization and planned reconnect verification against the ignored local `DATABASE_URL`; used the selected Supabase plugin only for supplementary project/table inspection.
- **Verification:** The application reached Supabase but authentication was rejected before DDL or data changes. The plugin showed the intended project as healthy with no public tables. `.env` was not read into output or source control.
- **Result/limits:** No tables, verification records, or unrelated data were created, changed, or deleted. DATA-01 remains incomplete until valid local database credentials are provided.
- **Commit/issue:** None recorded by the AI assistant.

## `DATA-01` — Live Supabase verification completed

- **AI assistance:** Re-ran verification through the application's SQLAlchemy/psycopg connection after local credentials were corrected.
- **Verification:** Initialized the four metadata tables idempotently; committed one connected Project/Job/Segment/Artifact dataset; disposed the engine; read it back through a new engine/session; confirmed UUIDs, timezone-aware timestamps, relationships, foreign keys, and status/time constraints; then deleted only the verification project and cascade-owned children.
- **Result/limits:** DATA-01 is complete. No API, frontend, worker, Auth, Storage, Realtime, RLS, or media-binary capability was added.
- **Commit/issue:** None recorded by the AI assistant.

## `UPLOAD-01` — Server-controlled video upload

- **AI assistance:** Implemented the minimal FastAPI multipart upload route and backend storage service using the existing SQLAlchemy/Supabase persistence layer.
- **Developer decision:** Use `storage/projects/<project UUID>/source/video.mp4` as a fixed server-only path; retain no client filename, expose only a relative storage reference, and compensate by deleting the new file when database persistence fails.
- **Affected areas:** `backend/app/api/projects.py`, `backend/app/services/uploads.py`, router/config wiring, `python-multipart`, and task records.
- **Verification:** Generated a small local MP4 and submitted normal plus traversal-style filename uploads over HTTP. Both returned 201, persisted through a new Supabase connection, used UUID-controlled relative paths, and were removed with their verification files.
- **Result/limits:** UPLOAD-01 is complete. MIME/type, size, duration, and corruption validation remain explicitly deferred to UPLOAD-02.
- **Commit/issue:** None recorded by the AI assistant.

## `UPLOAD-02` — Video upload validation

- **AI assistance:** Centralized the agreed MP4/100 MiB/1800-second defaults, added bounded streaming validation, and integrated `ffprobe` container, video-stream, readability, and duration checks before persistence.
- **Developer decision:** Retain UPLOAD-01's UUID-only local storage and SQLAlchemy/Supabase flow; use the installed `ffprobe` executable with an argument list and timeout instead of adding a Python media library.
- **Affected areas:** Upload configuration, storage service, FastAPI error mapping, authoritative upload documentation, and task/audit records.
- **Verification:** Real multipart FastAPI requests against Supabase accepted valid and traversal-filename MP4 uploads (201); rejected an AVI (415), 104857601-byte upload (413), corrupt MP4 (422), and 1801-second MP4 (422). Every rejected name had zero Project rows and no residual UUID directory. Verification rows and generated media were deleted; `compileall`, `pip check`, and `git diff --check` passed; `.env` and runtime storage remain ignored.
- **Result/limits:** UPLOAD-02 is complete. Validation is intentionally limited to MP4 type, configured byte size, container/readability/video stream, and duration; no transcoding or later media pipeline work was added.
- **Commit/issue:** None recorded by the AI assistant.

## `UI-01` — Backend prerequisite for persistent project list

- **AI assistance:** Implemented the minimal FastAPI project-list endpoint with an explicit Pydantic response schema and added the Vite development proxy for `/api` requests.
- **Developer decision:** Expose the existing relative `source_media_reference` and map the persisted `business_status` column to the stable API field `status`; do not add unpersisted UI fields or direct Supabase access from React.
- **Affected areas:** `backend/app/api/projects.py`, new project response schemas, `frontend/vite.config.ts`, and append-only task records.
- **Verification:** Uploaded a real MP4 through the existing endpoint, listed it through FastAPI, read it through a new SQLAlchemy engine/session, confirmed the source reference was not absolute, and reached the same endpoint through `/api/projects` via Vite. Verification data/files were removed; compileall, pip check, frontend build, and `git diff --check` passed.
- **Result/limits:** The backend prerequisite is ready. UI-01 remains incomplete because frontend implementation is intentionally out of scope.
- **Commit/issue:** None recorded by the AI assistant.

## `UI-01` — React project list and upload flow

- **AI assistance:** Implemented the typed React project list, multipart upload form, loading/empty/submitting/success/error states, client-side MP4/size checks, and accessible minimal styling.
- **Developer decision:** Keep API calls on the existing `/api` proxy, use only persisted response fields, show source presence without exposing the internal storage reference as a link, and leave backend validation authoritative.
- **Affected areas:** `frontend/src/App.tsx`, `frontend/src/index.css`, and task audit records.
- **Verification:** Vite loaded the page without application console errors; persisted backend data appeared in the UI and remained after browser reload; form validation rendered a friendly missing-file error; real valid and rejected files were tested through the existing FastAPI upload contract; `npm run build`, `git diff --check`, and frontend direct-Supabase search passed. Verification records/files were removed.
- **Result/limits:** Frontend implementation is present, but UI-01 is not complete because the browser automation environment rejected local file injection, so a real upload initiated by the browser UI could not be observed end-to-end.
- **Commit/issue:** None recorded by the AI assistant.

## `UI-01` — Post-upload form reset fix

- **AI assistance:** Inspected the reported successful-upload failure and corrected the async form reset by capturing `event.currentTarget` before the first await.
- **Developer decision:** Keep the existing upload/list API flow and state behavior unchanged; only replace the unsafe post-await event access.
- **Affected areas:** `frontend/src/App.tsx` and task audit records.
- **Verification:** Confirmed the submit handler uses the stable form reference for reset and no longer reads `event.currentTarget` after an async boundary; `npm run build` and `git diff --check` passed.
- **Result/limits:** The confirmed null-reset bug is fixed. Manual browser verification of the complete upload flow remains required.
- **Commit/issue:** None recorded by the AI assistant.

## `UI-01` — Manual browser acceptance completed

- **AI assistance:** Recorded the developer-provided manual acceptance evidence and updated the task status; no implementation changes were made in this close-out.
- **Developer decision:** Accept the native file-picker upload, immediate list refresh, safe form reset, and browser-refresh persistence as the final UI-01 evidence.
- **Affected areas:** `TASKS.md` and append-only task audit records.
- **Verification:** Developer manually selected a real valid MP4, uploaded it through React, confirmed the form reset and immediate new Project appearance, refreshed the browser, and confirmed the Project persisted with no prior reset error. `npm run build` and `git diff --check` passed.
- **Result/limits:** UI-01 is complete. No remaining issue was reported.
- **Commit/issue:** None recorded by the AI assistant.

## `JOB-01` — PostgreSQL-backed enqueue and worker foundation

- **AI assistance:** Added a project-scoped FastAPI enqueue route and a separate Python worker that serializes PostgreSQL claims, selects the oldest queued Job, and keeps only one Job in `running` state. Added configurable polling and documented the no-pipeline behavior.
- **Developer decision:** Reuse existing Job fields and Supabase PostgreSQL; do not add a queue dependency, schema fields, or fake successful processing.
- **Affected areas:** Backend project API, job response schema, worker, backend configuration, architecture/task records, and append-only logs.
- **Verification:** `python -m compileall -q app`, `python -m pip check`, and FastAPI import/OpenAPI route inspection passed. A runtime SQLAlchemy connection returned Supabase ENOTFOUND tenant/user; Supabase MCP schema inspection timed out while the project listing reported the database inactive.
- **Result/limits:** Code foundation is present, but live Job persistence, separate-process claiming, sequential behavior, and persistence after reconnect remain unverified. JOB-01 remains incomplete.
- **Commit/issue:** None recorded by the AI assistant.

## `JOB-01` — Live Supabase verification completed

- **AI assistance:** Ran the real FastAPI enqueue flow against the configured Supabase PostgreSQL database, launched the worker as a separate Python process, verified sequential claiming and fresh-connection persistence, and cleaned up only the temporary Project and Jobs created for this run.
- **Developer decision:** Leave a claimed Job `running`/`claimed` until a real processing pipeline exists; do not mark it successful or add recovery behavior in JOB-01.
- **Affected areas:** `TASKS.md` and append-only task audit records; no implementation changes were needed during live verification.
- **Verification:** SQLAlchemy connected successfully. Both HTTP enqueue requests returned 202 promptly with `queued`; the independent worker claimed the first Job as `running`/`claimed`, while the second stayed `queued`. API and worker had distinct live PIDs. A new engine/session and Supabase MCP confirmed the persisted rows; temporary records were deleted. `compileall`, `pip check`, `git diff --check`, and ignore/secret checks passed; unittest discovery found no tests.
- **Result/limits:** JOB-01 acceptance is complete. The worker intentionally leaves the claimed verification Job running; all verification data was removed afterward. Supabase MCP reported RLS disabled on the existing public tables; that unrelated schema setting was left unchanged.
- **Commit/issue:** None recorded by the AI assistant.

## `JOB-02` — Persisted lifecycle, interruption recovery, and retry

- **AI assistance:** Extended the existing Job lifecycle with safe success/failure transition helpers, restart recovery under a worker-process advisory lock, typed read/retry endpoints, and persisted queue/claim timestamps. Reused `safe_error`, `started_at`, and timezone-aware `completed_at`; no migration was needed.
- **Developer decision:** Preserve interrupted/failed Jobs as history, create a new record for retry, never automatically resume work, and leave verification Jobs short of `succeeded` because no real processing pipeline exists.
- **Affected areas:** Job API/schema, project enqueue stage, worker lifecycle, FastAPI router registration, architecture/task status, and append-only audit records.
- **Verification:** Against real Supabase, confirmed API `queued`/GET state; separate worker `running`/`claimed` and `started_at`; forced worker termination followed by startup recovery to `interrupted` with a reason and finish time; retry kept the original unchanged and created a new queued Job; queued/running retries returned 409; failure helper persisted a bounded path-redacted summary and finish time; next Job claimed only after the prior one failed. Fresh SQLAlchemy sessions and Supabase MCP confirmed records; only test Project and Jobs were deleted. `compileall`, `pip check`, `git diff --check`, and secret/ignore checks passed; unittest discovery found no tests.
- **Result/limits:** JOB-02 is complete. No Job was marked succeeded. Existing lifecycle columns were sufficient, so Supabase schema/data outside verification rows was unchanged.
- **Commit/issue:** None recorded by the AI assistant.

## `UI-02` — Real persisted Job status and stage UI

- **AI assistance:** Added the typed Project-scoped Job listing endpoint and connected the existing React project list to enqueue, recover, display, and poll persisted Job lifecycle state.
- **Developer decision:** Keep FastAPI as the only frontend data boundary, poll only queued/running Jobs at a four-second interval, show only persisted stage/error/timestamps, and never imply pipeline completion or numeric progress.
- **Affected areas:** `backend/app/api/projects.py`, `frontend/src/App.tsx`, `frontend/src/index.css`, `docs/ARCHITECTURE.md`, and task audit records.
- **Verification:** Against real Supabase through FastAPI/Vite, the UI created a queued Job with the worker stopped, recovered the same Job after refresh, displayed running/claimed after a separate worker claimed it, and displayed interrupted plus its safe reason after worker restart. Verification rows were removed. `npm run build`, backend `compileall`, `pip check`, unittest discovery (0 tests), `git diff --check`, frontend Supabase/progress search, and secret/ignore checks passed.
- **Result/limits:** UI-02 is complete. Jobs remain `running` until a worker restart marks uncompleted work interrupted; no ASR/translation pipeline was added.
- **Commit/issue:** None recorded by the AI assistant.

## `UI-02` — Manual browser acceptance close-out

- **AI assistance:** Recorded the developer's final manual browser acceptance and clarified the UI-02 task evidence; no implementation changes were needed.
- **Developer decision:** Accept the real queued state, reload recovery of the same persisted Job, worker-driven `running`/`claimed` state, worker-restart `interrupted` state, and the absence of fabricated percentage progress.
- **Affected areas:** `TASKS.md` and append-only task audit records.
- **Verification:** The developer confirmed the end-to-end browser flow against the backend. `npm run build` and `git diff --check` passed during this close-out.
- **Result/limits:** UI-02 is complete. The worker still has no ASR/translation pipeline, which remains out of scope.
- **Commit/issue:** None recorded by the AI assistant.

## `ASR-01` — Real Whisper transcription and Segment persistence

- **AI assistance:** Implemented a focused faster-whisper service with a reused per-worker model, managed source-path resolution, timestamp/text normalization, safe transcript replacement, and transactional Segment persistence; connected ASR stages to the existing sequential worker.
- **Developer decision:** Keep the existing combined `transcribe_translate` Job truthful by leaving it `running` after ASR; preserve translated/revised transcript data on rerun conflicts; attempt CUDA then explicitly fall back to CPU.
- **Affected areas:** ASR service, worker lifecycle, pinned backend dependency, ignored model/cache locations, normalization tests, architecture/environment records, and task audit records.
- **Verification:** Real uploaded speech and silent MP4s were processed by the separate worker against Supabase. Fresh SQLAlchemy sessions confirmed transcript timestamps/IDs and empty translation fields; rerun did not duplicate Segments; no-speech yielded zero Segments; edited transcript data was preserved after a safe failure. CUDA inference failed due to unavailable `cublas64_12.dll`; real CPU `int8` inference succeeded. Removed only verification records and media. `compileall`, `pip check`, 3 unit tests, `git diff --check`, secret/ignore checks passed.
- **Result/limits:** ASR-01 is complete. GPU inference is not verified, combined Jobs remain running until translation exists, and Supabase MCP reported public-table RLS disabled; no unrelated Supabase security setting was changed.
- **Commit/issue:** None recorded by the AI assistant.

## `TRANS-01` — Gemini translation for persisted Segments

- **AI assistance:** Added the official `google-genai` SDK integration, centralized model/key/batch configuration, structured batch response validation, all-or-nothing translation persistence, and worker success/no-speech transitions.
- **Developer decision:** Use stable `gemini-3.8-flash`; send deterministic batches rather than per-Segment requests; preserve exact persisted Segment identity/source/timing/order; never count partial or malformed results as success; skip Gemini for no-speech Projects.
- **Affected areas:** Local configuration example and backend config, translation service, sequential worker lifecycle, focused unit tests, architecture/environment documentation, and task audit records. No database schema or frontend changes.
- **Verification:** Against real Supabase, a FastAPI-uploaded speech video produced four ASR Segments and one real Gemini structured request; all translations persisted, Job reached `succeeded`/`translation_ready`, and a pre-translation snapshot matched after a fresh SQLAlchemy reconnect. Supabase MCP independently confirmed persisted rows. A silent video completed `succeeded`/`no_speech` with zero Segments and no Gemini call. Nine unit tests passed for valid/invalid mappings, preserving existing translations, and no-partial-write behavior. Existing JOB-02 safe failure and interruption recovery were confirmed. Verification Projects/Jobs/Segments/files were removed. `compileall`, `pip check`, `git diff --check`, frontend Supabase search, and secret/ignore checks passed.
- **Result/limits:** TRANS-01 is complete. No quota retry/backoff or translation editing was added; these remain out of scope. Supabase MCP reported RLS disabled on existing public tables; no policy/schema change was made.
- **Commit/issue:** None recorded by the AI assistant.

## `TRANS-02` — Bounded Gemini retries and quota handling

- **AI assistance:** Added structured-first provider error classification, immediate quota/permanent failure, a single bounded retry for transient requests, and a single same-batch retry for malformed structured output. Added deterministic mock-provider tests and kept translation validation and transactional persistence unchanged.
- **Developer decision:** Do not make real Gemini calls to simulate quota; do not add schema changes, model switching, or quota fallback/splitting. Preserve existing safe worker failure handling and exact Segment identity/content.
- **Affected areas:** Translation service, unit tests, architecture retry behavior, task status, and append-only audit logs. No database schema, provider, or frontend changes.
- **Verification:** All 14 backend unit tests passed; `compileall`, `pip check`, `git diff --check`, secret/runtime-file and ignore checks passed. Retry sleeps were mocked. No real Gemini request was made.
- **Result/limits:** TRANS-02 is complete. Transient backoff is fixed at 0.5 seconds and attempted once; context-limit splitting is not implemented.
- **Commit/issue:** None recorded by the AI assistant.

## `TTS-01` — Vietnamese Edge-TTS audio per Segment

- **AI assistance:** Implemented readiness-gated TTS Job enqueue, sequential worker dispatch, Edge-TTS service with adaptive WPS pacing, bounded concurrency/retries, FFprobe duration measurement, transactional Artifact publication, safe audio APIs, and focused frontend playback controls.
- **Developer decision:** Keep TTS as a separate explicit `tts` operation; preserve source timestamps and translation text; preserve prior valid artifacts if regeneration fails; leave final rendering and timeline changes for later tasks. Keep TTS-01 partial until real Project and browser playback acceptance.
- **Affected areas:** Backend configuration, Artifact metadata and additive Supabase migration, TTS API/service/worker, Project viewer UI, unit tests, environment/architecture records, task and append-only audit logs.
- **Verification:** 44 backend unit tests passed; frontend production build, Python compileall, pip check, and `git diff --check` passed. A real Edge-TTS sample using `vi-VN-HoaiMyNeural` was measured by FFprobe at 3,480 ms. SQLAlchemy and Supabase MCP confirmed the new Artifact columns.
- **Result/limits:** Implementation is partial pending real persisted Project worker execution and browser audio playback. Supabase reports RLS disabled on existing public tables; this task did not alter those unrelated policies. Dynamic time stretching, timeline shifting, mixing, and rendering remain future work.
- **Commit/issue:** None recorded by the AI assistant.

## `TTS-01` — Manual acceptance close-out

- **AI assistance:** Updated the TTS-01 task status and appended the user's real browser acceptance evidence; clarified that synchronization and rendering remain future work.
- **Developer decision:** Accept the verified `demo2` Job, readiness, per-Segment playback, adaptive rate, duration persistence, refresh, and source-data preservation results. Keep TTS-02 and rendering tasks pending.
- **Affected areas:** `TASKS.md`, `docs/ARCHITECTURE.md`, and append-only task audit records.
- **Verification:** Recorded the manual results supplied by the user. No automated checks were rerun except `git diff --check`.
- **Result/limits:** TTS-01 is complete. Audio/video synchronization, Dynamic Video Time-Stretching, and rendering are not part of TTS-01.
- **Commit/issue:** None recorded by the AI assistant.

## `TTS-02` — Duration analysis and dynamic timeline planning

- **AI assistance:** Implemented a read-only timeline planning service and typed API, current TTS Artifact provenance checks, a Project viewer analysis panel, and deterministic planner/API tests. Updated the TTS-02 task scope and relevant architecture/environment records.
- **Developer decision:** Keep the plan read-only, cap source-video stretch at 1.4×, preserve all source timestamps, and leave task status partial until manual browser acceptance. Do not implement rendering, audio time-stretching, mixing, or subtitles.
- **Affected areas:** `backend/app/api/projects.py`, timeline schema/service, `frontend/src/App.tsx`, `frontend/src/index.css`, tests, `TASKS.md`, architecture/environment documentation, and append-only task logs.
- **Verification:** 57 backend unit tests, frontend production build, `compileall`, `pip check`, and `git diff --check` passed. The real `demo2` endpoint call through FastAPI/SQLAlchemy returned a read-only plan for 11 persisted Segments and TTS Artifacts: 21,339 ms original, 25,211 ms planned, 3,872 ms added, 9 stretch operations, and 8 blocking cap conflicts. Browser acceptance remains pending.
- **Result/limits:** TTS-02 remains partial pending user browser verification. No schema or dependency changes; no video or audio was rendered.
- **Commit/issue:** None recorded by the AI assistant.

## `TTS-02` — Manual acceptance close-out

- **AI assistance:** Updated the task status and appended the user's manual browser acceptance evidence while preserving the earlier implementation log.
- **Developer decision:** Treat the eight 1.4× cap conflicts as valid analysis output and complete TTS-02; keep `demo2` non-renderable until conflicts are resolved. Leave video stretching execution, mixing, subtitle synchronization, and rendering for future tasks.
- **Affected areas:** `TASKS.md`, `docs/CHANGELOG.md`, and this append-only audit log.
- **Verification:** Recorded the user's real-browser results. Ran `git diff --check`; no automated tests were rerun.
- **Result/limits:** TTS-02 is complete. The `demo2` plan still has eight unresolved timing conflicts and is not ready for rendering.
- **Commit/issue:** None recorded by the AI assistant.

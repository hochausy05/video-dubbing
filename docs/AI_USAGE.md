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

## `TTS-03` — Duration-aware TTS optimization and timeline conflict resolution

- **AI assistance:** Implemented the typed optimization Job API/result, sequential worker operation, bounded Edge-TTS rate attempts with measured-duration re-planning, guarded atomic Artifact replacement, recovery cleanup for unpublished interrupted work, frontend status/result controls, and focused deterministic tests. Added only the required PostgreSQL Artifact-rate constraint expansion and documented the configuration/workflow.
- **Developer decision:** Keep optimization bounded to existing planner-blocking Segments and rates up to +35%; never edit translations or source timestamps. A successful optimization Job reports its actual result even if timing conflicts remain; it never implies render readiness. Leave TTS-03 partial until real Project/browser acceptance.
- **Affected areas:** Backend TTS API/config/model/service/worker/schemas, frontend Project viewer, one Supabase migration, unit tests, task/architecture/environment docs, and append-only audit logs.
- **Verification:** 70 backend unit tests passed, including 13 TTS optimization tests; `npm run build`, backend `compileall`, `pip check`, and `git diff --check` passed. The additive check constraint was applied to the active Supabase project and independently inspected through Supabase MCP and SQLAlchemy. Secret/ignore check confirmed `.env` and runtime/build directories are ignored. No real Edge-TTS optimization run or browser acceptance was performed.
- **Result/limits:** TTS-03 is partial pending real worker/API/browser acceptance. No video stretching, mixing, subtitles, or rendering was implemented. Supabase MCP reported RLS disabled on existing public AutoDub tables; this unrelated configuration was left unchanged.
- **Commit/issue:** None recorded by the AI assistant.

## `TTS-03` — Manual acceptance close-out

- **AI assistance:** Recorded the user's real `demo2` browser acceptance, marked TTS-03 complete, and advanced the current task pointer to pending RENDER-01. Preserved the existing implementation log and appended close-out records.
- **Developer decision:** Accept the real Edge-TTS optimization results while keeping `demo2` explicitly non-renderable with six unresolved conflicts. Leave timeline conflict resolution and video rendering pending.
- **Affected areas:** `TASKS.md`, `docs/CHANGELOG.md`, and this append-only audit log.
- **Verification:** Recorded the manual results supplied by the user. Ran `git diff --check`; earlier automated results were not rerun.
- **Result/limits:** TTS-03 is complete. Six conflicts remain (64, 536, 216, 232, 232, and 920 ms excess); no rendering readiness is claimed.
- **Commit/issue:** None recorded by the AI assistant.

## `TIMELINE-01` — Guided timeline conflict resolution

- **AI assistance:** Inspected EDIT-02 and TTS-01/02/03 flows; extended the existing viewer with stable-ID conflict details, links into the existing translation editor, truthful stale timeline/audio messaging, and full-Project TTS regeneration guidance. Added focused tests for translation fingerprint invalidation and transactional full regeneration. Documented the workflow and render-readiness boundary.
- **Developer decision:** Reuse the existing full TTS Job because current generation validates a complete transcript snapshot and publishes the complete Artifact set atomically. Do not attempt selective regeneration or automatic translation rewriting. Keep TIMELINE-01 partial until real browser acceptance.
- **Affected areas:** `TASKS.md`, architecture notes, Project viewer UI/styles, TTS pipeline tests, and append-only task logs.
- **Verification:** 72 backend unit tests, `npm run build`, backend `compileall`, `pip check`, `git diff --check`, and source secret/ignore checks passed. Automated tests used mocked synthesis; no real Edge-TTS request or browser flow was run.
- **Result/limits:** The user must manually verify the guided workflow on `demo2`. No rendering, audio mixing, or subtitle generation was added.
- **Commit/issue:** None recorded by the AI assistant.

## `TIMELINE-01` — Segment 10 duration investigation

- **AI assistance:** Traced translation persistence, TTS enqueue/worker dispatch, Edge-TTS inputs, FFprobe measurement, Artifact publication/provenance, planner selection, API responses, and frontend rendering. Inspected the existing `demo2` Segment 10 Artifact and media read-only through SQLAlchemy, FFprobe/FFmpeg, and Supabase MCP. Added an end-to-end deterministic regression test for translation edit, stale Artifact rejection, full regeneration, current Artifact selection, and timeline recalculation.
- **Developer decision:** Treat the identical 1,872 ms values as valid measurements because the old and current files are distinct and independently measure to 78 MP3 frames; keep +20% because both texts remain above the existing adaptive-rate threshold. Do not force duration changes or modify production code. Leave TIMELINE-01 partial pending browser acceptance.
- **Affected areas:** `tests/unit/test_tts_pipeline.py` and append-only task audit records.
- **Verification:** The user-provided current translation matched the current Artifact fingerprint; historical Artifact fingerprint matched the original text. SQLAlchemy and Supabase MCP agreed on current persisted metadata. `/tts-audio` and `/tts-timeline-plan` API calls returned the persisted 1,872 ms, +20%, 920 ms Segment 10 conflict. FFprobe measured old/current files; FFmpeg silence detection showed a longer low-amplitude tail in the current file, without evidence that the application inserts padding. 73 backend unit tests, frontend production build, `compileall`, `pip check`, and `git diff --check` passed. No real synthesis was triggered and no Project data was changed.
- **Result/limits:** No production defect was confirmed. The unchanged total duration is consistent with the measured current media, though differing trailing low-amplitude regions merit a separate explicit product decision about silence trimming/measurement. Browser acceptance remains outstanding.
- **Commit/issue:** None recorded by the AI assistant.

## `UI-03` — Responsive Project workspace redesign

- **AI assistance:** Reorganized the Project Viewer into video, transcript, and TTS/timeline panels; added responsive layouts, contained Segment-list scrolling, conflict-target highlighting/navigation, and collapsible timeline details.
- **Developer decision:** Kept all existing API calls and TTS/timeline logic. Protected an unsaved translation draft when a user tries to open another Segment, and left UI-03 partial pending browser acceptance.
- **Affected areas:** `frontend/src/App.tsx`, `frontend/src/index.css`, `TASKS.md`, and append-only task logs.
- **Verification:** `npm run build` and `git diff --check` passed. No browser acceptance was performed.
- **Result/limits:** Responsive behavior and preserved editing/playback/navigation workflows need manual checks at wide desktop, laptop, and mobile viewports. TIMELINE-01 remains pending its separate acceptance.
- **Commit/issue:** None recorded by the AI assistant.

## `TTS-04` — Silence-aware TTS normalization

- **AI assistance:** Implemented conservative decoded-signal tail-silence analysis with FFmpeg, media re-encoding and FFprobe verification, versioned provenance sidecars, normalization in standard TTS generation and optimization candidates, and a separate existing-audio normalization Job with atomic Artifact replacement. Added synthetic-media and API/worker persistence tests and documented the behavior.
- **Developer decision:** Preserve raw Edge-TTS media, never adjust duration metadata without changing media, keep internal pauses, skip uncertain trims, preserve current voice/rate, and avoid running normalization against demo2 until browser/listening review. No schema or dependency changes.
- **Affected areas:** TTS services, Project API and schemas, worker dispatch, timeline/optimization validation, Project Viewer, focused tests, task and architecture records.
- **Verification:** 87 backend unit tests, frontend production build, backend `compileall`, `pip check`, and `git diff --check` passed. Tests use deterministic synthetic media and mocked provider calls; no real Project media was normalized.
- **Result/limits:** TTS-04 remains partial pending user browser playback/listening and refreshed timeline acceptance on demo2. No Supabase data was changed, and no real-world duration/conflict reduction is claimed.
- **Commit/issue:** None recorded by the AI assistant.

## `TTS-04` — demo2 normalization Job investigation

- **AI assistance:** Compared read-only SQLAlchemy and Supabase rows, current Artifact provenance/sidecar measurements, and the live timeline API. Traced a failed normalization Job to an order-sensitive snapshot comparison; changed both snapshots to compare by Artifact ID, added reversed-UUID worker integration coverage, and clarified the UI distinction between a failed Job and a timeline based on current published media.
- **Developer decision:** Preserve the current demo2 Artifact generation, media, and rates; do not rerun Edge-TTS or normalization against real data. Keep TTS-04 partial pending browser playback and listening acceptance.
- **Affected areas:** Normalization worker service, worker integration tests, Project Viewer messaging, and architecture/task audit records.
- **Verification:** SQLAlchemy and Supabase MCP agree that the failed normalization Job published zero Artifacts and the successful TTS generation owns all 11 current Artifacts. The live read-only timeline API returned 23,730 ms and two blockers. Five focused normalization tests passed, including the new ordering regression. No demo2 rows/files were modified.
- **Result/limits:** A code ordering defect explains the false stale failure. Real browser acceptance/listening remains pending; the Project is not renderable.
- **Commit/issue:** None recorded by the AI assistant.

## `TTS-04` — Manual acceptance close-out

- **AI assistance:** Updated the task status and append-only project audit records from the user's manual browser acceptance results. Kept the remaining timeline blockers explicitly unresolved.
- **Developer decision:** Mark TTS-04 complete after acceptance of the repeated normalization result; keep TIMELINE-01 partial because the current plan still has two blocking conflicts. Do not alter application logic or demo2 data.
- **Affected areas:** `TASKS.md`, `docs/CHANGELOG.md`, and this audit log.
- **Verification:** User confirmed the normalization Job reached `tts_normalization_complete`, processed 11 files with 0 additional files shortened and 0 ms additional duration recovered, preserved durations on repeat, and accepted the result. Segment 10 is 1,045 ms versus 1,872 ms originally. Timeline reports 23,730 ms output and two blockers (Segment 3: 246 ms; Segment 10: 93 ms). The prior 88-test backend suite, frontend build, `compileall`, `pip check`, and `git diff --check` had passed; only `git diff --check` was rerun for this documentation close-out.
- **Result/limits:** TTS-04 is complete. Timeline blockers remain; no render-ready status is claimed. No application code or Project data was changed.
- **Commit/issue:** None recorded by the AI assistant.

## `RENDER-01` — Timeline-based MP4 rendering

- **AI assistance:** Implemented a tracked render Job using the existing worker, TTS timeline planner, Artifact model, controlled storage and Project Viewer. Added filtergraph construction for complete source interval partitions, planner-derived video/audio stretch and dubbing placement, H.264/AAC verification, input fingerprints, atomic publication, current-render APIs and UI recovery. Added synthetic FFmpeg/SQLite/API regression coverage and updated architecture/environment/task logs.
- **Developer decision:** Keep the existing timeline planner authoritative, use CPU `libx264`, preserve the current render Artifact on failures, reject stale inputs, and keep RENDER-01 partial pending browser acceptance. Do not render or modify `demo2`; keep TIMELINE-01 partial.
- **Affected areas:** Render service, Project API, existing worker and Job retry boundary, typed render schema, Project Viewer, environment sample, focused tests and task/architecture/environment audit records.
- **Verification:** 16 focused render tests and 104 backend unit tests passed, with real FFmpeg/FFprobe on synthetic media; `npm run build`, Python `compileall`, `pip check`, `git diff --check`, and ignored-secret checks passed. No Supabase schema migration, real Project rendering, Edge-TTS synthesis, or demo2 data change was performed.
- **Result/limits:** Synthetic API/worker publication, mixed streams, timestamp placement, stale-data rollback, previous Artifact preservation, MP4 Range preview/download, and persistence after a fresh SQLite engine are verified. Real Project browser playback/listening/timing/download/refresh acceptance remains pending.
- **Commit/issue:** None recorded by the AI assistant.

## `TIMELINE-01` and `RENDER-01` — demo2 manual acceptance close-out

- **AI assistance:** Updated task statuses and append-only audit records from the user's confirmed browser acceptance. Reconciled the architecture's previous pending-acceptance statement with the newly reported real Project result.
- **Developer decision:** Mark TIMELINE-01 and RENDER-01 complete; preserve the already completed TTS-04 status and leave unrelated task statuses unchanged. Do not alter application logic or demo2 data, and do not rerun tests or rendering.
- **Affected areas:** `TASKS.md`, the RENDER-01 acceptance paragraph in `docs/ARCHITECTURE.md`, and append-only task logs.
- **Verification:** User confirmed on `demo2` that the timeline planner reported zero blockers and ready-to-render; the render Job completed at `render_complete`; preview and download were available; planned and verified output durations were both 23,681 ms; the plan had 11 TTS Segments and 7 stretch operations. `git diff --check` was run for this close-out. No additional tests were run.
- **Result/limits:** TIMELINE-01 and RENDER-01 are complete based on user-confirmed browser acceptance. No new playback/listening detail beyond the user's report is claimed. No Project rows or media were changed.
- **Commit/issue:** None recorded by the AI assistant.

## `AUDIO-01` — Timeline-aware audio mixing implementation

- **AI assistance:** Added validated per-render mix settings, a deterministic output-timeline ducking envelope, FFmpeg integration, artifact provenance/API exposure, Project Viewer controls, and focused regression/integration coverage. Applied the additive nullable Job settings column to the active Supabase project after inspecting its current schema.
- **Developer decision:** Preserve fixed-mix compatibility, use conservative Auto Ducking defaults (0.35 background, 0.08 ducked, 1.0 TTS; 80 ms attack, 250 ms release, 350 ms bridge), keep the existing 0.95 limiter, and never alter planner timing or source/TTS assets. Keep AUDIO-01 partial pending the user's real-Project listening acceptance; do not render demo2.
- **Affected areas:** Render Job/API/schema/model, audio mixing and render worker service, viewer settings and published-render messaging, additive Supabase migration, architecture/environment/task records, and focused tests.
- **Verification:** 115 backend unit tests passed, including FFmpeg/FFprobe synthetic-media checks for ducked/background RMS and planned output duration, Artifact preservation across a changed-settings render failure, and existing v1 render compatibility; frontend production build, `compileall`, `pip check`, Supabase schema inspection, and a SQLAlchemy connection/query through configured `DATABASE_URL` passed. No real Project audio was rendered or listened to.
- **Result/limits:** Per-Job settings are persisted, included in render fingerprints and artifact sidecars, and returned from the API. Auto Ducking reduces the complete original soundtrack and cannot isolate speech. Browser refresh and manual audio quality acceptance remain unverified.
- **Commit/issue:** None recorded by the AI assistant.

## `AUDIO-01` — demo2 manual listening acceptance close-out

- **AI assistance:** Updated the AUDIO-01 task status and appended the user-confirmed manual browser/listening evidence to the project audit logs.
- **Developer decision:** Mark AUDIO-01 complete using the user's acceptance of Auto Ducking on `demo2`; preserve implementation and demo2 data/media, and do not rerun tests or rendering.
- **Affected areas:** `TASKS.md`, `docs/CHANGELOG.md`, and this audit log.
- **Verification:** User confirmed the resulting mix was satisfactory with 0.35 background gain, 0.08 ducked gain, 1.0 Vietnamese TTS gain, 80 ms attack, 250 ms release, and 350 ms short-gap bridging. Prior reported checks: 115 backend unit tests, frontend build, `compileall`, `pip check`, `git diff --check`, and successful Supabase migration. No additional checks were run for this close-out.
- **Result/limits:** AUDIO-01 is complete based on the user's real-world listening acceptance. No further measurements or test results are claimed.
- **Commit/issue:** None recorded by the AI assistant.

## `LEGACY-01` — Legacy desktop parity audit

- **AI assistance:** Compared the four available desktop modules with current AutoDub translation, ASR, TTS, timeline, and render services; documented source references, parity classifications, unsafe legacy behaviors, current safeguards, and an evidence-based TRANS-03 implementation checklist. Updated the task pointer and roadmap priority without changing application code or existing task evidence.
- **Developer decision:** Treat desktop source as the required reference before pipeline algorithm changes. Keep the strict UUID mapping, no-fallback behavior, bounded TRANS-02 retry policy, transactional persistence, measured media provenance, and authoritative timeline blockers. Mark LEGACY-01 complete for static source availability and comparison only; do not claim runtime parity. Project currently has no genre field, so no schema change was proposed.
- **Affected areas:** `docs/LEGACY_PARITY_AUDIT.md`, `PLAN.md`, `TASKS.md`, and append-only audit logs.
- **Verification:** Confirmed all four original modules exist in the neighboring reference directory, inspected current implementation and Project fields, and ran `git diff --check` successfully. No runtime tests, provider requests, media processing, database/project access, or demo data changes were performed.
- **Result/limits:** Source-level findings are recorded. TRANS-03 is the next task; model limits, context-window size, translation quality, runtime parity, and any initial TTS rate-policy change remain unverified.
- **Commit/issue:** None recorded by the AI assistant.

## `TRANS-03` — Legacy-informed Bulk-First contextual translation

- **AI assistance:** Implemented full-transcript-first request planning with bounded input/output budgets, deterministic ordered fallback batches, adjacent context-only rows, timeline-aware prompt context, strict target-ID output validation, safe request metrics, and provider SDK retry/timeout configuration. Expanded deterministic translation tests and updated the source audit, architecture, task status, and append-only logs.
- **Developer decision:** Reuse the legacy bulk/context/localization intent selectively, but retain stable UUIDs, exact persisted timestamps, no source-text fallback, strict complete mappings, atomic all-or-nothing persistence, and TRANS-02 classification. No genre field exists, so none was invented. Disable Google SDK automatic retries and keep the application retry policy authoritative. Do not call Gemini or claim translation-quality improvement; reserve real-output comparison for TRANS-04 with explicit approval.
- **Affected areas:** Translation service/configuration, `.env.example`, focused translation tests, legacy parity audit, architecture and task/audit records.
- **Verification:** 16 focused translation unit tests passed using mocked Gemini responses; the 267-Segment case persisted one complete set from one mocked request under explicit budgets. Python `compileall`, `pip check`, and `git diff --check` passed. No real Gemini request, Supabase access, Project/media mutation, or frontend change was made.
- **Result/limits:** Functional request planning and integrity safeguards are covered by deterministic tests. Local UTF-8 byte estimates are conservative proxies rather than provider tokenization; model-specific limits must be configured lower when needed. Real translation quality remains unverified.
- **Commit/issue:** None recorded by the AI assistant.

## `TRANS-03-FIX` — Gemini 503/504 diagnosis preparation

- **AI assistance:** Compared current Gemini client/request settings with the pre-TRANS-03 Git revision and added an opt-in diagnostic script for plain text, minimal structured JSON, and the current TRANS-03 prompt using one synthetic Segment. The script reports safe status/category/timing/model metadata and does not access Project rows or print credentials, prompts, or provider payloads.
- **Developer decision:** Do not send live Gemini requests without explicit approval. Do not change the translation algorithm without a reproduced cause. Preserve existing ID validation, no-fallback behavior, batching, and atomic persistence.
- **Affected areas:** `backend/scripts/diagnose_gemini_requests.py` and append-only audit logs.
- **Verification:** 16 focused translation unit tests passed; backend `compileall`, `pip check`, and `git diff --check` passed. The script's no-confirmation guard was exercised and made no live calls. No live provider test or Project/database access was performed.
- **Result/limits:** The configured model (`gemini-3.8-flash`) and structured response schema were present before TRANS-03. The current SDK timeout is 120,000 ms; SDK retry is capped at one attempt, leaving the bounded application retry to account for the two observed attempts. AFC wrapper behavior may default on, but no tools/functions are configured and it does not add requests. The 503/504 failure remains unreproduced; the three live diagnostics await explicit approval.
- **Commit/issue:** None recorded by the AI assistant.

## `GEMINI-FIX` — Gemini access, safe diagnostics, and transcript-only retry

- **AI assistance:** Kept environment loading centralized at the repository root with OS overrides, added safe model discovery and an explicitly gated minimal generation probe, added pre-ASR configured-model availability validation, exposed sanitized provider status/reason/model/retryability through Job-safe errors, and added a transcript-only retry Job that reuses the existing transactional translation service without invoking Whisper.
- **Developer decision:** Preserve the current model default and do not auto-switch. Do not make paid generation requests without explicit approval. Retain TRANS-03 contextual Bulk-First behavior, strict ID validation, no source fallback, and all-or-nothing persistence. Reject translation retry when persisted Segments contain translations/edits or do not match the current Project revision.
- **Affected areas:** Gemini configuration example, translation service and worker, Project API, diagnostic CLI, task/architecture records, and focused unit tests.
- **Verification:** All 131 backend unit tests passed; Python `compileall`, `pip check`, and `git diff --check` passed. Offline tests cover environment resolution/overrides, model-list filtering, safe HTTP error handling, pre-ASR failure, and retry dispatch without Whisper. The active resolved model ID was read without exposing the API key. No live Gemini request or Project/media mutation was performed.
- **Result/limits:** Current environment resolves `gemini-3.5-flash-lite`; user-reported 403/404/503/504 failures were not reproduced. Model discovery command: `cd backend; .\.venv\Scripts\python.exe scripts\gemini_diagnostics.py list`. A single minimal generation probe remains behind `--confirm-live` and requires developer approval. No claim that Gemini has been fixed is made.
- **Commit/issue:** None recorded by the AI assistant.

## `GEMINI-FIX-02` — Investigate generation 403/404 and disable unused AFC

- **AI assistance:** Compared Google Gen AI SDK 2.28.0 client initialization and request paths. Explicitly selected the Gemini Developer API (`vertexai=False`, `v1beta`), disabled client-side AFC for translation and minimal diagnostic requests with no tools, and extended safe provider error extraction to include structured Google SDK status/reason/message with credential, link, and payload redaction. Clarified the worker catalog check does not prove inference entitlement.
- **Developer decision:** Do not change the model default, add fallback, alter TRANS-03, or send paid provider requests. Treat `models.list` results as catalog metadata only. Escalate the unresolved 403/404 to Google project/key access and model entitlement review.
- **Affected areas:** Translation client/service, diagnostic command, worker pre-ASR catalog stage, focused tests, architecture/task records, and append-only audit logs.
- **Verification:** 27 focused translation, diagnostic, and transcript-retry unit tests passed; backend `compileall` and `pip check` passed. Runtime inspection confirmed Gemini Developer API base URL, `v1beta`, 120,000 ms timeout, no Vertex/Enterprise flags, and no proxy environment variables. SDK source inspection confirmed `models.list` and `generateContent` share the client/base/version but call distinct GET and POST paths. No live Gemini call or Project mutation was performed.
- **Result/limits:** The user-provided 403 `PERMISSION_DENIED` and 404 `NOT_FOUND` for catalog-listed models are consistent with Google-side project/API entitlement or model access restrictions; the project’s AI Studio/billing/key status was not accessible here, so the exact account state is unverified. A successful generation request is still required before calling the integration fixed.
- **Commit/issue:** None recorded by the AI assistant.

## `GEMINI-FIX` — Live Gemini acceptance and current worker restart

- **AI assistance:** Identified the stale AutoDub worker process tree from its module command, executable paths, working directory, and the prior unsupported-operation failure. Stopped only that idle worker, launched the current repository worker from `backend/.venv`, verified its imported module path and `translate_existing` dispatch, then monitored one authorized translation-only Job.
- **Developer decision:** Authorize one live translation acceptance test with the configured Free Tier key and `gemini-3.5-flash-lite`. Do not submit another Job if this attempt fails; do not use Whisper or alter other Projects.
- **Affected areas:** `TASKS.md` and append-only verification logs; no application implementation or schema changes in this close-out.
- **Verification:** The actual FastAPI endpoint accepted Job `856d5093-88bc-4050-bbbb-37588bba1017` with HTTP 202. The separate worker completed `translate_existing` as `succeeded` / `translation_ready`; logs show one full-transcript request, one provider attempt, and 11 target Segments. A fresh SQLAlchemy engine/session confirmed all 11 translations are nonempty and mapped to the original IDs, while Segment IDs, ordering, timestamps, source text, and revisions remained unchanged. Other Projects' Segment data and Job counts were unchanged. The earlier stale-worker Job remained terminal; no Whisper ran. The worker started for this verification was stopped after completion.
- **Result/limits:** GEMINI-FIX acceptance passed with the configured model and no fallback. Translation structure and ID mapping were verified; no separate linguistic quality review was performed. RESULT-01 and FLOW-01 remain pending.
- **Commit/issue:** None recorded by the AI assistant.

## `RESULT-01` — Render Artifact ownership and revision validation

- **AI assistance:** Traced the existing render metadata, preview, and download routes through their shared current-Artifact resolver. Added explicit Project ownership, Artifact revision, Job ownership, Job input revision, succeeded status, and `render_complete` stage checks. Added integration coverage asserting all result routes reject invalid provenance.
- **Developer decision:** Preserve the existing media generation pipeline and API URLs. Keep stale/missing results as safe 404 responses. Limit changes to read-time Artifact/Job provenance validation; do not modify TTS, timeline, audio mixing, render generation, media storage, or database schema.
- **Affected areas:** Render Artifact validation, focused API integration tests, architecture/task documentation, and append-only logs.
- **Verification:** `test_video_render.py` passed all 21 tests using synthetic local media and SQLite, including valid Range preview/download, stale source rejection, and mismatched Project/revision/Job cases. Backend `compileall`, `pip check`, and `git diff --check` passed. No frontend build was needed because the UI and API contract did not change.
- **Result/limits:** RESULT-01 is complete. Existing `demo2` render browser acceptance remains the recorded real media evidence; this task did not rerun it or modify any Project. FLOW-01 is ready to begin with a permitted Project/media selection and fresh runtime-state check; it remains incomplete until the complete real integration flow is exercised.
- **Commit/issue:** None recorded by the AI assistant.

## `FLOW-01` — End-to-end integration acceptance investigation

- **AI assistance:** Traced upload, worker dispatch, API lifecycle, media storage, timeline, and render Artifact flows. Inspected persisted Project/Job/Segment/Artifact data through SQLAlchemy and the real FastAPI read endpoints without changing Project data. Ran the full offline backend test suite.
- **Developer decision:** Do not rerun Whisper, Gemini, Edge-TTS, or rendering without explicit live-run approval. Do not alter user-edited Segments, current Artifacts, or stale-result validation.
- **Affected areas:** `TASKS.md` and append-only audit logs only; no implementation or architecture changes were made.
- **Verification:** All 134 backend unit/integration tests passed; `compileall`, `pip check`, and `git diff --check` passed. Read-only checks on `demo2` found a valid stored source video, 11 current translated Segments, 11 current TTS Artifacts, and a successful historical render Job/MP4 (H.264/AAC, 23,681 ms; sidecar and digest matched). The live API served source/Segment/TTS data but returned 404 for rendered metadata/preview/download because the latest same-revision translation Job failed safely due to existing transcript edits; the timeline API reports `project_translation_not_ready`.
- **Result/limits:** FLOW-01 remains partial. The previously rendered file exists and is internally verified, but current result delivery correctly withholds it under the present Job/readiness state. A fresh complete run requires permitted media and approval for real faster-whisper, Gemini, and Edge-TTS calls plus persisted verification records.
- **Commit/issue:** None recorded by the AI assistant.

## `FLOW-01` — Authorized live pipeline attempt

- **AI assistance:** With explicit user authorization, copied the permitted `demo2` source video through the real FastAPI upload endpoint into a new verification Project, started the repository worker separately, and monitored the existing ASR/translation, TTS, timeline, and optimization workflows through persisted Job state and SQLAlchemy/API reads.
- **Developer decision:** Do not alter `demo2` or other existing Projects. Permit one fresh live run using faster-whisper, the configured Gemini model, and Edge-TTS; do not submit another Job after the optimization failure and do not bypass timeline blockers.
- **Affected areas:** `TASKS.md` and append-only logs only; no application implementation, schema, TTS/timeline/render module, or existing Project was changed.
- **Verification:** Real upload returned HTTP 201. The separate worker completed the combined ASR/Gemini Job as `succeeded`/`translation_ready` with 11 valid persisted Segments; logs show one full-transcript Gemini request on `gemini-3.5-flash-lite`, one attempt, no retry. The real TTS Job completed `succeeded`/`tts_ready` with 11 current Artifacts. The authoritative timeline returned 6 stretch operations and 2 over-cap blockers (234 ms and 118 ms). One existing bounded optimization Job failed with the safe error `Vietnamese voice generation failed for a Segment.` Pre/post snapshots confirmed the failure preserved all 11 current Artifacts and Segment translation/timestamp data. Other Projects' Segment/Job counts were unchanged. No render Job or final video was produced. The complete 134-test backend suite, `compileall`, `pip check`, and `git diff --check` passed.
- **Result/limits:** FLOW-01 remains partial because optimization failed and the planner still blocks rendering. No additional live requests were made after that failure.
- **Commit/issue:** None recorded by the AI assistant.

## `FLOW-01` — Optimization failure diagnosis and safe logging

- **AI assistance:** Inspected the failed persisted optimization Job, current Project timeline, Segment-to-Artifact mapping, source files, worker code, and Edge-TTS retry/error handling. Added local diagnostic logging limited to exception class and integer HTTP status; provider exception text and payload remain excluded.
- **Developer decision:** Preserve all current translations and TTS Artifacts, do not rerun Whisper/Gemini, and do not bypass the planner's 1.4× cap. Do not make another Edge-TTS request without a separate explicit approval.
- **Affected areas:** `backend/app/services/tts.py`, focused TTS logging regression test, `TASKS.md`, and append-only logs.
- **Verification:** SQLAlchemy read-only inspection confirmed the failed Job has only the generic safe error, current normalized Artifacts exist for all 11 Segments, and current blockers map to Segment positions 4 and 9 (234 ms and 118 ms excess). No corresponding worker log file or traceback was available. The focused 11-test TTS suite and complete 135-test backend suite passed; `compileall`, `pip check`, and `git diff --check` passed. No provider calls or Project/media mutations were performed.
- **Result/limits:** The exact provider failure remains unknown because the original exception details were neither persisted nor locally logged. A single bounded optimization Job would target only the two blocker translations at rates 22% and 35%; the current code can make at most 12 Edge-TTS requests across the 4 possible syntheses and 3-attempt retry limit. It requires explicit approval. FLOW-01 remains partial; no render Job or MP4 exists for this verification Project.
- **Commit/issue:** None recorded by the AI assistant.

## `FLOW-01` — Authorized optimization attempt and stop condition

- **AI assistance:** Started the current `backend/.venv` worker as a separate process, verified it acquired the PostgreSQL worker advisory lock, submitted the approved optimization Job for the verification Project, monitored its persisted state and local worker logs, then stopped that worker after failure.
- **Developer decision:** One bounded Edge-TTS optimization Job was approved for positions 4 and 9 only (rates 22% and 35%, existing maximum three attempts per synthesis). No Gemini/Whisper calls, further retry Job, translation/timestamp edits, or render bypass were allowed.
- **Affected areas:** `backend/app/services/tts.py`, its safe logging regression test, FLOW-01 task and append-only logs. No schema or unrelated Project was changed.
- **Verification:** API returned HTTP 202 for Job `3b4f7433-e836-4997-806f-1fcb78de299f`. Worker log reported `NoAudioReceived` with no HTTP status; the Edge-TTS package raises this when a stream ends without audio data. The log lacked Segment identity, so the affected one of positions 4/9 cannot be known. Fresh SQLAlchemy verification showed all 11 prior TTS Artifacts remained current, no active Job, unchanged revision, and the same two planner blockers; rendered-video metadata/preview/download all returned 404. No MP4 was generated. The 135-test backend suite, `compileall`, `pip check`, and `git diff --check` passed.
- **Result/limits:** Stop condition was honored; no further live request was made. The observation confirms an empty Edge-TTS audio stream but does not establish whether the cause was provider-side, request-specific, or transient. FLOW-01 remains partial.
- **Commit/issue:** None recorded by the AI assistant.

## `FLOW-01` — Bounded Edge-TTS recovery and deterministic optimization

- **AI assistance:** Classified `NoAudioReceived` as an empty-stream transient exception and added it to the existing three-attempt backoff. Serialized optimization operations, tracked synthesis operations separately from provider request attempts, enforced a finite request ceiling from eligible Segments/rate tiers/retry cap, and added safe per-attempt attribution with candidate Artifact IDs that are reused for transactional publication.
- **Developer decision:** Keep permanent 4xx/configuration failures non-retryable, preserve current Artifacts until all candidates and snapshots validate, do not alter timeline limits, and make no live Edge-TTS/Gemini/Whisper call without separate approval.
- **Affected areas:** TTS synthesis/retry service, TTS optimization service, focused unit tests, architecture/task notes, and append-only logs. No schema change.
- **Verification:** Focused TTS and optimization tests passed; complete backend suite passed (138 tests). Tests cover NoAudioReceived retry then success, three-attempt exhaustion, non-retryable 403/permanent errors, sequential two-Segment rate steps, 4-operation/12-request budget enforcement, Artifact ID attribution, old-Artifact preservation on failure, and stale-input rejection. `compileall`, `pip check`, and `git diff --check` passed. No provider calls or persisted Project changes were made.
- **Result/limits:** Offline behavior is verified. FLOW-01 remains partial until the user approves one bounded live continuation on the existing verification Project and an actual render passes timeline, FFprobe, and API preview/range/download checks.
- **Commit/issue:** None recorded by the AI assistant.

## `TTS-INCREMENTAL-01` — Safe incremental TTS regeneration

- **AI assistance:** Added a shared strict current-Artifact validator and applied it to TTS selection, timeline planning and audio API validity. Implemented selective synthesis, exact preservation of reusable/optimized Artifacts, final snapshot and producer/file revalidation, atomic replacement publication and zero-change success without output files. Updated frontend messages and focused offline regression tests.
- **Developer decision:** Keep the existing Project enqueue contract, revision requirements, configured voice, rate policy for changed text and render safety. Preserve all unrelated working-tree changes. No live providers, real Jobs, Project data changes, dependencies or schema changes were authorized or performed.
- **Affected areas:** TTS Artifact validation/generation, timeline and Project audio reads, frontend messages, targeted tests, architecture/task notes and append-only logs.
- **Verification:** Passed 86 TTS/timeline tests, 10 Project API tests and 21 render regression tests (117 relevant offline tests total); frontend build/typecheck, Python compile checks and `git diff --check` passed. A 272-Segment SQLite fixture with fake synthesis proves one edited translation generates one replacement while 271 Artifact IDs, paths, metadata, files, producer Jobs and optimized rates remain unchanged. Tests cover three edits, zero edits, +35% reuse, invalid/ambiguous inputs, mixed producers, revision safety, reuse revalidation, concurrent changes and database rollback.
- **Result/limits:** COMPLETE against the requested offline definition of done. No real browser acceptance, provider recovery, PostgreSQL concurrency experiment or latency improvement is claimed. Existing legacy sidecar compatibility is retained; unassignable current Artifact associations fail safely. FLOW-01 remains partial.
- **Commit/issue:** None recorded by the AI assistant.

## `TIMELINE-UX-01` — Preserve last-known timeline blockers during edits

- **AI assistance:** Traced timeline state through translation saves, analysis requests, and TTS/optimization/normalization Job completion. Updated the viewer to retain the last successful plan as a stale reference, validate successful replacement responses, preserve results/errors across reanalysis attempts, and navigate blockers by stable Segment ID with scroll, editor focus, and video seeking without autoplay. Updated architecture/task notes and append-only logs.
- **Developer decision:** Keep timeline analysis in viewer memory only, make reanalysis explicit after audio changes, prevent stale results from enabling frontend optimization/render actions, and leave backend Artifact/render checks unchanged. No provider calls, real Jobs, media rendering, Project data changes, schema changes, or dependencies were authorized or performed.
- **Affected areas:** `frontend/src/App.tsx`, timeline/Project API/render regression verification, `docs/ARCHITECTURE.md`, `TASKS.md`, `docs/CHANGELOG.md`, `docs/AI_USAGE.md`.
- **Verification:** `test_tts_timeline.py` (12 tests), `test_project_viewer_api.py` (10 tests), and `test_video_render.py` (21 tests) passed. `npm run build` passed, including TypeScript; `git diff --check` passed. The repository has no frontend component-test runner, so UI interactions were not browser-tested.
- **Result/limits:** Offline implementation and checks are complete, but TIMELINE-UX-01 remains partial pending browser acceptance of edit retention, blocker navigation, and successful/failed reanalysis. Last-known analysis survives edits and Jobs only while the same Project Viewer remains open; Project navigation and browser refresh clear it. Existing backend planner and Artifact validation remain authoritative for optimization/render.
- **Commit/issue:** None recorded by the AI assistant.

## `AV-SYNC-03` — Execute joint timeline plans in FFmpeg

- **AI assistance:** Extended the existing renderer to load and validate the latest successful current-revision `av-sync-v1` plan, execute its exact interval speeds and selected TTS Artifact mapping, and verify decoded source/output frame coverage and 48 kHz sample timing before atomic publication. Added a strict `timeline-render-v3` sidecar for joint plans and synthetic FFmpeg/SQLite regression coverage. Updated the AV-SYNC-02 source probe to base plan duration on decoded frame coverage and reserve a margin for two output frames at the 0.5× speed limit plus one sample.
- **Developer decision:** Keep the legacy renderer compatible; reject stale/unsupported joint plans, blockers, invalid partitions, and negative slack. Do not use real Projects/providers or apply the PostgreSQL migration; keep broader FLOW-01 separate.
- **Affected areas:** `backend/app/services/video_render.py`, `backend/app/services/av_sync_optimization.py`, focused render/optimization tests, `TASKS.md`, `docs/ARCHITECTURE.md`, and append-only logs.
- **Verification:** 59 focused renderer, joint-planner, optimizer, legacy timeline, and audio-mixing tests passed. Synthetic FFmpeg executed 0.7×, 0.5×, and 1.0× plans, preserved decoded source-frame count, verified sample-aligned dub placement and strict frame/sample coverage, and exercised joint Job render publication/current-result retrieval. Python `compileall`, `pip check`, and `git diff --check` passed. No live providers, real Project, Supabase connection, or migration application was used.
- **Result/limits:** COMPLETE for offline AV-SYNC-03 acceptance. No real application Project was rendered. The migration `backend/migrations/20261026_av_sync_02_joint_plan.sql` remains unapplied and PostgreSQL deployment validation remains outstanding under AV-SYNC-02.
- **Commit/issue:** None recorded by the AI assistant.

## `AV-SYNC-03` — Progress tracking consistency check

- **AI assistance:** Reconciled the task status, changelog, architecture notes, and AI usage record with the implemented AV-SYNC-03 evidence; clarified that PostgreSQL migration validation is a deployment prerequisite and FLOW-01 remains separate.
- **Developer decision:** Preserve prior changelog history, keep AV-SYNC-03 complete for its offline acceptance, and leave AV-SYNC-02/FLOW-01 limitations explicit. No implementation or migration changes were made in this documentation check.
- **Affected areas:** `TASKS.md`, `docs/CHANGELOG.md`, and `docs/AI_USAGE.md`; architecture was reviewed and already reflected the renderer contract.
- **Verification:** Confirmed the AV-SYNC-03 task entry is checked, the exact dated changelog heading exists, and the prior implementation record reports 59 passing focused tests plus `compileall`, `pip check`, and `git diff --check`. Tests were not rerun in this documentation-only pass; `git diff --check` was rerun.
- **Result/limits:** Tracking is consistent. Real Project rendering and PostgreSQL migration validation remain unverified; AV-SYNC-02 remains partial and FLOW-01 is unchanged.
- **Commit/issue:** None recorded by the AI assistant.

## `AV-SYNC-02` — Joint TTS/video planning foundation

- **AI assistance:** Implemented a deterministic joint timeline solver, typed `av-sync-v1` plan and Job result, conservative microsecond duration helper, project-scoped enqueue/result routes, sequential bounded TTS candidate synthesis, selected Artifact staging/transactional publication with snapshot revalidation, additive PostgreSQL migration, and focused offline planner/service tests. Added documentation describing the renderer compatibility gate and remaining verification limits.
- **Developer decision:** Keep all provider calls and real Project changes out of scope; do not begin AV-SYNC-03. The new contract must never advertise a mathematically feasible plan as renderable while the active renderer supports only its existing plan.
- **Affected areas:** Job/Artifact metadata, timeline schemas/services, Project API, worker dispatch, migration, tests and task/architecture logs.
- **Verification:** `test_joint_timeline.py` (8), `test_av_sync_optimization.py` (4), `test_audio_normalization.py` (10), `test_project_viewer_api.py` (11), `test_video_render.py` (22), `test_tts_incremental.py` (25), and `test_tts_pipeline.py` (5) passed. Python `compileall` and `pip check` passed. No live providers, Project/media mutation, migration application or full render was performed.
- **Result/limits:** PARTIAL. Candidate synthesis and selected Artifact publication have deterministic mocked tests, but real PostgreSQL migration/locking and FFprobe frame/sample coverage are unverified; the new joint contract is never renderable until AV-SYNC-03 implements its renderer support.
- **Commit/issue:** None recorded by the AI assistant.

## `AV-SYNC-03` — Final progress record

- **AI assistance:** Appended the final tracking reconciliation after the older AV-SYNC-02 history entry, preserving existing log text and clarifying the current AV-SYNC-03 completion state and PostgreSQL deployment prerequisite.
- **Developer decision:** AV-SYNC-03 is complete for offline acceptance; AV-SYNC-02 and FLOW-01 remain partial as recorded in `TASKS.md`. Do not start another task or apply the migration as part of this documentation check.
- **Affected areas:** `docs/CHANGELOG.md`, `docs/AI_USAGE.md`, and the current-task pointer in `TASKS.md`. `docs/ARCHITECTURE.md` already describes the renderer/migration state and was not changed in this follow-up.
- **Verification:** Confirmed the final dated changelog heading is at end of file, AV-SYNC-03 is checked in `TASKS.md`, AV-SYNC-02 is still partial, and the next prerequisite is stated. `git diff --check` passed; implementation tests were not rerun in this documentation-only follow-up.
- **Result/limits:** Progress tracking is consistent. The recorded 59-test offline result remains the implementation evidence; real Project and PostgreSQL/Supabase verification are outstanding.
- **Commit/issue:** None recorded by the AI assistant.

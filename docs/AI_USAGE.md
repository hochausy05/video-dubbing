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

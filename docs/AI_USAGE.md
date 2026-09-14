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

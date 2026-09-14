# AutoDub Tasks

## Status convention

- `[ ]` planned or not yet verified; `[x]` complete with evidence.
- `Current Task` is the only authoritative pointer to active work.
- A phase may span multiple weeks. See `PLAN.md` for phase exit gates.
- Task criteria describe the minimum evidence; details belong in code/tests or the routed design document.

## Current Task

- **Phase:** 3 — Supabase PostgreSQL, projects, and upload
- **Task:** `DATA-01`
- **Next after verified completion:** See the Phase 3 task list.
- **Scope:** See the `DATA-01` task entry below.

## Phase 1 — Documents and environment

- [x] `INIT-01` — Create project overview, plan, rules, backlog, and planned architecture. Evidence: files, internal links, and implementation status checked.
- [x] `INIT-02` — Add placeholder repository structure and `.gitignore`. Evidence: expected paths exist; no runtime data or application implementation claimed.
- [x] `INIT-03` — Confirm the MVP scope, flow, architecture, exclusions, and phase order. Evidence: authoritative documents are consistent.
- [x] `INIT-04` — Review the development/demo machine and worker environment. Evidence: verified facts and unverified GPU/Whisper status recorded in `docs/ENVIRONMENT.md`.
- [x] `ENV-00` — Ensure sufficient project-drive space. Evidence: project moved to drive D with about 27 GB free; continue monitoring the 10 GB reserve target.
- [ ] `GIT-01` — Initialize/configure the repository remote and make the first real push. Complete only with the correct remote and an actual GitHub commit; run only when requested.

## Phase 2 — FastAPI and React foundations

- [x] `ENV-01` — Bootstrap minimal FastAPI. Complete when a local health endpoint works and a test or reproducible check passes.
- [x] `ENV-02` — Bootstrap React, TypeScript, and Vite. Complete when the welcome page runs and the production build passes.
- [x] `ENV-03` — Pin dependencies and add secret-free example configuration. Complete when tested setup instructions are documented.

## Phase 3 — Supabase PostgreSQL, projects, and upload

- [x] `DATA-01` — Implement `Project`, `Job`, `Segment`, and `Artifact` metadata persistence in Supabase-hosted PostgreSQL through FastAPI, using SQLAlchemy and a PostgreSQL driver. Configure the connection only through uncommitted `DATABASE_URL`; use UUID identifiers and timezone-aware timestamps where appropriate. Verified table initialization, connected-record persistence after a new engine/session, foreign-key relationships, constraints, and cleanup through the application connection.
- [ ] `UPLOAD-01` — Store uploaded video under server-generated IDs. Verify valid upload and hostile/unusual filenames cannot control storage paths.
- [ ] `UPLOAD-02` — Validate actual format, configured size, and duration. Verify corrupt, unsupported, and over-limit input is rejected clearly.
- [ ] `UI-01` — Connect project list/create/upload UI to the API. Verify projects persist across browser refresh.

## Phase 4 — Jobs and Python worker

- [ ] `JOB-01` — Add a separate sequential Python worker. Verify the API persists/returns a job ID and the worker claims one queued job at a time.
- [ ] `JOB-02` — Persist job state, stage, errors, and interrupted-job policy. Verify refresh/restart does not silently lose or strand work.
- [ ] `UI-02` — Display backend job state/stage. Verify the UI does not invent progress percentages.

## Phase 5 — Whisper transcript

- [ ] `ASR-01` — Transcribe a short permitted sample with timestamps. Verify text/timestamps and correct handling of no-speech input.

## Phase 6 — Gemini and translation review

- [ ] `TRANS-01` — Translate each segment to Vietnamese with Gemini while preserving segment ID and source text. Reject incomplete/invalid provider structure.
- [ ] `TRANS-02` — Add classified translation/quota failures and bounded retry. Mark simulated-provider tests explicitly as mocks.
- [ ] `EDIT-01` — Show video and source/translated segment table. Verify rows match stable segment IDs.
- [ ] `EDIT-02` — Edit, persist, and confirm a translation revision. Verify content survives refresh.
- [ ] `EDIT-03` — Validate translation before TTS. Flag empty/error segments and invalidate artifacts from older revisions.

## Phase 7 — Edge-TTS and FFmpeg output

- [ ] `TTS-01` — Select a verified Vietnamese voice and generate valid per-segment audio without content loss.
- [ ] `TTS-02` — Report TTS failure and support controlled retry; never substitute silent audio as success.
- [ ] `RENDER-01` — Render dubbed MP4 and SRT with FFmpeg. Watch/listen to output and inspect timing, including overlong speech.
- [ ] `RESULT-01` — Preview/download artifacts for the correct project and confirmed revision.
- [ ] `FLOW-01` — Run the complete flow with permitted media and real integration evidence; mocks alone are insufficient.

## Phase 8 — QA, polish, and final report

- [ ] `QA-01` — Add unit/integration coverage for validation, state, segments, and provider failures.
- [ ] `QA-02` — Test missing audio/speech, corrupt input, exhausted quota, TTS failure, and FFmpeg failure.
- [ ] `QA-03` — Measure each stage on the selected demo machine/input and record limits without extrapolation.
- [ ] `QA-04` — Verify Git excludes secrets/runtime data and cleanup cannot escape the intended job path.
- [ ] `DOC-01` — Update verified setup, screenshots, demo evidence, and limitations to match the application.
- [ ] `DEMO-01` — Prepare and rerun the presentation scenario on the selected environment.

## Recurring weekly work

- [ ] Create/update the task issue.
- [ ] Commit and push at least one verified, meaningful increment.
- [ ] Review the diff and run relevant checks before commit.
- [ ] Append required AI-use and task-change records.
- [ ] Create a report from `docs/weekly/TEMPLATE.md` without modifying the template into a specific week's report.

## Unscheduled backlog outside the MVP

- [ ] Authentication, authorization, and multiple users.
- [ ] Payments.
- [ ] Social-link download or automatic posting.
- [ ] Voice cloning, lip sync, subtitle OCR, or advanced voice/music separation.
- [ ] Batch/concurrent processing, advanced timeline editing, or public Internet deployment.

Do not implement backlog items without explicit approval.

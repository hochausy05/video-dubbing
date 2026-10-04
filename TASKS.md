# AutoDub Tasks

## Status convention

- `[ ]` planned or not yet verified; `[x]` complete with evidence.
- `Current Task` is the only authoritative pointer to active work.
- A phase may span multiple weeks. See `PLAN.md` for phase exit gates.
- Task criteria describe the minimum evidence; details belong in code/tests or the routed design document.

## Current Task

- **Phase:** 4 — Jobs and Python worker
- **Task:** `UI-02`
- **Next after verified completion:** `ASR-01`.
- **Scope:** See the `UI-02` task entry below.

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
- [x] `UPLOAD-01` — Store uploaded video under server-generated IDs. Verified real multipart uploads persist Project metadata in Supabase and use only deterministic relative paths under local server-managed storage; hostile filenames cannot control destination paths.
- [x] `UPLOAD-02` — Validate actual format, configured size, and duration. Verify corrupt, unsupported, and over-limit input is rejected clearly.
- [x] `UI-01` — Connect project list/create/upload UI to the API. Verify projects persist across browser refresh. Evidence: manual browser verification confirmed native MP4 selection, successful React upload, safe form reset, immediate project-list refresh, and persistence after browser refresh.

## Phase 4 — Jobs and Python worker

- [x] `JOB-01` — Add a separate sequential Python worker. Evidence: SQLAlchemy connected to the active Supabase project; FastAPI returned a real Job ID and `queued` within 2.5 seconds; a separate worker process claimed that Job as `running`/`claimed`, while a second persisted Job stayed `queued`; new SQLAlchemy engine/session and Supabase MCP confirmed both records; verification Project/Jobs were removed; compileall, pip check, and repository checks passed. Claimed Jobs remain `running` until a real pipeline is implemented.
- [x] `JOB-02` — Persist job state, stage, errors, and interrupted-job policy. Evidence: on Supabase, API GET returned persisted queue/claim/interruption/failure fields; killing a claimed worker then starting a fresh process changed the abandoned Job to `interrupted` with stage, safe reason and completion time; retry created a distinct queued Job and left the original unchanged; retries of queued and running Jobs returned 409; bounded failure transition persisted a path-redacted error; another Job stayed queued until only one running slot was free; fresh SQLAlchemy sessions confirmed timezone-aware lifecycle timestamps; verification Project/Jobs were removed; compileall, pip check and repository checks passed. Jobs are not completed without a real handler.
- [x] `UI-02` — Display backend job state/stage. Evidence: on Supabase, the UI enqueued a real Job while the worker was stopped and displayed `queued`/`queued`; browser refresh recovered the same persisted Job; a separate Python worker changed it to `running`/`claimed`; worker restart changed it to `interrupted` with the persisted safe reason, which the UI displayed. Developer manually confirmed this browser flow and the absence of fabricated percentage progress. Verification Project/Jobs were removed; frontend build, backend compileall/pip check, `git diff --check`, and secret/ignore checks passed. No direct frontend Supabase access was found.

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

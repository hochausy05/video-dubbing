# AutoDub Tasks

## Status convention

- `[ ]` planned or not yet verified; `[x]` complete with evidence.
- `Current Task` is the only authoritative pointer to active work.
- A phase may span multiple weeks. See `PLAN.md` for phase exit gates.
- Task criteria describe the minimum evidence; details belong in code/tests or the routed design document.

## Current Task

- **Phase:** 7 — Edge-TTS and FFmpeg output
- **Task:** `RENDER-01`
- **Next after verified completion:** `RESULT-01`.
- **Scope:** See the `RENDER-01` task entry below.

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

- [x] `ASR-01` — Transcribe a short permitted sample with timestamps. Evidence: faster-whisper `small` ran through the separate worker against real uploaded speech and no-speech MP4s; timestamped Segments persisted to Supabase through SQLAlchemy and were confirmed from a fresh session. The speech transcript remained a single row after a safe rerun; no-speech persisted zero rows. CUDA inference was attempted but failed because CTranslate2 could not load `cublas64_12.dll`; real CPU `int8` inference succeeded. Combined Jobs remain `running` after ASR because translation is not implemented.

## Phase 6 — Gemini and translation review

- [x] `TRANS-01` — Translate each segment to Vietnamese with Gemini while preserving segment ID and source text. Evidence: the real FastAPI/worker flow sent four ASR Segments in one structured Gemini request; every Vietnamese result persisted to Supabase, and a pre-translation snapshot matched afterward for Segment IDs, source text, timestamps, and order. FastAPI returned `succeeded`/`translation_ready`; fresh SQLAlchemy and independent Supabase MCP queries confirmed persistence. No-speech completed `succeeded`/`no_speech` with zero Segments and no Gemini call. Nine unit tests reject missing, duplicate, unknown, malformed, and empty results, confirm an invalid later batch leaves all Segment data unchanged, and protect existing translations. JOB-02 failure and interruption transitions were also verified; task verification data was removed.
- [x] `TRANS-02` — Add classified translation/quota failures and bounded retry. Mark simulated-provider tests explicitly as mocks. Evidence: deterministic mock-provider tests confirm HTTP 429/quota and authentication/configuration errors fail without retry; transient network errors and malformed structured results retry the same batch at most once; repeated transient and malformed responses fail without changing persisted Segment data or falling back to source text. Backoff is bounded to 0.5 seconds and tests replace it with a mock. `compileall`, `pip check`, all 14 unit tests, `git diff --check`, and secret/runtime/ignore checks passed. No real Gemini request or schema change was used.
- [x] `EDIT-01` — Show video and source/translated segment table. Verify rows match stable segment IDs. Evidence: developer manually confirmed the original video plays, Chinese source and Vietnamese translation display, timestamp selection seeks accurately, active Segment highlighting follows playback, timestamps align, and a browser refresh preserves transcript and translation data.
- [x] `EDIT-02` — Edit, persist, and confirm a translation revision. Verify content survives refresh. Evidence: on a real Project, the user manually confirmed editing/saving Vietnamese translations, persistence after F5, Cancel discarding unsaved edits, rejection of empty/whitespace-only translations, and continued video playback, click-to-seek, timestamp display, and automatic Segment highlighting. Backend API validation and persistence are covered by 22 passing unit tests; frontend production build, compileall, pip check, and diff checks passed. The backend-disconnection/save-failure scenario was not manually tested.
- [x] `EDIT-03` — Validate translation before TTS. Evidence: on the real `demo2` Project, the user verified readiness succeeds with 11 Segments, 0 blocking errors, and 0 warnings; saving a Vietnamese translation invalidates the previous result and revalidation returns updated results; video preview and transcript functionality remain operational. 33 backend unit tests, frontend build, compileall, and pip check passed in the prior automated verification. Error/warning scenarios and issue navigation were covered by automated tests but were not manually checked in the browser.

## Phase 7 — Edge-TTS and FFmpeg output

- [x] `TTS-01` — Select a verified Vietnamese voice and generate valid per-segment audio without content loss. Evidence: on the real `demo2` Project, the user confirmed the TTS Job reached `succeeded`/`tts_ready`, readiness reported 11 Segments with 0 errors and 0 warnings, per-Segment Vietnamese audio played without truncation, adaptive `+20%` rate and measured durations displayed, results persisted after F5, and source timestamps/translations remained unchanged. Segment-level speech generation is complete; synchronization and video time-stretching remain future work.
- [x] `TTS-02` — Analyze measured TTS durations and plan a deterministic output timeline with dynamic video stretch operations capped at 1.4×. Evidence: on the real `demo2` Project, the user confirmed the UI reports 21,339 ms source duration, 25,211 ms planned duration, 3,872 ms added duration, and 9 of 11 Segments requiring stretch; it displays 8 blocking timing conflicts and their Segment navigation, with consistent results after refresh. These are valid analysis findings; the plan is not renderable until conflicts are resolved. Source timestamps remain unchanged. Executing dynamic stretch, mixing, subtitle synchronization, and final rendering remain future work.
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

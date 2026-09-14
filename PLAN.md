# AutoDub Development Plan

## Purpose

This file defines phase order and exit gates. It does not track completion; use `TASKS.md` for status.

## Delivery principles

- Build and verify the MVP incrementally throughout the semester.
- Each task must produce a small, inspectable outcome before later work begins.
- Each week should contain real, meaningful GitHub progress; never fabricate commits, tests, measurements, or dates.
- A phase may take one or several weeks.
- Expand scope only after the local single-user MVP flow has verified evidence.

## Phases

| Phase | Focus | Exit evidence |
| --- | --- | --- |
| 1 | Documents and environment | Consistent scope/architecture plus recorded machine and tooling checks |
| 2 | FastAPI and React foundations | Local API health check and a buildable basic UI |
| 3 | Supabase PostgreSQL, projects, and upload | Persistent metadata in Supabase PostgreSQL plus safe validation/storage of accepted videos |
| 4 | Jobs and worker | API returns a job ID; a separate worker processes one queued job; status survives reload/restart policy |
| 5 | Whisper transcript | A permitted sample produces valid segments and timestamps |
| 6 | Gemini and translation review | Segment translation is editable, persisted, revisioned, and confirmable |
| 7 | Edge-TTS and FFmpeg output | Confirmed revision produces valid audio, MP4, and SRT artifacts |
| 8 | QA, UI polish, and final report | End-to-end evidence, measured limits, reproducible setup, demo materials |

## Transition rules

1. Do not treat documentation or mocks as proof that a runtime integration works.
2. Do not start a dependent task until the required predecessor evidence exists.
3. For AI/video phases, use permitted test media and record the real environment and result.
4. Document known limitations instead of hiding them or silently substituting invalid output.

## Weekly evidence

- Create or update an issue using the task ID when work starts.
- Commit coherent changes and push actual progress during the week.
- Record checks, results, limitations, and links in a weekly report based on `docs/weekly/TEMPLATE.md`.
- Keep weekly reporting separate from task status and the append-only task changelog.

## Risk controls

| Risk | Control |
| --- | --- |
| GPU is unavailable or incompatible | Test short CPU input; benchmark before optimizing; never claim GPU support without evidence |
| Worker/runtime mismatch | Verify the selected Windows environment before adding queue complexity |
| Provider quota or network failure | Bounded retry, classified errors, clear user feedback |
| Missing or incorrect translation | Preserve source text; allow segment review and confirmation |
| Speech exceeds segment duration | Measure and warn; never truncate a sentence silently |
| Large media exhausts disk/RAM | Enforce input limits, run one worker, isolate project/job files, monitor free space |
| Scope expansion | Complete the MVP first; keep excluded features in backlog |

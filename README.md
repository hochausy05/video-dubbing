# AutoDub

AutoDub is a local-first web application that translates spoken video content into Vietnamese, lets the user review the translation, generates Vietnamese speech, and exports a dubbed video with subtitles.

> Course Project 4. The project is developed incrementally, with verified progress recorded by task and on GitHub.

## Current snapshot

- Current task: `ENV-01` — bootstrap a minimal FastAPI backend.
- Completed foundations: project documents, repository placeholders, MVP scope, machine review, and disk-space check.
- Runtime features are planned unless `TASKS.md` marks them complete with evidence.
- The project is on drive D with about 27 GB free; keep roughly 10 GB free during development.

`TASKS.md` is the only source of truth for task status.

## MVP

One local user processes one video at a time:

1. Create a project and upload a validated MP4.
2. Transcribe speech with Whisper and keep segment timestamps.
3. Translate segments to Vietnamese with Gemini.
4. Review, edit, and confirm a translation revision.
5. Generate Vietnamese speech with Edge-TTS.
6. Render MP4 and SRT output with FFmpeg.
7. Preview and download the current artifacts.

Detailed behavior and acceptance criteria live in `docs/PRD.md`.

## Planned stack

| Area | Choice |
| --- | --- |
| Frontend | React, TypeScript, Vite |
| API | Python 3.11, FastAPI |
| Background processing | Separate Python worker; one job at a time |
| Persistence | SQLite plus backend-managed local storage |
| Speech recognition | faster-whisper, starting with model `small` |
| Translation | Gemini through the Google Gen AI SDK |
| Speech generation | Edge-TTS, subject to integration testing |
| Video processing | FFmpeg and ffprobe |

Versions and commands are added only after they are tested. Redis/RQ is not required for the MVP.

## Repository map

| Path | Responsibility |
| --- | --- |
| `frontend/src/pages/` | Application pages |
| `frontend/src/components/` | Reusable UI components |
| `frontend/src/services/` | Browser-to-API calls |
| `backend/app/api/` | HTTP request/response boundary |
| `backend/app/core/` | Configuration, logging, shared utilities |
| `backend/app/models/` | Persistence models |
| `backend/app/schemas/` | Request/response contracts |
| `backend/app/services/` | Domain and AI/video operations |
| `backend/app/workers/` | Background job execution |
| `tests/` | Unit, integration, and end-to-end tests |
| `storage/` | Ignored runtime data |
| `docs/` | Product, architecture, environment, and audit records |

Placeholder directories may contain `.gitkeep`; their presence does not mean a feature is implemented.

## Documentation map

| File | Authoritative for |
| --- | --- |
| `TASKS.md` | Current task, completion state, task acceptance |
| `PLAN.md` | Phase order and phase exit gates |
| `RULES.md` | Mandatory engineering and documentation rules |
| `docs/PRD.md` | Product scope, user stories, functional requirements |
| `docs/ARCHITECTURE.md` | Component boundaries, data flow, technical contracts |
| `docs/ENVIRONMENT.md` | Verified local machine and tooling facts |
| `docs/AI_USAGE.md` | AI-assistance audit entries |
| `docs/CHANGELOG.md` | Append-only Vietnamese task change history |
| `AGENTS.md` | Minimal-context instructions for coding agents |

Agents must follow the selective reading protocol in `AGENTS.md`; prompts should not ask them to read all documents.

## Responsible use

- Process only content the user owns or is permitted to use.
- Never commit API keys, private video, runtime databases, generated media, or sensitive logs.
- Inform users when text is sent to an external AI service.
- Treat AI output as reviewable assistance, not guaranteed correctness.

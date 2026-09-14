# AutoDub Agent Guide

## Goal

Work on one requested task at a time while loading the smallest useful project context.

## Context-loading protocol

Do **not** read every Markdown file by default.

1. Read `RULES.md`.
2. In `TASKS.md`, read only `Current Task` and the matching task entry.
3. Inspect the repository paths that the task may change.
4. Use the routing table below to load only relevant document sections.
5. Read additional documents only when a concrete ambiguity cannot be resolved from code, tests, or the routed source of truth.

Use heading search before opening a long document, for example:

```bash
rg -n "^## |^### |TASK-ID|FR-[0-9]+|NFR-[0-9]+|US-[0-9]+" <file>
```

## Document routing

| Task type | Read in addition to `RULES.md` and the task entry |
| --- | --- |
| Project overview or onboarding | Relevant section of `README.md` |
| Roadmap, phase order, or scope scheduling | Relevant phase in `PLAN.md` |
| Product behavior or acceptance | Matching `US`, `FR`, or `NFR` section in `docs/PRD.md` |
| Component boundaries, data flow, API, worker, or storage | Relevant section in `docs/ARCHITECTURE.md` |
| Python, Node, FFmpeg, GPU, disk, or local setup | Relevant section in `docs/ENVIRONMENT.md` |
| AI-use audit | Latest relevant entry in `docs/AI_USAGE.md` |
| Change history | Only the latest relevant entry or `tail -n 40 docs/CHANGELOG.md` |

Examples:

- `ENV-*`: `docs/ENVIRONMENT.md`; architecture only if component boundaries change.
- `DATA-*`, `JOB-*`: data/worker sections of `docs/ARCHITECTURE.md` plus matching PRD requirements.
- `UPLOAD-*`, `ASR-*`, `TRANS-*`, `TTS-*`, `RENDER-*`: matching pipeline section and matching PRD requirements.
- `UI-*`, `EDIT-*`, `RESULT-*`: matching user story plus relevant API boundary.
- `QA-*`: acceptance criteria of the behavior under test; do not load unrelated product sections.
- `DOC-*`, `INIT-*`: only documents explicitly affected by the requested documentation change.

## Execution protocol

- State the task ID, goal, scope, and expected files before editing.
- Preserve unrelated developer changes.
- Do not implement later tasks or speculative abstractions.
- Verify with the smallest relevant reproducible checks.
- Mark a task complete only when its acceptance criteria have real evidence.
- After work, update only the authoritative documents affected by facts that changed.
- Follow the append-only change-log rules in `RULES.md`; never rewrite old entries.
- Record material AI assistance in `docs/AI_USAGE.md` when required.
- Report changed files, checks run, results, and anything not verified.
- Do not commit, push, rewrite Git history, or perform destructive cleanup unless explicitly requested.


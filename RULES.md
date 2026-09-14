# AutoDub Engineering Rules

## 1. Sources of truth

- `TASKS.md`: task status and task-level acceptance.
- `PLAN.md`: phase order and exit gates.
- `docs/PRD.md`: product scope and behavior.
- `docs/ARCHITECTURE.md`: technical boundaries and data flow.
- `docs/ENVIRONMENT.md`: verified machine/tooling facts.
- `docs/CHANGELOG.md`: append-only Vietnamese history of task changes.
- `docs/AI_USAGE.md`: append-only audit of material AI assistance.

Do not duplicate changing facts across files. If a fact belongs to one source of truth, link to it elsewhere.

## 2. Minimal-context workflow

- Follow the routing table in `AGENTS.md`; never read every Markdown file by default.
- Always read this file and only the current task block/matching task line in `TASKS.md`.
- Search headings and requirement/task IDs before opening long sections.
- Load a second document only when the task type requires it or a concrete ambiguity remains.
- Inspect relevant code and tests before assuming a planned document reflects implementation.

## 3. Task scope and completion

- Work only on the requested task ID. Do not implement later tasks or the entire system.
- State the task goal, scope, and expected files before editing.
- Preserve unrelated developer changes and keep each change reviewable.
- Ask before materially changing the stack, MVP scope, or architecture.
- A functional task is complete only when its `TASKS.md` criteria pass with real, reproducible evidence.
- A documentation task requires consistency, path/link, and status checks; it does not require fake runtime tests.
- Record unverified behavior, remaining limits, and failed checks explicitly.
- Never fabricate test output, performance data, deployment URLs, commits, issues, or dates.
- After two ineffective attempts at the same failure, stop, summarize evidence, and propose a different approach.

## 4. Architecture boundaries

- `frontend/` renders UI and calls the API; it must not hold secrets or run Python/FFmpeg directly.
- `backend/app/api/` validates HTTP input and delegates work; it must not keep a request open for the full media pipeline.
- `backend/app/services/` owns domain and AI/video operations without UI dependencies.
- `backend/app/workers/` executes background jobs and persists status; the MVP processes one video job at a time.
- `backend/app/models/` and `backend/app/schemas/` separate persistence models from API contracts.
- `storage/` contains server-managed runtime data. Never accept an arbitrary client filesystem path.
- Do not add microservices, frameworks, queues, or abstractions without a task-backed need.

## 5. Data and pipeline integrity

- Keep stable segment IDs, order, timestamps, source text, and translated text as separate fields.
- Validate non-empty content, timestamp ordering, segment count, and provider response structure.
- Never report success using untranslated fallback text, silent audio, incomplete segments, or stale artifacts.
- Never truncate long TTS text merely to make generation pass; split safely or report the problem.
- Use only a user-confirmed translation revision for TTS/render.
- Editing a translation invalidates audio/video created from an older revision.
- Persist job status and errors; browser memory is not authoritative.
- Bounded retries must distinguish transient, quota, network, and data errors and must not duplicate jobs/artifacts.

## 6. Files, processes, and security

- Generate project/job IDs and isolate their storage directories on the server.
- Validate actual file type, configured size, and duration; do not trust an extension alone.
- Invoke FFmpeg with an argument list, never a shell command built from user input.
- Use timeouts and release files/processes on success and failure paths.
- Never commit `.env`, secrets, virtual environments, downloaded dependencies/models, private media, runtime databases, artifacts, or sensitive logs.
- Never expose API keys or full sensitive content in logs.
- Cleanup must target one validated project/job path; never delete a broad directory.
- Do not expose the local demo publicly without access, quota, and resource controls.
- Inform the user before or when text is sent to an external AI provider.
- Use only media/code/assets that the developer owns or may legally use; preserve required attribution.

## 7. Validation and reporting

- Run the smallest relevant unit, integration, build, lint, or manual check.
- Report exact commands/actions and actual outcomes.
- `git diff --check` is required after text/code changes when Git is available.
- Review the diff before changing task status.
- Do not commit, push, force-push, delete branches, or rewrite history unless explicitly requested.

## 8. Task changelog — mandatory append-only rule

At the end of a task that is completed, paused, or blocked **after repository changes were made**, append one Vietnamese entry to `docs/CHANGELOG.md`.

Mandatory rules:

- Append at the end of the file; keep oldest entries first.
- Never delete, overwrite, reorder, consolidate, or edit an older entry.
- To correct an old entry, append a new correction that references the original task/date.
- Read only the last 40 lines before appending; do not load the full log unless explicitly auditing history.
- Write verified facts only. Do not include prompts, chain-of-thought, secrets, or placeholders.
- Keep the log itself free of templates and instructions; this section is the only writing specification.
- Use Vietnamese even though all other project documents are English.

Append this structure:

```markdown
## YYYY-MM-DD — TASK-ID: Tên nhiệm vụ

- **Trạng thái:** Hoàn thành | Một phần | Bị chặn
- **Thay đổi:** Mô tả ngắn gọn thay đổi thực tế.
- **Tệp:** `path/to/file`, ...
- **Kiểm chứng:** Lệnh/thao tác và kết quả thực tế.
- **Còn lại:** Không | Nội dung chưa hoàn tất hoặc chưa kiểm chứng.
```

If no repository file changed, do not create a changelog entry.

## 9. AI usage log

When AI materially contributes to implementation, design, debugging, or documentation, append a concise English entry to `docs/AI_USAGE.md`. Record the task, assistance, developer decision, changed areas, real verification, result/limits, and commit/issue link when one exists. Never store full conversations or sensitive data.


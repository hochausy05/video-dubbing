import { ChangeEvent, FormEvent, useEffect, useState } from "react";

type JobStatus = "queued" | "running" | "succeeded" | "failed" | "interrupted";

type Project = {
  id: string;
  name: string;
  status: string;
  source_media_reference: string | null;
  created_at: string;
};

type Segment = {
  id: string;
  project_id: string;
  position: number;
  start_seconds: number;
  end_seconds: number;
  source_text: string;
  translated_text: string | null;
};

type ReadinessIssue = {
  code: string;
  severity: "error" | "warning";
  message: string;
  segment_id: string | null;
};

type TTSReadiness = {
  project_id: string;
  ready: boolean;
  segment_count: number;
  blocking_error_count: number;
  warning_count: number;
  issues: ReadinessIssue[];
};

type JobState = {
  id: string;
  project_id: string;
  status: JobStatus;
  stage?: string | null;
  error?: string | null;
  created_at?: string;
  started_at?: string | null;
  finished_at?: string | null;
};

type ApiError = {
  detail?: string;
};

const MAX_FILE_SIZE = 100 * 1024 * 1024;
const JOB_POLL_INTERVAL_MS = 4000;

const jobStatusLabels: Record<JobStatus, string> = {
  queued: "Waiting",
  running: "Processing",
  succeeded: "Completed",
  failed: "Failed",
  interrupted: "Interrupted",
};

function getErrorMessage(response: Response, body: ApiError | null): string {
  if (body?.detail) {
    return body.detail;
  }

  if (response.status === 413) {
    return "The video is larger than the 100 MiB limit.";
  }

  return "Something went wrong. Please try again.";
}

async function readError(response: Response): Promise<string> {
  let body: ApiError | null = null;

  try {
    body = (await response.json()) as ApiError;
  } catch {
    // Use the safe generic message below when the server did not return JSON.
  }

  return getErrorMessage(response, body);
}

function formatDate(value: string): string {
  return new Intl.DateTimeFormat(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(value));
}

function formatTimestamp(value: number): string {
  const totalMilliseconds = Math.max(0, Math.floor(value * 1000));
  const minutes = Math.floor(totalMilliseconds / 60_000);
  const seconds = Math.floor((totalMilliseconds % 60_000) / 1000);
  const milliseconds = totalMilliseconds % 1000;
  return `${String(minutes).padStart(2, "0")}:${String(seconds).padStart(2, "0")}.${String(milliseconds).padStart(3, "0")}`;
}

function App() {
  const [projects, setProjects] = useState<Project[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [name, setName] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [jobsByProject, setJobsByProject] = useState<Record<string, JobState>>({});
  const [jobErrorsByProject, setJobErrorsByProject] = useState<Record<string, string>>({});
  const [enqueueErrorsByProject, setEnqueueErrorsByProject] = useState<Record<string, string>>({});
  const [enqueueingProjects, setEnqueueingProjects] = useState<Record<string, boolean>>({});
  const [selectedProject, setSelectedProject] = useState<Project | null>(null);
  const [segments, setSegments] = useState<Segment[]>([]);
  const [segmentsLoading, setSegmentsLoading] = useState(false);
  const [segmentsError, setSegmentsError] = useState<string | null>(null);
  const [videoError, setVideoError] = useState(false);
  const [currentTime, setCurrentTime] = useState(0);
  const [editingSegmentId, setEditingSegmentId] = useState<string | null>(null);
  const [translationDraft, setTranslationDraft] = useState("");
  const [savingSegmentId, setSavingSegmentId] = useState<string | null>(null);
  const [translationSaveErrors, setTranslationSaveErrors] = useState<Record<string, string>>({});
  const [ttsReadiness, setTtsReadiness] = useState<TTSReadiness | null>(null);
  const [readinessLoading, setReadinessLoading] = useState(false);
  const [readinessError, setReadinessError] = useState<string | null>(null);

  async function loadProjectJobs(projectList: Project[]) {
    await Promise.all(projectList.map(async (project) => {
      try {
        const response = await fetch(`/api/projects/${project.id}/jobs`);
        if (!response.ok) {
          throw new Error(await readError(response));
        }

        const persistedJobs = (await response.json()) as JobState[];
        setJobsByProject((current) => {
          const next = { ...current };
          if (persistedJobs[0]) {
            next[project.id] = persistedJobs[0];
          } else {
            delete next[project.id];
          }
          return next;
        });
        setJobErrorsByProject((current) => {
          const next = { ...current };
          delete next[project.id];
          return next;
        });
      } catch (loadError) {
        setJobErrorsByProject((current) => ({
          ...current,
          [project.id]: loadError instanceof Error ? loadError.message : "Unable to load Job state.",
        }));
      }
    }));
  }

  async function loadProjects() {
    setIsLoading(true);
    setError(null);

    try {
      const response = await fetch("/api/projects");
      if (!response.ok) {
        throw new Error(await readError(response));
      }

      const projectList = (await response.json()) as Project[];
      setProjects(projectList);
      await loadProjectJobs(projectList);
      const requestedProjectId = new URLSearchParams(window.location.search).get("project");
      const requestedProject = projectList.find((project) => project.id === requestedProjectId);
      if (requestedProject) {
        await openProject(requestedProject, false);
      }
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : "Unable to load projects.");
    } finally {
      setIsLoading(false);
    }
  }

  useEffect(() => {
    void loadProjects();
  }, []);

  async function openProject(project: Project, updateUrl = true) {
    setSelectedProject(project);
    setSegments([]);
    setSegmentsLoading(true);
    setSegmentsError(null);
    setVideoError(false);
    setCurrentTime(0);
    setTtsReadiness(null);
    setReadinessError(null);
    if (updateUrl) {
      window.history.pushState({}, "", `?project=${encodeURIComponent(project.id)}`);
    }
    try {
      const response = await fetch(`/api/projects/${project.id}/segments`);
      if (!response.ok) throw new Error(await readError(response));
      setSegments((await response.json()) as Segment[]);
    } catch (loadError) {
      setSegmentsError(loadError instanceof Error ? loadError.message : "Unable to load transcript.");
    } finally {
      setSegmentsLoading(false);
    }
  }

  function closeProject() {
    setSelectedProject(null);
    setSegments([]);
    window.history.pushState({}, "", window.location.pathname);
  }

  function seekToSegment(segment: Segment) {
    const video = document.querySelector<HTMLVideoElement>(".project-video");
    if (video) {
      video.currentTime = segment.start_seconds;
      void video.play().catch(() => undefined);
    }
  }

  async function checkTtsReadiness() {
    if (!selectedProject) return;
    setReadinessLoading(true);
    setTtsReadiness(null);
    setReadinessError(null);
    try {
      const response = await fetch(`/api/projects/${selectedProject.id}/tts-readiness`);
      if (!response.ok) throw new Error(await readError(response));
      setTtsReadiness((await response.json()) as TTSReadiness);
    } catch (requestError) {
      setReadinessError(requestError instanceof Error ? requestError.message : "Unable to validate TTS readiness.");
    } finally {
      setReadinessLoading(false);
    }
  }

  function locateReadinessSegment(segmentId: string) {
    const row = document.getElementById(`segment-${segmentId}`);
    row?.scrollIntoView({ behavior: "smooth", block: "center" });
    const segment = segments.find((item) => item.id === segmentId);
    if (segment) seekToSegment(segment);
  }

  function beginTranslationEdit(segment: Segment) {
    setEditingSegmentId(segment.id);
    setTranslationDraft(segment.translated_text ?? "");
    setTranslationSaveErrors((current) => {
      const next = { ...current };
      delete next[segment.id];
      return next;
    });
  }

  function cancelTranslationEdit(segmentId: string) {
    setEditingSegmentId(null);
    setTranslationDraft("");
    setTranslationSaveErrors((current) => {
      const next = { ...current };
      delete next[segmentId];
      return next;
    });
  }

  async function saveTranslation(segment: Segment) {
    const translatedText = translationDraft.trim();
    if (!translatedText) {
      setTranslationSaveErrors((current) => ({ ...current, [segment.id]: "Enter a Vietnamese translation before saving." }));
      return;
    }
    setSavingSegmentId(segment.id);
    setTranslationSaveErrors((current) => {
      const next = { ...current };
      delete next[segment.id];
      return next;
    });
    try {
      const response = await fetch(`/api/projects/${selectedProject?.id}/segments/${segment.id}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ translated_text: translatedText }),
      });
      if (!response.ok) throw new Error(await readError(response));
      const updatedSegment = (await response.json()) as Segment;
      setSegments((current) => current.map((item) => item.id === updatedSegment.id ? updatedSegment : item));
      setTtsReadiness(null);
      setReadinessError(null);
      setEditingSegmentId(null);
      setTranslationDraft("");
    } catch (saveError) {
      setTranslationSaveErrors((current) => ({
        ...current,
        [segment.id]: saveError instanceof Error ? saveError.message : "Unable to save this translation.",
      }));
    } finally {
      setSavingSegmentId(null);
    }
  }

  const activeJobsKey = Object.entries(jobsByProject)
    .filter(([, job]) => job.status === "queued" || job.status === "running")
    .map(([projectId, job]) => `${projectId}:${job.id}`)
    .sort()
    .join("|");

  useEffect(() => {
    const activeJobs = Object.entries(jobsByProject)
      .filter(([, job]) => job.status === "queued" || job.status === "running")
      .map(([projectId, job]) => ({ projectId, jobId: job.id }));
    if (!activeJobs.length) {
      return;
    }

    let stopped = false;
    const timers = new Set<number>();
    for (const { projectId, jobId } of activeJobs) {
      const poll = async () => {
        try {
          const response = await fetch(`/api/jobs/${jobId}`);
          if (!response.ok) {
            throw new Error(await readError(response));
          }
          const persistedJob = (await response.json()) as JobState;
          setJobsByProject((current) => {
            if (current[projectId]?.id !== jobId) {
              return current;
            }
            return { ...current, [projectId]: persistedJob };
          });
          setJobErrorsByProject((current) => {
            const next = { ...current };
            delete next[projectId];
            return next;
          });
        } catch (pollError) {
          setJobErrorsByProject((current) => ({
            ...current,
            [projectId]: pollError instanceof Error ? pollError.message : "Unable to refresh Job state.",
          }));
        }

        if (!stopped) {
          const timer = window.setTimeout(poll, JOB_POLL_INTERVAL_MS);
          timers.add(timer);
        }
      };
      timers.add(window.setTimeout(poll, JOB_POLL_INTERVAL_MS));
    }

    return () => {
      stopped = true;
      timers.forEach(window.clearTimeout);
    };
  }, [activeJobsKey]);

  const selectedJobStatus = selectedProject ? jobsByProject[selectedProject.id]?.status : undefined;
  useEffect(() => {
    if (!selectedProject || selectedJobStatus !== "succeeded") return;
    let cancelled = false;
    void fetch(`/api/projects/${selectedProject.id}/segments`)
      .then(async (response) => {
        if (!response.ok) throw new Error(await readError(response));
        return (await response.json()) as Segment[];
      })
      .then((latestSegments) => {
        if (!cancelled) {
          setSegments(latestSegments);
          setSegmentsError(null);
        }
      })
      .catch((loadError: unknown) => {
        if (!cancelled) {
          setSegmentsError(loadError instanceof Error ? loadError.message : "Unable to load transcript.");
        }
      });
    return () => { cancelled = true; };
  }, [selectedProject?.id, selectedJobStatus]);

  async function startProcessing(project: Project) {
    setEnqueueingProjects((current) => ({ ...current, [project.id]: true }));
    setEnqueueErrorsByProject((current) => {
      const next = { ...current };
      delete next[project.id];
      return next;
    });

    try {
      const response = await fetch(`/api/projects/${project.id}/jobs`, { method: "POST" });
      if (!response.ok) {
        throw new Error(await readError(response));
      }
      const createdJob = (await response.json()) as JobState;
      setJobsByProject((current) => ({ ...current, [project.id]: createdJob }));

      try {
        const detailResponse = await fetch(`/api/jobs/${createdJob.id}`);
        if (detailResponse.ok) {
          const persistedJob = (await detailResponse.json()) as JobState;
          setJobsByProject((current) => ({ ...current, [project.id]: persistedJob }));
        }
      } catch {
        // Keep the real queued response visible if loading lifecycle details fails.
      }
    } catch (enqueueError) {
      setEnqueueErrorsByProject((current) => ({
        ...current,
        [project.id]: enqueueError instanceof Error ? enqueueError.message : "Unable to start processing.",
      }));
    } finally {
      setEnqueueingProjects((current) => ({ ...current, [project.id]: false }));
    }
  }

  function handleFileChange(event: ChangeEvent<HTMLInputElement>) {
    const selectedFile = event.target.files?.[0] ?? null;
    setFile(selectedFile);
    setError(null);
    setSuccess(null);
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = event.currentTarget;
    if (isSubmitting) {
      return;
    }

    setError(null);
    setSuccess(null);

    if (!name.trim()) {
      setError("Enter a project name.");
      return;
    }

    if (!file) {
      setError("Choose an MP4 video to upload.");
      return;
    }

    if (!file.name.toLowerCase().endsWith(".mp4")) {
      setError("Choose an MP4 video file.");
      return;
    }

    if (file.size > MAX_FILE_SIZE) {
      setError("The video is larger than the 100 MiB limit.");
      return;
    }

    setIsSubmitting(true);
    const formData = new FormData();
    formData.append("name", name.trim());
    formData.append("source_video", file);

    try {
      const response = await fetch("/api/projects/upload", {
        method: "POST",
        body: formData,
      });

      if (!response.ok) {
        throw new Error(await readError(response));
      }

      const createdProject = (await response.json()) as { name: string };
      setName("");
      setFile(null);
      form.reset();
      await loadProjects();
      setSuccess(`“${createdProject.name}” was uploaded successfully.`);
    } catch (uploadError) {
      setError(uploadError instanceof Error ? uploadError.message : "Unable to upload the video.");
    } finally {
      setIsSubmitting(false);
    }
  }

  if (selectedProject) {
    const activeSegment = segments.find((segment) => currentTime >= segment.start_seconds && currentTime < segment.end_seconds);
    const job = jobsByProject[selectedProject.id];
    const transcriptReady = Boolean(job?.status === "succeeded" || segments.length > 0);
    return (
      <main className="app-shell">
        <button className="back-button" type="button" onClick={closeProject}>← Projects</button>
        <header className="page-header viewer-header">
          <p className="eyebrow">Project viewer</p>
          <h1>{selectedProject.name}</h1>
          <p className="intro">Original video and persisted source/translation Segments.</p>
        </header>
        <section className="viewer-grid">
          <div className="video-panel card">
            {videoError ? <p className="state-message">The source video is missing or could not be played.</p> : (
              <video className="project-video" controls preload="metadata" src={`/api/projects/${selectedProject.id}/video`}
                onTimeUpdate={(event) => setCurrentTime(event.currentTarget.currentTime)}
                onError={() => setVideoError(true)} />
            )}
            <p className="video-caption">Original uploaded video</p>
          </div>
          <section className="transcript-panel card" aria-labelledby="transcript-heading">
            <div className="transcript-heading">
              <div><p className="section-kicker">Transcript</p><h2 id="transcript-heading">Source &amp; Vietnamese</h2></div>
              {job && <span className={`status-badge job-status-${job.status}`}>{jobStatusLabels[job.status]}</span>}
            </div>
            {job?.stage && <p className="job-stage">Stage: {job.stage}</p>}
            {(job?.status === "failed" || job?.status === "interrupted") && job.error && <p className="job-error">{job.error}</p>}
            {job?.status === "queued" || job?.status === "running" ? <p className="state-message">Transcript is being processed. Reopen this Project after processing completes.</p> : null}
            <section className="readiness-panel" aria-labelledby="readiness-heading" aria-live="polite">
              <div className="readiness-action">
                <h3 id="readiness-heading">TTS readiness</h3>
                <button type="button" onClick={() => void checkTtsReadiness()} disabled={readinessLoading}>
                  {readinessLoading ? "Checking…" : "Kiểm tra trước khi tạo giọng đọc"}
                </button>
              </div>
              {readinessError && <p className="inline-error" role="alert">{readinessError}</p>}
              {readinessLoading && <p className="state-message">Checking persisted transcript and translation data…</p>}
              {ttsReadiness && <>
                <p className={ttsReadiness.ready ? "readiness-ready" : "readiness-blocked"}>
                  {ttsReadiness.ready ? "Ready for future TTS" : "Not ready for future TTS"}
                </p>
                <p className="readiness-counts">
                  {ttsReadiness.segment_count} Segments · {ttsReadiness.blocking_error_count} errors · {ttsReadiness.warning_count} warnings
                </p>
                {ttsReadiness.blocking_error_count > 0 && <div className="readiness-issues">
                  <h4>Blocking errors ({ttsReadiness.blocking_error_count})</h4>
                  <ul>{ttsReadiness.issues.filter((issue) => issue.severity === "error").map((issue, index) => (
                    <li key={`${issue.code}-${issue.segment_id ?? "project"}-${index}`}>
                      {issue.segment_id ? <button type="button" className="issue-link" onClick={() => locateReadinessSegment(issue.segment_id!)}>{issue.message}</button> : issue.message}
                    </li>
                  ))}</ul>
                </div>}
                {ttsReadiness.warning_count > 0 && <div className="readiness-issues warning-list">
                  <h4>Warnings ({ttsReadiness.warning_count})</h4>
                  <ul>{ttsReadiness.issues.filter((issue) => issue.severity === "warning").map((issue, index) => (
                    <li key={`${issue.code}-${issue.segment_id ?? "project"}-${index}`}>
                      {issue.segment_id ? <button type="button" className="issue-link" onClick={() => locateReadinessSegment(issue.segment_id!)}>{issue.message}</button> : issue.message}
                    </li>
                  ))}</ul>
                </div>}
              </>}
            </section>
            {segmentsLoading && <p className="state-message">Loading transcript…</p>}
            {segmentsError && <p className="message error-message" role="alert">{segmentsError}</p>}
            {!segmentsLoading && !segmentsError && segments.length === 0 && (
              <p className="state-message">{transcriptReady ? "No speech was detected in this video." : "No transcript is available yet."}</p>
            )}
            {segments.length > 0 && <ol className="segment-list">
              {segments.map((segment) => <li id={`segment-${segment.id}`} key={segment.id} className={activeSegment?.id === segment.id ? "segment-row segment-active" : "segment-row"}>
                <button type="button" className="segment-seek" onClick={() => seekToSegment(segment)} aria-label={`Seek to ${formatTimestamp(segment.start_seconds)}`}>
                  {formatTimestamp(segment.start_seconds)}
                </button>
                  <div className="segment-languages">
                  <p>{segment.source_text}</p>
                    {editingSegmentId === segment.id ? (
                      <div className="translation-editor">
                        <label htmlFor={`translation-${segment.id}`}>Vietnamese translation</label>
                        <textarea id={`translation-${segment.id}`} value={translationDraft} maxLength={10000}
                          onChange={(event) => setTranslationDraft(event.target.value)} disabled={savingSegmentId === segment.id} />
                        <span className="field-help">Up to 10,000 characters. Empty translations cannot be saved.</span>
                        {translationSaveErrors[segment.id] && <p className="inline-error" role="alert">{translationSaveErrors[segment.id]}</p>}
                        <div className="translation-actions">
                          <button type="button" onClick={() => void saveTranslation(segment)} disabled={savingSegmentId === segment.id || !translationDraft.trim()}>
                            {savingSegmentId === segment.id ? "Saving…" : "Save"}
                          </button>
                          <button type="button" className="secondary-button" onClick={() => cancelTranslationEdit(segment.id)} disabled={savingSegmentId === segment.id}>Cancel</button>
                        </div>
                      </div>
                    ) : (
                      <>
                        <p className={segment.translated_text ? "translated-text" : "translation-pending"}>{segment.translated_text || "Vietnamese translation not available yet."}</p>
                        <button type="button" className="edit-translation" onClick={() => beginTranslationEdit(segment)}
                          disabled={Boolean(editingSegmentId) || selectedJobStatus !== "succeeded"}>
                          {segment.translated_text ? "Edit translation" : "Add translation"}
                        </button>
                      </>
                    )}
                </div>
              </li>)}
            </ol>}
          </section>
        </section>
      </main>
    );
  }

  return (
    <main className="app-shell">
      <header className="page-header">
        <p className="eyebrow">AutoDub</p>
        <h1>Projects</h1>
        <p className="intro">Upload a video to start a new dubbing project.</p>
      </header>

      <section className="card upload-card" aria-labelledby="upload-heading">
        <div>
          <p className="section-kicker">New project</p>
          <h2 id="upload-heading">Upload source video</h2>
        </div>
        <form onSubmit={handleSubmit} noValidate>
          <div className="form-grid">
            <label>
              Project name
              <input
                type="text"
                value={name}
                onChange={(event) => setName(event.target.value)}
                maxLength={255}
                placeholder="e.g. Product launch"
                disabled={isSubmitting}
              />
            </label>
            <label>
              MP4 video
              <input
                type="file"
                accept="video/mp4,.mp4"
                onChange={handleFileChange}
                disabled={isSubmitting}
              />
              <span className="field-help">MP4 only, up to 100 MiB. Maximum duration: 30 minutes.</span>
            </label>
          </div>
          <button type="submit" disabled={isSubmitting}>
            {isSubmitting ? "Uploading…" : "Upload project"}
          </button>
        </form>
      </section>

      <div className="feedback" aria-live="polite">
        {error && <p className="message error-message" role="alert">{error}</p>}
        {success && <p className="message success-message" role="status">{success}</p>}
      </div>

      <section className="projects-section" aria-labelledby="projects-heading">
        <div className="section-heading">
          <div>
            <p className="section-kicker">Your workspace</p>
            <h2 id="projects-heading">Project list</h2>
          </div>
          <span className="project-count">{projects.length} {projects.length === 1 ? "project" : "projects"}</span>
        </div>

        {isLoading && <p className="state-message">Loading projects…</p>}
        {!isLoading && projects.length === 0 && (
          <p className="state-message empty-state">No projects yet. Upload an MP4 above to get started.</p>
        )}
        {!isLoading && projects.length > 0 && (
          <ul className="project-list">
            {projects.map((project) => (
              <li className="project-item" key={project.id}>
                <div className="project-info">
                  <h3>{project.name}</h3>
                  <p>Created {formatDate(project.created_at)}</p>
                  <button type="button" className="open-project" onClick={() => void openProject(project)}>Open video &amp; transcript</button>
                </div>
                <div className="project-meta">
                  <span className={`status-badge status-${project.status}`}>{project.status.replaceAll("_", " ")}</span>
                  <span className="source-state">{project.source_media_reference ? "Source uploaded" : "No source media"}</span>
                </div>
                <div className="project-job">
                  <div className="job-state" aria-live="polite">
                    <h4>Processing job</h4>
                    {jobsByProject[project.id] ? (
                      <>
                        <div className="job-status-line">
                          <span className={`status-badge job-status-${jobsByProject[project.id].status}`}>
                            {jobStatusLabels[jobsByProject[project.id].status]}
                          </span>
                          <span className="job-stage">Stage: {jobsByProject[project.id].stage || "Not reported"}</span>
                        </div>
                        <dl className="job-timestamps">
                          {jobsByProject[project.id].created_at && <div><dt>Created</dt><dd>{formatDate(jobsByProject[project.id].created_at!)}</dd></div>}
                          {jobsByProject[project.id].started_at && <div><dt>Started</dt><dd>{formatDate(jobsByProject[project.id].started_at!)}</dd></div>}
                          {jobsByProject[project.id].finished_at && <div><dt>Finished</dt><dd>{formatDate(jobsByProject[project.id].finished_at!)}</dd></div>}
                        </dl>
                        {(jobsByProject[project.id].status === "failed" || jobsByProject[project.id].status === "interrupted") && jobsByProject[project.id].error && (
                          <p className="job-error">{jobsByProject[project.id].error}</p>
                        )}
                      </>
                    ) : (
                      <p className="job-stage">{jobErrorsByProject[project.id] ? "Job state unavailable." : "No processing Job yet."}</p>
                    )}
                    {jobErrorsByProject[project.id] && <p className="inline-error" role="alert">{jobErrorsByProject[project.id]}</p>}
                    {enqueueErrorsByProject[project.id] && <p className="inline-error" role="alert">{enqueueErrorsByProject[project.id]}</p>}
                  </div>
                  <button
                    type="button"
                    onClick={() => void startProcessing(project)}
                    disabled={Boolean(enqueueingProjects[project.id]) || jobsByProject[project.id]?.status === "queued" || jobsByProject[project.id]?.status === "running"}
                  >
                    {enqueueingProjects[project.id] ? "Starting…" : jobsByProject[project.id]?.status === "queued" || jobsByProject[project.id]?.status === "running" ? "Job active" : "Start processing"}
                  </button>
                </div>
              </li>
            ))}
          </ul>
        )}
      </section>
    </main>
  );
}

export default App;

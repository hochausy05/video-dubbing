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
  job_type?: string;
  status: JobStatus;
  stage?: string | null;
  error?: string | null;
  created_at?: string;
  started_at?: string | null;
  finished_at?: string | null;
};

type TTSArtifact = {
  id: string;
  project_id: string;
  segment_id: string;
  duration_ms: number;
  voice: string;
  rate_percent: number;
  audio_url: string;
  current: boolean;
};

type TimelineIssue = {
  code: string;
  severity: "blocking" | "warning";
  message: string;
  segment_ids: string[];
};

type PlannedSegmentTiming = {
  segment_id: string;
  position: number;
  original_start_ms: number;
  original_end_ms: number;
  tts_audio_duration_ms: number;
  output_audio_start_ms: number;
  output_audio_end_ms: number;
  cumulative_shift_ms: number;
  stretch_factor: number | null;
  added_duration_ms: number;
  unresolved_overlap_ms: number;
};

type TimelineStretchOperation = {
  operation_order: number;
  segment_id: string;
  source_start_ms: number;
  source_end_ms: number;
  stretch_factor: number;
  expected_output_duration_ms: number;
  added_duration_ms: number;
};

type TTSTimelinePlan = {
  project_id: string;
  original_video_duration_ms: number | null;
  planned_output_video_duration_ms: number | null;
  segment_count: number;
  stretch_segment_count: number;
  total_added_duration_ms: number;
  renderable: boolean;
  blocking_issue_count: number;
  issues: TimelineIssue[];
  segments: PlannedSegmentTiming[];
  stretch_operations: TimelineStretchOperation[];
};

type TTSOptimizationResult = {
  job_id: string;
  project_id: string;
  status: JobStatus;
  stage: string | null;
  error: string | null;
  updated_segments: { segment_id: string; rate_percent: number; duration_ms: number; resolved: boolean }[];
  resolved_conflict_segment_ids: string[];
  remaining_conflicts: { code: string; message: string; segment_id: string; remaining_excess_ms: number }[];
  renderable: boolean;
  recommendation: string | null;
  stale: boolean;
};

type TTSNormalizationResult = {
  job_id: string;
  project_id: string;
  status: JobStatus;
  stage: string | null;
  error: string | null;
  files_processed: number;
  files_shortened: number;
  total_recovered_ms: number;
  segments: {
    segment_id: string;
    rate_percent: number;
    original_duration_ms: number;
    final_duration_ms: number;
    removed_silence_ms: number;
    trimmed: boolean;
    skipped_reason: string | null;
  }[];
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
  const [focusedSegmentId, setFocusedSegmentId] = useState<string | null>(null);
  const [editingSegmentId, setEditingSegmentId] = useState<string | null>(null);
  const [translationDraft, setTranslationDraft] = useState("");
  const [savingSegmentId, setSavingSegmentId] = useState<string | null>(null);
  const [translationSaveErrors, setTranslationSaveErrors] = useState<Record<string, string>>({});
  const [ttsReadiness, setTtsReadiness] = useState<TTSReadiness | null>(null);
  const [readinessLoading, setReadinessLoading] = useState(false);
  const [readinessError, setReadinessError] = useState<string | null>(null);
  const [ttsAudioBySegment, setTtsAudioBySegment] = useState<Record<string, TTSArtifact>>({});
  const [ttsAudioError, setTtsAudioError] = useState<string | null>(null);
  const [timelinePlan, setTimelinePlan] = useState<TTSTimelinePlan | null>(null);
  const [timelineLoading, setTimelineLoading] = useState(false);
  const [timelineError, setTimelineError] = useState<string | null>(null);
  const [timelineNotice, setTimelineNotice] = useState<string | null>(null);
  const [optimizationResult, setOptimizationResult] = useState<TTSOptimizationResult | null>(null);
  const [optimizationError, setOptimizationError] = useState<string | null>(null);
  const [normalizationResult, setNormalizationResult] = useState<TTSNormalizationResult | null>(null);
  const [normalizationError, setNormalizationError] = useState<string | null>(null);

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
    setTtsAudioBySegment({});
    setTtsAudioError(null);
    setTimelinePlan(null);
    setTimelineError(null);
    setTimelineNotice(null);
    setOptimizationResult(null);
    setOptimizationError(null);
    setNormalizationResult(null);
    setNormalizationError(null);
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
    await loadProjectTtsAudio(project.id);
  }

  async function loadProjectTtsAudio(projectId: string) {
    try {
      const response = await fetch(`/api/projects/${projectId}/tts-audio`);
      if (!response.ok) throw new Error(await readError(response));
      const artifacts = (await response.json()) as TTSArtifact[];
      setTtsAudioBySegment(Object.fromEntries(artifacts.map((artifact) => [artifact.segment_id, artifact])));
      setTtsAudioError(null);
    } catch (loadError) {
      setTtsAudioError(loadError instanceof Error ? loadError.message : "Unable to load generated audio.");
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

  async function analyzeTtsTimeline() {
    if (!selectedProject) return;
    setTimelineLoading(true);
    setTimelineError(null);
    setTimelineNotice(null);
    setTimelinePlan(null);
    try {
      const response = await fetch(`/api/projects/${selectedProject.id}/tts-timeline-plan`);
      if (!response.ok) throw new Error(await readError(response));
      setTimelinePlan((await response.json()) as TTSTimelinePlan);
    } catch (requestError) {
      setTimelineError(requestError instanceof Error ? requestError.message : "Unable to analyze the TTS timeline.");
    } finally {
      setTimelineLoading(false);
    }
  }

  async function loadTtsOptimizationResult(projectId: string, jobId: string) {
    setOptimizationError(null);
    try {
      const response = await fetch(`/api/projects/${projectId}/tts-optimization-jobs/${jobId}`);
      if (!response.ok) throw new Error(await readError(response));
      setOptimizationResult((await response.json()) as TTSOptimizationResult);
    } catch (requestError) {
      setOptimizationError(requestError instanceof Error ? requestError.message : "Unable to load optimization results.");
    }
  }

  async function loadTtsNormalizationResult(projectId: string, jobId: string) {
    setNormalizationError(null);
    try {
      const response = await fetch(`/api/projects/${projectId}/tts-normalization-jobs/${jobId}`);
      if (!response.ok) throw new Error(await readError(response));
      setNormalizationResult((await response.json()) as TTSNormalizationResult);
    } catch (requestError) {
      setNormalizationError(requestError instanceof Error ? requestError.message : "Unable to load normalization results.");
    }
  }

  function locateReadinessSegment(segmentId: string) {
    const row = document.getElementById(`segment-${segmentId}`);
    const list = row?.closest<HTMLOListElement>(".segment-list");
    if (row && list) {
      const listBounds = list.getBoundingClientRect();
      const rowBounds = row.getBoundingClientRect();
      list.scrollBy({
        top: rowBounds.top - listBounds.top - (list.clientHeight - row.clientHeight) / 2,
        behavior: "smooth",
      });
      setFocusedSegmentId(segmentId);
    }
    const segment = segments.find((item) => item.id === segmentId);
    if (segment) seekToSegment(segment);
  }

  function beginTranslationEdit(segment: Segment) {
    if (editingSegmentId && editingSegmentId !== segment.id) {
      const currentSegment = segments.find((item) => item.id === editingSegmentId);
      if (currentSegment && translationDraft.trim() !== (currentSegment.translated_text ?? "").trim()) {
        setTimelineNotice("Save or cancel the current translation before opening another Segment. Your unsaved text is preserved.");
        return;
      }
    }
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
      if (selectedProject) await loadProjectTtsAudio(selectedProject.id);
      setTimelinePlan(null);
      setTimelineError(null);
      setTimelineNotice("Translation saved. Existing audio for this Segment may now be outdated. Regenerate full-Project TTS, then analyze the timeline again.");
      setOptimizationResult(null);
      setOptimizationError(null);
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
          if (persistedJob.job_type === "tts" && persistedJob.status === "succeeded") {
            setTimelinePlan(null);
            setTimelineNotice("Full-Project TTS generation completed. Analyze the timeline again to verify the newly measured audio. Previous optimized speaking rates were reset to the standard adaptive rates; run duration optimization again if needed.");
            void loadProjectTtsAudio(projectId);
          }
          if (persistedJob.job_type === "tts" && ["failed", "interrupted"].includes(persistedJob.status)) {
            setTimelinePlan(null);
            setTimelineNotice("TTS regeneration did not complete. Previously published audio was preserved; analyze the timeline to check whether it still matches the saved translations.");
            void loadProjectTtsAudio(projectId);
          }
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
  const selectedJob = selectedProject ? jobsByProject[selectedProject.id] : undefined;
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

  useEffect(() => {
    if (!selectedProject || selectedJob?.job_type !== "tts_optimize") return;
    if (!["succeeded", "failed", "interrupted"].includes(selectedJob.status)) return;
    void loadTtsOptimizationResult(selectedProject.id, selectedJob.id);
    if (selectedJob.status === "succeeded") {
      setTimelineNotice(null);
      void fetch(`/api/projects/${selectedProject.id}/tts-timeline-plan`)
        .then(async (response) => {
          if (!response.ok) throw new Error(await readError(response));
          setTimelinePlan((await response.json()) as TTSTimelinePlan);
        })
        .catch((planError: unknown) => setTimelineError(
          planError instanceof Error ? planError.message : "Unable to refresh the TTS timeline."
        ));
      void loadProjectTtsAudio(selectedProject.id);
    }
  }, [selectedProject?.id, selectedJob?.id, selectedJob?.status, selectedJob?.job_type]);

  useEffect(() => {
    if (!selectedProject || selectedJob?.job_type !== "tts_normalize") return;
    void loadTtsNormalizationResult(selectedProject.id, selectedJob.id);
    if (selectedJob.status === "succeeded") {
      setTimelinePlan(null);
      setOptimizationResult(null);
      setOptimizationError(null);
      setTimelineNotice("TTS audio normalization completed. Timeline analysis was refreshed from the newly published audio.");
      void fetch(`/api/projects/${selectedProject.id}/tts-timeline-plan`)
        .then(async (response) => {
          if (!response.ok) throw new Error(await readError(response));
          setTimelinePlan((await response.json()) as TTSTimelinePlan);
        })
        .catch((planError: unknown) => setTimelineError(
          planError instanceof Error ? planError.message : "Unable to refresh the TTS timeline."
        ));
      void loadProjectTtsAudio(selectedProject.id);
    }
  }, [selectedProject?.id, selectedJob?.id, selectedJob?.status, selectedJob?.job_type]);

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

  async function startTts(project: Project) {
    setTimelinePlan(null);
    setTimelineError(null);
    setTimelineNotice(null);
    setOptimizationResult(null);
    setOptimizationError(null);
    setEnqueueingProjects((current) => ({ ...current, [project.id]: true }));
    setEnqueueErrorsByProject((current) => ({ ...current, [project.id]: "" }));
    try {
      const response = await fetch(`/api/projects/${project.id}/tts-jobs`, { method: "POST" });
      if (!response.ok) throw new Error(await readError(response));
      const created = (await response.json()) as JobState;
      setJobsByProject((current) => ({ ...current, [project.id]: { ...created, job_type: "tts" } }));
      setTimelineNotice("Full-Project TTS regeneration is queued. It uses standard adaptive rates and does not preserve previous TTS-03 optimized rates; you may need to optimize again afterward.");
    } catch (enqueueError) {
      setTimelineNotice("TTS regeneration was not queued. The previous timeline result was cleared; analyze the persisted data again before relying on it.");
      setEnqueueErrorsByProject((current) => ({
        ...current,
        [project.id]: enqueueError instanceof Error ? enqueueError.message : "Unable to start Vietnamese voice generation.",
      }));
    } finally {
      setEnqueueingProjects((current) => ({ ...current, [project.id]: false }));
    }
  }

  async function optimizeTtsDuration(project: Project) {
    setTimelinePlan(null);
    setTimelineError(null);
    setTimelineNotice(null);
    setOptimizationResult(null);
    setOptimizationError(null);
    setEnqueueingProjects((current) => ({ ...current, [project.id]: true }));
    setEnqueueErrorsByProject((current) => ({ ...current, [project.id]: "" }));
    try {
      const response = await fetch(`/api/projects/${project.id}/tts-optimization-jobs`, { method: "POST" });
      if (!response.ok) throw new Error(await readError(response));
      const created = (await response.json()) as JobState;
      setJobsByProject((current) => ({ ...current, [project.id]: { ...created, job_type: "tts_optimize" } }));
      setTimelineNotice("TTS duration optimization is queued. The timeline will be recalculated after the Job completes.");
    } catch (enqueueError) {
      setTimelineNotice("TTS duration optimization was not queued. Analyze the persisted timeline again before relying on prior results.");
      setEnqueueErrorsByProject((current) => ({
        ...current,
        [project.id]: enqueueError instanceof Error ? enqueueError.message : "Unable to optimize TTS duration.",
      }));
    } finally {
      setEnqueueingProjects((current) => ({ ...current, [project.id]: false }));
    }
  }

  async function normalizeTtsAudio(project: Project) {
    setTimelinePlan(null);
    setTimelineError(null);
    setTimelineNotice(null);
    setOptimizationResult(null);
    setOptimizationError(null);
    setNormalizationResult(null);
    setNormalizationError(null);
    setEnqueueingProjects((current) => ({ ...current, [project.id]: true }));
    try {
      const response = await fetch(`/api/projects/${project.id}/tts-normalization-jobs`, { method: "POST" });
      if (!response.ok) throw new Error(await readError(response));
      const created = (await response.json()) as JobState;
      setJobsByProject((current) => ({ ...current, [project.id]: { ...created, job_type: "tts_normalize" } }));
      setTimelineNotice("Audio normalization is queued. It trims only confidently detected excess boundary silence and does not regenerate speech.");
    } catch (enqueueError) {
      setTimelineNotice("Audio normalization was not queued. Existing audio remains unchanged.");
      setNormalizationError(enqueueError instanceof Error ? enqueueError.message : "Unable to queue audio normalization.");
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
    const optimizationJob = job?.job_type === "tts_optimize";
    const hasTtsAudio = Object.keys(ttsAudioBySegment).length > 0;
    const normalizationJob = job?.job_type === "tts_normalize";
    const timelineAvailable = (job?.job_type === "tts" && job.stage === "tts_ready") || optimizationJob || normalizationJob || hasTtsAudio;
    const canAnalyzeTimeline = job?.status !== "queued" && job?.status !== "running";
    const canNormalizeAudio = segments.length > 0 && segments.every((segment) => ttsAudioBySegment[segment.id]?.current)
      && job?.status !== "queued" && job?.status !== "running";
    const timelineConflictIssues = timelinePlan?.issues.filter((issue) =>
      issue.severity === "blocking" && ["stretch_limit_exceeded", "stretch_interval_overlaps_dialogue"].includes(issue.code)
    ) ?? [];
    const optimizableTimeline = Boolean(
      timelinePlan && timelinePlan.blocking_issue_count > 0 &&
      timelinePlan.issues.filter((issue) => issue.severity === "blocking")
        .every((issue) => ["stretch_limit_exceeded", "stretch_interval_overlaps_dialogue"].includes(issue.code))
    );
    const transcriptReady = Boolean(job?.status === "succeeded" || segments.length > 0);
    return (
      <main className="app-shell viewer-shell">
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
            {job && <div className="video-job-summary">
              <div className="transcript-heading">
                <h2>Project job</h2>
                <span className={`status-badge job-status-${job.status}`}>{jobStatusLabels[job.status]}</span>
              </div>
              {job.stage && <p className="job-stage">Stage: {job.stage}</p>}
              {(job.status === "failed" || job.status === "interrupted") && job.error && <p className="job-error">{job.error}</p>}
              {(job.status === "queued" || job.status === "running") && job.job_type !== "tts_optimize" && <p className="job-stage">Transcript processing is {job.status}.</p>}
            </div>}
          </div>
          <section className="transcript-panel card" aria-labelledby="transcript-heading">
            <div className="transcript-heading">
              <div><p className="section-kicker">Transcript</p><h2 id="transcript-heading">Source &amp; Vietnamese</h2></div>
            </div>
            {segmentsLoading && <p className="state-message">Loading transcript…</p>}
            {segmentsError && <p className="message error-message" role="alert">{segmentsError}</p>}
            {!segmentsLoading && !segmentsError && segments.length === 0 && (
              <p className="state-message">{transcriptReady ? "No speech was detected in this video." : "No transcript is available yet."}</p>
            )}
            {segments.length > 0 && <ol className="segment-list" tabIndex={0} aria-label="Transcript Segments">
              {segments.map((segment) => <li id={`segment-${segment.id}`} key={segment.id} className={`segment-row${activeSegment?.id === segment.id ? " segment-active" : ""}${focusedSegmentId === segment.id ? " segment-focused" : ""}`}>
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
                        {ttsAudioBySegment[segment.id] && (ttsAudioBySegment[segment.id].current ? <div className="segment-audio">
                          <audio controls preload="none" src={ttsAudioBySegment[segment.id].audio_url}>Audio playback is not supported by this browser.</audio>
                          <span>{(ttsAudioBySegment[segment.id].duration_ms / 1000).toFixed(2)}s generated audio · {ttsAudioBySegment[segment.id].rate_percent > 0 ? `+${ttsAudioBySegment[segment.id].rate_percent}%` : "normal rate"}</span>
                        </div> : <p className="translation-pending">Saved audio may be outdated after this translation changed; regenerate TTS.</p>)}
                        <button type="button" className="edit-translation" onClick={() => beginTranslationEdit(segment)}
                          disabled={Boolean(editingSegmentId) || job?.status === "queued" || job?.status === "running"}>
                          {segment.translated_text ? "Edit translation" : "Add translation"}
                        </button>
                      </>
                    )}
                </div>
              </li>)}
            </ol>}
          </section>
          <aside className="timeline-workspace card" aria-label="TTS and timeline workspace">
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
              {ttsReadiness?.ready && job?.status !== "queued" && job?.status !== "running" && <button
                type="button"
                className="tts-start-button"
                onClick={() => void startTts(selectedProject)}
                disabled={enqueueingProjects[selectedProject.id]}
              >
                {enqueueingProjects[selectedProject.id] ? "Đang xếp hàng…" : "Tạo giọng đọc tiếng Việt"}
              </button>}
              {enqueueErrorsByProject[selectedProject.id] && <p className="inline-error" role="alert">{enqueueErrorsByProject[selectedProject.id]}</p>}
              {ttsAudioError && <p className="inline-error" role="alert">{ttsAudioError}</p>}
              {hasTtsAudio && <div className="normalization-action">
                <p>Normalize current TTS audio to remove confidently detected excess boundary silence. Speech text, saved translations, and speaking rates are preserved; Edge-TTS is not called.</p>
                <button type="button" onClick={() => void normalizeTtsAudio(selectedProject)} disabled={!canNormalizeAudio || enqueueingProjects[selectedProject.id]}>
                  {enqueueingProjects[selectedProject.id] ? "Queuing normalization…" : "Normalize TTS audio"}
                </button>
                {!canNormalizeAudio && job?.status !== "queued" && job?.status !== "running" && <p className="field-help">Normalization requires one current audio Artifact for every persisted Segment.</p>}
              </div>}
              {normalizationError && <p className="inline-error" role="alert">{normalizationError}</p>}
            </section>
            {timelineAvailable && <section className="timeline-panel" aria-labelledby="timeline-heading" aria-live="polite">
              <div className="timeline-action">
                <div><p className="section-kicker">Output planning</p><h3 id="timeline-heading">TTS timeline analysis</h3></div>
              {canAnalyzeTimeline && <button type="button" onClick={() => void analyzeTtsTimeline()} disabled={timelineLoading}>
                  {timelineLoading ? "Analyzing…" : "Analyze timeline"}
                </button>}
              </div>
              {job?.job_type === "tts" && (job.status === "queued" || job.status === "running") && <p className="state-message">Full-Project TTS regeneration is {job.status === "queued" ? "queued" : "running"}. Previously published audio remains until the complete replacement set is validated. Analysis is available after the Job ends; TTS-03 optimized rates are not retained by this regeneration.</p>}
              {optimizationJob && (job.status === "queued" || job.status === "running") && <p className="state-message">TTS duration optimization is {job.status === "queued" ? "queued" : "running"}; saved audio remains available until replacements are validated.</p>}
              {normalizationJob && (job.status === "queued" || job.status === "running") && <p className="state-message">TTS audio normalization is {job.status === "queued" ? "queued" : "running"}; the existing Artifact generation remains published until the replacement set is validated.</p>}
              {normalizationJob && normalizationResult?.status === "failed" && timelinePlan && <p className="state-message">This normalization Job failed without publishing Artifacts. The timeline analysis below uses the currently published audio generation.</p>}
              {normalizationResult && normalizationResult.status === "succeeded" && <section className="normalization-results" aria-label="TTS normalization results">
                <h4>Normalization result</h4>
                <p>{normalizationResult.files_processed} audio file(s) processed · {normalizationResult.files_shortened} shortened · {normalizationResult.total_recovered_ms} ms recovered</p>
                <ul>{normalizationResult.segments.map((item) => {
                  const segment = segments.find((row) => row.id === item.segment_id);
                  return <li key={item.segment_id}>
                    {segment ? `Segment ${segment.position + 1}` : "Segment"}: {item.original_duration_ms} → {item.final_duration_ms} ms
                    {item.trimmed ? ` (−${item.removed_silence_ms} ms)` : ` · unchanged${item.skipped_reason ? `: ${item.skipped_reason}` : ""}`}
                    {item.rate_percent > 0 ? ` · +${item.rate_percent}%` : " · normal rate"}
                  </li>;
                })}</ul>
              </section>}
              {normalizationResult && (normalizationResult.status === "failed" || normalizationResult.status === "interrupted") && normalizationResult.error && <p className="job-error" role="alert">{normalizationResult.error}</p>}
              {timelineError && <p className="inline-error" role="alert">{timelineError}</p>}
              {optimizationError && <p className="inline-error" role="alert">{optimizationError}</p>}
              {timelineNotice && <p className="state-message" role="status">{timelineNotice}</p>}
              {!timelinePlan && !timelineLoading && !timelineError && !timelineNotice && <p className="state-message">Analyze the current persisted audio and translations to view timeline readiness.</p>}
              {timelineLoading && <p className="state-message">Verifying saved audio and measuring the original video…</p>}
              {optimizationResult && <div className="optimization-results">
                {optimizationResult.stale ? <p className="timeline-blocked" role="status">This optimization result is stale because the Project translations or TTS audio changed. It does not describe the current timeline; use Analyze timeline for current persisted data.</p> : <details>
                <summary>Optimization result · {optimizationResult.updated_segments.length} improved · {optimizationResult.remaining_conflicts.length} conflicts remain</summary>
                {optimizationResult.error && <p className="job-error">{optimizationResult.error}</p>}
                {optimizationResult.updated_segments.length > 0 && <>
                  <p>{optimizationResult.updated_segments.length} Segment audio file(s) improved using measured durations.</p>
                  <ul>{optimizationResult.updated_segments.map((item) => {
                    const segment = segments.find((row) => row.id === item.segment_id);
                    return <li key={item.segment_id}>
                      {segment ? <button type="button" className="issue-link" onClick={() => locateReadinessSegment(item.segment_id)}>Segment {segment.position + 1}</button> : "Segment"}
                      <span> · +{item.rate_percent}% · {item.duration_ms} ms · {item.resolved ? "conflict resolved" : "conflict remains"}</span>
                    </li>;
                  })}</ul>
                </>}
                {optimizationResult.resolved_conflict_segment_ids.length > 0 && <p className="timeline-clear">Resolved conflicts: {optimizationResult.resolved_conflict_segment_ids.map((id) => {
                  const segment = segments.find((row) => row.id === id);
                  return segment ? segment.position + 1 : "Segment";
                }).join(", ")}.</p>}
                {optimizationResult.remaining_conflicts.length > 0 && <div className="timeline-issues">
                  <h4>Remaining conflicts</h4>
                  <ul>{optimizationResult.remaining_conflicts.map((issue, index) => {
                    const segment = segments.find((row) => row.id === issue.segment_id);
                    return <li key={`${issue.code}-${issue.segment_id}-${index}`}>
                      <button type="button" className="issue-link" onClick={() => segment && locateReadinessSegment(issue.segment_id)}>
                        {segment ? `Segment ${segment.position + 1}: ` : ""}{issue.message} Remaining excess: {issue.remaining_excess_ms} ms.
                      </button>
                    </li>;
                  })}</ul>
                </div>}
                {!optimizationResult.renderable && optimizationResult.recommendation && <p className="timeline-blocked">The timeline is still not renderable. {optimizationResult.recommendation}</p>}
                {optimizationResult.renderable && <p className="timeline-clear">No blocking timeline conflicts remain.</p>}
                </details>}
              </div>}
              {timelinePlan && <>
                <p className={timelinePlan.renderable ? "timeline-clear" : "timeline-blocked"}>
                  {timelinePlan.renderable ? "Timeline ready for rendering. No blocking issues remain; no video has been rendered." : `Planning blocked by ${timelinePlan.blocking_issue_count} issue(s).`}
                </p>
                <dl className="timeline-summary">
                  <div><dt>Original video</dt><dd>{timelinePlan.original_video_duration_ms === null ? "Unavailable" : formatTimestamp(timelinePlan.original_video_duration_ms / 1000)}</dd></div>
                  <div><dt>Planned output</dt><dd>{timelinePlan.planned_output_video_duration_ms === null ? "Unavailable" : formatTimestamp(timelinePlan.planned_output_video_duration_ms / 1000)}</dd></div>
                  <div><dt>Additional duration</dt><dd>{formatTimestamp(timelinePlan.total_added_duration_ms / 1000)}</dd></div>
                  <div><dt>Segments to stretch</dt><dd>{timelinePlan.stretch_segment_count} / {timelinePlan.segment_count}</dd></div>
                </dl>
                {timelineConflictIssues.length > 0 && <div className="timeline-conflict-list">
                  <h4>Resolve timing conflicts</h4>
                  <p>Shortening unnecessary words may help the generated audio fit. Any word-count or duration guess cannot guarantee a fit; measured TTS duration is authoritative. Your saved translation is never rewritten automatically.</p>
                  <ol>{timelineConflictIssues.flatMap((issue) => issue.segment_ids.map((segmentId) => {
                    const segment = segments.find((item) => item.id === segmentId);
                    const timing = timelinePlan.segments.find((item) => item.segment_id === segmentId);
                    if (!segment) return null;
                    const artifact = ttsAudioBySegment[segmentId];
                    return <li key={`${issue.code}-${segmentId}`}>
                      <div className="timeline-conflict-heading">
                        <strong>Segment {segment.position + 1}</strong>
                        <code>{segment.id}</code>
                      </div>
                      <dl className="conflict-details">
                        <div><dt>Source duration</dt><dd>{timing ? `${timing.original_end_ms - timing.original_start_ms} ms` : "Unavailable"}</dd></div>
                        <div><dt>Measured TTS audio</dt><dd>{timing ? `${timing.tts_audio_duration_ms} ms` : "Unavailable"}</dd></div>
                        <div><dt>Speaking rate</dt><dd>{artifact ? (artifact.rate_percent > 0 ? `+${artifact.rate_percent}%` : "Normal rate") : "Unavailable"}</dd></div>
                        <div><dt>Remaining excess</dt><dd>{timing ? `${timing.unresolved_overlap_ms} ms` : "Unavailable"}</dd></div>
                      </dl>
                      <p className="conflict-translation">{segment.translated_text || "No Vietnamese translation is available."}</p>
                      <p className="conflict-reason">{issue.message}</p>
                      <button type="button" className="edit-translation" onClick={() => {
                        beginTranslationEdit(segment);
                        locateReadinessSegment(segmentId);
                      }}>Open Segment and edit translation</button>
                    </li>;
                  }))}</ol>
                </div>}
                {timelinePlan.issues.length > 0 && <details className="timeline-issues">
                  <summary>Planning issues ({timelinePlan.issues.filter((issue) => issue.severity === "blocking").length} blocking, {timelinePlan.issues.filter((issue) => issue.severity === "warning").length} warnings)</summary>
                  <ul>{timelinePlan.issues.map((issue, index) => <li key={`${issue.code}-${index}`}>
                    <strong>{issue.severity === "blocking" ? "Blocking: " : "Warning: "}</strong>
                    {issue.segment_ids[0]
                      ? <button type="button" className="issue-link" onClick={() => locateReadinessSegment(issue.segment_ids[0])}>{issue.message}</button>
                      : issue.message}
                  </li>)}</ul>
                </details>}
                {timelinePlan.stretch_operations.length > 0 && <div className="timeline-operations">
                  <details>
                  <summary>Planned stretch operations ({timelinePlan.stretch_operations.length})</summary>
                  <ol>{timelinePlan.stretch_operations.map((operation) => {
                    const timing = timelinePlan.segments.find((item) => item.segment_id === operation.segment_id);
                    return <li key={`${operation.operation_order}-${operation.segment_id}`}>
                      <button type="button" className="issue-link" onClick={() => locateReadinessSegment(operation.segment_id)}>
                        Segment {timing?.position === undefined ? operation.operation_order : timing.position + 1}
                      </button>
                      <span> {formatTimestamp(operation.source_start_ms / 1000)}–{formatTimestamp(operation.source_end_ms / 1000)} · {operation.stretch_factor.toFixed(3)}× · +{operation.added_duration_ms} ms</span>
                      {timing && <span> · Output audio {formatTimestamp(timing.output_audio_start_ms / 1000)}–{formatTimestamp(timing.output_audio_end_ms / 1000)}</span>}
                    </li>;
                  })}</ol>
                  </details>
                </div>}
                {canAnalyzeTimeline && job?.status !== "queued" && optimizableTimeline && <button
                  type="button" className="tts-start-button"
                  onClick={() => void optimizeTtsDuration(selectedProject)}
                  disabled={enqueueingProjects[selectedProject.id]}
                >
                  {enqueueingProjects[selectedProject.id] ? "Queuing optimization…" : "Optimize TTS duration"}
                </button>}
                {!timelinePlan.renderable && timelinePlan.blocking_issue_count > 0 && job?.status === "succeeded" && <p className="state-message">Optimization only changes generated audio. Edit Vietnamese translations above if conflicts remain.</p>}
              </>}
            </section>}
          </aside>
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

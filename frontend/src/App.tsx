import { ChangeEvent, FormEvent, useEffect, useState } from "react";

type Project = {
  id: string;
  name: string;
  status: string;
  source_media_reference: string | null;
  created_at: string;
};

type ApiError = {
  detail?: string;
};

const MAX_FILE_SIZE = 100 * 1024 * 1024;

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

function App() {
  const [projects, setProjects] = useState<Project[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [name, setName] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  async function loadProjects() {
    setIsLoading(true);
    setError(null);

    try {
      const response = await fetch("/api/projects");
      if (!response.ok) {
        throw new Error(await readError(response));
      }

      setProjects((await response.json()) as Project[]);
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : "Unable to load projects.");
    } finally {
      setIsLoading(false);
    }
  }

  useEffect(() => {
    void loadProjects();
  }, []);

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
                <div>
                  <h3>{project.name}</h3>
                  <p>Created {formatDate(project.created_at)}</p>
                </div>
                <div className="project-meta">
                  <span className={`status-badge status-${project.status}`}>{project.status.replaceAll("_", " ")}</span>
                  <span className="source-state">{project.source_media_reference ? "Source uploaded" : "No source media"}</span>
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

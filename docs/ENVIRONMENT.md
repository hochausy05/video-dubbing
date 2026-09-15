# AutoDub Development Environment

## Scope

This file records facts verified during `INIT-04` and `ENV-00` plus explicit environment decisions. It does not prove that application dependencies or the full pipeline work.

## Verified machine and tools

| Item | Verified value |
| --- | --- |
| Operating system | Windows |
| CPU | Intel Core i5-12500H; 12 cores, 16 threads |
| RAM | 15.73 GB |
| GPU | NVIDIA GeForce RTX 3060 Laptop GPU; 6144 MiB VRAM |
| NVIDIA driver | 552.44 |
| System/default Python | 3.14.2 |
| Selected backend Python | 3.11 at `C:\Users\hocha\AppData\Local\Programs\Python\Python311\python.exe` |
| Node.js | 22.19.0 |
| npm | 11.6.0 |
| FFmpeg/ffprobe | 8.1.2 full build; available in `PATH` |
| Detected hardware encoders | `h264_nvenc`, `hevc_nvenc` |
| Project drive | D |
| Free space at `ENV-00` | About 27 GB |

## Decisions

- Create the backend virtual environment with Python 3.11; do not use system Python 3.14.2 for this project.
- Run the API and worker directly on Windows; WSL is not required for the MVP.
- Process one video job at a time.
- Start Whisper evaluation with model `small`.
- Prefer `h264_nvenc` when verified at render time; keep a CPU fallback.
- Keep the project on drive D and maintain about 10 GB free during development.
- For `DATA-01`, use Supabase-hosted PostgreSQL through SQLAlchemy and a PostgreSQL driver. Supply its `DATABASE_URL` through uncommitted backend/worker environment configuration only.

## Ready for upcoming tasks

- Python 3.11 is available for `ENV-01`/`ENV-03` setup.
- Node.js and npm are available for `ENV-02`/`ENV-03` setup.
- FFmpeg and ffprobe are in `PATH`; the build advertises NVIDIA encoders.
- Current drive capacity is sufficient to start the MVP.

## Not yet verified

- `.venv`, project packages, and Whisper model are not yet installed by the recorded environment tasks.
- faster-whisper/Whisper has not run on the GPU; GPU support must not be claimed before `ASR-01` evidence.
- Gemini, Edge-TTS, and end-to-end performance remain unverified. The configured MP4 upload limits are documented in `docs/PRD.md`; UPLOAD-02 must verify enforcement through the FastAPI endpoint.
- Detected NVENC support does not prove every render command will succeed.
- Supabase connection and DATA-01 persistence verification completed using the ignored local `DATABASE_URL`; future environment or credential changes require a fresh connection check.

## Resource guardrail

Monitor drive D before model downloads and media processing. Intermediate audio/video can multiply source size. Stop and free targeted, known-safe data if available capacity approaches the 10 GB reserve; never use broad cleanup commands.

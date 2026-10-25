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
- RENDER-01 currently uses FFmpeg `libx264` CPU encoding for predictable availability. NVENC encoder presence is not treated as verified runtime support; no GPU rendering path is claimed.
- AUDIO-01 render requests default to Auto Ducking (background gain `0.35`, ducked gain `0.08`, TTS gain `1.0`, 80 ms attack, 250 ms release, 350 ms bridge). Gains are bounded to `0`–`1`; `RENDER_ORIGINAL_AUDIO_GAIN` remains the compatibility default for legacy clients that omit render settings (default `0.10`). The final FFmpeg `alimiter` uses a 0.95 ceiling. Auto Ducking lowers the entire original soundtrack and does not separate voices.
- Keep the project on drive D and maintain about 10 GB free during development.
- For `DATA-01`, use Supabase-hosted PostgreSQL through SQLAlchemy and a PostgreSQL driver. Supply its `DATABASE_URL` through uncommitted backend/worker environment configuration only.
- TTS-01 pins `edge-tts==7.3.1`, defaults to Vietnamese voice `vi-VN-HoaiMyNeural`, and bounds concurrent Segment requests to five. `EDGE_TTS_VOICE` and `EDGE_TTS_CONCURRENCY` are optional backend/worker settings.

## Ready for upcoming tasks

- Python 3.11 is available for `ENV-01`/`ENV-03` setup.
- Node.js and npm are available for `ENV-02`/`ENV-03` setup.
- FFmpeg and ffprobe are in `PATH`; the build advertises NVIDIA encoders.
- Current drive capacity is sufficient to start the MVP.
- `faster-whisper==1.2.1` is installed in the Python 3.11 backend environment. Real inference with model `small` succeeded on CPU using compute type `int8`.
- `google-genai==2.28.0` is installed in the Python 3.11 backend environment. The configured `gemini-3.8-flash` model completed a real structured Vietnamese translation request and persisted all four Segment translations to Supabase; no credential value is recorded here.
- `edge-tts==7.3.1` generated a real sample with `vi-VN-HoaiMyNeural`; FFprobe measured the sample at 3,480 ms. This verifies the standalone voice/service, not persisted Project processing or browser playback.
- TTS-03 optimization is bounded by `TTS_OPTIMIZATION_MAX_RATE_PERCENT` (default 35; allowed 20–35) and `TTS_OPTIMIZATION_MAX_ATTEMPTS` (default 4; allowed 1–4). No new dependency is required.

## Not yet verified

- CUDA Whisper inference was attempted on the RTX 3060 but failed because `cublas64_12.dll` was unavailable to CTranslate2; the worker logged the failure and completed real CPU `int8` inference. GPU inference remains unverified and is not claimed.
- TTS-01 persisted worker generation, per-Segment browser playback, measured duration display and refresh persistence, and TTS-02 timeline analysis were manually accepted on `demo2`. TTS-03's real optimization worker/API/browser flow remains pending manual acceptance. No end-to-end performance claim is made. The configured MP4 upload limits are documented in `docs/PRD.md`; UPLOAD-02 must verify enforcement through the FastAPI endpoint.
- Detected NVENC support does not prove every render command will succeed.
- RENDER-01 rendering, preview, download and refresh were manually accepted by the user on `demo2`; planned and verified output durations were both 23,681 ms. AUDIO-01 has not yet been manually listened to on a real Project; its implementation verification uses synthetic media and local test storage only, and no demo2 media or data was changed.
- Supabase connection and DATA-01 persistence verification completed using the ignored local `DATABASE_URL`; future environment or credential changes require a fresh connection check.

## Resource guardrail

Monitor drive D before model downloads and media processing. Intermediate audio/video can multiply source size. Stop and free targeted, known-safe data if available capacity approaches the 10 GB reserve; never use broad cleanup commands.

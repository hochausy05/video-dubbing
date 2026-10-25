-- AUDIO-01: persist validated per-render mix settings for the independent worker.
ALTER TABLE public.autodub_jobs
    ADD COLUMN IF NOT EXISTS audio_settings json;

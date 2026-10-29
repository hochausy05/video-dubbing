-- AV-SYNC-02: persist the bounded optimization result and allow its +25% TTS candidate.
ALTER TABLE public.autodub_jobs
    ADD COLUMN IF NOT EXISTS result_json json;

ALTER TABLE public.autodub_artifacts
    DROP CONSTRAINT IF EXISTS ck_autodub_artifacts_rate_range;

ALTER TABLE public.autodub_artifacts
    ADD CONSTRAINT ck_autodub_artifacts_rate_range
    CHECK (rate_percent IS NULL OR rate_percent IN (0, 6, 12, 14, 20, 22, 25, 35));

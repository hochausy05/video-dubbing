-- TTS-01: additive nullable metadata for per-Segment generated audio.
ALTER TABLE public.autodub_artifacts
    ADD COLUMN IF NOT EXISTS segment_id uuid
        REFERENCES public.autodub_segments(id) ON DELETE CASCADE,
    ADD COLUMN IF NOT EXISTS duration_ms integer,
    ADD COLUMN IF NOT EXISTS provenance_fingerprint varchar(64),
    ADD COLUMN IF NOT EXISTS voice varchar(255),
    ADD COLUMN IF NOT EXISTS rate_percent integer;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'ck_autodub_artifacts_duration_positive'
    ) THEN
        ALTER TABLE public.autodub_artifacts
            ADD CONSTRAINT ck_autodub_artifacts_duration_positive
            CHECK (duration_ms IS NULL OR duration_ms > 0);
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'ck_autodub_artifacts_rate_range'
    ) THEN
        ALTER TABLE public.autodub_artifacts
            ADD CONSTRAINT ck_autodub_artifacts_rate_range
            CHECK (rate_percent IS NULL OR rate_percent IN (0, 6, 12, 20));
    END IF;
END $$;

CREATE INDEX IF NOT EXISTS ix_autodub_artifacts_segment_current
    ON public.autodub_artifacts (project_id, segment_id, created_at DESC)
    WHERE is_current = true;

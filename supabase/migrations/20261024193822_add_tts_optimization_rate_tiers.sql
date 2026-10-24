-- Expand only the persisted Edge-TTS rate allow-list; existing Artifact rows are unchanged.
ALTER TABLE public.autodub_artifacts
    DROP CONSTRAINT IF EXISTS ck_autodub_artifacts_rate_range;

ALTER TABLE public.autodub_artifacts
    ADD CONSTRAINT ck_autodub_artifacts_rate_range
    CHECK (rate_percent IS NULL OR rate_percent IN (0, 6, 12, 14, 20, 22, 35));

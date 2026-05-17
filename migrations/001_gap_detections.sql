-- Gap Detection Agent — Supabase Schema
-- Run once against project mbkstodswexxvdgyunio

CREATE TABLE IF NOT EXISTS gap_detections (
  id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  project_name     TEXT NOT NULL,
  gap_category     TEXT NOT NULL,  -- integration | security | feature | schema | deployment | error_handling
  gap_description  TEXT NOT NULL,
  severity         TEXT NOT NULL CHECK (severity IN ('critical','high','medium','low')),
  status           TEXT NOT NULL DEFAULT 'open' CHECK (status IN ('open','acknowledged','in_progress','resolved')),
  notes            TEXT,
  created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at       TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_gap_detections_project ON gap_detections (project_name);
CREATE INDEX IF NOT EXISTS idx_gap_detections_status  ON gap_detections (status);
CREATE INDEX IF NOT EXISTS idx_gap_detections_created ON gap_detections (created_at DESC);

-- Unique constraint so re-scans don't double-log open gaps
CREATE UNIQUE INDEX IF NOT EXISTS idx_gap_dedup
  ON gap_detections (project_name, gap_description)
  WHERE status IN ('open','acknowledged','in_progress');

-- Auto-update updated_at
CREATE OR REPLACE FUNCTION touch_updated_at()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN NEW.updated_at = NOW(); RETURN NEW; END; $$;

DROP TRIGGER IF EXISTS trg_gap_updated_at ON gap_detections;
CREATE TRIGGER trg_gap_updated_at
  BEFORE UPDATE ON gap_detections
  FOR EACH ROW EXECUTE FUNCTION touch_updated_at();

-- RLS: service role bypasses; no public read
ALTER TABLE gap_detections ENABLE ROW LEVEL SECURITY;
CREATE POLICY "service role full access" ON gap_detections
  USING (auth.role() = 'service_role')
  WITH CHECK (auth.role() = 'service_role');

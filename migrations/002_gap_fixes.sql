-- Migration 002: auto-heal tracking
-- Add auto_executed flag to gap_detections
ALTER TABLE gap_detections
  ADD COLUMN IF NOT EXISTS auto_executed BOOLEAN NOT NULL DEFAULT FALSE;

-- Track every fix attempt: code executed, rollback script, outcome
CREATE TABLE IF NOT EXISTS gap_fixes (
  id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  gap_detection_id  UUID NOT NULL REFERENCES gap_detections(id) ON DELETE CASCADE,
  fix_type          TEXT NOT NULL, -- railway_redeploy | sql_migration | env_update | manual_only
  fix_code          TEXT NOT NULL,
  rollback_script   TEXT NOT NULL,
  validation_log    JSONB,         -- pre/post smoke test results
  status            TEXT NOT NULL DEFAULT 'pending'
                    CHECK (status IN ('pending','executing','success','failed','rolled_back')),
  failure_reason    TEXT,
  executed_at       TIMESTAMPTZ,
  rolled_back_at    TIMESTAMPTZ,
  created_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at        TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_gap_fixes_gap  ON gap_fixes (gap_detection_id);
CREATE INDEX IF NOT EXISTS idx_gap_fixes_stat ON gap_fixes (status);

DROP TRIGGER IF EXISTS trg_gap_fix_updated_at ON gap_fixes;
CREATE TRIGGER trg_gap_fix_updated_at
  BEFORE UPDATE ON gap_fixes
  FOR EACH ROW EXECUTE FUNCTION touch_updated_at();

ALTER TABLE gap_fixes ENABLE ROW LEVEL SECURITY;
CREATE POLICY "service role full access" ON gap_fixes
  USING (auth.role() = 'service_role')
  WITH CHECK (auth.role() = 'service_role');

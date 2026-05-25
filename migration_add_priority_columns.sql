-- ============================================================
-- migration_add_priority_columns.sql
-- Run this ONCE on your PostgreSQL database before deploying.
-- ============================================================

-- 1. Add importance_override column to task table
--    Students can set their own importance (1.0 – 10.0)
--    NULL means "use the category default"
ALTER TABLE task
    ADD COLUMN IF NOT EXISTS importance_override NUMERIC(4, 2) NULL;

-- 2. Add priority_score column (calculated by the engine, stored for fast reads)
ALTER TABLE task
    ADD COLUMN IF NOT EXISTS priority_score NUMERIC(6, 4) NULL;

-- 3. Add quadrant column (DO FIRST / SCHEDULE / DELEGATE / ELIMINATE)
ALTER TABLE task
    ADD COLUMN IF NOT EXISTS quadrant VARCHAR(20) NULL;

-- 4. Add scored_at column (timestamp when priority was last calculated)
ALTER TABLE task
    ADD COLUMN IF NOT EXISTS scored_at TIMESTAMP NULL;

-- 5. Add completed_at column (timestamp when student marked task as done)
--    Needed for behaviour scoring
ALTER TABLE task
    ADD COLUMN IF NOT EXISTS completed_at TIMESTAMP NULL;

-- 6. Create an index on (student_id, status) for fast filtering
CREATE INDEX IF NOT EXISTS idx_task_student_status
    ON task (student_id, status);

-- 7. Create an index on priority_score for fast ordering
CREATE INDEX IF NOT EXISTS idx_task_priority_score
    ON task (priority_score DESC);

-- ============================================================
-- Verify the changes
-- ============================================================
SELECT column_name, data_type, is_nullable
FROM information_schema.columns
WHERE table_name = 'task'
ORDER BY ordinal_position;

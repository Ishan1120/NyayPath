-- =====================================================================
-- NyayPath Migration: 20261102000001_concurrent_meeting_exclusion.sql
-- Phase 6.1: Atomic Database-Level Protection Against Concurrent Meeting Double-Booking
-- =====================================================================

-- 1. Ensure btree_gist extension is installed to enable GiST indexing on UUID and timestamps
CREATE EXTENSION IF NOT EXISTS btree_gist;

-- 2. Add Exclusion Constraint on consultation_meetings
-- Prevents overlapping confirmed appointment intervals for the same advocate
-- Time interval: [scheduled_start, scheduled_end)
-- Status: strictly enforced when status = 'CONFIRMED'
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'exclude_overlapping_confirmed_meetings'
    ) THEN
        ALTER TABLE public.consultation_meetings
        ADD CONSTRAINT exclude_overlapping_confirmed_meetings
        EXCLUDE USING gist (
            lawyer_user_id WITH =,
            tstzrange(scheduled_start, scheduled_end, '[)') WITH &&
        )
        WHERE (status = 'CONFIRMED');
    END IF;
END $$;


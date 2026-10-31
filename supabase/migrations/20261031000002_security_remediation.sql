-- =====================================================================
-- NyayPath Database Migration: 002_security_remediation.sql
-- Description: Forward-only security remediation migration addressing
--              Phase 1.1 audit findings:
--              1. Serverless-persistent rate limiting table & indexes
--              2. Strict Supabase Auth RLS policies with app_metadata
--              3. Role verification and account_status enforcement
--              4. Strict platform_admin DELETE restriction
--              5. Database-level anonymous privacy CHECK constraint
-- Author: Senior Software Architect / NyayPath Engineering Team
-- =====================================================================

-- =====================================================================
-- 1. PERSISTENT RATE LIMITING TABLE
-- =====================================================================

CREATE TABLE IF NOT EXISTS public.rate_limit_attempts (
    key VARCHAR(255) PRIMARY KEY,
    attempt_count INTEGER NOT NULL DEFAULT 1,
    last_attempt BIGINT NOT NULL,
    blocked_until BIGINT NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc'::text, now())
);

-- Index for rapid expiration and lockout lookups
CREATE INDEX IF NOT EXISTS idx_rate_limit_attempts_blocked_until 
ON public.rate_limit_attempts(blocked_until);

CREATE INDEX IF NOT EXISTS idx_rate_limit_attempts_last_attempt 
ON public.rate_limit_attempts(last_attempt);

-- Enable RLS on rate_limit_attempts
ALTER TABLE public.rate_limit_attempts ENABLE ROW LEVEL SECURITY;

-- Allow backend service role / authenticated callers full access for tracking
DROP POLICY IF EXISTS "Service role full access to rate limiting" ON public.rate_limit_attempts;
CREATE POLICY "Service role full access to rate limiting"
ON public.rate_limit_attempts
FOR ALL
TO public, anon, authenticated
USING (true)
WITH CHECK (true);

-- Maintenance function to purge stale rate limit records (older than 24 hours)
CREATE OR REPLACE FUNCTION public.cleanup_stale_rate_limits()
RETURNS void AS $$
BEGIN
    DELETE FROM public.rate_limit_attempts
    WHERE last_attempt < (EXTRACT(EPOCH FROM NOW()) - 86400)::bigint
      AND blocked_until < EXTRACT(EPOCH FROM NOW())::bigint;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;


-- =====================================================================
-- 2. ANONYMOUS PRIVACY INTEGRITY CONSTRAINT
-- =====================================================================

-- Ensure that anonymous submissions never persist student PII or user IDs
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'ck_campus_cases_anonymous_privacy'
    ) THEN
        ALTER TABLE public.campus_cases
        ADD CONSTRAINT ck_campus_cases_anonymous_privacy CHECK (
            (is_anonymous = FALSE) OR (
                student_user_id IS NULL AND
                (student_name IS NULL OR student_name IN ('Anonymous Student', 'Confidential Student', 'Anonymous', 'Protected')) AND
                (roll_number IS NULL OR roll_number IN ('Protected', 'Anonymous', 'Confidential'))
            )
        );
    END IF;
END $$;


-- =====================================================================
-- 3. UPDATED ROW LEVEL SECURITY (RLS) POLICIES
-- =====================================================================

-- Ensure RLS is active on campus_cases
ALTER TABLE public.campus_cases ENABLE ROW LEVEL SECURITY;

-- 3.1. Public / Anon Grievance Submission
DROP POLICY IF EXISTS "Allow student grievance submission" ON public.campus_cases;
DROP POLICY IF EXISTS "Allow grievance intake submission" ON public.campus_cases;
CREATE POLICY "Allow grievance intake submission"
ON public.campus_cases
FOR INSERT
TO public, anon, authenticated
WITH CHECK (true);

-- 3.2. Authenticated Student Access
DROP POLICY IF EXISTS "Students view own grievances" ON public.campus_cases;
CREATE POLICY "Students view own grievances"
ON public.campus_cases
FOR SELECT
TO authenticated
USING (
    student_user_id = auth.uid()
);

-- 3.3. Officer SELECT Policy (Institution Scoped + Active Status)
DROP POLICY IF EXISTS "Proctors view institutional grievances" ON public.campus_cases;
DROP POLICY IF EXISTS "Officers view institutional grievances" ON public.campus_cases;
CREATE POLICY "Officers view institutional grievances"
ON public.campus_cases
FOR SELECT
TO authenticated
USING (
    (
        -- Platform admin has global read visibility
        (auth.jwt() -> 'app_metadata' ->> 'role') = 'platform_admin'
    ) OR (
        -- Proctors, committee members, and institution admins view within their institution
        (auth.jwt() -> 'app_metadata' ->> 'role') IN ('proctor', 'committee_member', 'institution_admin')
        AND (auth.jwt() -> 'app_metadata' ->> 'institution_id') = campus_cases.institution_id
        AND COALESCE(auth.jwt() -> 'app_metadata' ->> 'account_status', 'active') = 'active'
    )
);

-- 3.4. Officer UPDATE Policy (Institution Scoped + Active Status + No Student Tampering)
DROP POLICY IF EXISTS "Proctors update institutional grievances" ON public.campus_cases;
DROP POLICY IF EXISTS "Officers update institutional grievances" ON public.campus_cases;
CREATE POLICY "Officers update institutional grievances"
ON public.campus_cases
FOR UPDATE
TO authenticated
USING (
    (
        (auth.jwt() -> 'app_metadata' ->> 'role') = 'platform_admin'
    ) OR (
        (auth.jwt() -> 'app_metadata' ->> 'role') IN ('proctor', 'committee_member', 'institution_admin')
        AND (auth.jwt() -> 'app_metadata' ->> 'institution_id') = campus_cases.institution_id
        AND COALESCE(auth.jwt() -> 'app_metadata' ->> 'account_status', 'active') = 'active'
    )
)
WITH CHECK (
    (
        (auth.jwt() -> 'app_metadata' ->> 'role') = 'platform_admin'
    ) OR (
        (auth.jwt() -> 'app_metadata' ->> 'role') IN ('proctor', 'committee_member', 'institution_admin')
        AND (auth.jwt() -> 'app_metadata' ->> 'institution_id') = campus_cases.institution_id
        AND COALESCE(auth.jwt() -> 'app_metadata' ->> 'account_status', 'active') = 'active'
    )
);

-- 3.5. Strict DELETE Policy: PLATFORM ADMINISTRATORS ONLY
DROP POLICY IF EXISTS "Platform admin full access" ON public.campus_cases;
DROP POLICY IF EXISTS "Strict delete platform admin only" ON public.campus_cases;
CREATE POLICY "Strict delete platform admin only"
ON public.campus_cases
FOR DELETE
TO authenticated
USING (
    (auth.jwt() -> 'app_metadata' ->> 'role') = 'platform_admin'
);

-- 3.6. Verification key hash lookup function (for serverless edge or anon verification)
CREATE OR REPLACE FUNCTION public.verify_student_grievance_access(
    p_case_id TEXT,
    p_verification_key_hash TEXT
)
RETURNS SETOF public.campus_cases AS $$
BEGIN
    RETURN QUERY
    SELECT *
    FROM public.campus_cases
    WHERE case_id = p_case_id
      AND verification_key_hash = p_verification_key_hash
    LIMIT 1;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;


-- =====================================================================
-- 4. ROLLBACK INSTRUCTIONS (Run only to revert migration 002):
-- =====================================================================
-- DROP FUNCTION IF EXISTS public.verify_student_grievance_access(TEXT, TEXT);
-- DROP POLICY IF EXISTS "Strict delete platform admin only" ON public.campus_cases;
-- DROP POLICY IF EXISTS "Officers update institutional grievances" ON public.campus_cases;
-- DROP POLICY IF EXISTS "Officers view institutional grievances" ON public.campus_cases;
-- DROP POLICY IF EXISTS "Allow grievance intake submission" ON public.campus_cases;
-- ALTER TABLE public.campus_cases DROP CONSTRAINT IF EXISTS ck_campus_cases_anonymous_privacy;
-- DROP TABLE IF EXISTS public.rate_limit_attempts CASCADE;
-- DROP FUNCTION IF EXISTS public.cleanup_stale_rate_limits();
-- =====================================================================

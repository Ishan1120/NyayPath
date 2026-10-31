-- =====================================================================
-- NyayPath Database Migration: 003_rate_limit_security_fix.sql
-- Phase: 1.3.4 Security Remediation
-- Description:
--   Forward-only correction for the overly permissive RLS policy on
--   public.rate_limit_attempts introduced in migration 002.
--
--   Migration 002 created the following policy (lines 36-42):
--
--     CREATE POLICY "Service role full access to rate limiting"
--     ON public.rate_limit_attempts FOR ALL
--     TO public, anon, authenticated
--     USING (true) WITH CHECK (true);
--
--   This policy allowed any anonymous or authenticated browser client to
--   directly READ or RESET their own rate-limiting state, completely
--   defeating the purpose of rate limiting.
--
-- Correction:
--   - Drop the permissive policy.
--   - Revoke all direct table access from anon, authenticated, and PUBLIC.
--   - Grant only the minimum required privileges to service_role.
--   - Ensure rate_limit_attempts is only accessible from the FastAPI
--     backend (which uses SUPABASE_SECRET_KEY / service_role client).
--   - Harden the cleanup_stale_rate_limits() function with SET search_path.
--   - Move cleanup_stale_rate_limits() to private schema (non-PostgREST-
--     exposed) to prevent direct HTTP RPC invocation.
--
-- Safety: This migration is forward-only and idempotent.
--         It may be applied whether or not migration 002 has been run.
--         IF migration 002 was never applied, this migration still
--         produces the correct final state (DROP IF EXISTS is safe).
--
-- Rollback: See ROLLBACK INSTRUCTIONS at the bottom.
-- =====================================================================

-- Ensure RLS is enabled (idempotent)
ALTER TABLE public.rate_limit_attempts ENABLE ROW LEVEL SECURITY;

-- =====================================================================
-- 1. REMOVE THE OVERLY PERMISSIVE POLICY
-- =====================================================================

DROP POLICY IF EXISTS "Service role full access to rate limiting"
    ON public.rate_limit_attempts;

-- Drop any other permissive policies that may have been created
DROP POLICY IF EXISTS "Rate limiting service access"
    ON public.rate_limit_attempts;
DROP POLICY IF EXISTS "Allow rate limit access"
    ON public.rate_limit_attempts;

-- =====================================================================
-- 2. REVOKE DIRECT TABLE ACCESS FROM BROWSER ROLES
-- =====================================================================
-- anon: the Supabase anonymous/publishable-key role (browser clients)
-- authenticated: Supabase Auth users (browser clients)
-- PUBLIC: default PostgreSQL role granted to all (belt-and-suspenders)

REVOKE ALL PRIVILEGES ON public.rate_limit_attempts FROM PUBLIC;
REVOKE ALL PRIVILEGES ON public.rate_limit_attempts FROM anon;
REVOKE ALL PRIVILEGES ON public.rate_limit_attempts FROM authenticated;

-- =====================================================================
-- 3. GRANT MINIMUM REQUIRED PRIVILEGES TO service_role ONLY
-- =====================================================================
-- The FastAPI backend uses SUPABASE_SECRET_KEY (service_role) to
-- manage rate limiting state. The following operations are required:
--   SELECT: check existing rate limit state
--   INSERT: create new rate limit record on first attempt
--   UPDATE: increment attempt count, set blocked_until
--   DELETE: reset limit on successful login
-- TRUNCATE is NOT granted (maintenance uses DELETE WHERE, not TRUNCATE).
-- REFERENCES, TRIGGER are NOT granted (not required for application use).

GRANT SELECT, INSERT, UPDATE, DELETE
    ON public.rate_limit_attempts
    TO service_role;

-- =====================================================================
-- 4. NO RLS POLICIES NEEDED FOR service_role
-- =====================================================================
-- In Supabase PostgreSQL, the service_role bypasses RLS by default.
-- Therefore, no USING/WITH CHECK policies are required for service_role.
-- Browser clients (anon/authenticated) have no grants, so they cannot
-- reach this table regardless of any RLS policy configuration.

-- =====================================================================
-- 4.1. REVOKE DIRECT ANONYMOUS INSERT ON public.campus_cases (Task 1)
-- =====================================================================
-- Direct anonymous table INSERT via PostgREST is unnecessary and dangerous:
-- it bypasses FastAPI field validation, rate limiting, and server-side HMAC hashing.
-- All grievance submissions are mediated exclusively by the FastAPI backend
-- (POST /api/campus-proctor/submit) using the privileged service_role client.

REVOKE INSERT ON public.campus_cases FROM PUBLIC;
REVOKE INSERT ON public.campus_cases FROM anon;

-- Drop permissive intake insertion policies
DROP POLICY IF EXISTS "Allow student grievance submission" ON public.campus_cases;
DROP POLICY IF EXISTS "Allow grievance intake submission" ON public.campus_cases;

-- =====================================================================
-- 5. MOVE cleanup_stale_rate_limits() TO NON-EXPOSED private SCHEMA
-- =====================================================================
-- The function in migration 002 was placed in the public schema and lacked
-- SET search_path = ''. Moving it into an internal 'private' schema ensures
-- PostgREST never surfaces it in its public HTTP RPC registry.
-- Explicitly revoking EXECUTE from anon and authenticated eliminates
-- any possibility of client-triggered rate-limiter maintenance.

CREATE SCHEMA IF NOT EXISTS private;
REVOKE ALL PRIVILEGES ON SCHEMA private FROM PUBLIC;
REVOKE ALL PRIVILEGES ON SCHEMA private FROM anon;
REVOKE ALL PRIVILEGES ON SCHEMA private FROM authenticated;
GRANT USAGE ON SCHEMA private TO service_role;

-- Drop legacy public function from migration 002
DROP FUNCTION IF EXISTS public.cleanup_stale_rate_limits();

CREATE OR REPLACE FUNCTION private.cleanup_stale_rate_limits()
RETURNS void
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = ''
AS $$
BEGIN
    DELETE FROM public.rate_limit_attempts
    WHERE last_attempt < (EXTRACT(EPOCH FROM NOW()) - 86400)::bigint
      AND blocked_until < EXTRACT(EPOCH FROM NOW())::bigint;
END;
$$;

-- Restrict execution exclusively to service_role
REVOKE EXECUTE ON FUNCTION private.cleanup_stale_rate_limits() FROM PUBLIC;
GRANT EXECUTE ON FUNCTION private.cleanup_stale_rate_limits() TO service_role;

-- =====================================================================
-- 6. REMOVE PUBLIC TRACKING RPC & ISOLATE IN private SCHEMA (Task 2)
-- =====================================================================
-- Migration 002 exposed public.verify_student_grievance_access() to anon
-- and authenticated roles via PostgREST HTTP RPC. This allowed browser
-- clients to invoke direct RPC endpoints without rate limiting.
--
-- Secure remediation:
--   - Revoke EXECUTE from PUBLIC, anon, and authenticated.
--   - Drop the function from public schema so PostgREST RPC cannot expose it.
--   - Move internal verification functionality into non-exposed 'private' schema.
--   - Student tracking verification is strictly enforced through FastAPI,
--     which enforces persistent rate limiting BEFORE querying the database.

DROP FUNCTION IF EXISTS public.verify_student_grievance_access(TEXT, TEXT);

CREATE OR REPLACE FUNCTION private.verify_case_tracking(
    p_case_id TEXT,
    p_verification_key_hash TEXT
)
RETURNS boolean
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = ''
AS $$
BEGIN
    RETURN EXISTS (
        SELECT 1
        FROM public.campus_cases
        WHERE case_id = p_case_id
          AND verification_key_hash = p_verification_key_hash
    );
END;
$$;

-- Restrict execution exclusively to service_role (backend only)
REVOKE ALL PRIVILEGES ON FUNCTION private.verify_case_tracking(TEXT, TEXT) FROM PUBLIC;
REVOKE ALL PRIVILEGES ON FUNCTION private.verify_case_tracking(TEXT, TEXT) FROM anon;
REVOKE ALL PRIVILEGES ON FUNCTION private.verify_case_tracking(TEXT, TEXT) FROM authenticated;
GRANT EXECUTE ON FUNCTION private.verify_case_tracking(TEXT, TEXT) TO service_role;


-- =====================================================================
-- VERIFICATION QUERIES (run manually after applying migration):
-- =====================================================================
-- Confirm no permissive policy remains:
--   SELECT policyname, roles, cmd, qual, with_check
--   FROM pg_policies
--   WHERE tablename = 'rate_limit_attempts';
--   --> Expected: 0 rows (no policies; service_role bypasses RLS)
--
-- Confirm grants:
--   SELECT grantee, privilege_type
--   FROM information_schema.role_table_grants
--   WHERE table_name = 'rate_limit_attempts'
--   ORDER BY grantee, privilege_type;
--   --> Expected: service_role has SELECT, INSERT, UPDATE, DELETE only
--
-- Confirm anon cannot select:
--   SET ROLE anon;
--   SELECT count(*) FROM public.rate_limit_attempts;
--   --> Expected: ERROR: permission denied for table rate_limit_attempts
--   RESET ROLE;


-- =====================================================================
-- ROLLBACK INSTRUCTIONS (run only to revert migration 003):
-- =====================================================================
-- -- Restore the old (insecure) policy from migration 002:
-- CREATE POLICY "Service role full access to rate limiting"
-- ON public.rate_limit_attempts FOR ALL
-- TO public, anon, authenticated
-- USING (true) WITH CHECK (true);
--
-- -- Restore grants (warning: this restores the vulnerability):
-- GRANT SELECT, INSERT, UPDATE, DELETE ON public.rate_limit_attempts TO anon;
-- GRANT SELECT, INSERT, UPDATE, DELETE ON public.rate_limit_attempts TO authenticated;
-- =====================================================================


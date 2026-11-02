-- =============================================================================
-- Migration: 20261102000003_verified_lawyers_and_privilege_hardening.sql
-- Description: Forward-only hardening for public.verified_lawyers view and table
--              privileges on public.platform_audit_logs.
-- 1. Sets security_invoker = true on verified_lawyers so PostgREST queries enforce RLS.
-- 2. Excludes private personal contact fields (email, phone) from the public directory.
-- 3. Explicitly revokes all table privileges from PUBLIC, anon, and authenticated,
--    granting only SELECT to anon and authenticated.
-- 4. Cleans up excess table privileges on platform_audit_logs to prevent unauthorized
--    TRUNCATE, UPDATE, or DELETE grants from default privileges.
-- =============================================================================

-- 1. Recreate verified_lawyers view with security_invoker = true and privacy protection
DROP VIEW IF EXISTS public.verified_lawyers CASCADE;

CREATE VIEW public.verified_lawyers
WITH (security_invoker = true)
AS
SELECT 
    id,
    full_name,
    bar_council,
    enrollment_state,
    years_of_practice,
    specializations,
    courts,
    languages,
    bio,
    consultation_preferences,
    photo_url,
    verification_status,
    created_at
FROM public.lawyer_profiles
WHERE verification_status = 'VERIFIED';

-- 2. Explicit privilege hygiene for verified_lawyers view
REVOKE ALL PRIVILEGES ON public.verified_lawyers FROM PUBLIC, anon, authenticated;
GRANT SELECT ON public.verified_lawyers TO anon, authenticated, service_role;

-- 3. Explicit privilege hygiene on platform_audit_logs
-- Ensure untrusted roles cannot TRUNCATE, UPDATE, or DELETE audit records
REVOKE ALL PRIVILEGES ON public.platform_audit_logs FROM PUBLIC, anon, authenticated;
GRANT SELECT, INSERT ON public.platform_audit_logs TO authenticated;
GRANT ALL PRIVILEGES ON public.platform_audit_logs TO service_role;

-- 4. Permit policy evaluation of is_platform_admin for anon role
GRANT EXECUTE ON FUNCTION private.is_platform_admin() TO anon;
GRANT EXECUTE ON FUNCTION private.is_platform_admin(UUID) TO anon;


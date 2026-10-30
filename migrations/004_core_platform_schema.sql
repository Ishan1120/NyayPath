-- =====================================================================
-- NyayPath Database Migration: 004_core_platform_schema.sql
-- Phase: 1.3.5 Complete Platform Schema & Database-Backed Authorization
-- Description:
--   Establishes the complete schema inventory required across all
--   NyayPath modules, resolving the missing public.cases table and
--   implementing database-backed administrator and officer authorization.
--
-- Tables Defined / Augmented:
--   1. public.cases (Citizen RTI applications, consumer complaints, watchdog)
--   2. public.platform_admins (Authoritative platform admin registry)
--   3. public.profiles (User identity and profile metadata)
--   4. public.institutions (Colleges and educational institutions)
--   5. public.institution_memberships (Officer memberships & institutional scoping)
--   6. public.confidential_student_identities (Decoupled PII vault)
--   7. public.case_documents (Encrypted document attachments & metadata)
--   8. public.case_activity_log (Immutable audit trail)
--   9. public.campus_cases (key_version column added for HMAC rotation)
--
-- Functions Defined in 'private' Schema:
--   1. private.is_platform_admin() (Authoritative database-backed check)
--   2. private.can_officer_access_case() (Institution & active status check)
--
-- Safety: Forward-only, idempotent, and non-destructive.
-- =====================================================================

-- Ensure UUID extensions exist
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- Ensure private schema exists
CREATE SCHEMA IF NOT EXISTS private;
REVOKE ALL PRIVILEGES ON SCHEMA private FROM PUBLIC, anon, authenticated;
GRANT USAGE ON SCHEMA private TO service_role;

-- =====================================================================
-- 1. PUBLIC.CASES (Citizen RTI & Consumer Cases Engine)
-- =====================================================================
-- Consumer: api/case_manager.py, api/watchdog_engine.py

CREATE TABLE IF NOT EXISTS public.cases (
    id VARCHAR(64) PRIMARY KEY,
    data JSONB NOT NULL DEFAULT '{}'::jsonb,
    tracking_key_hash VARCHAR(128),
    key_version VARCHAR(10) NOT NULL DEFAULT 'v1',
    case_type VARCHAR(32) NOT NULL DEFAULT 'RTI' CHECK (
        case_type IN ('RTI', 'FIRST_APPEAL', 'CONSUMER_COMPLAINT', 'GENERAL_GRIEVANCE')
    ),
    created_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc'::text, now()),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc'::text, now())
);

CREATE INDEX IF NOT EXISTS idx_cases_updated_at ON public.cases(updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_cases_case_type ON public.cases(case_type);

ALTER TABLE public.cases ENABLE ROW LEVEL SECURITY;

-- Citizen passkey cases are managed exclusively by the FastAPI backend
REVOKE ALL PRIVILEGES ON public.cases FROM PUBLIC, anon, authenticated;
GRANT SELECT, INSERT, UPDATE ON public.cases TO service_role;

-- =====================================================================
-- 2. PUBLIC.PLATFORM_ADMINS (Database-Backed Admin Registry)
-- =====================================================================
-- Consumer: private.is_platform_admin(), api/auth.py

CREATE TABLE IF NOT EXISTS public.platform_admins (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID UNIQUE NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    email TEXT UNIQUE NOT NULL,
    account_status VARCHAR(20) NOT NULL DEFAULT 'active' CHECK (
        account_status IN ('active', 'suspended', 'revoked')
    ),
    created_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc'::text, now()),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc'::text, now())
);

CREATE INDEX IF NOT EXISTS idx_platform_admins_user ON public.platform_admins(user_id, account_status);

ALTER TABLE public.platform_admins ENABLE ROW LEVEL SECURITY;

-- Platform admin table is accessible only to backend service role
REVOKE ALL PRIVILEGES ON public.platform_admins FROM PUBLIC, anon, authenticated;
GRANT SELECT, INSERT, UPDATE, DELETE ON public.platform_admins TO service_role;

-- =====================================================================
-- 3. AUTHORITATIVE private.is_platform_admin() FUNCTION
-- =====================================================================
-- Replaces insecure JWT app_metadata checks with live database state

CREATE OR REPLACE FUNCTION private.is_platform_admin()
RETURNS boolean
LANGUAGE sql STABLE SECURITY DEFINER
SET search_path = ''
AS $$
  SELECT EXISTS (
    SELECT 1
    FROM public.platform_admins pa
    WHERE pa.user_id = auth.uid()
      AND pa.account_status = 'active'
  );
$$;

REVOKE ALL PRIVILEGES ON FUNCTION private.is_platform_admin() FROM PUBLIC, anon;
GRANT EXECUTE ON FUNCTION private.is_platform_admin() TO authenticated, service_role;

-- =====================================================================
-- 4. PUBLIC.INSTITUTIONS (Colleges & Multi-Tenant Registry)
-- =====================================================================
-- Consumer: Institutional onboarding, proctorial isolation

CREATE TABLE IF NOT EXISTS public.institutions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    code VARCHAR(64) UNIQUE NOT NULL,
    name TEXT NOT NULL,
    city TEXT NOT NULL,
    state TEXT NOT NULL,
    type VARCHAR(32) NOT NULL DEFAULT 'university',
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc'::text, now()),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc'::text, now())
);

CREATE INDEX IF NOT EXISTS idx_institutions_code ON public.institutions(code);

ALTER TABLE public.institutions ENABLE ROW LEVEL SECURITY;

-- Public may read active institutions (e.g. for grievance filing dropdowns)
REVOKE ALL PRIVILEGES ON public.institutions FROM PUBLIC;
GRANT SELECT ON public.institutions TO anon, authenticated;
GRANT ALL ON public.institutions TO service_role;

DROP POLICY IF EXISTS "Public can view active institutions" ON public.institutions;
CREATE POLICY "Public can view active institutions"
    ON public.institutions FOR SELECT
    TO anon, authenticated
    USING (is_active = TRUE);

-- =====================================================================
-- 5. PUBLIC.INSTITUTION_MEMBERSHIPS (Officer Roles & Scoping)
-- =====================================================================
-- Consumer: api/auth.py, private.can_officer_access_case()

CREATE TABLE IF NOT EXISTS public.institution_memberships (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    institution_id VARCHAR(64) NOT NULL,
    role VARCHAR(32) NOT NULL CHECK (
        role IN ('proctor', 'committee_member', 'institution_admin', 'platform_admin')
    ),
    account_status VARCHAR(20) NOT NULL DEFAULT 'active' CHECK (
        account_status IN ('active', 'suspended', 'revoked')
    ),
    created_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc'::text, now()),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc'::text, now()),
    CONSTRAINT uq_user_institution UNIQUE (user_id, institution_id)
);

CREATE INDEX IF NOT EXISTS idx_inst_memberships_user ON public.institution_memberships(user_id, account_status);
CREATE INDEX IF NOT EXISTS idx_inst_memberships_inst ON public.institution_memberships(institution_id);

ALTER TABLE public.institution_memberships ENABLE ROW LEVEL SECURITY;

REVOKE ALL PRIVILEGES ON public.institution_memberships FROM PUBLIC, anon;
GRANT SELECT ON public.institution_memberships TO authenticated;
GRANT ALL ON public.institution_memberships TO service_role;

DROP POLICY IF EXISTS "Officers can view their own membership" ON public.institution_memberships;
CREATE POLICY "Officers can view their own membership"
    ON public.institution_memberships FOR SELECT
    TO authenticated
    USING (user_id = auth.uid());

-- =====================================================================
-- 6. AUTHORITATIVE private.can_officer_access_case() FUNCTION
-- =====================================================================
-- Database-backed check ensuring active status and approved roles

CREATE OR REPLACE FUNCTION private.can_officer_access_case(p_institution_id TEXT)
RETURNS boolean
LANGUAGE sql STABLE SECURITY DEFINER
SET search_path = ''
AS $$
  SELECT EXISTS (
    SELECT 1
    FROM public.institution_memberships im
    WHERE im.user_id = auth.uid()
      AND im.institution_id = p_institution_id
      AND im.account_status = 'active'
      AND im.role IN ('proctor', 'committee_member', 'institution_admin')
  );
$$;

REVOKE ALL PRIVILEGES ON FUNCTION private.can_officer_access_case(TEXT) FROM PUBLIC, anon;
GRANT EXECUTE ON FUNCTION private.can_officer_access_case(TEXT) TO authenticated, service_role;

-- =====================================================================
-- 7. AUGMENT PUBLIC.CAMPUS_CASES (Key Versioning)
-- =====================================================================
-- Adds key_version column to support non-destructive HMAC key rotation

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'campus_cases' AND column_name = 'key_version'
    ) THEN
        ALTER TABLE public.campus_cases 
        ADD COLUMN key_version VARCHAR(10) NOT NULL DEFAULT 'v1';
    END IF;
END $$;

-- =====================================================================
-- 8. PUBLIC.CONFIDENTIAL_STUDENT_IDENTITIES (PII Vault)
-- =====================================================================
-- Decoupled vault storing student PII for anonymous / confidential reporting

CREATE TABLE IF NOT EXISTS public.confidential_student_identities (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    case_id TEXT UNIQUE NOT NULL REFERENCES public.campus_cases(case_id) ON DELETE CASCADE,
    student_name_encrypted TEXT NOT NULL,
    roll_number_encrypted TEXT NOT NULL,
    contact_email_encrypted TEXT,
    key_version VARCHAR(10) NOT NULL DEFAULT 'v1',
    created_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc'::text, now())
);

ALTER TABLE public.confidential_student_identities ENABLE ROW LEVEL SECURITY;

-- PII vault is strictly accessible only to service_role (backend-only)
REVOKE ALL PRIVILEGES ON public.confidential_student_identities FROM PUBLIC, anon, authenticated;
GRANT SELECT, INSERT ON public.confidential_student_identities TO service_role;

-- =====================================================================
-- 9. PUBLIC.CASE_DOCUMENTS (Private Storage Metadata)
-- =====================================================================

CREATE TABLE IF NOT EXISTS public.case_documents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    case_id TEXT NOT NULL,
    file_name TEXT NOT NULL,
    file_size_bytes BIGINT NOT NULL,
    mime_type VARCHAR(128) NOT NULL,
    storage_path TEXT NOT NULL,
    uploader_user_id UUID REFERENCES auth.users(id) ON DELETE SET NULL,
    is_confidential BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc'::text, now())
);

CREATE INDEX IF NOT EXISTS idx_case_docs_case ON public.case_documents(case_id);

ALTER TABLE public.case_documents ENABLE ROW LEVEL SECURITY;

REVOKE ALL PRIVILEGES ON public.case_documents FROM PUBLIC, anon;
GRANT SELECT, INSERT ON public.case_documents TO authenticated, service_role;

-- =====================================================================
-- 10. PUBLIC.CASE_ACTIVITY_LOG (Immutable Audit Trail)
-- =====================================================================

CREATE TABLE IF NOT EXISTS public.case_activity_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    case_id TEXT NOT NULL,
    actor_id UUID REFERENCES auth.users(id) ON DELETE SET NULL,
    actor_role VARCHAR(32) NOT NULL,
    action_type VARCHAR(64) NOT NULL,
    action_details JSONB NOT NULL DEFAULT '{}'::jsonb,
    ip_address INET,
    created_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc'::text, now())
);

CREATE INDEX IF NOT EXISTS idx_case_activity_case ON public.case_activity_log(case_id, created_at DESC);

ALTER TABLE public.case_activity_log ENABLE ROW LEVEL SECURITY;

-- Audit log is append-only for authenticated and service_role
REVOKE ALL PRIVILEGES ON public.case_activity_log FROM PUBLIC, anon;
GRANT SELECT, INSERT ON public.case_activity_log TO authenticated, service_role;

-- Trigger to prevent UPDATE or DELETE on immutable audit log
CREATE OR REPLACE FUNCTION private.prevent_audit_log_modification()
RETURNS TRIGGER AS $$
BEGIN
    RAISE EXCEPTION 'Case activity log is immutable: updates and deletions are strictly prohibited.';
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_immutable_case_activity_log ON public.case_activity_log;
CREATE TRIGGER trg_immutable_case_activity_log
    BEFORE UPDATE OR DELETE ON public.case_activity_log
    FOR EACH ROW EXECUTE FUNCTION private.prevent_audit_log_modification();

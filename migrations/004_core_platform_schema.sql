-- =====================================================================
-- NyayPath Database Migration: 004_core_platform_schema.sql
-- Phase: 1.3.5 Complete Platform Schema & Database-Backed Authorization
-- Description:
--   Establishes the complete schema inventory required across all
--   NyayPath modules, resolving the missing public.cases table,
--   implementing database-backed administrator and officer authorization,
--   enforcing immutable audit logs, and preventing client privilege escalation.
--
-- Tables Defined / Augmented:
--   1. public.cases (Citizen RTI applications, consumer complaints, watchdog)
--      - id UUID PRIMARY KEY (Internal opaque identifier)
--      - case_id VARCHAR(64) UNIQUE (Public human-readable identifier)
--   2. public.platform_admins (Authoritative platform admin registry)
--   3. public.profiles (User identity, contact details, and role registry)
--   4. public.institutions (Colleges and educational institutions)
--   5. public.institution_memberships (Officer memberships & institutional scoping)
--   6. public.campus_cases (key_version column added for HMAC rotation)
--   7. public.confidential_student_identities (Decoupled PII vault)
--   8. public.case_documents (Encrypted document attachments & metadata)
--   9. public.case_activity_log (Immutable audit trail, backend-only insert)
--  10. public.legal_precedents (Curated legal precedents repository)
--  11. public.saved_research (Citizen/advocate bookmarked precedents)
--
-- Functions Defined in 'private' Schema:
--   1. private.is_platform_admin() (Authoritative database-backed check)
--   2. private.can_officer_access_case() (Institution & active status check)
--   3. private.prevent_audit_log_modification() (Blocks UPDATE/DELETE on audit logs)
--   4. private.enforce_profile_immutability() (Blocks privilege escalation on profiles)
--
-- Safety: Forward-only, idempotent, and non-destructive.
-- =====================================================================

-- Ensure UUID extensions exist
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- Ensure private schema exists and is secured against public/anon access
CREATE SCHEMA IF NOT EXISTS private;
REVOKE ALL PRIVILEGES ON SCHEMA private FROM PUBLIC, anon;
GRANT USAGE ON SCHEMA private TO authenticated, service_role;

-- =====================================================================
-- 1. PUBLIC.CASES (Citizen RTI & Consumer Cases Engine)
-- =====================================================================
-- Internal opaque UUID primary key + separate public case_id identifier.
-- Consumers: api/case_manager.py, api/watchdog_engine.py

CREATE TABLE IF NOT EXISTS public.cases (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    case_id VARCHAR(64) UNIQUE NOT NULL,
    data JSONB NOT NULL DEFAULT '{}'::jsonb,
    tracking_key_hash VARCHAR(128),
    key_version VARCHAR(10) NOT NULL DEFAULT 'v1',
    case_type VARCHAR(32) NOT NULL DEFAULT 'RTI' CHECK (
        case_type IN ('RTI', 'FIRST_APPEAL', 'CONSUMER_COMPLAINT', 'GENERAL_GRIEVANCE')
    ),
    created_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc'::text, now()),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc'::text, now())
);

CREATE INDEX IF NOT EXISTS idx_cases_case_id ON public.cases(case_id);
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
-- 4. PUBLIC.PROFILES (User Identity & Role Registry)
-- =====================================================================
-- Consumer: User profile management, role verification

CREATE TABLE IF NOT EXISTS public.profiles (
    id UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
    email TEXT,
    full_name TEXT,
    phone TEXT,
    role VARCHAR(32) NOT NULL DEFAULT 'citizen' CHECK (
        role IN ('citizen', 'student', 'proctor', 'committee_member', 'institution_admin', 'platform_admin')
    ),
    is_verified BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc'::text, now()),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc'::text, now())
);

ALTER TABLE public.profiles ENABLE ROW LEVEL SECURITY;

REVOKE ALL PRIVILEGES ON public.profiles FROM PUBLIC, anon;
GRANT SELECT, UPDATE ON public.profiles TO authenticated;
GRANT ALL ON public.profiles TO service_role;

DROP POLICY IF EXISTS "Users can view own profile" ON public.profiles;
CREATE POLICY "Users can view own profile"
    ON public.profiles FOR SELECT
    TO authenticated
    USING (id = auth.uid());

DROP POLICY IF EXISTS "Users can update own profile contact details" ON public.profiles;
CREATE POLICY "Users can update own profile contact details"
    ON public.profiles FOR UPDATE
    TO authenticated
    USING (id = auth.uid())
    WITH CHECK (id = auth.uid());

-- Immutability trigger preventing client privilege escalation on role and is_verified
CREATE OR REPLACE FUNCTION private.enforce_profile_immutability()
RETURNS TRIGGER AS $$
BEGIN
    -- When called by authenticated client (not service_role backend)
    IF current_user != 'service_role' AND auth.role() = 'authenticated' THEN
        IF NEW.role IS DISTINCT FROM OLD.role THEN
            RAISE EXCEPTION 'Privilege escalation rejected: users cannot modify their own assigned role.';
        END IF;
        IF NEW.is_verified IS DISTINCT FROM OLD.is_verified THEN
            RAISE EXCEPTION 'Verification escalation rejected: users cannot modify their own verification status.';
        END IF;
        IF NEW.id IS DISTINCT FROM OLD.id THEN
            RAISE EXCEPTION 'Identity modification rejected.';
        END IF;
    END IF;
    NEW.updated_at = timezone('utc'::text, now());
    RETURN NEW;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER SET search_path = '';

DROP TRIGGER IF EXISTS trg_profile_immutability ON public.profiles;
CREATE TRIGGER trg_profile_immutability
    BEFORE UPDATE ON public.profiles
    FOR EACH ROW EXECUTE FUNCTION private.enforce_profile_immutability();

-- =====================================================================
-- 5. PUBLIC.INSTITUTIONS (Colleges & Multi-Tenant Registry)
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

REVOKE ALL PRIVILEGES ON public.institutions FROM PUBLIC;
GRANT SELECT ON public.institutions TO anon, authenticated;
GRANT ALL ON public.institutions TO service_role;

DROP POLICY IF EXISTS "Public can view active institutions" ON public.institutions;
CREATE POLICY "Public can view active institutions"
    ON public.institutions FOR SELECT
    TO anon, authenticated
    USING (is_active = TRUE);

-- =====================================================================
-- 6. PUBLIC.INSTITUTION_MEMBERSHIPS (Officer Roles & Scoping)
-- =====================================================================
-- Consumer: api/auth.py, private.can_officer_access_case()
-- Notice: Authenticated users have SELECT only; NO client INSERT or UPDATE.

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
-- 7. AUTHORITATIVE private.can_officer_access_case() FUNCTION
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
-- 8. AUGMENT PUBLIC.CAMPUS_CASES (Key Versioning)
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
-- 9. PUBLIC.CONFIDENTIAL_STUDENT_IDENTITIES (PII Vault)
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
-- 10. PUBLIC.CASE_DOCUMENTS (Private Storage Metadata)
-- =====================================================================
-- Storage paths use internal UUID: {case_uuid}/{doc_uuid}_{filename}

CREATE TABLE IF NOT EXISTS public.case_documents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    case_uuid UUID NOT NULL REFERENCES public.cases(id) ON DELETE CASCADE,
    case_id VARCHAR(64) NOT NULL,
    file_name TEXT NOT NULL,
    file_size_bytes BIGINT NOT NULL,
    mime_type VARCHAR(128) NOT NULL,
    storage_path TEXT NOT NULL,
    uploader_user_id UUID REFERENCES auth.users(id) ON DELETE SET NULL,
    is_confidential BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc'::text, now())
);

CREATE INDEX IF NOT EXISTS idx_case_docs_case_uuid ON public.case_documents(case_uuid);
CREATE INDEX IF NOT EXISTS idx_case_docs_case_id ON public.case_documents(case_id);

ALTER TABLE public.case_documents ENABLE ROW LEVEL SECURITY;

REVOKE ALL PRIVILEGES ON public.case_documents FROM PUBLIC, anon;
GRANT SELECT, INSERT ON public.case_documents TO authenticated, service_role;

DROP POLICY IF EXISTS "Authenticated users can view attachments for their cases" ON public.case_documents;
CREATE POLICY "Authenticated users can view attachments for their cases"
    ON public.case_documents FOR SELECT
    TO authenticated
    USING (
        uploader_user_id = auth.uid()
        OR private.is_platform_admin()
    );

-- =====================================================================
-- 11. PUBLIC.CASE_ACTIVITY_LOG (Immutable Audit Trail)
-- =====================================================================
-- Task 2: authenticated has SELECT only; INSERT is restricted to service_role.

CREATE TABLE IF NOT EXISTS public.case_activity_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    case_uuid UUID REFERENCES public.cases(id) ON DELETE SET NULL,
    case_id VARCHAR(64) NOT NULL,
    actor_id UUID REFERENCES auth.users(id) ON DELETE SET NULL,
    actor_role VARCHAR(32) NOT NULL,
    action_type VARCHAR(64) NOT NULL,
    action_details JSONB NOT NULL DEFAULT '{}'::jsonb,
    ip_address INET,
    created_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc'::text, now())
);

CREATE INDEX IF NOT EXISTS idx_case_activity_case ON public.case_activity_log(case_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_case_activity_uuid ON public.case_activity_log(case_uuid, created_at DESC);

ALTER TABLE public.case_activity_log ENABLE ROW LEVEL SECURITY;

-- Audit log is append-only for service_role; authenticated can read own/authorized actions
REVOKE ALL PRIVILEGES ON public.case_activity_log FROM PUBLIC, anon, authenticated;
GRANT SELECT ON public.case_activity_log TO authenticated;
GRANT SELECT, INSERT ON public.case_activity_log TO service_role;

DROP POLICY IF EXISTS "Officers and users can view authorized activity logs" ON public.case_activity_log;
CREATE POLICY "Officers and users can view authorized activity logs"
    ON public.case_activity_log FOR SELECT
    TO authenticated
    USING (
        actor_id = auth.uid()
        OR private.is_platform_admin()
    );

-- Trigger to prevent UPDATE or DELETE on immutable audit log
CREATE OR REPLACE FUNCTION private.prevent_audit_log_modification()
RETURNS TRIGGER AS $$
BEGIN
    RAISE EXCEPTION 'Case activity log is immutable: updates and deletions are strictly prohibited.';
END;
$$ LANGUAGE plpgsql SECURITY DEFINER SET search_path = '';

DROP TRIGGER IF EXISTS trg_immutable_case_activity_log ON public.case_activity_log;
CREATE TRIGGER trg_immutable_case_activity_log
    BEFORE UPDATE OR DELETE ON public.case_activity_log
    FOR EACH ROW EXECUTE FUNCTION private.prevent_audit_log_modification();

-- =====================================================================
-- 12. PUBLIC.LEGAL_PRECEDENTS (Curated Legal Intelligence)
-- =====================================================================
-- Consumer: api/precedent_library.py

CREATE TABLE IF NOT EXISTS public.legal_precedents (
    id VARCHAR(128) PRIMARY KEY,
    citation TEXT NOT NULL,
    title TEXT NOT NULL,
    court VARCHAR(128) NOT NULL,
    bench TEXT,
    judgment_date DATE,
    category VARCHAR(64) NOT NULL,
    summary TEXT NOT NULL,
    statutory_provisions TEXT[],
    ratio_decidendi TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc'::text, now())
);

ALTER TABLE public.legal_precedents ENABLE ROW LEVEL SECURITY;

REVOKE ALL PRIVILEGES ON public.legal_precedents FROM PUBLIC;
GRANT SELECT ON public.legal_precedents TO anon, authenticated;
GRANT ALL ON public.legal_precedents TO service_role;

DROP POLICY IF EXISTS "Public can view legal precedents" ON public.legal_precedents;
CREATE POLICY "Public can view legal precedents"
    ON public.legal_precedents FOR SELECT
    TO anon, authenticated
    USING (true);

-- =====================================================================
-- 13. PUBLIC.SAVED_RESEARCH (User Precedent Bookmarks)
-- =====================================================================
-- Consumer: Citizen & advocate legal research workspace

CREATE TABLE IF NOT EXISTS public.saved_research (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    precedent_id VARCHAR(128) NOT NULL REFERENCES public.legal_precedents(id) ON DELETE CASCADE,
    notes TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc'::text, now()),
    CONSTRAINT uq_user_precedent UNIQUE (user_id, precedent_id)
);

ALTER TABLE public.saved_research ENABLE ROW LEVEL SECURITY;

REVOKE ALL PRIVILEGES ON public.saved_research FROM PUBLIC, anon;
GRANT SELECT, INSERT, DELETE ON public.saved_research TO authenticated;
GRANT ALL ON public.saved_research TO service_role;

DROP POLICY IF EXISTS "Users can manage own saved research" ON public.saved_research;
CREATE POLICY "Users can manage own saved research"
    ON public.saved_research FOR ALL
    TO authenticated
    USING (user_id = auth.uid())
    WITH CHECK (user_id = auth.uid());

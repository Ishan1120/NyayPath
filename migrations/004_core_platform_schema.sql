-- =====================================================================
-- NyayPath Database Migration: 004_core_platform_schema.sql
-- Phase: 1.3.6 / 1.3.7 Complete Platform Schema & Unified Relational Integrity
-- Description:
--   Establishes the authoritative parent case entity (public.cases) with
--   internal UUID primary keys, links campus grievances via enforceable
--   foreign keys, establishes immutable audit trails with RESTRICT deletion
--   guards, enforces institution UUID relationships, and guards client
--   privilege escalation boundaries.
--
-- Tables Defined / Augmented:
--   1. public.cases (Authoritative Unified Parent Case Entity)
--      - id UUID PRIMARY KEY (Internal opaque identifier)
--      - case_id VARCHAR(64) UNIQUE (Public human-readable identifier)
--      - Supports: RTI, CONSUMER_COMPLAINT, GENERAL_GRIEVANCE, CAMPUS_GRIEVANCE
--   2. public.institutions (Colleges and multi-tenant registry with UUID PK)
--   3. public.campus_cases (Sub-record linked to cases and institutions via FK)
--   4. public.platform_admins (Authoritative platform admin registry)
--   5. public.profiles (User identity, contact details, and role registry)
--   6. public.institution_memberships (Officer memberships with institution UUID FK)
--   7. public.confidential_student_identities (Decoupled PII vault)
--   8. public.case_documents (Encrypted document attachments & metadata)
--   9. public.case_activity_log (Immutable audit trail, RESTRICT deletion guards)
--  10. public.legal_precedents (Curated legal precedents repository)
--  11. public.saved_research (Citizen/advocate bookmarked precedents)
--
-- Functions Defined in 'private' Schema:
--   1. private.sync_campus_case_parent() (Synchronizes campus cases to parent cases)
--   2. private.is_platform_admin() (Authoritative database-backed check)
--   3. private.can_officer_access_case(UUID) (Institutional UUID scoping check)
--   4. private.prevent_audit_log_modification() (Blocks UPDATE/DELETE on audit logs)
--   5. private.enforce_profile_immutability() (Blocks privilege escalation on profiles)
--
-- Safety: Forward-only, strictly linear, idempotent, and non-destructive.
-- =====================================================================

-- Ensure UUID extensions exist
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- Ensure private schema exists and is secured against public/anon access
CREATE SCHEMA IF NOT EXISTS private;
REVOKE ALL PRIVILEGES ON SCHEMA private FROM PUBLIC, anon;
GRANT USAGE ON SCHEMA private TO authenticated, service_role;

-- =====================================================================
-- 1. PUBLIC.CASES (Authoritative Unified Parent Case Entity)
-- =====================================================================
-- Internal opaque UUID primary key + separate public case_id identifier.
-- Consumers: api/case_manager.py, api/watchdog_engine.py, api/campus_proctor.py

CREATE TABLE IF NOT EXISTS public.cases (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    case_id VARCHAR(64) UNIQUE NOT NULL,
    data JSONB NOT NULL DEFAULT '{}'::jsonb,
    tracking_key_hash VARCHAR(128),
    key_version VARCHAR(10) NOT NULL DEFAULT 'v1',
    case_type VARCHAR(32) NOT NULL DEFAULT 'RTI' CHECK (
        case_type IN ('RTI', 'FIRST_APPEAL', 'CONSUMER_COMPLAINT', 'GENERAL_GRIEVANCE', 'CAMPUS_GRIEVANCE')
    ),
    status VARCHAR(32) NOT NULL DEFAULT 'FILED',
    is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
    deleted_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc'::text, now()),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc'::text, now())
);

CREATE INDEX IF NOT EXISTS idx_cases_case_id ON public.cases(case_id);
CREATE INDEX IF NOT EXISTS idx_cases_updated_at ON public.cases(updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_cases_case_type ON public.cases(case_type);
CREATE INDEX IF NOT EXISTS idx_cases_active ON public.cases(is_deleted) WHERE is_deleted = FALSE;

ALTER TABLE public.cases ENABLE ROW LEVEL SECURITY;

-- Parent cases are managed exclusively by the FastAPI backend
REVOKE ALL PRIVILEGES ON public.cases FROM PUBLIC, anon, authenticated;
GRANT SELECT, INSERT, UPDATE ON public.cases TO service_role;

-- =====================================================================
-- 2. PUBLIC.INSTITUTIONS (Colleges & Multi-Tenant Registry)
-- =====================================================================
-- Placed before campus_cases and institution_memberships to ensure linear FK resolution.

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

-- Seed standard institutions with fixed deterministic UUIDs
INSERT INTO public.institutions (id, code, name, city, state)
VALUES 
    ('00000000-0000-0000-0000-000000000001'::uuid, 'INST_DEFAULT', 'Default Academic Institution', 'New Delhi', 'Delhi'),
    ('00000000-0000-0000-0000-000000000002'::uuid, 'INST_NIT_DELHI', 'National Institute of Technology Delhi', 'New Delhi', 'Delhi'),
    ('00000000-0000-0000-0000-000000000003'::uuid, 'INST_UP_TECH', 'UP Technical University', 'Lucknow', 'Uttar Pradesh')
ON CONFLICT (code) DO NOTHING;

-- =====================================================================
-- 3. UNIFY CAMPUS CASES WITH PARENT CASES & INSTITUTIONS (Task 1 & Task 2)
-- =====================================================================
-- Augment campus_cases with key_version if not present
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

-- Augment campus_cases with institution_uuid referencing public.institutions(id)
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'campus_cases' AND column_name = 'institution_uuid'
    ) THEN
        ALTER TABLE public.campus_cases 
        ADD COLUMN institution_uuid UUID REFERENCES public.institutions(id) ON DELETE RESTRICT;

        -- Backfill from institutions matching code
        UPDATE public.campus_cases cc
        SET institution_uuid = inst.id
        FROM public.institutions inst
        WHERE cc.institution_id = inst.code;

        -- Fallback to default institution if unmatched
        UPDATE public.campus_cases
        SET institution_uuid = '00000000-0000-0000-0000-000000000001'::uuid
        WHERE institution_uuid IS NULL;
    END IF;
END $$;

-- Backfill parent case records for any existing campus_cases:
INSERT INTO public.cases (id, case_id, case_type, status, tracking_key_hash, key_version, created_at, updated_at)
SELECT id, case_id, 'CAMPUS_GRIEVANCE', status, verification_key_hash, key_version, created_at, updated_at
FROM public.campus_cases
ON CONFLICT (case_id) DO NOTHING;

-- Enforce foreign key linkage from campus_cases(id) to parent cases(id)
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.table_constraints 
        WHERE constraint_name = 'fk_campus_cases_parent'
    ) THEN
        ALTER TABLE public.campus_cases
        ADD CONSTRAINT fk_campus_cases_parent
        FOREIGN KEY (id) REFERENCES public.cases(id) ON DELETE RESTRICT;
    END IF;
END $$;

-- Synchronization function to ensure atomic parent/child consistency without recursive loops
CREATE OR REPLACE FUNCTION private.sync_campus_case_parent()
RETURNS TRIGGER AS $$
BEGIN
    -- Prevent recursive trigger invocation
    IF pg_trigger_depth() > 1 THEN
        RETURN NEW;
    END IF;

    IF TG_OP = 'INSERT' THEN
        -- Insert parent row into public.cases
        -- Guarantees parent exists before campus_cases foreign key check commits
        INSERT INTO public.cases (
            id,
            case_id,
            case_type,
            status,
            tracking_key_hash,
            key_version,
            created_at,
            updated_at
        ) VALUES (
            NEW.id,
            NEW.case_id,
            'CAMPUS_GRIEVANCE',
            NEW.status,
            NEW.verification_key_hash,
            NEW.key_version,
            NEW.created_at,
            NEW.updated_at
        )
        ON CONFLICT (case_id) DO UPDATE SET
            status = EXCLUDED.status,
            tracking_key_hash = EXCLUDED.tracking_key_hash,
            key_version = EXCLUDED.key_version,
            updated_at = EXCLUDED.updated_at
        WHERE public.cases.id = NEW.id; -- STRICT: Never allows altering parent UUID!

        RETURN NEW;

    ELSIF TG_OP = 'UPDATE' THEN
        -- Keep parent cases synchronized when status, key, or timestamp updates
        UPDATE public.cases
        SET
            status = NEW.status,
            tracking_key_hash = NEW.verification_key_hash,
            key_version = NEW.key_version,
            updated_at = NEW.updated_at
        WHERE id = NEW.id;

        RETURN NEW;
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER SET search_path = '';

DROP TRIGGER IF EXISTS trg_sync_campus_case_insert ON public.campus_cases;
CREATE TRIGGER trg_sync_campus_case_insert
    BEFORE INSERT ON public.campus_cases
    FOR EACH ROW EXECUTE FUNCTION private.sync_campus_case_parent();

DROP TRIGGER IF EXISTS trg_sync_campus_case_update ON public.campus_cases;
CREATE TRIGGER trg_sync_campus_case_update
    AFTER UPDATE OF status, verification_key_hash, key_version, updated_at ON public.campus_cases
    FOR EACH ROW EXECUTE FUNCTION private.sync_campus_case_parent();

-- =====================================================================
-- 4. PUBLIC.PLATFORM_ADMINS (Database-Backed Admin Registry)
-- =====================================================================
-- Consumer: private.is_platform_admin(), api/auth.py

CREATE TABLE IF NOT EXISTS public.platform_admins (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID UNIQUE NOT NULL REFERENCES auth.users(id) ON DELETE RESTRICT,
    email TEXT UNIQUE NOT NULL,
    account_status VARCHAR(20) NOT NULL DEFAULT 'active' CHECK (
        account_status IN ('active', 'suspended', 'revoked')
    ),
    created_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc'::text, now()),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc'::text, now())
);

CREATE INDEX IF NOT EXISTS idx_platform_admins_user ON public.platform_admins(user_id, account_status);

ALTER TABLE public.platform_admins ENABLE ROW LEVEL SECURITY;

REVOKE ALL PRIVILEGES ON public.platform_admins FROM PUBLIC, anon, authenticated;
GRANT SELECT, INSERT, UPDATE, DELETE ON public.platform_admins TO service_role;

-- =====================================================================
-- 5. AUTHORITATIVE private.is_platform_admin() FUNCTION
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
-- 6. PUBLIC.PROFILES (User Identity & Role Registry)
-- =====================================================================
-- Consumer: User profile management, role verification

CREATE TABLE IF NOT EXISTS public.profiles (
    id UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE RESTRICT,
    email TEXT,
    full_name TEXT,
    phone TEXT,
    role VARCHAR(32) NOT NULL DEFAULT 'citizen' CHECK (
        role IN ('citizen', 'student', 'proctor', 'committee_member', 'institution_admin', 'platform_admin')
    ),
    account_status VARCHAR(20) NOT NULL DEFAULT 'active' CHECK (
        account_status IN ('active', 'suspended', 'deactivated', 'revoked')
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
    IF current_user != 'service_role' AND auth.role() = 'authenticated' THEN
        IF NEW.role IS DISTINCT FROM OLD.role THEN
            RAISE EXCEPTION 'Privilege escalation rejected: users cannot modify their own assigned role.';
        END IF;
        IF NEW.is_verified IS DISTINCT FROM OLD.is_verified THEN
            RAISE EXCEPTION 'Verification escalation rejected: users cannot modify their own verification status.';
        END IF;
        IF NEW.account_status IS DISTINCT FROM OLD.account_status THEN
            RAISE EXCEPTION 'Status modification rejected: users cannot modify their own account status.';
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
-- 7. PUBLIC.INSTITUTION_MEMBERSHIPS (Officer Roles with UUID FK)
-- =====================================================================
-- Task 2: Uses authoritative UUID FK referencing public.institutions(id).
-- Notice: Authenticated users have SELECT only; NO client INSERT or UPDATE.

CREATE TABLE IF NOT EXISTS public.institution_memberships (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE RESTRICT,
    institution_id UUID NOT NULL REFERENCES public.institutions(id) ON DELETE RESTRICT,
    institution_code VARCHAR(64) NOT NULL,
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
-- 8. AUTHORITATIVE private.can_officer_access_case(UUID) FUNCTION
-- =====================================================================
-- Task 2: Accepts UUID and performs exact UUID-to-UUID comparison.

CREATE OR REPLACE FUNCTION private.can_officer_access_case(p_institution_id UUID)
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

REVOKE ALL PRIVILEGES ON FUNCTION private.can_officer_access_case(UUID) FROM PUBLIC, anon;
GRANT EXECUTE ON FUNCTION private.can_officer_access_case(UUID) TO authenticated, service_role;

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
GRANT SELECT, INSERT, UPDATE, DELETE ON public.confidential_student_identities TO service_role;

-- =====================================================================
-- 10. PUBLIC.CASE_DOCUMENTS (Unified Document Vault)
-- =====================================================================
-- Storage paths use internal UUID: {case_uuid}/{doc_uuid}_{filename}
-- Enforces ON DELETE RESTRICT to preserve referential integrity

CREATE TABLE IF NOT EXISTS public.case_documents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    case_uuid UUID NOT NULL REFERENCES public.cases(id) ON DELETE RESTRICT,
    case_id VARCHAR(64) NOT NULL,
    file_name TEXT NOT NULL,
    file_size_bytes BIGINT NOT NULL,
    mime_type VARCHAR(128) NOT NULL,
    storage_path TEXT NOT NULL,
    uploader_user_id UUID REFERENCES auth.users(id) ON DELETE RESTRICT,
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
-- Task 2 & Task 4: authenticated has SELECT only; INSERT restricted to service_role.
-- Foreign keys use ON DELETE RESTRICT to avoid conflicting with the immutability trigger.
-- action_details strictly contains operational telemetry (NEVER personal PII or raw credentials).

CREATE TABLE IF NOT EXISTS public.case_activity_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    case_uuid UUID NOT NULL REFERENCES public.cases(id) ON DELETE RESTRICT,
    case_id VARCHAR(64) NOT NULL,
    actor_id UUID REFERENCES auth.users(id) ON DELETE RESTRICT,
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
        -- 1. Platform admins can view all activity logs
        private.is_platform_admin()
        OR
        -- 2. Actors can view their own logged actions
        actor_id = auth.uid()
        OR
        -- 3. Officers can view logs for cases belonging to their authorized institution UUID
        EXISTS (
            SELECT 1 FROM public.campus_cases cc
            WHERE cc.id = case_activity_log.case_uuid
              AND cc.institution_uuid IS NOT NULL
              AND private.can_officer_access_case(cc.institution_uuid)
        )
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
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE RESTRICT,
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

-- =====================================================================
-- 14. PRIVATE STORAGE BUCKET FOR CASE DOCUMENTS (Task 3 & 8)
-- =====================================================================
-- Idempotently creates private bucket 'case_documents' if Supabase storage schema exists

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.schemata WHERE schema_name = 'storage') THEN
        INSERT INTO storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
        VALUES (
            'case_documents',
            'case_documents',
            FALSE, -- Private bucket
            10485760, -- 10MB maximum file size limit
            ARRAY['application/pdf', 'image/jpeg', 'image/png']
        )
        ON CONFLICT (id) DO UPDATE SET
            public = FALSE,
            file_size_limit = 10485760;

        -- Authenticated users can view authorized attachments
        DROP POLICY IF EXISTS "Authenticated users view case attachments" ON storage.objects;
        CREATE POLICY "Authenticated users view case attachments"
            ON storage.objects FOR SELECT
            TO authenticated
            USING (bucket_id = 'case_documents');

        -- Backend service_role manages attachments
        DROP POLICY IF EXISTS "Service role manages case attachments" ON storage.objects;
        CREATE POLICY "Service role manages case attachments"
            ON storage.objects FOR ALL
            TO service_role
            USING (bucket_id = 'case_documents')
            WITH CHECK (bucket_id = 'case_documents');
    END IF;
END $$;

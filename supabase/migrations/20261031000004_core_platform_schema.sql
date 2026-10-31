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

-- NOTE: Initial public.institutions table starts strictly EMPTY.
-- Institution onboarding is strictly mediated by platform administrators via verified onboarding operations.
-- No unapproved placeholder, test, or fictional institutional records are seeded.

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

        -- Backfill from institutions matching code if any verified institutions exist
        UPDATE public.campus_cases cc
        SET institution_uuid = inst.id
        FROM public.institutions inst
        WHERE cc.institution_id = inst.code;
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
-- Task 1: public.cases is strictly the single source of truth for case status and credentials.
-- Task 1 Collision Rules:
-- 1. Same case_id with different UUID: REJECT via RAISE EXCEPTION.
-- 2. Same UUID with different case_id: REJECT via RAISE EXCEPTION.
-- 3. Mismatched case_type: REJECT via RAISE EXCEPTION.
-- 4. Pre-created or retry parent: Inherit authoritative parent status/credentials/timestamps; DO NOT overwrite parent.
-- 5. Child update attempts to alter id or case_id: REJECT via RAISE EXCEPTION.
-- 6. Child update attempts to independently modify any parent-owned field (status, tracking key, timestamps): REJECT via RAISE EXCEPTION.
CREATE OR REPLACE FUNCTION private.sync_campus_case_parent()
RETURNS TRIGGER AS $$
DECLARE
    v_existing_parent RECORD;
BEGIN
    -- Prevent recursive trigger invocation
    IF pg_trigger_depth() > 1 THEN
        RETURN NEW;
    END IF;

    IF TG_OP = 'INSERT' THEN
        -- Check if parent row already exists by id OR case_id
        SELECT id, case_id, case_type, status, tracking_key_hash, key_version, created_at, updated_at INTO v_existing_parent
        FROM public.cases
        WHERE id = NEW.id OR case_id = NEW.case_id
        LIMIT 1;

        IF FOUND THEN
            -- Collision Check 1: Same case_id but different UUID -> REJECT!
            IF v_existing_parent.case_id = NEW.case_id AND v_existing_parent.id <> NEW.id THEN
                RAISE EXCEPTION 'Case ID collision: case_id % already exists with parent UUID %, cannot associate with child UUID %',
                    NEW.case_id, v_existing_parent.id, NEW.id;
            END IF;

            -- Collision Check 2: Same UUID but different case_id -> REJECT!
            IF v_existing_parent.id = NEW.id AND v_existing_parent.case_id <> NEW.case_id THEN
                RAISE EXCEPTION 'UUID collision: UUID % already exists with case_id %, cannot associate with child case_id %',
                    NEW.id, v_existing_parent.case_id, NEW.case_id;
            END IF;

            -- Collision Check 3: Mismatched case_type -> REJECT!
            IF v_existing_parent.case_type <> 'CAMPUS_GRIEVANCE' THEN
                RAISE EXCEPTION 'Case type collision: Parent case % is classified as %, cannot attach as child CAMPUS_GRIEVANCE',
                    v_existing_parent.case_id, v_existing_parent.case_type;
            END IF;

            -- Collision Check 4: Existing parent matches UUID, case_id, and case_type (Idempotent intake / retry)
            -- Strictly inherit authoritative parent values including timestamps without overwriting with stale child data
            NEW.status := v_existing_parent.status;
            NEW.verification_key_hash := v_existing_parent.tracking_key_hash;
            NEW.key_version := v_existing_parent.key_version;
            NEW.created_at := v_existing_parent.created_at;
            NEW.updated_at := v_existing_parent.updated_at;

            RETURN NEW;
        ELSE
            -- No parent exists: Atomically create the authoritative parent row in public.cases
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
                COALESCE(NEW.status, 'SUBMITTED'),
                NEW.verification_key_hash,
                COALESCE(NEW.key_version, 'v1'),
                COALESCE(NEW.created_at, timezone('utc'::text, now())),
                COALESCE(NEW.updated_at, timezone('utc'::text, now()))
            );

            RETURN NEW;
        END IF;

    ELSIF TG_OP = 'UPDATE' THEN
        -- Collision Check 5: Child update attempts to modify parent identifiers -> REJECT!
        IF NEW.id IS DISTINCT FROM OLD.id THEN
            RAISE EXCEPTION 'Parent identifier immutability violation: campus_cases.id cannot be altered (attempted % -> %)',
                OLD.id, NEW.id;
        END IF;

        IF NEW.case_id IS DISTINCT FROM OLD.case_id THEN
            RAISE EXCEPTION 'Parent identifier immutability violation: campus_cases.case_id cannot be altered (attempted % -> %)',
                OLD.case_id, NEW.case_id;
        END IF;

        -- Check 6: Enforce one-way authority. Child cannot independently modify ANY parent-owned field.
        -- When pg_trigger_depth() = 1, this is a direct child update bypassing public.cases.
        IF NEW.status IS DISTINCT FROM OLD.status THEN
            RAISE EXCEPTION 'Parent authority violation: status is authoritatively owned by public.cases and cannot be modified via child campus_cases table. Update public.cases instead.';
        END IF;

        IF NEW.verification_key_hash IS DISTINCT FROM OLD.verification_key_hash OR
           NEW.key_version IS DISTINCT FROM OLD.key_version THEN
            RAISE EXCEPTION 'Parent authority violation: Tracking credentials are authoritatively owned by public.cases and cannot be modified via child campus_cases table.';
        END IF;

        IF NEW.created_at IS DISTINCT FROM OLD.created_at THEN
            RAISE EXCEPTION 'Parent authority violation: created_at is authoritatively owned by public.cases and is strictly immutable.';
        END IF;

        IF NEW.updated_at IS DISTINCT FROM OLD.updated_at THEN
            RAISE EXCEPTION 'Parent authority violation: updated_at is authoritatively owned by public.cases and is synchronized via parent updates.';
        END IF;

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
    BEFORE UPDATE ON public.campus_cases
    FOR EACH ROW EXECUTE FUNCTION private.sync_campus_case_parent();

-- =====================================================================
-- Authoritative parent-to-child status synchronization trigger (Task 1)
-- =====================================================================
CREATE OR REPLACE FUNCTION private.sync_parent_case_to_campus()
RETURNS TRIGGER AS $$
BEGIN
    -- Prevent recursive trigger loops
    IF pg_trigger_depth() > 1 THEN
        RETURN NEW;
    END IF;

    -- Propagate authoritative parent status, tracking key, and timestamp changes down to campus_cases
    UPDATE public.campus_cases
    SET
        status = NEW.status,
        verification_key_hash = NEW.tracking_key_hash,
        key_version = NEW.key_version,
        updated_at = NEW.updated_at
    WHERE id = NEW.id;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER SET search_path = '';

DROP TRIGGER IF EXISTS trg_sync_parent_case_update ON public.cases;
CREATE TRIGGER trg_sync_parent_case_update
    AFTER UPDATE OF status, tracking_key_hash, key_version, updated_at ON public.cases
    FOR EACH ROW EXECUTE FUNCTION private.sync_parent_case_to_campus();

-- =====================================================================
-- 4. ATOMIC GRIEVANCE STATUS UPDATE RPC (Phase 1.3.7 - Task 1 & Task 4)
-- =====================================================================
-- Executes parent and child status updates inside a single atomic database transaction.
-- 1. Verifies case_type = 'CAMPUS_GRIEVANCE' and locks parent row (SELECT ... FOR UPDATE).
-- 2. Strictly prevents modification of RTI, Consumer, or general cases.
-- 3. Verifies child campus_cases record exists before updating.
-- 4. Enforces single-child row update (ROW_COUNT = 1); rolls back completely on any mismatch.
-- 5. Preserves existing child history without overwriting with empty arrays.
-- 6. Returns strictly allowlisted non-sensitive workflow fields.
-- 7. SECURITY DEFINER with SET search_path = '' and fail-closed service_role authorization.

CREATE OR REPLACE FUNCTION public.update_campus_grievance_status(
    p_case_id VARCHAR(64),
    p_new_status VARCHAR(64),
    p_proctor_notes TEXT DEFAULT NULL,
    p_hearing_date DATE DEFAULT NULL,
    p_action_taken TEXT DEFAULT NULL,
    p_resolution_details TEXT DEFAULT NULL,
    p_assigned_proctor TEXT DEFAULT NULL,
    p_assigned_committee TEXT DEFAULT NULL,
    p_history JSONB DEFAULT NULL
)
RETURNS JSONB
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = ''
AS $$
DECLARE
    v_case_uuid UUID;
    v_actual_case_type VARCHAR(64);
    v_updated_at TIMESTAMPTZ := timezone('utc'::text, now());
    v_child_updated_count INT;
    v_result JSONB;
BEGIN
    -- Runtime defense-in-depth check: fail-closed role check (NULL claims or non-service_role rejected)
    IF COALESCE(current_setting('request.jwt.claim.role', true), '') <> 'service_role'
       AND COALESCE(auth.role(), '') <> 'service_role' THEN
        RAISE EXCEPTION 'Access denied: update_campus_grievance_status is restricted to backend service_role only.';
    END IF;

    -- 1. Locate and lock authoritative parent case with explicit case_type check (Task 1)
    SELECT id, case_type INTO v_case_uuid, v_actual_case_type
    FROM public.cases
    WHERE case_id = p_case_id
    FOR UPDATE;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Case % not found', p_case_id;
    END IF;

    IF v_actual_case_type <> 'CAMPUS_GRIEVANCE' THEN
        RAISE EXCEPTION 'Case % is not a campus grievance (case_type mismatch: %)', p_case_id, v_actual_case_type;
    END IF;

    -- 2. Verify child campus_cases record exists before updating (Task 1)
    IF NOT EXISTS (
        SELECT 1 FROM public.campus_cases cc WHERE cc.id = v_case_uuid FOR UPDATE
    ) THEN
        RAISE EXCEPTION 'Campus case record not found for parent case % (id: %)', p_case_id, v_case_uuid;
    END IF;

    -- 3. Update authoritative parent in public.cases
    UPDATE public.cases
    SET
        status = p_new_status,
        updated_at = v_updated_at
    WHERE id = v_case_uuid;

    -- 4. Update campus-specific fields in public.campus_cases atomically (Task 4)
    -- Preserves existing history; appends new history only when provided; uses typed hearing_date
    UPDATE public.campus_cases
    SET
        proctor_notes = COALESCE(p_proctor_notes, proctor_notes),
        hearing_date = CASE
            WHEN p_hearing_date IS NOT NULL THEN p_hearing_date::text
            ELSE hearing_date
        END,
        action_taken = COALESCE(p_action_taken, action_taken),
        resolution_details = COALESCE(p_resolution_details, resolution_details),
        assigned_proctor = COALESCE(p_assigned_proctor, assigned_proctor),
        assigned_committee = COALESCE(p_assigned_committee, assigned_committee),
        history = CASE
            WHEN p_history IS NOT NULL AND jsonb_array_length(p_history) > 0 THEN
                COALESCE(history, '[]'::jsonb) || p_history
            ELSE history
        END
    WHERE id = v_case_uuid;

    GET DIAGNOSTICS v_child_updated_count = ROW_COUNT;
    IF v_child_updated_count <> 1 THEN
        RAISE EXCEPTION 'Atomic update violation: Expected exactly 1 child row updated, got %', v_child_updated_count;
    END IF;

    -- 5. Return strictly allowlisted non-sensitive workflow fields (Task 4)
    SELECT jsonb_build_object(
        'case_id', cc.case_id,
        'status', c.status,
        'updated_at', c.updated_at,
        'proctor_notes', cc.proctor_notes,
        'hearing_date', cc.hearing_date,
        'action_taken', cc.action_taken,
        'resolution_details', cc.resolution_details,
        'assigned_proctor', cc.assigned_proctor,
        'assigned_committee', cc.assigned_committee
    ) INTO v_result
    FROM public.campus_cases cc
    JOIN public.cases c ON c.id = cc.id
    WHERE cc.id = v_case_uuid;

    RETURN v_result;
END;
$$;

REVOKE ALL PRIVILEGES ON FUNCTION public.update_campus_grievance_status(
    VARCHAR(64), VARCHAR(64), TEXT, DATE, TEXT, TEXT, TEXT, TEXT, JSONB
) FROM PUBLIC, anon, authenticated;

GRANT EXECUTE ON FUNCTION public.update_campus_grievance_status(
    VARCHAR(64), VARCHAR(64), TEXT, DATE, TEXT, TEXT, TEXT, TEXT, JSONB
) TO service_role;

-- =====================================================================
-- 5. PUBLIC.PLATFORM_ADMINS (Database-Backed Admin Registry)
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
        role IN ('citizen', 'student', 'proctor', 'chief_proctor', 'committee_member', 'institution_admin', 'platform_admin')
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
        role IN ('proctor', 'chief_proctor', 'committee_member', 'institution_admin', 'platform_admin')
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
-- 8. AUTHORITATIVE private.can_officer_access_case(UUID, TEXT) FUNCTION
-- =====================================================================
-- Evaluates live database membership rows: checks active status and authorized officer roles.
-- Supports both primary institution_uuid and fallback institution_code.

CREATE OR REPLACE FUNCTION private.can_officer_access_case(
    p_institution_uuid UUID,
    p_institution_code TEXT DEFAULT NULL
)
RETURNS boolean
LANGUAGE sql STABLE SECURITY DEFINER
SET search_path = ''
AS $$
  SELECT EXISTS (
    SELECT 1
    FROM public.institution_memberships im
    WHERE im.user_id = auth.uid()
      AND (
        (p_institution_uuid IS NOT NULL AND im.institution_id = p_institution_uuid)
        OR (p_institution_uuid IS NULL AND p_institution_code IS NOT NULL AND im.institution_code = p_institution_code)
      )
      AND im.account_status = 'active'
      AND im.role IN ('proctor', 'chief_proctor', 'committee_member', 'institution_admin')
  );
$$;

REVOKE ALL PRIVILEGES ON FUNCTION private.can_officer_access_case(UUID, TEXT) FROM PUBLIC, anon;
GRANT EXECUTE ON FUNCTION private.can_officer_access_case(UUID, TEXT) TO authenticated, service_role;

-- =====================================================================
-- 8b. AUTHORITATIVE CAMPUS_CASES RLS POLICIES (Institutional Scoping & Confidentiality Gating)
-- =====================================================================
-- Replaces legacy migration 002 JWT app_metadata policies with live database checks.
-- Enforces:
-- 1. Standard / non-confidential grievances: viewable by all active institution officers for triage.
-- 2. Confidential / strict-confidential grievances: strictly viewable only by directly assigned proctor
--    or authorized committee members / institution admins. Unassigned proctors are blocked.

DROP POLICY IF EXISTS "Officers view institutional grievances" ON public.campus_cases;
CREATE POLICY "Officers view institutional grievances"
ON public.campus_cases FOR SELECT
TO authenticated
USING (
    private.is_platform_admin()
    OR (
        private.can_officer_access_case(institution_uuid, institution_id)
        AND (
            confidentiality_mode NOT IN ('CONFIDENTIAL', 'STRICT_CONFIDENTIAL')
            OR assigned_proctor = auth.uid()::text
            OR EXISTS (
                SELECT 1 FROM public.profiles p
                WHERE p.id = auth.uid() AND p.full_name IS NOT NULL AND p.full_name = campus_cases.assigned_proctor
            )
            OR EXISTS (
                SELECT 1 FROM public.institution_memberships im
                WHERE im.user_id = auth.uid()
                  AND (
                      (campus_cases.institution_uuid IS NOT NULL AND im.institution_id = campus_cases.institution_uuid)
                      OR (campus_cases.institution_uuid IS NULL AND im.institution_code = campus_cases.institution_id)
                  )
                  AND im.role IN ('committee_member', 'institution_admin')
                  AND im.account_status = 'active'
            )
        )
    )
);

DROP POLICY IF EXISTS "Officers update institutional grievances" ON public.campus_cases;
CREATE POLICY "Officers update institutional grievances"
ON public.campus_cases FOR UPDATE
TO authenticated
USING (
    private.is_platform_admin()
    OR (
        private.can_officer_access_case(institution_uuid, institution_id)
        AND (
            confidentiality_mode NOT IN ('CONFIDENTIAL', 'STRICT_CONFIDENTIAL')
            OR assigned_proctor = auth.uid()::text
            OR EXISTS (
                SELECT 1 FROM public.profiles p
                WHERE p.id = auth.uid() AND p.full_name IS NOT NULL AND p.full_name = campus_cases.assigned_proctor
            )
            OR EXISTS (
                SELECT 1 FROM public.institution_memberships im
                WHERE im.user_id = auth.uid()
                  AND (
                      (campus_cases.institution_uuid IS NOT NULL AND im.institution_id = campus_cases.institution_uuid)
                      OR (campus_cases.institution_uuid IS NULL AND im.institution_code = campus_cases.institution_id)
                  )
                  AND im.role IN ('committee_member', 'institution_admin')
                  AND im.account_status = 'active'
            )
        )
    )
)
WITH CHECK (
    private.is_platform_admin()
    OR (
        private.can_officer_access_case(institution_uuid, institution_id)
        AND (
            confidentiality_mode NOT IN ('CONFIDENTIAL', 'STRICT_CONFIDENTIAL')
            OR assigned_proctor = auth.uid()::text
            OR EXISTS (
                SELECT 1 FROM public.profiles p
                WHERE p.id = auth.uid() AND p.full_name IS NOT NULL AND p.full_name = campus_cases.assigned_proctor
            )
            OR EXISTS (
                SELECT 1 FROM public.institution_memberships im
                WHERE im.user_id = auth.uid()
                  AND (
                      (campus_cases.institution_uuid IS NOT NULL AND im.institution_id = campus_cases.institution_uuid)
                      OR (campus_cases.institution_uuid IS NULL AND im.institution_code = campus_cases.institution_id)
                  )
                  AND im.role IN ('committee_member', 'institution_admin')
                  AND im.account_status = 'active'
            )
        )
    )
);

DROP POLICY IF EXISTS "Strict delete platform admin only" ON public.campus_cases;
CREATE POLICY "Strict delete platform admin only"
ON public.campus_cases FOR DELETE
TO authenticated
USING (
    private.is_platform_admin()
);

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
        OR EXISTS (
            SELECT 1 FROM public.campus_cases cc
            WHERE cc.id = case_documents.case_uuid
              AND private.can_officer_access_case(cc.institution_uuid, cc.institution_id)
              AND (
                  (cc.confidentiality_mode NOT IN ('CONFIDENTIAL', 'STRICT_CONFIDENTIAL') AND case_documents.is_confidential IS NOT TRUE)
                  OR cc.assigned_proctor = auth.uid()::text
                  OR EXISTS (
                      SELECT 1 FROM public.institution_memberships im
                      WHERE im.user_id = auth.uid()
                        AND (
                            (cc.institution_uuid IS NOT NULL AND im.institution_id = cc.institution_uuid)
                            OR (cc.institution_uuid IS NULL AND im.institution_code = cc.institution_id)
                        )
                        AND im.role IN ('committee_member', 'institution_admin')
                        AND im.account_status = 'active'
                  )
              )
        )
    );

-- =====================================================================
-- 11. PUBLIC.AUDIT_ACTOR_MAPPINGS (Pseudonymous Audit Identity Vault - Task 2)
-- =====================================================================
-- Connects stable pseudonymous audit_actor_id to auth.users(id).
-- Approved erasure removes the mapping row, permanently unlinking historical events without modifying them.
-- Avoids fabricated users in auth.users while preventing FK deletion conflicts on immutable logs.

CREATE TABLE IF NOT EXISTS public.audit_actor_mappings (
    audit_actor_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID UNIQUE NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc'::text, now())
);

CREATE INDEX IF NOT EXISTS idx_audit_actor_user ON public.audit_actor_mappings(user_id);

ALTER TABLE public.audit_actor_mappings ENABLE ROW LEVEL SECURITY;

-- Mapping table is strictly backend-only (service_role)
REVOKE ALL PRIVILEGES ON public.audit_actor_mappings FROM PUBLIC, anon, authenticated;
GRANT SELECT, INSERT, UPDATE, DELETE ON public.audit_actor_mappings TO service_role;

-- Helper function to fetch calling user's audit_actor_id without granting general SELECT on audit_actor_mappings
CREATE OR REPLACE FUNCTION private.get_current_user_audit_actor_id()
RETURNS UUID
LANGUAGE sql STABLE SECURITY DEFINER
SET search_path = ''
AS $$
  SELECT aam.audit_actor_id
  FROM public.audit_actor_mappings aam
  WHERE aam.user_id = auth.uid();
$$;

REVOKE ALL PRIVILEGES ON FUNCTION private.get_current_user_audit_actor_id() FROM PUBLIC, anon;
GRANT EXECUTE ON FUNCTION private.get_current_user_audit_actor_id() TO authenticated, service_role;

-- =====================================================================
-- 13. PUBLIC.CASE_ACTIVITY_LOG (Append-Only Audit Trail)
-- =====================================================================
-- Task 3: References stable pseudonymous audit_actor_id (not auth.users directly).
-- audit_actor_id is NULL for SYSTEM and ANONYMOUS events; actor_type distinguishes provenance.
-- ip_address INET is strictly excluded; ICT perimeter logs are stored separately.
-- action_details strictly contains operational telemetry (NEVER personal PII or raw credentials).
-- Append-only under application permissions; guarded against client/officer modifications.

CREATE TABLE IF NOT EXISTS public.case_activity_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    case_uuid UUID NOT NULL REFERENCES public.cases(id) ON DELETE RESTRICT,
    case_id VARCHAR(64) NOT NULL,
    audit_actor_id UUID, -- Nullable for SYSTEM and ANONYMOUS actions; required for USER
    actor_type VARCHAR(16) NOT NULL DEFAULT 'USER' CHECK (
        actor_type IN ('USER', 'SYSTEM', 'ANONYMOUS')
    ),
    actor_role VARCHAR(32) NOT NULL,
    action_type VARCHAR(64) NOT NULL,
    action_details JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc'::text, now()),
    CONSTRAINT chk_audit_actor_integrity CHECK (
        (actor_type = 'USER' AND audit_actor_id IS NOT NULL) OR
        (actor_type IN ('SYSTEM', 'ANONYMOUS') AND audit_actor_id IS NULL)
    )
);

CREATE INDEX IF NOT EXISTS idx_case_activity_case ON public.case_activity_log(case_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_case_activity_uuid ON public.case_activity_log(case_uuid, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_case_activity_actor ON public.case_activity_log(audit_actor_id);

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
        -- 2. Authenticated users can view actions associated with their active audit_actor_id
        audit_actor_id = private.get_current_user_audit_actor_id()
        OR
        -- 3. Officers can view logs only for cases they are authorized to access (enforcing institutional scope & confidentiality)
        EXISTS (
            SELECT 1 FROM public.campus_cases cc
            WHERE cc.id = case_activity_log.case_uuid
              AND private.can_officer_access_case(cc.institution_uuid, cc.institution_id)
              AND (
                  cc.confidentiality_mode NOT IN ('CONFIDENTIAL', 'STRICT_CONFIDENTIAL')
                  OR cc.assigned_proctor = auth.uid()::text
                  OR EXISTS (
                      SELECT 1 FROM public.profiles p
                      WHERE p.id = auth.uid() AND p.full_name IS NOT NULL AND p.full_name = cc.assigned_proctor
                  )
                  OR EXISTS (
                      SELECT 1 FROM public.institution_memberships im
                      WHERE im.user_id = auth.uid()
                        AND (
                            (cc.institution_uuid IS NOT NULL AND im.institution_id = cc.institution_uuid)
                            OR (cc.institution_uuid IS NULL AND im.institution_code = cc.institution_id)
                        )
                        AND im.role IN ('committee_member', 'institution_admin')
                        AND im.account_status = 'active'
                  )
              )
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
-- 13. PUBLIC.LEGAL_PRECEDENTS (Curated Legal Intelligence)
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
-- 15. PRIVATE STORAGE BUCKET FOR CASE DOCUMENTS (Task 5)
-- =====================================================================
-- Idempotently creates private bucket 'case-documents' if Supabase storage schema exists

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.schemata WHERE schema_name = 'storage') THEN
        INSERT INTO storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
        VALUES (
            'case-documents',
            'case-documents',
            FALSE, -- Strictly private bucket
            10485760, -- 10MB maximum file size limit
            ARRAY['application/pdf', 'image/jpeg', 'image/png', 'image/webp']
        )
        ON CONFLICT (id) DO UPDATE SET
            public = FALSE,
            file_size_limit = 10485760,
            allowed_mime_types = ARRAY['application/pdf', 'image/jpeg', 'image/png', 'image/webp'];

        -- Authorized users view case attachments (strictly scoped; no broad SELECT)
        DROP POLICY IF EXISTS "Authenticated users view case attachments" ON storage.objects;
        DROP POLICY IF EXISTS "Authorized users view case attachments" ON storage.objects;
        CREATE POLICY "Authorized users view case attachments"
            ON storage.objects FOR SELECT
            TO authenticated
            USING (
                bucket_id = 'case-documents'
                AND (
                    -- 1. Platform Admin global oversight
                    private.is_platform_admin()
                    OR
                    -- 2. Direct uploader/owner
                    owner = auth.uid()
                    OR
                    EXISTS (
                        SELECT 1 FROM public.case_documents cd
                        WHERE cd.storage_path = storage.objects.name
                          AND cd.uploader_user_id = auth.uid()
                    )
                    OR
                    -- 3. Case Owner (Student)
                    EXISTS (
                        SELECT 1 FROM public.case_documents cd
                        JOIN public.campus_cases cc ON cc.id = cd.case_uuid
                        WHERE cd.storage_path = storage.objects.name
                          AND cc.student_user_id = auth.uid()
                    )
                    OR
                    -- 4. Authorized institutional officers matching case confidentiality
                    EXISTS (
                        SELECT 1 FROM public.case_documents cd
                        JOIN public.campus_cases cc ON cc.id = cd.case_uuid
                        WHERE cd.storage_path = storage.objects.name
                          AND private.can_officer_access_case(cc.institution_uuid, cc.institution_id)
                          AND (
                              (cc.confidentiality_mode NOT IN ('CONFIDENTIAL', 'STRICT_CONFIDENTIAL') AND cd.is_confidential IS NOT TRUE)
                              OR cc.assigned_proctor = auth.uid()::text
                              OR EXISTS (
                                  SELECT 1 FROM public.institution_memberships im
                                  WHERE im.user_id = auth.uid()
                                    AND (
                                        (cc.institution_uuid IS NOT NULL AND im.institution_id = cc.institution_uuid)
                                        OR (cc.institution_uuid IS NULL AND im.institution_code = cc.institution_id)
                                    )
                                    AND im.role IN ('committee_member', 'institution_admin')
                                    AND im.account_status = 'active'
                              )
                          )
                    )
                )
            );

        -- Backend service_role manages attachments
        DROP POLICY IF EXISTS "Service role manages case attachments" ON storage.objects;
        CREATE POLICY "Service role manages case attachments"
            ON storage.objects FOR ALL
            TO service_role
            USING (bucket_id = 'case-documents')
            WITH CHECK (bucket_id = 'case-documents');
    END IF;
END $$;

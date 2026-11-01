-- =====================================================================
-- NyayPath Migration: 20261101000003_lawyer_connect_schema.sql
-- Phase 5: Lawyer Workspace, Lawyer Directory, Consultation Requests & Consent-Based Case Sharing
-- Target Environment: Local Supabase PostgreSQL 17.11
-- =====================================================================

-- 1. Extend profiles.role to allow 'lawyer'
ALTER TABLE public.profiles DROP CONSTRAINT IF EXISTS profiles_role_check;
ALTER TABLE public.profiles ADD CONSTRAINT profiles_role_check CHECK (
    role IN ('citizen', 'student', 'proctor', 'chief_proctor', 'committee_member', 'institution_admin', 'platform_admin', 'lawyer')
);

-- 2. Lawyer Profiles Table
CREATE TABLE IF NOT EXISTS public.lawyer_profiles (
    id UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
    full_name TEXT NOT NULL,
    email TEXT NOT NULL,
    phone TEXT,
    bar_council TEXT NOT NULL,
    enrollment_state TEXT NOT NULL,
    enrollment_number TEXT NOT NULL,
    years_of_practice INT NOT NULL DEFAULT 0 CHECK (years_of_practice >= 0),
    specializations TEXT[] NOT NULL DEFAULT '{}',
    courts TEXT[] NOT NULL DEFAULT '{}',
    languages TEXT[] NOT NULL DEFAULT '{}',
    bio TEXT,
    consultation_preferences JSONB NOT NULL DEFAULT '{"modes": ["ONLINE", "IN_PERSON"], "consultation_fee": "PRO_BONO"}'::jsonb,
    photo_url TEXT,
    verification_status VARCHAR(20) NOT NULL DEFAULT 'PENDING' CHECK (
        verification_status IN ('PENDING', 'VERIFIED', 'REJECTED', 'SUSPENDED')
    ),
    verified_at TIMESTAMPTZ,
    verified_by UUID REFERENCES auth.users(id),
    verification_notes TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc'::text, now()),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc'::text, now())
);

CREATE INDEX IF NOT EXISTS idx_lawyer_profiles_verification ON public.lawyer_profiles(verification_status);
CREATE INDEX IF NOT EXISTS idx_lawyer_profiles_state ON public.lawyer_profiles(enrollment_state);
CREATE INDEX IF NOT EXISTS idx_lawyer_profiles_specializations ON public.lawyer_profiles USING GIN(specializations);

ALTER TABLE public.lawyer_profiles ENABLE ROW LEVEL SECURITY;

REVOKE ALL PRIVILEGES ON public.lawyer_profiles FROM PUBLIC, anon;
GRANT SELECT ON public.lawyer_profiles TO authenticated, anon;
GRANT ALL PRIVILEGES ON public.lawyer_profiles TO service_role;

DROP POLICY IF EXISTS "Public view verified lawyers only" ON public.lawyer_profiles;
CREATE POLICY "Public view verified lawyers only"
ON public.lawyer_profiles FOR SELECT
TO authenticated, anon
USING (
    verification_status = 'VERIFIED'
    OR (auth.uid() IS NOT NULL AND auth.uid() = id)
    OR (auth.uid() IS NOT NULL AND private.is_platform_admin(auth.uid()))
);

DROP POLICY IF EXISTS "Lawyers update own profile" ON public.lawyer_profiles;
CREATE POLICY "Lawyers update own profile"
ON public.lawyer_profiles FOR UPDATE
TO authenticated
USING (auth.uid() = id)
WITH CHECK (
    auth.uid() = id
    AND (
        -- Lawyers cannot self-verify
        verification_status = (SELECT lp.verification_status FROM public.lawyer_profiles lp WHERE lp.id = auth.uid())
    )
);

DROP POLICY IF EXISTS "Lawyers insert own profile" ON public.lawyer_profiles;
CREATE POLICY "Lawyers insert own profile"
ON public.lawyer_profiles FOR INSERT
TO authenticated
WITH CHECK (
    auth.uid() = id
    AND verification_status = 'PENDING'
);

-- Public view with masked enrollment details
CREATE OR REPLACE VIEW public.verified_lawyers AS
SELECT 
    id,
    full_name,
    email,
    phone,
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

GRANT SELECT ON public.verified_lawyers TO authenticated, anon;

-- 3. Consultation Requests Table
CREATE TABLE IF NOT EXISTS public.consultation_requests (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    citizen_user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    lawyer_user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    case_id VARCHAR(64),
    case_uuid UUID REFERENCES public.cases(id) ON DELETE SET NULL,
    legal_issue TEXT NOT NULL,
    description TEXT NOT NULL,
    preferred_mode VARCHAR(20) NOT NULL DEFAULT 'ONLINE' CHECK (
        preferred_mode IN ('ONLINE', 'IN_PERSON', 'PHONE')
    ),
    status VARCHAR(20) NOT NULL DEFAULT 'PENDING' CHECK (
        status IN ('PENDING', 'ACCEPTED', 'DECLINED', 'WITHDRAWN', 'COMPLETED')
    ),
    lawyer_response TEXT,
    response_date TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc'::text, now()),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc'::text, now())
);

CREATE INDEX IF NOT EXISTS idx_consultation_requests_citizen ON public.consultation_requests(citizen_user_id);
CREATE INDEX IF NOT EXISTS idx_consultation_requests_lawyer ON public.consultation_requests(lawyer_user_id);
CREATE INDEX IF NOT EXISTS idx_consultation_requests_status ON public.consultation_requests(status);

ALTER TABLE public.consultation_requests ENABLE ROW LEVEL SECURITY;

REVOKE ALL PRIVILEGES ON public.consultation_requests FROM PUBLIC, anon;
GRANT SELECT, INSERT, UPDATE ON public.consultation_requests TO authenticated;
GRANT ALL PRIVILEGES ON public.consultation_requests TO service_role;

DROP POLICY IF EXISTS "Users view their own consultation requests" ON public.consultation_requests;
CREATE POLICY "Users view their own consultation requests"
ON public.consultation_requests FOR SELECT
TO authenticated
USING (
    citizen_user_id = auth.uid()
    OR lawyer_user_id = auth.uid()
    OR private.is_platform_admin(auth.uid())
);

DROP POLICY IF EXISTS "Citizens create consultation requests" ON public.consultation_requests;
CREATE POLICY "Citizens create consultation requests"
ON public.consultation_requests FOR INSERT
TO authenticated
WITH CHECK (
    citizen_user_id = auth.uid()
);

DROP POLICY IF EXISTS "Participants update consultation requests" ON public.consultation_requests;
CREATE POLICY "Participants update consultation requests"
ON public.consultation_requests FOR UPDATE
TO authenticated
USING (
    citizen_user_id = auth.uid()
    OR lawyer_user_id = auth.uid()
    OR private.is_platform_admin(auth.uid())
);

-- 4. Lawyer Case Access (Explicit Consent-Based Case Sharing & Revocation)
CREATE TABLE IF NOT EXISTS public.lawyer_case_access (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    case_id VARCHAR(64) NOT NULL,
    case_uuid UUID NOT NULL REFERENCES public.cases(id) ON DELETE CASCADE,
    citizen_user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    lawyer_user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    consultation_request_id UUID REFERENCES public.consultation_requests(id) ON DELETE SET NULL,
    access_status VARCHAR(20) NOT NULL DEFAULT 'ACTIVE' CHECK (
        access_status IN ('ACTIVE', 'REVOKED')
    ),
    shared_scope VARCHAR(32) NOT NULL DEFAULT 'CASE_AND_DOCS' CHECK (
        shared_scope IN ('METADATA_ONLY', 'CASE_AND_DOCS')
    ),
    granted_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc'::text, now()),
    revoked_at TIMESTAMPTZ,
    CONSTRAINT uq_case_lawyer_access UNIQUE (case_uuid, lawyer_user_id)
);

CREATE INDEX IF NOT EXISTS idx_lawyer_case_access_lawyer ON public.lawyer_case_access(lawyer_user_id, access_status);
CREATE INDEX IF NOT EXISTS idx_lawyer_case_access_case ON public.lawyer_case_access(case_uuid, access_status);
CREATE INDEX IF NOT EXISTS idx_lawyer_case_access_citizen ON public.lawyer_case_access(citizen_user_id);

ALTER TABLE public.lawyer_case_access ENABLE ROW LEVEL SECURITY;

REVOKE ALL PRIVILEGES ON public.lawyer_case_access FROM PUBLIC, anon;
GRANT SELECT, INSERT, UPDATE ON public.lawyer_case_access TO authenticated;
GRANT ALL PRIVILEGES ON public.lawyer_case_access TO service_role;

DROP POLICY IF EXISTS "Users view their lawyer case access" ON public.lawyer_case_access;
CREATE POLICY "Users view their lawyer case access"
ON public.lawyer_case_access FOR SELECT
TO authenticated
USING (
    citizen_user_id = auth.uid()
    OR lawyer_user_id = auth.uid()
    OR private.is_platform_admin(auth.uid())
);

-- 5. Platform Admin Verification Security Definer RPC
CREATE OR REPLACE FUNCTION public.admin_verify_lawyer(
    p_lawyer_user_id UUID,
    p_decision VARCHAR(20),
    p_notes TEXT DEFAULT NULL
)
RETURNS JSONB
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public, auth, pg_temp
AS $$
DECLARE
    v_admin_id UUID := auth.uid();
    v_updated RECORD;
BEGIN
    IF v_admin_id IS NOT NULL AND NOT private.is_platform_admin(v_admin_id) THEN
        RAISE EXCEPTION 'Access denied: Only platform administrators can verify or reject lawyers.';
    END IF;

    IF p_decision NOT IN ('VERIFIED', 'REJECTED', 'SUSPENDED') THEN
        RAISE EXCEPTION 'Invalid verification decision: Must be VERIFIED, REJECTED, or SUSPENDED.';
    END IF;

    UPDATE public.lawyer_profiles
    SET 
        verification_status = p_decision,
        verified_at = CASE WHEN p_decision = 'VERIFIED' THEN timezone('utc'::text, now()) ELSE verified_at END,
        verified_by = v_admin_id,
        verification_notes = COALESCE(p_notes, verification_notes),
        updated_at = timezone('utc'::text, now())
    WHERE id = p_lawyer_user_id
    RETURNING * INTO v_updated;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Lawyer profile not found for user %', p_lawyer_user_id;
    END IF;

    IF p_decision = 'VERIFIED' THEN
        UPDATE public.profiles SET role = 'lawyer', updated_at = timezone('utc'::text, now()) WHERE id = p_lawyer_user_id;
    ELSIF p_decision = 'SUSPENDED' THEN
        UPDATE public.profiles SET account_status = 'suspended', updated_at = timezone('utc'::text, now()) WHERE id = p_lawyer_user_id;
    END IF;

    RETURN jsonb_build_object(
        'status', 'success',
        'lawyer_user_id', p_lawyer_user_id,
        'verification_status', p_decision
    );
END;
$$;

REVOKE ALL PRIVILEGES ON FUNCTION public.admin_verify_lawyer(UUID, VARCHAR, TEXT) FROM PUBLIC, anon;
GRANT EXECUTE ON FUNCTION public.admin_verify_lawyer(UUID, VARCHAR, TEXT) TO authenticated, service_role;

NOTIFY pgrst, 'reload schema';


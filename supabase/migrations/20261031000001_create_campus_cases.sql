-- =====================================================================
-- NyayPath Database Migration: 001_create_campus_cases.sql
-- Description: Creates persistent table, indexes, and RLS policies for 
--              College Proctorial & Student Grievance Redressal System.
-- Author: Senior Software Architect / NyayPath Engineering Team
-- =====================================================================

-- 1. Enable UUID Extension (standard in PostgreSQL / Supabase)
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- 2. Create campus_cases table
CREATE TABLE IF NOT EXISTS public.campus_cases (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    case_id TEXT NOT NULL,
    institution_id TEXT NOT NULL DEFAULT 'INST_DEFAULT',
    student_user_id UUID REFERENCES auth.users(id) ON DELETE SET NULL,
    student_name TEXT,
    roll_number TEXT,
    department TEXT NOT NULL,
    year TEXT NOT NULL,
    category TEXT NOT NULL,
    subject TEXT NOT NULL,
    description TEXT NOT NULL,
    incident_date TEXT,
    is_anonymous BOOLEAN NOT NULL DEFAULT FALSE,
    confidentiality_mode TEXT NOT NULL DEFAULT 'CONFIDENTIAL',
    severity TEXT NOT NULL DEFAULT 'NORMAL',
    status TEXT NOT NULL DEFAULT 'SUBMITTED',
    proctor_notes TEXT DEFAULT 'Grievance received by the Proctorial Grievance Redressal Cell. Acknowledged.',
    hearing_date TEXT DEFAULT 'Pending Proctorial Review',
    action_taken TEXT DEFAULT 'Pending inquiry by departmental committee.',
    resolution_details TEXT,
    resolution_deadline DATE,
    assigned_proctor TEXT,
    assigned_proctor_user_id UUID REFERENCES auth.users(id) ON DELETE SET NULL,
    assigned_committee TEXT,
    supporting_documents JSONB NOT NULL DEFAULT '[]'::jsonb,
    verification_key_hash TEXT NOT NULL,
    history JSONB NOT NULL DEFAULT '[]'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc'::text, now()),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc'::text, now()),

    -- Constraints
    CONSTRAINT uq_campus_cases_case_id UNIQUE (case_id),
    CONSTRAINT ck_campus_cases_status CHECK (
        status IN ('SUBMITTED', 'UNDER_INQUIRY', 'HEARING_SCHEDULED', 'ACTION_TAKEN', 'RESOLVED', 'CLOSED')
    ),
    CONSTRAINT ck_campus_cases_severity CHECK (
        severity IN ('NORMAL', 'HIGH', 'URGENT')
    )
);

-- 3. High-Performance Indexes
CREATE INDEX IF NOT EXISTS idx_campus_cases_case_id ON public.campus_cases(case_id);
CREATE INDEX IF NOT EXISTS idx_campus_cases_institution ON public.campus_cases(institution_id);
CREATE INDEX IF NOT EXISTS idx_campus_cases_status ON public.campus_cases(status);
CREATE INDEX IF NOT EXISTS idx_campus_cases_created_at ON public.campus_cases(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_campus_cases_student_user ON public.campus_cases(student_user_id) WHERE student_user_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_campus_cases_assigned_proctor_uuid ON public.campus_cases(assigned_proctor_user_id) WHERE assigned_proctor_user_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_campus_cases_verification ON public.campus_cases(case_id, verification_key_hash);

-- 4. Automatic updated_at trigger function
CREATE OR REPLACE FUNCTION public.set_current_timestamp_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = timezone('utc'::text, now());
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_campus_cases_updated_at ON public.campus_cases;
CREATE TRIGGER trg_campus_cases_updated_at
BEFORE UPDATE ON public.campus_cases
FOR EACH ROW
EXECUTE FUNCTION public.set_current_timestamp_updated_at();

-- 5. Enable Row Level Security (RLS)
ALTER TABLE public.campus_cases ENABLE ROW LEVEL SECURITY;

-- 6. Row Level Security Policies

-- Policy 1: Public / Anon can INSERT new grievances (Student submission workflow)
DROP POLICY IF EXISTS "Allow student grievance submission" ON public.campus_cases;
CREATE POLICY "Allow student grievance submission"
ON public.campus_cases
FOR INSERT
TO public, anon, authenticated
WITH CHECK (true);

-- Policy 2: Authenticated student can view their own grievances
DROP POLICY IF EXISTS "Students view own grievances" ON public.campus_cases;
CREATE POLICY "Students view own grievances"
ON public.campus_cases
FOR SELECT
TO authenticated
USING (
    student_user_id = auth.uid()
);

-- Policy 3: Proctors and Committee Members can SELECT grievances for their institution
DROP POLICY IF EXISTS "Proctors view institutional grievances" ON public.campus_cases;
CREATE POLICY "Proctors view institutional grievances"
ON public.campus_cases
FOR SELECT
TO authenticated
USING (
    institution_id = (auth.jwt() -> 'app_metadata' ->> 'institution_id')
    OR (auth.jwt() -> 'app_metadata' ->> 'role') = 'platform_admin'
);

-- Policy 4: Proctors, Committee Members and Institution Admins can UPDATE institutional grievances
DROP POLICY IF EXISTS "Proctors update institutional grievances" ON public.campus_cases;
CREATE POLICY "Proctors update institutional grievances"
ON public.campus_cases
FOR UPDATE
TO authenticated
USING (
    institution_id = (auth.jwt() -> 'app_metadata' ->> 'institution_id')
    OR (auth.jwt() -> 'app_metadata' ->> 'role') = 'platform_admin'
)
WITH CHECK (
    institution_id = (auth.jwt() -> 'app_metadata' ->> 'institution_id')
    OR (auth.jwt() -> 'app_metadata' ->> 'role') = 'platform_admin'
);

-- Policy 5: Platform Administrators have unrestricted access
DROP POLICY IF EXISTS "Platform admin full access" ON public.campus_cases;
CREATE POLICY "Platform admin full access"
ON public.campus_cases
FOR ALL
TO authenticated
USING (
    (auth.jwt() -> 'app_metadata' ->> 'role') = 'platform_admin'
);

-- =====================================================================
-- ROLLBACK SCRIPT (Run only to revert migration):
-- ---------------------------------------------------------------------
-- DROP TABLE IF EXISTS public.campus_cases CASCADE;
-- DROP FUNCTION IF EXISTS public.set_current_timestamp_updated_at CASCADE;
-- =====================================================================

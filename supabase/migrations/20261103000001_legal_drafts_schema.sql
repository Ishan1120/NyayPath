-- =====================================================================
-- NyayPath Migration: Legal Drafts Persistence & Scope Expansion
-- Version: 20261103000001
-- Scope: Local forward-only migration for legal drafts storage,
--        draft-to-lawyer linking, and expanded lawyer consent scopes.
-- DO NOT APPLY TO REMOTE STAGING WITHOUT SEPARATE AUTHORIZATION.
-- =====================================================================

-- 1. PUBLIC.LEGAL_DRAFTS
CREATE TABLE IF NOT EXISTS public.legal_drafts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    case_id VARCHAR(100),
    title VARCHAR(255) NOT NULL DEFAULT 'Untitled Draft',
    document_type VARCHAR(100) NOT NULL DEFAULT 'RTI',
    facts TEXT,
    legal_provisions TEXT,
    requested_relief TEXT,
    draft_content TEXT NOT NULL,
    lawyer_brief TEXT,
    status VARCHAR(50) NOT NULL DEFAULT 'DRAFT' CHECK (
        status IN ('DRAFT', 'SAVED', 'FINALIZED', 'SHARED', 'ARCHIVED')
    ),
    version INTEGER NOT NULL DEFAULT 1 CHECK (version >= 1),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_legal_drafts_user ON public.legal_drafts(user_id);
CREATE INDEX IF NOT EXISTS idx_legal_drafts_case ON public.legal_drafts(case_id);
CREATE INDEX IF NOT EXISTS idx_legal_drafts_status ON public.legal_drafts(status);

-- Enable Row Level Security
ALTER TABLE public.legal_drafts ENABLE ROW LEVEL SECURITY;

-- Revoke broad permissions
REVOKE ALL PRIVILEGES ON public.legal_drafts FROM PUBLIC, anon;
GRANT SELECT, INSERT, UPDATE, DELETE ON public.legal_drafts TO authenticated;
GRANT ALL ON public.legal_drafts TO service_role;

-- RLS Policy: Users can only manage their own drafts
DROP POLICY IF EXISTS "Users can manage own legal drafts" ON public.legal_drafts;
CREATE POLICY "Users can manage own legal drafts"
    ON public.legal_drafts FOR ALL
    TO authenticated
    USING (user_id = auth.uid())
    WITH CHECK (user_id = auth.uid());

-- Trigger to maintain updated_at
CREATE OR REPLACE FUNCTION private.set_updated_at_timestamp()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

DROP TRIGGER IF EXISTS trg_legal_drafts_updated_at ON public.legal_drafts;
CREATE TRIGGER trg_legal_drafts_updated_at
    BEFORE UPDATE ON public.legal_drafts
    FOR EACH ROW
    EXECUTE FUNCTION private.set_updated_at_timestamp();

-- 2. Add draft link columns to consultation_requests if they do not exist
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_schema = 'public' 
          AND table_name = 'consultation_requests' 
          AND column_name = 'draft_id'
    ) THEN
        ALTER TABLE public.consultation_requests 
        ADD COLUMN draft_id UUID REFERENCES public.legal_drafts(id) ON DELETE SET NULL;
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_schema = 'public' 
          AND table_name = 'consultation_requests' 
          AND column_name = 'include_draft'
    ) THEN
        ALTER TABLE public.consultation_requests 
        ADD COLUMN include_draft BOOLEAN NOT NULL DEFAULT false;
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_schema = 'public' 
          AND table_name = 'consultation_requests' 
          AND column_name = 'consent_text'
    ) THEN
        ALTER TABLE public.consultation_requests 
        ADD COLUMN consent_text TEXT;
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_schema = 'public' 
          AND table_name = 'consultation_requests' 
          AND column_name = 'consent_timestamp'
    ) THEN
        ALTER TABLE public.consultation_requests 
        ADD COLUMN consent_timestamp TIMESTAMPTZ;
    END IF;
END $$;

-- 3. Expand shared_scope constraint on lawyer_case_access to allow 'FULL'
DO $$
BEGIN
    -- Drop existing check constraint if it restricts to only METADATA_ONLY and CASE_AND_DOCS
    IF EXISTS (
        SELECT 1 FROM pg_constraint 
        WHERE conname = 'lawyer_case_access_shared_scope_check'
    ) THEN
        ALTER TABLE public.lawyer_case_access 
        DROP CONSTRAINT lawyer_case_access_shared_scope_check;
    END IF;

    ALTER TABLE public.lawyer_case_access 
    ADD CONSTRAINT lawyer_case_access_shared_scope_check 
    CHECK (shared_scope IN ('METADATA_ONLY', 'CASE_AND_DOCS', 'FULL'));
END $$;


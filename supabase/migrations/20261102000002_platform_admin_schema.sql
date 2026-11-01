-- =====================================================================
-- NyayPath Migration: 20261102000002_platform_admin_schema.sql
-- Description: Phase 7 Platform Administration & Immutable Audit Trail
-- Author: Senior Platform Architect / NyayPath Engineering Team
-- =====================================================================

-- 1. Create Immutable Platform Audit Logs Table
CREATE TABLE IF NOT EXISTS public.platform_audit_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    actor_user_id UUID REFERENCES auth.users(id) ON DELETE SET NULL,
    actor_email TEXT,
    actor_role VARCHAR(32) NOT NULL DEFAULT 'platform_admin',
    action_type VARCHAR(64) NOT NULL,
    target_entity_type VARCHAR(64) NOT NULL,
    target_entity_id TEXT NOT NULL,
    institution_code VARCHAR(64),
    details JSONB NOT NULL DEFAULT '{}'::jsonb,
    reason TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc'::text, now())
);

-- 2. Indexes for Querying and Filtering
CREATE INDEX IF NOT EXISTS idx_platform_audit_action ON public.platform_audit_logs(action_type, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_platform_audit_entity ON public.platform_audit_logs(target_entity_type, target_entity_id);
CREATE INDEX IF NOT EXISTS idx_platform_audit_actor ON public.platform_audit_logs(actor_user_id);
CREATE INDEX IF NOT EXISTS idx_platform_audit_created ON public.platform_audit_logs(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_platform_audit_inst ON public.platform_audit_logs(institution_code) WHERE institution_code IS NOT NULL;

-- 3. Immutability Trigger: Prohibits UPDATE and DELETE operations
CREATE OR REPLACE FUNCTION private.prevent_platform_audit_log_modification()
RETURNS TRIGGER AS $$
BEGIN
    RAISE EXCEPTION 'Platform audit log is strictly immutable: UPDATE and DELETE operations are prohibited.';
END;
$$ LANGUAGE plpgsql SECURITY DEFINER SET search_path = '';

DROP TRIGGER IF EXISTS trg_platform_audit_immutability ON public.platform_audit_logs;
CREATE TRIGGER trg_platform_audit_immutability
    BEFORE UPDATE OR DELETE ON public.platform_audit_logs
    FOR EACH ROW EXECUTE FUNCTION private.prevent_platform_audit_log_modification();

-- 4. Row Level Security for Platform Audit Logs
ALTER TABLE public.platform_audit_logs ENABLE ROW LEVEL SECURITY;

REVOKE ALL PRIVILEGES ON public.platform_audit_logs FROM PUBLIC, anon;
GRANT SELECT ON public.platform_audit_logs TO authenticated;
GRANT SELECT, INSERT ON public.platform_audit_logs TO service_role;

DROP POLICY IF EXISTS "Platform admins view platform audit logs" ON public.platform_audit_logs;
CREATE POLICY "Platform admins view platform audit logs"
    ON public.platform_audit_logs FOR SELECT
    TO authenticated
    USING (private.is_platform_admin());

DROP POLICY IF EXISTS "Platform admins insert platform audit logs" ON public.platform_audit_logs;
CREATE POLICY "Platform admins insert platform audit logs"
    ON public.platform_audit_logs FOR INSERT
    TO authenticated
    WITH CHECK (private.is_platform_admin());

-- 5. RPC Helper for Audited Exceptional Case Access
CREATE OR REPLACE FUNCTION public.admin_audit_exceptional_access(
    p_case_id TEXT,
    p_reason TEXT,
    p_metadata JSONB DEFAULT '{}'::jsonb
)
RETURNS JSONB
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public, auth, pg_temp
AS $$
DECLARE
    v_admin_id UUID := auth.uid();
    v_admin_email TEXT;
    v_log_id UUID;
BEGIN
    IF v_admin_id IS NOT NULL AND NOT private.is_platform_admin(v_admin_id) THEN
        RAISE EXCEPTION 'Access denied: Only platform administrators can record exceptional confidential access.';
    END IF;

    IF p_reason IS NULL OR length(trim(p_reason)) < 10 THEN
        RAISE EXCEPTION 'A legitimate operational reason (minimum 10 characters) is required for exceptional case access.';
    END IF;

    SELECT email INTO v_admin_email FROM auth.users WHERE id = v_admin_id;

    INSERT INTO public.platform_audit_logs (
        actor_user_id,
        actor_email,
        actor_role,
        action_type,
        target_entity_type,
        target_entity_id,
        reason,
        details
    ) VALUES (
        v_admin_id,
        COALESCE(v_admin_email, 'platform-admin@nyaypath.gov'),
        'platform_admin',
        'EXCEPTIONAL_CONFIDENTIAL_CASE_ACCESS',
        'CASE',
        p_case_id,
        p_reason,
        COALESCE(p_metadata, '{}'::jsonb)
    ) RETURNING id INTO v_log_id;

    RETURN jsonb_build_object(
        'status', 'success',
        'audit_log_id', v_log_id,
        'case_id', p_case_id,
        'timestamp', timezone('utc'::text, now())
    );
END;
$$;

REVOKE ALL PRIVILEGES ON FUNCTION public.admin_audit_exceptional_access(TEXT, TEXT, JSONB) FROM PUBLIC, anon;
GRANT EXECUTE ON FUNCTION public.admin_audit_exceptional_access(TEXT, TEXT, JSONB) TO authenticated, service_role;

NOTIFY pgrst, 'reload schema';


-- Migration: 20261101000002_notifications_hardening.sql
-- Description: Phase 3 Notification Data Integrity, Immutability Trigger & Least-Privilege Grants

-- 1. Create Trigger Function to Enforce Immutability of Core Notification Fields
CREATE OR REPLACE FUNCTION private.enforce_notification_immutability()
RETURNS TRIGGER
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public, pg_temp
AS $$
BEGIN
    -- Disallow changes to primary key, recipient, event type, content, case references, or timestamps
    IF NEW.id <> OLD.id OR
       NEW.recipient_user_id <> OLD.recipient_user_id OR
       NEW.event_type <> OLD.event_type OR
       NEW.title <> OLD.title OR
       NEW.message <> OLD.message OR
       NEW.related_case_id <> OLD.related_case_id OR
       NEW.created_at <> OLD.created_at OR
       (NEW.case_uuid IS DISTINCT FROM OLD.case_uuid) OR
       (NEW.action_url IS DISTINCT FROM OLD.action_url) OR
       (NEW.idempotency_key IS DISTINCT FROM OLD.idempotency_key) OR
       (NEW.metadata IS DISTINCT FROM OLD.metadata) THEN
        RAISE EXCEPTION 'Notification content is immutable. Only is_read and read_at can be modified by users.';
    END IF;

    -- Automatically update read_at timestamp when is_read transitions from false to true
    IF NEW.is_read = true AND OLD.is_read = false AND NEW.read_at IS NULL THEN
        NEW.read_at := timezone('utc'::text, now());
    END IF;

    RETURN NEW;
END;
$$;

-- 2. Bind BEFORE UPDATE trigger to public.notifications
DROP TRIGGER IF EXISTS trg_notification_immutability ON public.notifications;
CREATE TRIGGER trg_notification_immutability
    BEFORE UPDATE ON public.notifications
    FOR EACH ROW
    EXECUTE FUNCTION private.enforce_notification_immutability();

-- 3. Least-Privilege Table Grants on public.notifications
-- Revoke all table-level privileges from anon and authenticated
REVOKE ALL ON TABLE public.notifications FROM PUBLIC, anon, authenticated;

-- Authenticated users may ONLY select their own rows, delete/dismiss them, or update is_read & read_at
GRANT SELECT, DELETE ON TABLE public.notifications TO authenticated;
GRANT UPDATE (is_read, read_at) ON TABLE public.notifications TO authenticated;

-- Service role retains full administrative privileges for server-side dispatch
GRANT ALL ON TABLE public.notifications TO service_role;

-- 4. Restrict private.create_notification Execution to service_role Only
REVOKE ALL ON FUNCTION private.create_notification(UUID, VARCHAR, TEXT, TEXT, VARCHAR, UUID, TEXT, TEXT, JSONB) FROM PUBLIC, anon, authenticated;
GRANT EXECUTE ON FUNCTION private.create_notification(UUID, VARCHAR, TEXT, TEXT, VARCHAR, UUID, TEXT, TEXT, JSONB) TO service_role;

-- 5. Tighten RLS UPDATE policy to explicitly restrict modification
DROP POLICY IF EXISTS "Users can update own notifications" ON public.notifications;
CREATE POLICY "Users can update own notification read status"
    ON public.notifications
    FOR UPDATE
    TO authenticated
    USING (recipient_user_id = auth.uid())
    WITH CHECK (recipient_user_id = auth.uid());

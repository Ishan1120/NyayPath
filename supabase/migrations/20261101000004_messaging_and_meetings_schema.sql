-- =====================================================================
-- NyayPath Migration: 20261101000004_messaging_and_meetings_schema.sql
-- Phase 6: Secure Messaging, Client Communication & Meeting Scheduling
-- Target Environment: Local Supabase PostgreSQL 17.11
-- =====================================================================

-- 1. CONVERSATIONS TABLE
CREATE TABLE IF NOT EXISTS public.conversations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    conversation_type VARCHAR(32) NOT NULL CHECK (
        conversation_type IN ('LAWYER_CITIZEN', 'INSTITUTION_CASE', 'GENERAL_CASE')
    ),
    title TEXT,
    related_case_uuid UUID REFERENCES public.cases(id) ON DELETE SET NULL,
    related_case_id VARCHAR(64),
    consultation_request_id UUID REFERENCES public.consultation_requests(id) ON DELETE SET NULL,
    created_by UUID NOT NULL REFERENCES auth.users(id) ON DELETE RESTRICT,
    conversation_status VARCHAR(20) NOT NULL DEFAULT 'ACTIVE' CHECK (
        conversation_status IN ('ACTIVE', 'ARCHIVED', 'BLOCKED')
    ),
    last_message_preview TEXT,
    last_message_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc'::text, now()),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc'::text, now())
);

CREATE INDEX IF NOT EXISTS idx_conversations_type ON public.conversations(conversation_type);
CREATE INDEX IF NOT EXISTS idx_conversations_status ON public.conversations(conversation_status);
CREATE INDEX IF NOT EXISTS idx_conversations_case ON public.conversations(related_case_uuid);
CREATE INDEX IF NOT EXISTS idx_conversations_consultation ON public.conversations(consultation_request_id);
CREATE INDEX IF NOT EXISTS idx_conversations_updated ON public.conversations(updated_at DESC);

-- 2. CONVERSATION PARTICIPANTS TABLE
CREATE TABLE IF NOT EXISTS public.conversation_participants (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    conversation_id UUID NOT NULL REFERENCES public.conversations(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    participant_role VARCHAR(32) NOT NULL DEFAULT 'member' CHECK (
        participant_role IN ('citizen', 'lawyer', 'proctor', 'chief_proctor', 'committee_member', 'admin', 'member')
    ),
    joined_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc'::text, now()),
    last_read_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc'::text, now()),
    participant_status VARCHAR(20) NOT NULL DEFAULT 'ACTIVE' CHECK (
        participant_status IN ('ACTIVE', 'LEFT', 'REMOVED')
    ),
    CONSTRAINT uq_conversation_participant UNIQUE (conversation_id, user_id)
);

CREATE INDEX IF NOT EXISTS idx_participants_user ON public.conversation_participants(user_id);
CREATE INDEX IF NOT EXISTS idx_participants_conv ON public.conversation_participants(conversation_id);

-- 3. MESSAGES TABLE
CREATE TABLE IF NOT EXISTS public.messages (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    conversation_id UUID NOT NULL REFERENCES public.conversations(id) ON DELETE CASCADE,
    sender_user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE RESTRICT,
    message_type VARCHAR(20) NOT NULL DEFAULT 'TEXT' CHECK (
        message_type IN ('TEXT', 'ATTACHMENT', 'SYSTEM', 'MEETING_LINK')
    ),
    message_body TEXT NOT NULL,
    client_message_id VARCHAR(128),
    created_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc'::text, now()),
    edited_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_messages_conv_created ON public.messages(conversation_id, created_at ASC);
CREATE INDEX IF NOT EXISTS idx_messages_sender ON public.messages(sender_user_id);
CREATE UNIQUE INDEX IF NOT EXISTS idx_messages_idempotency ON public.messages(conversation_id, client_message_id) 
    WHERE client_message_id IS NOT NULL;

-- 4. MESSAGE ATTACHMENTS TABLE
CREATE TABLE IF NOT EXISTS public.message_attachments (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    message_id UUID NOT NULL REFERENCES public.messages(id) ON DELETE CASCADE,
    conversation_id UUID NOT NULL REFERENCES public.conversations(id) ON DELETE CASCADE,
    storage_path TEXT NOT NULL,
    file_name TEXT NOT NULL,
    mime_type TEXT NOT NULL,
    file_size INTEGER NOT NULL,
    uploaded_by UUID NOT NULL REFERENCES auth.users(id) ON DELETE RESTRICT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc'::text, now())
);

CREATE INDEX IF NOT EXISTS idx_attachments_msg ON public.message_attachments(message_id);
CREATE INDEX IF NOT EXISTS idx_attachments_conv ON public.message_attachments(conversation_id);

-- 5. CONSULTATION MEETINGS TABLE
CREATE TABLE IF NOT EXISTS public.consultation_meetings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    consultation_request_id UUID REFERENCES public.consultation_requests(id) ON DELETE SET NULL,
    conversation_id UUID REFERENCES public.conversations(id) ON DELETE SET NULL,
    citizen_user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    lawyer_user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    case_uuid UUID REFERENCES public.cases(id) ON DELETE SET NULL,
    case_id VARCHAR(64),
    scheduled_start TIMESTAMPTZ NOT NULL,
    scheduled_end TIMESTAMPTZ NOT NULL,
    meeting_mode VARCHAR(20) NOT NULL DEFAULT 'ONLINE' CHECK (
        meeting_mode IN ('ONLINE', 'IN_PERSON', 'PHONE')
    ),
    status VARCHAR(30) NOT NULL DEFAULT 'REQUESTED' CHECK (
        status IN ('REQUESTED', 'CONFIRMED', 'DECLINED', 'RESCHEDULE_REQUESTED', 'CANCELLED', 'COMPLETED', 'NO_SHOW')
    ),
    agenda TEXT,
    online_meeting_url TEXT,
    location_details TEXT,
    phone_contact TEXT,
    notes TEXT,
    created_by UUID NOT NULL REFERENCES auth.users(id) ON DELETE RESTRICT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc'::text, now()),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc'::text, now())
);

CREATE INDEX IF NOT EXISTS idx_meetings_lawyer_time ON public.consultation_meetings(lawyer_user_id, scheduled_start, scheduled_end);
CREATE INDEX IF NOT EXISTS idx_meetings_citizen ON public.consultation_meetings(citizen_user_id);
CREATE INDEX IF NOT EXISTS idx_meetings_consultation ON public.consultation_meetings(consultation_request_id);
CREATE INDEX IF NOT EXISTS idx_meetings_status ON public.consultation_meetings(status);

-- 6. LAWYER AVAILABILITY TABLE
CREATE TABLE IF NOT EXISTS public.lawyer_availability (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    lawyer_user_id UUID UNIQUE NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    available_days INTEGER[] NOT NULL DEFAULT '{1,2,3,4,5}',
    start_time_utc TIME NOT NULL DEFAULT '04:30:00',
    end_time_utc TIME NOT NULL DEFAULT '12:30:00',
    slot_duration_minutes INTEGER NOT NULL DEFAULT 30 CHECK (slot_duration_minutes >= 15 AND slot_duration_minutes <= 120),
    timezone VARCHAR(64) NOT NULL DEFAULT 'Asia/Kolkata',
    unavailable_dates DATE[] NOT NULL DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc'::text, now()),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc'::text, now())
);

CREATE INDEX IF NOT EXISTS idx_lawyer_availability_user ON public.lawyer_availability(lawyer_user_id);

-- 7. STORAGE BUCKET FOR MESSAGE ATTACHMENTS
INSERT INTO storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
VALUES (
    'message-attachments',
    'message-attachments',
    false,
    10485760, -- 10MB
    ARRAY['application/pdf', 'image/jpeg', 'image/png', 'image/webp']
)
ON CONFLICT (id) DO NOTHING;

-- 8. TRIGGER TO AUTO-UPDATE CONVERSATION PREVIEW ON NEW MESSAGE
CREATE OR REPLACE FUNCTION private.trg_update_conversation_last_message()
RETURNS TRIGGER
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public, private, pg_temp
AS $$
BEGIN
    UPDATE public.conversations
    SET 
        last_message_preview = substring(NEW.message_body from 1 for 150),
        last_message_at = NEW.created_at,
        updated_at = NEW.created_at
    WHERE id = NEW.conversation_id;
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_message_inserted ON public.messages;
CREATE TRIGGER trg_message_inserted
AFTER INSERT ON public.messages
FOR EACH ROW
EXECUTE FUNCTION private.trg_update_conversation_last_message();

-- 9. ROW LEVEL SECURITY (RLS) POLICIES
ALTER TABLE public.conversations ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.conversation_participants ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.messages ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.message_attachments ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.consultation_meetings ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.lawyer_availability ENABLE ROW LEVEL SECURITY;

-- Grants
GRANT SELECT, INSERT, UPDATE ON public.conversations TO authenticated;
GRANT SELECT, INSERT, UPDATE, DELETE ON public.conversation_participants TO authenticated;
GRANT SELECT, INSERT ON public.messages TO authenticated;
GRANT SELECT, INSERT ON public.message_attachments TO authenticated;
GRANT SELECT, INSERT, UPDATE ON public.consultation_meetings TO authenticated;
GRANT SELECT ON public.lawyer_availability TO authenticated, anon;
GRANT INSERT, UPDATE, DELETE ON public.lawyer_availability TO authenticated;

GRANT ALL PRIVILEGES ON public.conversations TO service_role;
GRANT ALL PRIVILEGES ON public.conversation_participants TO service_role;
GRANT ALL PRIVILEGES ON public.messages TO service_role;
GRANT ALL PRIVILEGES ON public.message_attachments TO service_role;
GRANT ALL PRIVILEGES ON public.consultation_meetings TO service_role;
GRANT ALL PRIVILEGES ON public.lawyer_availability TO service_role;

-- Policies for Conversations
DROP POLICY IF EXISTS "Participants view conversations" ON public.conversations;
CREATE POLICY "Participants view conversations"
ON public.conversations FOR SELECT
TO authenticated
USING (
    EXISTS (
        SELECT 1 FROM public.conversation_participants cp
        WHERE cp.conversation_id = conversations.id
          AND cp.user_id = auth.uid()
          AND cp.participant_status = 'ACTIVE'
    )
    OR private.is_platform_admin(auth.uid())
);

DROP POLICY IF EXISTS "Authenticated users create conversations" ON public.conversations;
CREATE POLICY "Authenticated users create conversations"
ON public.conversations FOR INSERT
TO authenticated
WITH CHECK (
    created_by = auth.uid()
);

-- Policies for Conversation Participants
DROP POLICY IF EXISTS "Participants view conversation roster" ON public.conversation_participants;
CREATE POLICY "Participants view conversation roster"
ON public.conversation_participants FOR SELECT
TO authenticated
USING (
    EXISTS (
        SELECT 1 FROM public.conversation_participants cp
        WHERE cp.conversation_id = conversation_participants.conversation_id
          AND cp.user_id = auth.uid()
    )
    OR private.is_platform_admin(auth.uid())
);

DROP POLICY IF EXISTS "Participants update own read status" ON public.conversation_participants;
CREATE POLICY "Participants update own read status"
ON public.conversation_participants FOR UPDATE
TO authenticated
USING (
    user_id = auth.uid()
    OR private.is_platform_admin(auth.uid())
)
WITH CHECK (
    user_id = auth.uid()
    OR private.is_platform_admin(auth.uid())
);

-- Policies for Messages
DROP POLICY IF EXISTS "Participants view messages" ON public.messages;
CREATE POLICY "Participants view messages"
ON public.messages FOR SELECT
TO authenticated
USING (
    EXISTS (
        SELECT 1 FROM public.conversation_participants cp
        WHERE cp.conversation_id = messages.conversation_id
          AND cp.user_id = auth.uid()
          AND cp.participant_status = 'ACTIVE'
    )
    OR private.is_platform_admin(auth.uid())
);

DROP POLICY IF EXISTS "Participants insert messages" ON public.messages;
CREATE POLICY "Participants insert messages"
ON public.messages FOR INSERT
TO authenticated
WITH CHECK (
    sender_user_id = auth.uid()
    AND EXISTS (
        SELECT 1 FROM public.conversation_participants cp
        WHERE cp.conversation_id = messages.conversation_id
          AND cp.user_id = auth.uid()
          AND cp.participant_status = 'ACTIVE'
    )
);

-- Policies for Message Attachments
DROP POLICY IF EXISTS "Participants view attachments" ON public.message_attachments;
CREATE POLICY "Participants view attachments"
ON public.message_attachments FOR SELECT
TO authenticated
USING (
    EXISTS (
        SELECT 1 FROM public.conversation_participants cp
        WHERE cp.conversation_id = message_attachments.conversation_id
          AND cp.user_id = auth.uid()
          AND cp.participant_status = 'ACTIVE'
    )
    OR private.is_platform_admin(auth.uid())
);

DROP POLICY IF EXISTS "Participants insert attachments" ON public.message_attachments;
CREATE POLICY "Participants insert attachments"
ON public.message_attachments FOR INSERT
TO authenticated
WITH CHECK (
    uploaded_by = auth.uid()
    AND EXISTS (
        SELECT 1 FROM public.conversation_participants cp
        WHERE cp.conversation_id = message_attachments.conversation_id
          AND cp.user_id = auth.uid()
          AND cp.participant_status = 'ACTIVE'
    )
);

-- Policies for Consultation Meetings
DROP POLICY IF EXISTS "Participants view meetings" ON public.consultation_meetings;
CREATE POLICY "Participants view meetings"
ON public.consultation_meetings FOR SELECT
TO authenticated
USING (
    citizen_user_id = auth.uid()
    OR lawyer_user_id = auth.uid()
    OR private.is_platform_admin(auth.uid())
);

DROP POLICY IF EXISTS "Participants create meetings" ON public.consultation_meetings;
CREATE POLICY "Participants create meetings"
ON public.consultation_meetings FOR INSERT
TO authenticated
WITH CHECK (
    created_by = auth.uid()
    AND (citizen_user_id = auth.uid() OR lawyer_user_id = auth.uid())
);

DROP POLICY IF EXISTS "Participants update meetings" ON public.consultation_meetings;
CREATE POLICY "Participants update meetings"
ON public.consultation_meetings FOR UPDATE
TO authenticated
USING (
    citizen_user_id = auth.uid()
    OR lawyer_user_id = auth.uid()
    OR private.is_platform_admin(auth.uid())
);

-- Policies for Lawyer Availability
DROP POLICY IF EXISTS "Anyone views lawyer availability" ON public.lawyer_availability;
CREATE POLICY "Anyone views lawyer availability"
ON public.lawyer_availability FOR SELECT
TO authenticated, anon
USING (true);

DROP POLICY IF EXISTS "Lawyers manage own availability" ON public.lawyer_availability;
CREATE POLICY "Lawyers manage own availability"
ON public.lawyer_availability FOR ALL
TO authenticated
USING (lawyer_user_id = auth.uid())
WITH CHECK (lawyer_user_id = auth.uid());


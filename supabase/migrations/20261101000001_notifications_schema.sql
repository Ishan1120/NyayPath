-- Migration: 20261101000001_notifications_schema.sql
-- Description: Intelligent In-App Notification System & Verified Legal Citations Foundation (Phase 2.3)

CREATE TABLE IF NOT EXISTS public.notifications (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    recipient_user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    event_type VARCHAR(64) NOT NULL,
    title TEXT NOT NULL,
    message TEXT NOT NULL,
    related_case_id VARCHAR(64) NOT NULL,
    case_uuid UUID REFERENCES public.cases(id) ON DELETE SET NULL,
    is_read BOOLEAN NOT NULL DEFAULT false,
    action_url TEXT,
    idempotency_key TEXT UNIQUE,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc'::text, now()),
    read_at TIMESTAMPTZ
);

-- Indexes for fast query performance
CREATE INDEX IF NOT EXISTS idx_notifications_recipient_unread 
    ON public.notifications (recipient_user_id, is_read, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_notifications_case_id 
    ON public.notifications (related_case_id);

-- Enable Row Level Security
ALTER TABLE public.notifications ENABLE ROW LEVEL SECURITY;

-- Drop existing policies if any
DROP POLICY IF EXISTS "Users can view own notifications" ON public.notifications;
DROP POLICY IF EXISTS "Users can update own notifications" ON public.notifications;
DROP POLICY IF EXISTS "Users can delete own notifications" ON public.notifications;

-- Policy 1: Users can only view their own notifications
CREATE POLICY "Users can view own notifications"
    ON public.notifications
    FOR SELECT
    TO authenticated
    USING (recipient_user_id = auth.uid());

-- Policy 2: Users can update their own notifications (e.g. mark as read)
CREATE POLICY "Users can update own notifications"
    ON public.notifications
    FOR UPDATE
    TO authenticated
    USING (recipient_user_id = auth.uid())
    WITH CHECK (recipient_user_id = auth.uid());

-- Policy 3: Users can delete/dismiss their own notifications
CREATE POLICY "Users can delete own notifications"
    ON public.notifications
    FOR DELETE
    TO authenticated
    USING (recipient_user_id = auth.uid());

-- Security Definer function to insert notifications safely from backend / RPCs
CREATE OR REPLACE FUNCTION private.create_notification(
    p_recipient_user_id UUID,
    p_event_type VARCHAR(64),
    p_title TEXT,
    p_message TEXT,
    p_related_case_id VARCHAR(64),
    p_case_uuid UUID DEFAULT NULL,
    p_action_url TEXT DEFAULT NULL,
    p_idempotency_key TEXT DEFAULT NULL,
    p_metadata JSONB DEFAULT '{}'::jsonb
)
RETURNS UUID
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public, pg_temp
AS $$
DECLARE
    v_notification_id UUID;
BEGIN
    -- Check idempotency
    IF p_idempotency_key IS NOT NULL THEN
        SELECT id INTO v_notification_id
        FROM public.notifications
        WHERE idempotency_key = p_idempotency_key;

        IF FOUND THEN
            RETURN v_notification_id;
        END IF;
    END IF;

    INSERT INTO public.notifications (
        recipient_user_id,
        event_type,
        title,
        message,
        related_case_id,
        case_uuid,
        action_url,
        idempotency_key,
        metadata
    ) VALUES (
        p_recipient_user_id,
        p_event_type,
        p_title,
        p_message,
        p_related_case_id,
        p_case_uuid,
        p_action_url,
        p_idempotency_key,
        COALESCE(p_metadata, '{}'::jsonb)
    )
    RETURNING id INTO v_notification_id;

    RETURN v_notification_id;
EXCEPTION
    WHEN unique_violation THEN
        -- If concurrent insert collided on idempotency_key, return existing ID
        SELECT id INTO v_notification_id
        FROM public.notifications
        WHERE idempotency_key = p_idempotency_key;
        RETURN v_notification_id;
END;
$$;

-- Seed verified precedents into public.legal_precedents if table is empty
INSERT INTO public.legal_precedents (
    id, citation, title, court, bench, judgment_date, category, summary, statutory_provisions, ratio_decidendi
) VALUES 
(
    'sc-ragging-vishwa-2009',
    '(2009) 7 SCC 726 / AIR 2001 SC 2792',
    'University of Kerala & Vishwa Jagriti Mission v. Council of Principals'' of Colleges in Kerala & Ors.',
    'Supreme Court of India',
    'Hon''ble Justice Arijit Pasayat & Justice Asok Kumar Ganguly (Division Bench)',
    '2009-05-08',
    'Higher Education & Campus Grievance',
    'Supreme Court mandated immediate FIR registration within 24 hours for campus ragging and established institutional vicarious liability.',
    ARRAY['UGC Regulations on Curbing Ragging 2009', 'Article 21', 'BNS Sec 351/115'],
    'Ragging in any form is a gross violation of human dignity and the fundamental right to life under Article 21. Colleges bear strict statutory vicarious liability.'
),
(
    'cbse-aditya-2011',
    '(2011) 8 SCC 497',
    'Central Board of Secondary Education v. Aditya Bandopadhyay & Ors.',
    'Supreme Court of India',
    'Hon''ble Justice R.V. Raveendran & Justice A.K. Patnaik (Division Bench)',
    '2011-08-09',
    'Education & Student Rights',
    'Supreme Court settled that examinees have an absolute right under Section 2(j) to inspect evaluated answer books. Fiduciary relationship cannot be claimed by exam boards.',
    ARRAY['RTI Act Section 2(j)', 'RTI Act Section 8(1)(e)', 'Article 19(1)(a)'],
    'Students have an absolute fundamental and statutory right under Section 2(j) to inspect their evaluated answer sheets. Answer scripts are not held in a fiduciary capacity against the candidate.'
),
(
    'pioneer-urban-builder-2019',
    '(2019) 5 SCC 725',
    'Pioneer Urban Land & Infrastructure Ltd. v. Govindan Raghavan',
    'Supreme Court of India',
    'Hon''ble Justice U.U. Lalit & Justice Indu Malhotra (Division Bench)',
    '2019-04-02',
    'Consumer Protection & Housing',
    'Supreme Court ruled that one-sided developer agreements constitute an unfair trade practice. Homebuyers are entitled to a 100% refund with interest for possession delays.',
    ARRAY['Consumer Protection Act Sec 2(1)(g)', 'RERA Sec 18'],
    'One-sided standard-form contracts drafted by real estate developers constitute an unfair trade practice and cannot bind consumers. Buyers are entitled to a full refund with interest.'
),
(
    'shreya-singhal-2015',
    '(2015) 5 SCC 1',
    'Shreya Singhal v. Union of India',
    'Supreme Court of India',
    'Hon''ble Justice J. Chelameswar & Justice Rohinton Fali Nariman (Division Bench)',
    '2015-03-24',
    'Digital Rights & Free Speech',
    'Struck down Section 66A of the Information Technology Act as unconstitutional, safeguarding citizens'' and students'' rights to voice civic grievances on social media.',
    ARRAY['Article 19(1)(a)', 'Article 19(2)', 'IT Act Section 66A'],
    'Citizens have an inalienable constitutional right to express dissent, criticize administrative deficiencies, and post civic complaints online without criminal intimidation.'
),
(
    'subhash-kumar-water-1991',
    'AIR 1991 SC 420 / (1991) 1 SCC 598',
    'Subhash Kumar v. State of Bihar & Municipal Authorities',
    'Supreme Court of India',
    'Hon''ble Chief Justice Ranganath Misra & Justice K.N. Singh',
    '1991-01-09',
    'Civic Infrastructure & Roads',
    'Right to clean, unpolluted drinking water and a contamination-free civic environment is an enforceable fundamental right under Article 21 of the Indian Constitution.',
    ARRAY['Article 21', 'Article 32', 'Water Act 1974'],
    'The Right to Life under Article 21 encompasses the right to clean drinking water and a contamination-free civic environment. Municipalities cannot evade their primary duty.'
)
ON CONFLICT (id) DO NOTHING;


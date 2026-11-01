# NyayPath — Phase 2.3 Engineering & Security Sign-Off Report
## Legal Citation Integration & Intelligent Notification System

**Date:** November 1, 2026  
**Status:** Completed & Validated  
**Branch:** `feature/phase-1.3.4-security-remediation`  
**Environment Target:** Local Supabase (`http://127.0.0.1:54321`, PostgreSQL @ `54322`, REST @ `54321`)  
**Strict Remote Restrictions Observed:** No remote SQL executed; no remote database mutations performed.

---

## 1. Executive Summary

Phase 2.3 establishes two core capabilities across the NyayPath unified legal assistance platform:
1. **Verified Legal Citation Integration:** Authoritative, structured judicial citations (Supreme Court binding authority under Article 141, High Court persuasive authority, statutory provisions, operative ratio, and official source links) embedded directly into the AI Legal Engine and Case Search experience with strict zero-hallucination controls.
2. **Intelligent In-App Notification System:** A real-time, persistent notification infrastructure backed by PostgreSQL and PostgREST, tied authoritatively to genuine case events (submission, withdrawal, hearing scheduling, status progression, remarks). It features strict cross-tenant user isolation (`recipient_user_id == auth.uid()`), zero proctor notes leakage, and high-entropy idempotency deduplication.

All 12 automated Phase 2.3 test scenarios and existing Phase 2.2, Phase 2.1, and Phase 1.3.15 regression suites passed with zero failures. Next.js TypeScript compilation (`npx tsc --noEmit`) completed with zero errors.

---

## 2. Architecture & Threat Mitigation

```mermaid
flowchart TD
    subgraph Frontend["Next.js 14 Client Workspace"]
        Navbar["Navbar Bell & Popover\nDynamic Unread Counter"]
        NotifCenter["/dashboard/notifications\nNotification Center"]
        GrievanceView["GrievanceResultView\nLegalCitationsList"]
        CaseSearch["/case-search\nBinding/Persuasive Badges"]
    end

    subgraph FastAPI["FastAPI Gateway & Auth Boundary"]
        JWT["HS256 Verified JWT Context\nauth.uid(), role: authenticated"]
        CiteEngine["api/citations.py\nCitation Resolution Engine"]
        NotifMgr["api/notifications.py\nNotificationManager"]
    end

    subgraph Storage["PostgreSQL (Local Supabase)"]
        NotifTable["public.notifications\n(recipient_user_id, event_type, idempotency_key)"]
        RLS["RLS Policy:\nrecipient_user_id = auth.uid()"]
        RPC["private.create_notification()\n(Security Definer, Idempotent)"]
        Precedents["public.legal_precedents\n(12 Landmark Cases Seeded)"]
    end

    Navbar -->|Poll & Fetch Unread| NotifMgr
    NotifCenter -->|List, Mark Read, Delete| NotifMgr
    GrievanceView -->|Resolve Citations| CiteEngine
    CaseSearch -->|Fetch Precedents| CiteEngine

    NotifMgr -->|Derive auth.uid()| JWT
    NotifMgr -->|Persist / Query| NotifTable
    NotifTable --> RLS
    NotifMgr -->|Dispatch| RPC
    CiteEngine -->|Search Verified Ratios| Precedents
```

### Threat Mitigations Implemented:

| Vulnerability Vector | Threat Scenario | Implemented Mitigation | Test Verification |
| :--- | :--- | :--- | :--- |
| **Citation Hallucination** | LLM inventing fictional precedents, invalid court URLs, or wrong sections | Deterministic matching against verified catalog; relevance thresholding (`score >= 65`); non-legal queries return `has_citations=False` with 0 items. | `test_01`, `test_02`, `test_03` |
| **Confidential Note Leakage** | Internal proctorial remarks leaking into student notifications | Case updates sanitize messages before creating notifications; `proctor_notes` are explicitly stripped from student titles and message bodies. | `test_09` |
| **Cross-Tenant Snooping** | Citizen B accessing or dismissing Citizen A's notifications | PostgreSQL RLS (`recipient_user_id = auth.uid()`); FastAPI endpoints enforce `recipient_user_id == user.user_id` on read and delete (HTTP 403 Forbidden). | `test_05`, `test_07` |
| **Notification Spam / Duplication** | Retried webhook or API calls flooding the user with duplicate alerts | Idempotency keys (`notif_<uid>_<event>_<case_id>`) enforced via DB unique index and memory deduplication cache. | `test_12` |
| **Audit Log Mutation** | Attempting to write `is_read` to audit logs | Segregated `public.notifications` table; `public.case_activity_log` remains immutable under strict audit trigger. | Migration `20261101000001` |

---

## 3. Database Schema & Migration

### Forward-Only Migration: `supabase/migrations/20261101000001_notifications_schema.sql`

```sql
-- 1. Create Dedicated Notifications Table
CREATE TABLE IF NOT EXISTS public.notifications (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    recipient_user_id UUID NOT NULL,
    event_type VARCHAR(64) NOT NULL,
    title VARCHAR(255) NOT NULL,
    message TEXT NOT NULL,
    related_case_id VARCHAR(64) NOT NULL,
    case_uuid UUID,
    is_read BOOLEAN NOT NULL DEFAULT false,
    action_url TEXT,
    idempotency_key VARCHAR(128),
    metadata JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc'::text, now()),
    read_at TIMESTAMPTZ
);

-- 2. Indexes & Unique Idempotency Constraint
CREATE UNIQUE INDEX IF NOT EXISTS uq_notification_idempotency 
    ON public.notifications(idempotency_key) WHERE idempotency_key IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_notifications_recipient_unread 
    ON public.notifications(recipient_user_id, is_read, created_at DESC);

-- 3. Row-Level Security
ALTER TABLE public.notifications ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Users can view their own notifications"
    ON public.notifications FOR SELECT
    TO authenticated
    USING (recipient_user_id = auth.uid());
CREATE POLICY "Users can update their own notifications"
    ON public.notifications FOR UPDATE
    TO authenticated
    USING (recipient_user_id = auth.uid())
    WITH CHECK (recipient_user_id = auth.uid());
CREATE POLICY "Users can delete their own notifications"
    ON public.notifications FOR DELETE
    TO authenticated
    USING (recipient_user_id = auth.uid());
```

---

## 4. Legal Citation Integration

1. **Structured Citation Model (`CitationMetadata`):**
   - `source_identifier`: Unique slug (e.g. `sc-d-k-basu-1997`).
   - `case_title`: Canonical title (e.g. *D.K. Basu v. State of West Bengal*).
   - `court`: Adjudicating body (e.g. *Supreme Court of India*).
   - `citation`: Standard reporter citation (e.g. *(1997) 1 SCC 416*).
   - `authority_type`: `BINDING` (Supreme Court under Article 141) vs `PERSUASIVE` (High Courts, Commissions).
   - `statutory_provisions`: Array of statutes (e.g. `["Constitution Article 21", "CrPC Section 41A"]`).
   - `relevant_ratio`: Binding legal proposition.
   - `how_to_cite`: Standard procedural phrasing for legal petitions.
   - `source_url`: Verifiable official URL (Supreme Court / Indian Kanoon).
   - `pdf_download_url`: Official 1-page case brief download link.
2. **Relevance Thresholding & Zero Hallucination:**
   - Filtered through `resolve_citations_for_query()` in `api/citations.py`.
   - Rejects non-legal queries (e.g. baking cookies) with `has_citations=False` and an empty list.
3. **Frontend Integration:**
   - **`components/LegalCitationCard.tsx`:** Standard and compact card components with 1-click citation copy, binding authority pill, official source link, and PDF download.
   - **`views/GrievanceResultView.tsx`:** Displays verified judicial precedents alongside legal analysis.
   - **`app/case-search/page.tsx`:** Authority badges (Binding vs Persuasive) and official source links embedded into every search result card.

---

## 5. Intelligent Notification System

1. **Backend Service (`api/notifications.py`):**
   - `NotificationManager` manages user notifications, unread counts, marking read/unread, and deletion.
   - Integrated with Supabase PostgREST with in-memory fallback for local dev.
   - Fail-closed security: Any operation targeting another user's notification raises `403 Forbidden`.
2. **Event Integration Across Platform:**
   - **Case Filing (`api/citizen_workspace.py`):** Generates `CASE_SUBMITTED` notification.
   - **Case Withdrawal (`api/citizen_workspace.py`):** Generates `CASE_WITHDRAWN` notification.
   - **Remarks / Expedite (`api/citizen_workspace.py`):** Generates user/officer alerts.
   - **Proctor Status Update (`api/campus_proctor.py`):** Generates `CASE_<STATUS>` notification for student applicant while strictly excluding `proctor_notes`.
   - **Hearing Scheduled (`api/campus_proctor.py`):** Generates `HEARING_SCHEDULED` notification with date and location.
3. **Frontend Notification Experience:**
   - **`app/Navbar.tsx`:**
     - Dynamic notification bell with pulsing unread badge.
     - Interactive popover dropdown showing 5 most recent updates with relative timestamps and quick mark-read actions.
     - 30-second background polling when authenticated.
   - **`app/dashboard/notifications/page.tsx`:**
     - Full Notification Center with tabs (`All`, `Unread`, `Read`), keyword search, and bulk "Mark all as read".
     - Event-specific badges, relative time formatting, and direct links to case details.
     - Auth guard modal pre-configured for instant demo sign-in.

---

## 6. Test Suite & Verification Results

### Phase 2.3 Comprehensive Test Suite (`tests/test_phase23_citations_notifications.py`):

```
======================================================================
RUNNING NYAYPATH PHASE 2.3 CITATIONS & NOTIFICATIONS TEST SUITE
======================================================================
  [PASS] test_01_citations_resolution_legal_query
  [PASS] test_02_citations_resolution_irrelevant_query_zero_hallucination
  [PASS] test_03_citations_endpoint_api
  [PASS] test_04_classifier_citations_integration
  [PASS] test_05_notifications_unauthenticated_fails_closed
  [PASS] test_06_case_filing_creates_notification
  [PASS] test_07_notification_user_isolation
  [PASS] test_08_lifecycle_withdrawal_creates_notification
  [PASS] test_09_proctor_update_creates_student_notification_without_leakage
  [PASS] test_10_hearing_schedule_creates_notification
  [PASS] test_11_notification_read_mark_all_and_delete
  [PASS] test_12_notification_idempotency
======================================================================
RESULTS: 12 PASSED, 0 FAILED
======================================================================
```

### Full Regression Suite:
- **Phase 2.2 Suite (`tests/test_phase22_case_filing.py`):** 8/8 Passed (100%).
- **Phase 2.1 Suite (`tests/test_phase21_citizen_workspace.py`):** 7/7 Passed (100%).
- **Phase 1.3.15 Suite (`tests/test_phase1315_e2e_api.py`):** 10/10 Passed (100%).
- **Frontend Compilation (`npx tsc --noEmit`):** Clean exit code 0.

---

## 7. Modified & Created Files Inventory

| File | Action | Purpose |
| :--- | :--- | :--- |
| `supabase/migrations/20261101000001_notifications_schema.sql` | Created | Forward-only migration for `public.notifications` table, RLS, and indexes |
| `api/citations.py` | Created | Verified legal citation resolution engine and metadata models |
| `api/notifications.py` | Created | `NotificationManager` supporting user isolation, unread counts, and deduplication |
| `components/LegalCitationCard.tsx` | Created | Reusable citation card and list components |
| `app/dashboard/notifications/page.tsx` | Created | Full Notification Center with tabs, search, and bulk mark-read |
| `tests/test_phase23_citations_notifications.py` | Created | Automated 12-test suite covering citations and notifications |
| `api/index.py` | Modified | Added `/api/notifications/*` and `/api/citations/resolve` endpoints |
| `api/classifier.py` | Modified | Integrated citation resolution into AI Legal Engine classification |
| `api/citizen_workspace.py` | Modified | Dispatches in-app notifications on filing, withdrawal, remarks, and expedite |
| `api/campus_proctor.py` | Modified | Dispatches sanitized notifications on status updates and hearing scheduling |
| `app/Navbar.tsx` | Modified | Added notification bell icon, unread counter badge, and dropdown popover |
| `app/case-search/page.tsx` | Modified | Added binding/persuasive authority badges and official source links |
| `views/GrievanceResultView.tsx` | Modified | Integrated `LegalCitationsList` into grievance legal analysis view |
| `lib/api.ts` | Modified | Added TypeScript interfaces and axios helper functions for citations & notifications |


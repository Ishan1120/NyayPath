# NyayPath — Phase 6.1 Final Corrections Report

## Case Conversation Revocation & Concurrent Meeting Booking Fixes

**Date:** November 2, 2026  
**Milestone:** Phase 6.1  
**Target Branch:** `feature/phase-1.3.4-security-remediation`  
**Database Target:** Local Supabase (`http://127.0.0.1:54321`, PostgreSQL 17.11 @ port `54322`)  
**Status:** **COMPLETED & VERIFIED**

---

## 1. Executive Summary

Phase 6.1 provides targeted, high-assurance security and concurrency remediations for the NyayPath communications and appointment scheduling subsystem introduced in Phase 6:

1. **Lawyer Case Access Revocation Hardening:** Fixed a critical security vulnerability where conversation access previously failed open when permission records were missing, unconfirmed, or encountering database errors. Implemented a centralized, fail-closed verification pipeline (`_verify_lawyer_case_access`) in `api/messaging.py` that enforces strict authorization record existence, exact UUID matching, `access_status == 'ACTIVE'`, and fine-grained `shared_scope` gating (`CASE_AND_DOCS` vs. `METADATA_ONLY`). Any missing record, inactive/revoked status, scope deficit, or database verification exception strictly terminates with `HTTP 403 Forbidden` without leaking conversation metadata or message contents.
2. **Atomic Meeting Double-Booking Prevention:** Solved concurrent appointment race conditions at the database engine level by adding an atomic PostgreSQL exclusion constraint (`exclude_overlapping_confirmed_meetings`) via the `btree_gist` extension on `public.consultation_meetings`. Overlapping confirmed intervals for the same advocate are serialized and rejected natively by the database (`SQLSTATE 23P01`). The backend catches this constraint violation in both creation and confirmation flows, returning a descriptive `HTTP 400 Bad Request`.
3. **Comprehensive Verification:** Executed a dedicated 12-test suite (`tests/test_phase6_1_corrections.py`) including a live multi-threaded concurrent race condition test verifying that two simultaneous requests for overlapping intervals result in exactly one `200 OK` and one `400 Bad Request`. Verified all existing regressions (Phase 6 Messaging, Phase 5 Lawyer Workspace, Phase 4 Institution/Proctor, Phase 3 Hardening, and TypeScript compilation).

---

## 2. Task 1: Lawyer Case-Access Revocation Hardening

### 2.1 The Vulnerability
In Phase 6, case-linked conversations (`conversation_type IN ('LAWYER_CITIZEN', 'GENERAL_CASE')`) checked for revoked access by querying:
```python
rev_res = self.supabase.table("lawyer_case_access").select("case_uuid").eq("lawyer_user_id", caller_uid).eq("access_status", "REVOKED").execute()
```
If an authorization record was missing entirely, pending verification, set to `INACTIVE`, or if the database query experienced an intermittent error, the query returned no rows with `access_status == 'REVOKED'`, inadvertently failing open and granting conversation access. Furthermore, scope-restricted access (`METADATA_ONLY`) did not prevent the retrieval or upload of document attachments.

### 2.2 Remediated Architecture & Fail-Closed Logic
A centralized validation method `_verify_lawyer_case_access` was implemented in `CommunicationManager` in `api/messaging.py`:

```python
def _verify_lawyer_case_access(
    self,
    lawyer_uid: str,
    case_uuid: str,
    required_scope: Optional[str] = None
) -> Dict[str, Any]:
    self._ensure_connected()
    if not self.supabase:
        raise HTTPException(status_code=500, detail="Database connection unavailable.")

    try:
        res = self.supabase.table("lawyer_case_access").select(
            "id, case_uuid, lawyer_user_id, access_status, shared_scope"
        ).eq("case_uuid", str(case_uuid)).eq("lawyer_user_id", str(lawyer_uid)).execute()
    except Exception as e:
        logger.error(f"Database error verifying lawyer case access for {lawyer_uid} on {case_uuid}: {e}")
        # Strictly fail closed on database exception
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: Unable to verify case sharing authorization."
        )

    # Missing record check
    if not res or not res.data or len(res.data) == 0:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: No active case sharing authorization found for this case."
        )

    access_row = res.data[0]

    # Exact UUID match check
    if str(access_row.get("lawyer_user_id")) != str(lawyer_uid) or str(access_row.get("case_uuid")) != str(case_uuid):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: Authorization record identity mismatch."
        )

    # Strict ACTIVE status check
    current_status = (access_row.get("access_status") or "").strip().upper()
    if current_status != "ACTIVE":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Access denied: Case sharing permission is {current_status.lower() or 'inactive'}."
        )

    # Scope-level check
    scope = (access_row.get("shared_scope") or "").strip().upper()
    if required_scope == "CASE_AND_DOCS" and scope != "CASE_AND_DOCS":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: Case sharing scope does not permit document attachment access."
        )

    return access_row
```

### 2.3 Comprehensive Endpoint Coverage
The fail-closed verification was woven across all communication touchpoints:

| Endpoint | Operation | Verification Applied |
| :--- | :--- | :--- |
| `POST /api/conversations/case/{case_uuid}` | Initialize or retrieve case conversation | Validates lawyer has active `lawyer_case_access` before creating or returning conversation. |
| `GET /api/conversations` | List user conversations | Filters case-linked conversations so lawyers only see conversations for cases where an `ACTIVE` record exists; excludes missing, revoked, inactive, or errored entries. |
| `GET /api/conversations/{id}` | Retrieve conversation metadata | Dynamically evaluates `_verify_lawyer_case_access` if caller is a lawyer on a case-linked conversation; returns `403 Forbidden` if missing or revoked. |
| `POST /api/conversations/{id}/messages` | Send message | Rechecks active case access. If `message_type == 'ATTACHMENT'`, enforces `required_scope="CASE_AND_DOCS"`. |
| `GET /api/conversations/{id}/messages` | List conversation messages | Revalidates case access. If `shared_scope == 'METADATA_ONLY'`, document attachments are withheld (`m["attachments"] = []`). |
| `POST /api/conversations/{id}/attachments` | Upload message attachment | Checks that caller has `required_scope="CASE_AND_DOCS"`; strictly blocks lawyers with `METADATA_ONLY` (`403 Forbidden`). |
| `GET /api/conversations/attachments/{id}/url` | Generate signed URL for document | Rechecks case authorization and requires `CASE_AND_DOCS`; rejects `METADATA_ONLY` lawyers (`403 Forbidden`). |
| `POST /api/conversations/{id}/read` | Mark conversation read | Enforces active membership and case permission verification prior to recording read receipts. |

### 2.4 Integrity of Citizen & Proctor Access
Citizen case owners and assigned college proctors bypass `lawyer_case_access` checks via their authoritative role models (`cases.data->>'citizen_user_id'` and `cases.data->>'assigned_proctor_user_id'` / `case_committee_assignments`), ensuring their regular workflow is completely unaffected.

---

## 3. Task 2: Meeting Concurrency & Atomic Database Protection

### 3.1 The Double-Booking Race Condition Problem
Application-level checks (such as `SELECT ... WHERE scheduled_start < new_end AND scheduled_end > new_start`) suffer from race conditions under concurrent execution: two requests executing simultaneously both observe zero confirmed meetings in the interval and proceed to update status to `CONFIRMED`.

### 3.2 Database Migration (`20261102000001_concurrent_meeting_exclusion.sql`)
To eliminate the race condition with ACID guarantees, an exclusion constraint was added in PostgreSQL using the `btree_gist` extension:

```sql
-- Migration: 20261102000001_concurrent_meeting_exclusion.sql
CREATE EXTENSION IF NOT EXISTS btree_gist;

ALTER TABLE public.consultation_meetings
DROP CONSTRAINT IF EXISTS exclude_overlapping_confirmed_meetings;

ALTER TABLE public.consultation_meetings
ADD CONSTRAINT exclude_overlapping_confirmed_meetings
EXCLUDE USING gist (
    lawyer_user_id WITH =,
    tstzrange(scheduled_start, scheduled_end, '[)') WITH &&
)
WHERE (status = 'CONFIRMED');
```

**Key Advantages:**
1. **Engine-Level Atomicity:** Handled directly inside PostgreSQL's transaction manager without table-level locking.
2. **Partial Index Efficiency:** The `WHERE (status = 'CONFIRMED')` clause ensures only confirmed bookings occupy slot reservations. Pending requests (`REQUESTED`), declined invitations (`DECLINED`), or cancellations (`CANCELLED`) do not conflict, immediately unblocking slots.
3. **Half-Open Range `[)`:** Uses standard half-open intervals `[start, end)`. An appointment ending at 10:30 and an appointment starting at 10:30 are adjacent and do not overlap.

### 3.3 Backend Exception Mapping
Both `schedule_meeting` and `update_meeting_status` in `api/messaging.py` wrap database mutations with exception handlers that detect PostgreSQL error code `23P01` (exclusion constraint violation):

```python
try:
    res = self.supabase.table("consultation_meetings").update(update_dict).eq("id", clean_id).execute()
except Exception as e:
    err_str = str(e).lower()
    if "exclude" in err_str or "23p01" in err_str or "conflict" in err_str:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot confirm: You have an overlapping confirmed meeting."
        )
    raise HTTPException(status_code=500, detail="Failed to update meeting status.")
```

### 3.4 Multi-Threaded Concurrency Test Results
In `tests/test_phase6_1_corrections.py`, `test_12_concurrent_simultaneous_confirmations_race_condition` dispatched two simultaneous HTTP PATCH confirmation requests using a `ThreadPoolExecutor(max_workers=2)` for overlapping time windows (`10:00 - 10:45` and `10:15 - 11:00`):

```
[Concurrency Test] Status codes returned: [200, 400]
PostgreSQL Verification: Exactly 1 row CONFIRMED, exactly 1 row REQUESTED.
```
One request succeeded (`HTTP 200 OK`) and the conflicting request was rejected atomically by the database constraint (`HTTP 400 Bad Request`).

---

## 4. Verification and Test Results

### 4.1 Phase 6.1 Dedicated Test Suite
**Command:** `py -m unittest tests/test_phase6_1_corrections.py`

| Test Name | Scenario Tested | Result |
| :--- | :--- | :---: |
| `test_01_lawyer_active_permission_succeeds` | Active permission + `CASE_AND_DOCS` allows conversation, messaging, and attachment access | **PASS** |
| `test_02_lawyer_revoked_permission_denied` | Revoked permission record strictly blocks lawyer across all endpoints (`HTTP 403`) | **PASS** |
| `test_03_lawyer_missing_permission_denied` | Missing permission record strictly blocks lawyer across all endpoints (`HTTP 403`) | **PASS** |
| `test_04_lawyer_inactive_permission_denied` | Inactive/non-ACTIVE permission record strictly blocks lawyer (`HTTP 403`) | **PASS** |
| `test_05_lawyer_scope_insufficient_for_attachments` | Lawyer with `METADATA_ONLY` scope is blocked from attachments (`HTTP 403`) | **PASS** |
| `test_06_database_verification_failure_fails_closed` | Database verification failure strictly fails closed with `HTTP 403` | **PASS** |
| `test_07_citizen_and_proctor_workflows_unaffected` | Citizen case owner and proctor workflows function unaffected | **PASS** |
| `test_08_meeting_first_confirmed_and_second_rejected_sequential` | Sequential overlapping booking rejection (`HTTP 400`) | **PASS** |
| `test_09_meeting_non_overlapping_bookings_both_succeed` | Adjacent non-overlapping bookings (10:00-10:30 & 10:30-11:00) both succeed | **PASS** |
| `test_10_cancelled_appointment_unblocks_future_booking` | Cancelling confirmed appointment unblocks future bookings for that time window | **PASS** |
| `test_11_meeting_privacy_masking_intact` | Sensitive credentials masked until confirmed | **PASS** |
| `test_12_concurrent_simultaneous_confirmations_race_condition` | Simultaneous race condition: Exactly one `200 OK` and one `400 Bad Request` | **PASS** |

**Summary:** 12 tests passed in 2.15 seconds.

### 4.2 Full Regression Test Suite

| Test Suite | Scope | Result | Execution Time |
| :--- | :--- | :---: | :---: |
| `tests/test_phase6_messaging.py` | Messaging, notifications, read receipts, attachments, meetings | **17 / 17 PASS** | 2.13s |
| `tests/test_phase5_lawyer_workspace.py` | Lawyer directory, profiles, case sharing, consultations | **15 / 15 PASS** | 1.94s |
| `tests/test_phase4_institution_proctor.py` | Proctor assignment, grievance management, committee access | **15 / 15 PASS** | 1.73s |
| `tests/test_phase3_hardening.py` | JWT authentication, RBAC, algorithm restrictions, key validation | **18 / 18 PASS** | 1.62s |
| `npx tsc --noEmit` | Next.js and React frontend TypeScript compilation | **0 Errors** | ~4s |

---

## 5. Security & Architectural Compliance

1. **Local Supabase Exclusivity:** All migrations, constraints, and test executions took place strictly against local Supabase (`http://127.0.0.1:54321`, PostgreSQL 17.11 @ port `54322`). Remote Supabase (`dbwojjxfhnmmwrnqxyqj`) and Vercel environments were completely untouched.
2. **Fail-Closed Security Standard:** In accordance with NyayPath's security baseline, permission checking functions default to access denial upon any irregularity (missing record, identity mismatch, inactive status, insufficient scope, or database exception).
3. **Information Disclosure Prevention:** Revocation failures reject requests at the conversation boundary before messages or attachments are retrieved, preventing unauthorized data leakage.
4. **Data Isolation:** All meeting double-booking tests and case access tests include strict teardown routines ensuring test database cleanliness.


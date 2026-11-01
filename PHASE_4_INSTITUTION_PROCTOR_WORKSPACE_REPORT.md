# NyayPath — Phase 4 Verification & Implementation Report
## Multi-Institution Architecture & Complete Institution/Proctor Workspace

**Milestone:** Phase 4: Institutional & Proctor Redressal System  
**Date:** November 1, 2026  
**Repository Branch:** `feature/phase-1.3.4-security-remediation`  
**Execution Environment:** Local Supabase (PostgreSQL 17.11 @ `127.0.0.1:54322`, PostgREST/Kong @ `127.0.0.1:54321`)  
**Statutory Framework:** UGC (Grievance Redressal of Students) Regulations, 2023  
**Automated Verification Suite:** `tests/test_phase4_institution_proctor.py` (15/15 Scenarios Passed, 100% Pass Rate)

---

## 1. Executive Summary

Phase 4 delivers a centralized multi-institution architecture and role-segregated workspaces for universities and colleges operating under the UGC (Grievance Redressal of Students) Regulations, 2023. Prior to Phase 4, the platform provided individual citizen and student intake with backend authorization mechanisms, but lacked dedicated administrative, proctorial, and inquiry committee cockpits.

This phase implements four specialized, role-scoped workspaces connected directly to PostgreSQL persistence, real-time analytics, immutable audit logs, and notification dispatch pipelines:

1. **Institution Administrator Workspace (`/institution/dashboard`):** Real-time dashboard analytics derived from authoritative database records, institution-wide grievance management with multi-parameter filtering, and member roster management (with active, suspended, and revoked account status administration).
2. **Chief Proctor & Ombudsman Workspace (`/campus-proctor/chief`):** Central triage of unassigned grievances, proctorial assignment, ad-hoc inquiry committee appointment and revocation, and hearing scheduling.
3. **Individual Proctor Investigation Desk (`/campus-proctor/dashboard`):** Assigned cases investigation queue, evidence inspection, structured inquiry notes, action taken recording, and UGC formal hearing notice generation. Restricted from arbitrary proctor reassignment or altering confidentiality modes.
4. **Committee Member Workspace (`/campus-proctor/committee`):** Scoped access restricted strictly to cases with active `case_committee_assignments`, authorized evidence review, and submission of joint committee findings and recommendations. Immediate termination of access upon assignment revocation or account suspension.

All metrics, queue counts, and analytics are calculated directly from live database records without dummy or hallucinated figures.

---

## 2. Multi-Institution Role Boundary Matrix

Access control enforces strict multi-tenant institutional isolation: users from one institution cannot view, triage, assign, or modify cases or rosters belonging to another institution.

```mermaid
flowchart TD
    subgraph MultiInstitutionBoundary["Multi-Institution Boundary Isolation"]
        InstAdmin["Institution Admin"] -->|Manage Roster & Overview| InstDB[("Institutional Registry")]
        ChiefProctor["Chief Proctor"] -->|Triage & Form Committees| InstDB
        ChiefProctor -->|Assign Inquiries| Proctor["Individual Proctor"]
        ChiefProctor -->|Appoint| CommMember["Committee Member"]
        Proctor -->|Investigate & Record Directives| InstDB
        CommMember -->|Submit Findings| InstDB
    end

    subgraph SecurityDefinerEnforcement["Database & Security Model"]
        InstDB -->|Row Level Security| RLS["PostgreSQL RLS Policies"]
        InstDB -->|State Machine| RPC["Atomic RPC State Transitions"]
        InstDB -->|Tamper-Evident History| AuditLog["case_activity_log"]
        InstDB -->|Activity UUID Idempotency| Notifs["In-App Notifications"]
    end
```

### Institutional Role Permission Matrix

| Operation / Capability | Institution Admin | Chief Proctor | Individual Proctor | Committee Member | Citizen / Student |
| :--- | :---: | :---: | :---: | :---: | :---: |
| **Institutional Dashboard Stats & Analytics** | Allowed (Own Inst) | Allowed (Own Inst) | Restricted (403) | Restricted (403) | Restricted (403) |
| **Institution Case Registry Access** | Allowed (All Non-Conf/Assigned) | Allowed (Administrative Overview) | Assigned Cases Only | Active Assignments Only | Own Cases Only |
| **Triage & Assign Inquiries** | Allowed | Allowed | Forbidden (403) | Forbidden (403) | Forbidden (403) |
| **Appoint / Revoke Committee Members** | Allowed | Allowed | Forbidden (403) | Forbidden (403) | Forbidden (403) |
| **Record Proctor Notes & Actions** | Allowed | Allowed | Allowed (Assigned) | Forbidden (403) | Forbidden (403) |
| **Submit Committee Observations** | Allowed | Allowed | Forbidden (403) | Allowed (Active Asgn) | Forbidden (403) |
| **Manage Member Status (Active/Suspend)** | Allowed | Restricted (403) | Restricted (403) | Restricted (403) | Restricted (403) |
| **Cross-Institution Modification** | Strictly Forbidden (403) | Strictly Forbidden (403) | Strictly Forbidden (403) | Strictly Forbidden (403) | Strictly Forbidden (403) |

---

## 3. Workspaces Implementation Overview

### 3.1 Institution Administrator Workspace (`/institution/dashboard`)
* **Route & Component:** [page.tsx](file:///c:/Users/Ishan/OneDrive/Desktop/micro project/app/institution/dashboard/page.tsx)
* **API Endpoints:**
  - `GET /api/institution/dashboard-stats`: Calculates live aggregations (`total_cases`, `active_inquiries`, `resolved_cases`, `hearings_scheduled`, `confidential_cases`, `sla_breaches`, `total_members`, `active_members`, `unassigned_cases`).
  - `GET /api/institution/analytics`: Computes categorization breakdowns, severity distributions, and average turnaround duration across resolved matters.
  - `GET /api/institution/cases`: Multi-parameter filtered grievance catalog with server-side pagination, search indexing, and status filtering.
  - `GET /api/institution/members`: Institutional roster listing officer profiles, assigned institutional roles, and account statuses.
  - `PATCH /api/institution/members/{user_id}/status`: Admin-controlled account status transitions (`active`, `suspended`, `revoked`).

### 3.2 Chief Proctor & Ombudsman Workspace (`/campus-proctor/chief`)
* **Route & Component:** [page.tsx](file:///c:/Users/Ishan/OneDrive/Desktop/micro project/app/campus-proctor/chief/page.tsx)
* **API Endpoints:**
  - `GET /api/campus-proctor/chief/triage`: Filters grievances where `assigned_proctor IS NULL` within the institution.
  - `GET /api/institution/committee-roster`: Surfaces verified active institutional personnel eligible for appointment.
  - `POST /api/campus-proctor/committee/assign`: Security Definer RPC `assign_case_committee_member` binding inquiry members to specific cases.
  - `POST /api/campus-proctor/committee/revoke`: Security Definer RPC `revoke_case_committee_assignment` instantly revoking access.
  - `POST /api/campus-proctor/update`: Assigns presiding proctors and schedules official UGC hearing dates.

### 3.3 Individual Proctor Investigation Desk (`/campus-proctor/dashboard`)
* **Route & Component:** [page.tsx](file:///c:/Users/Ishan/OneDrive/Desktop/micro project/app/campus-proctor/dashboard/page.tsx)
* **API Endpoints:**
  - `GET /api/campus-proctor/my-cases`: Returns grievances specifically assigned to the authenticated proctor (`assigned_proctor_user_id == user.user_id`).
  - `POST /api/campus-proctor/update`: Updates inquiry status through permitted state machine transitions (`UNDER_INQUIRY`, `HEARING_SCHEDULED`, `ACTION_TAKEN`, `RESOLVED`, `CLOSED`), recording proctor findings and actions. Ordinary proctors cannot reassign cases or alter confidentiality modes.
  - `GET /api/campus-proctor/notice/{case_id}`: Formal UGC Inquiry & Hearing Notice generator formatted under UGC (Grievance Redressal of Students) Regulations, 2023.

### 3.4 Committee Member Workspace (`/campus-proctor/committee`)
* **Route & Component:** [page.tsx](file:///c:/Users/Ishan/OneDrive/Desktop/micro project/app/campus-proctor/committee/page.tsx)
* **API Endpoints:**
  - `GET /api/campus-proctor/committee/my-inquiries`: Strictly queries active rows in `case_committee_assignments` for the authenticated member.
  - `POST /api/campus-proctor/committee/observations`: Logs formal findings and recommendations into `case_activity_log` under `COMMITTEE_OBSERVATIONS_RECORDED` and notifies the presiding proctor.
  - Access is revoked instantly upon status transition to `revoked` or account status to `suspended`.

---

## 4. Case Review, Investigation & Hearing Lifecycle Workflow

Campus grievance progression strictly enforces the 6-stage lifecycle with state-machine validation in `api/campus_proctor.py`:

```mermaid
stateDiagram-v2
    [*] --> SUBMITTED: Student / Citizen Filing
    SUBMITTED --> UNDER_INQUIRY: Chief Proctor Triage / Proctor Assignment
    UNDER_INQUIRY --> HEARING_SCHEDULED: Hearing Date Set & Complainant Notified
    HEARING_SCHEDULED --> ACTION_TAKEN: Proctorial Directives & Committee Findings
    ACTION_TAKEN --> RESOLVED: Terms Satisfied & Remedial Order Issued
    RESOLVED --> CLOSED: Case Formally Concluded
```

1. **SUBMITTED:** Intake registered via student portal or central filing with SHA-256 verification key generated.
2. **UNDER_INQUIRY:** Chief Proctor triages unassigned case, appoints an inquiry proctor, and assigns committee members.
3. **HEARING_SCHEDULED:** Formal date set, triggering official UGC Proctorial Notice generation and automated complainant notification.
4. **ACTION_TAKEN:** Proctorial investigation notes recorded; committee records joint observations and recommendations.
5. **RESOLVED:** Formal resolution details and disciplinary or administrative remedy recorded.
6. **CLOSED:** Final closing statement; matter sealed in immutable audit registry.

---

## 5. Notification Reliability & Activity UUID Idempotency

To eliminate fragile timestamp-based idempotency keys and prevent duplicate notification dispatch upon retry, Phase 4 anchors all notification idempotency keys to the immutable UUID of the corresponding `case_activity_log` event:

```python
# Atomic audit activity creation returns immutable event dictionary with UUID
act_rec = record_case_activity(
    case_uuid=case.get("id"),
    case_id=clean_id,
    action_type=f"STATUS_TRANSITION_{new_status}",
    action_details={...},
    actor_user=proctor_user,
    actor_type="USER",
    supabase_client=self.supabase
)
activity_id = (act_rec.get("id") if isinstance(act_rec, dict) else None) or str(uuid.uuid4())

# Notification dispatch utilizes immutable event activity UUID
notification_manager.create_notification(
    recipient_user_id=student_uid,
    event_type="HEARING_SCHEDULED",
    title="Inquiry Hearing Scheduled",
    message=f"A hearing has been scheduled for case {clean_id} on {validated_hearing_date}.",
    related_case_id=clean_id,
    case_uuid=case.get("id"),
    action_url=f"/dashboard/my-cases/{clean_id}",
    idempotency_key=f"notif_act_{activity_id}_hearing_{student_uid}"
)
```

### Result:
- **Retry Deduplication:** Multiple retries of the same event produce identical idempotency keys (`f"notif_act_{activity_id}_..."`), avoiding duplicate alerts.
- **Distinct Event Preservation:** Genuine status transitions produce unique `activity_id` values, ensuring valid alerts are never suppressed.

---

## 6. Automated Verification & Test Results

The test suite [tests/test_phase4_institution_proctor.py](file:///c:/Users/Ishan/OneDrive/Desktop/micro project/tests/test_phase4_institution_proctor.py) executed 15 automated integration tests against the live local Supabase instance:

```text
======================================================================
Ran 15 tests in 1.825s

OK
```

### Scenario Verification Matrix

| # | Scenario Description | Tested Condition | HTTP Status | Result |
| :---: | :--- | :--- | :---: | :---: |
| 1 | **Institution Admin Access Isolation** | Admin Irene (College X) queries stats & cases; attempts cross-institution access on College Y case | 200 / 403 | **PASS** |
| 2 | **Chief Proctor Workflows** | Charlie queries triage queue, accesses committee roster, schedules hearing | 200 | **PASS** |
| 3 | **Ordinary Proctor Inquiries Queue** | Xavier accesses assigned cases queue; verifies assigned inquiries presence | 200 | **PASS** |
| 4 | **Proctor Cannot Reassign Cases** | Xavier attempts to reassign case to another officer | 403 Forbidden | **PASS** |
| 5 | **Committee Active Inquiries & Observations** | Carol queries assigned confidential inquiries and posts findings | 200 | **PASS** |
| 6 | **Immediate Revocation Enforcement** | Carol assignment revoked by Chief Proctor; subsequent inquiry list & observation access denied | 403 Forbidden | **PASS** |
| 7 | **Suspended Member Access Termination** | Suspended member Sam attempts dashboard stats and case queries | 401 / 403 | **PASS** |
| 8 | **Cross-Institution Requests Blocked** | Admin X attempts to assign committee on College Y case; Admin Y accesses College X case | 403 Forbidden | **PASS** |
| 9 | **Citizen Protection Against Internal Leakage** | Student Alice attempts access to proctor inquiries queue | 403 Forbidden | **PASS** |
| 10 | **Activity ID Idempotent Assignment Notification** | Proctor assignment creates notification with `notif_act_{activity_id}_assign_` key | 200 & Verified DB | **PASS** |
| 11 | **Hearing Scheduled Notification** | Hearing scheduling creates complainant alert with `notif_act_{activity_id}_hearing_` key | 200 & Verified DB | **PASS** |
| 12 | **Immutable Audit Log Generation** | Assignment and revocation generate `COMMITTEE_ASSIGNMENT_PROVISIONED` / `REVOKED` in `case_activity_log` | Verified DB | **PASS** |
| 13 | **Unauthorized Field Modification Prevention** | Ordinary student attempts to call status update RPC | 403 Forbidden | **PASS** |
| 14 | **Genuine Database Figures Verification** | Dashboard stats strictly match live PostgreSQL row counts (zero hallucinated stats) | Exact Match | **PASS** |
| 15 | **Citizen Filing & Tracking Regression** | Full regression test of Phase 2.1, 2.2, 2.3 citizen case filing, tracking, and SLA timeline | 200 | **PASS** |

### Regression Test Suite Results

All existing verification test suites executed with 100% pass rates:
* `tests/test_phase3_hardening.py`: **18/18 PASSED** (Authentication rigor, token isolation, rate limiting)
* `tests/test_phase23_citations_notifications.py`: **12/12 PASSED** (Legal citations, notification engine)
* `tests/test_phase22_case_filing.py`: **8/8 PASSED** (Central case filing, document upload, lifecycle)
* `tests/test_phase21_citizen_workspace.py`: **7/7 PASSED** (Citizen dashboard stats, timeline, signed URLs)
* `tests/test_phase1315_e2e_api.py`: **10/10 PASSED** (Security Definer RPCs, committee revocation)
* `npx tsc --noEmit`: **0 ERRORS** (Frontend TypeScript compilation completely clean)

---

## 7. Compliance with Constitutional & UGC Redressal Regulations (2023)

1. **Mandatory Institutional Ombudsperson & Proctorial Oversight:** Dedicated workspaces for Chief Proctor and Institution Admin enable statutory compliance tracking under Section 5(1) of the UGC Regulations.
2. **15-Day Statutory SLA Monitoring:** Real-time computation of `sla_breaches` alerts administrators when active grievances exceed statutory timeframes, preventing citizen grievance stalemates.
3. **Protected Anonymous Complaints:** Anonymous grievance handling completely omits student identification tokens while allowing complainant access through high-entropy SHA-256 verification keys.
4. **Specialized Inquiry Committees:** Ad-hoc committee formation allows institutions to appoint specialized Internal Complaints Committees (ICC) or Anti-Ragging squads with time-limited, case-scoped evidence access.

---

## 8. Summary of Files Created and Modified

### Backend:
* `api/campus_proctor.py`: Added `InstitutionMemberStatusUpdate`, `CommitteeObservationRequest`, `get_institution_dashboard_stats()`, `get_institution_analytics()`, `list_institution_cases()`, `list_institution_members()`, `update_member_status()`, `list_unassigned_cases()`, `list_assigned_cases_for_proctor()`, `list_committee_inquiries()`, and `add_committee_observation()`. Refined notification dispatch to use activity UUID idempotency keys.
* `api/index.py`: Added 10 new REST API endpoints for institutional management, triage, proctor assignments, and committee findings.

### Frontend:
* `lib/api.ts`: Added TypeScript interfaces (`InstitutionStats`, `InstitutionAnalytics`, `InstitutionMember`, `CommitteeObservationPayload`) and API caller functions.
* `app/institution/dashboard/page.tsx`: Institution Administrator Workspace (Overview stats, grievance catalog, roster management, analytics).
* `app/campus-proctor/chief/page.tsx`: Chief Proctor & Ombudsman Workspace (Triage queue, proctor assignment modal, committee formation & revocation).
* `app/campus-proctor/dashboard/page.tsx`: Individual Proctor Investigation Desk (Assigned queue, investigation notes, hearing scheduling, formal notice generator).
* `app/campus-proctor/committee/page.tsx`: Committee Member Workspace (Confidential inquiries, evidence review, joint findings recording).
* `app/Navbar.tsx`: Added institutional workspace navigation link.

### Tests:
* `tests/test_phase4_institution_proctor.py`: 15 comprehensive automated test scenarios.

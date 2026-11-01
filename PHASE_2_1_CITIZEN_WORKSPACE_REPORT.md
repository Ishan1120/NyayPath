# NyayPath — Phase 2.1 Citizen Dashboard & My Cases Workspace Report

**Date:** November 1, 2026  
**Milestone:** Phase 2.1 — Citizen Dashboard & My Cases Workspace  
**Branch:** `feature/phase-1.3.4-security-remediation`  
**Execution Environment:** Local Supabase (PostgreSQL 17.11 @ `http://127.0.0.1:54321`)  
**TypeScript Status:** `npx tsc --noEmit` clean (0 errors)  
**Security Status:** Pass — Zero PII / Proctor Note Leaks, Strict Ownership Isolation Verified  

---

## 1. Executive Summary

Phase 2.1 introduces the **Citizen Dashboard & My Cases Workspace** to the NyayPath unified legal platform. Citizens and students now possess an integrated, highly intuitive, and strictly isolated portal to track filed legal petitions, campus grievances, and statutory RTI requests, review milestone progress timelines, securely access documents, and launch AI-assisted legal drafting.

All backend endpoints enforce **strict fail-closed authorization**, deriving caller identity exclusively from the verified JWT `auth.uid()` rather than untrusted client-supplied user IDs. Internal officer-only notes (`proctor_notes`), verification hashes, and internal committee deliberations remain strictly hidden from citizens.

---

## 2. Architectural Overview

```mermaid
flowchart TD
    subgraph Frontend["Next.js Frontend (App Router)"]
        Navbar["Navbar (app/Navbar.tsx)"]
        Dashboard["Citizen Dashboard (app/dashboard/page.tsx)"]
        MyCases["My Cases Workspace (app/dashboard/my-cases/page.tsx)"]
        CaseDetails["Case Details & Timeline (app/dashboard/my-cases/[id]/page.tsx)"]
        Gateway["AI Legal Engine (views/GatewayView.tsx)"]
    end

    subgraph Backend["FastAPI Backend (api/)"]
        Index["FastAPI Router (api/index.py)"]
        CitizenMgr["Citizen Workspace Manager (api/citizen_workspace.py)"]
        AuthModule["RBAC & JWT Verification (api/auth.py)"]
        DocAccess["Document Access Manager (api/document_access.py)"]
    end

    subgraph Database["Local Supabase / PostgreSQL 17.11"]
        Cases["public.cases (Parent Cases)"]
        CampusCases["public.campus_cases (Grievances)"]
        CaseDocs["public.case_documents (Attachments)"]
        CaseLogs["public.case_activity_log (Audit & Timeline)"]
        AuthUsers["auth.users & public.profiles"]
    end

    Navbar --> Dashboard
    Navbar --> MyCases
    Dashboard --> Gateway
    Dashboard --> MyCases
    MyCases --> CaseDetails
    
    Dashboard -->|GET /api/citizen/dashboard-stats| Index
    MyCases -->|GET /api/citizen/cases| Index
    CaseDetails -->|GET /api/citizen/cases/{id}| Index
    CaseDetails -->|GET /api/campus-proctor/document-url| Index

    Index --> AuthModule
    Index --> CitizenMgr
    Index --> DocAccess

    CitizenMgr --> Cases
    CitizenMgr --> CampusCases
    CitizenMgr --> CaseDocs
    CitizenMgr --> CaseLogs
    DocAccess --> CaseDocs
```

---

## 3. Implementation Details

### 3.1 Backend Endpoints & Architecture (`api/citizen_workspace.py` & `api/index.py`)

1. **`GET /api/citizen/dashboard-stats`**:
   - Authenticated via `get_current_authenticated_user(request)`.
   - Derives `user_id` strictly from cryptographically verified Bearer JWT (`auth.uid()`).
   - Queries `campus_cases` where `student_user_id == user.user_id` and `cases` where `data->>'citizen_user_id' == user.user_id`.
   - Computes live statistics:
     - `total_cases`: Total volume of cases owned by the user.
     - `active_cases`: Cases currently in `SUBMITTED`, `UNDER_INQUIRY`, `HEARING_SCHEDULED`, `ACTION_TAKEN`, `IN_REVIEW`, `IN_PROGRESS`, `FILED`, or `PENDING`.
     - `resolved_cases`: Cases in `RESOLVED`, `CLOSED`, `COMPLETED`, or `DISPOSED`.
     - `pending_actions`: Cases requiring urgent applicant attendance (e.g., `HEARING_SCHEDULED` or inquiry attendance notices).
     - `recent_cases`: The top 5 cases ordered chronologically.
     - `user_profile`: Citizen metadata (`user_id`, `name`, `email`, `role`, `institution_id`).

2. **`GET /api/citizen/cases`**:
   - Query filters: `status`, `category`, `search`, `sort_by`, `sort_order`, `page`, `limit`.
   - Enforces strict single-tenant / cross-user isolation: users can never view grievances filed by another user.
   - Fully sanitizes response objects: completely strips `proctor_notes`, `verification_key_hash`, and `key_version`.

3. **`GET /api/citizen/cases/{case_id}`**:
   - Checks ownership: `case["student_user_id"] == user.user_id` or `case["user_id"] == user.user_id`.
   - Unauthorized callers receive **HTTP 403 Forbidden**; non-existent cases return **HTTP 404 Not Found**.
   - Chronological Timeline: Built from `case_activity_log` and case lifecycle events, filtering out internal officer deliberations.
   - Document Inventory: Normalizes attached files from `case_documents` and `supporting_documents` with document identifiers for authorized signing.
   - Internal Note Shielding: Strictly eliminates `proctor_notes` and confidential inquiry commentary.

4. **`POST /api/citizen/auth/login`**:
   - Authenticates citizen and student credentials with brute-force rate-limiting (`enforce_rate_limit(action="citizen_login")`).
   - Issues standard HS256 JWT containing Supabase Auth claims (`aud: authenticated`, `role: authenticated`, `app_metadata.role: student|citizen`, `sub: UUID`).

### 3.2 Frontend Applications & Views

1. **Citizen Dashboard (`app/dashboard/page.tsx`)**:
   - Personalized greeting banner with user role badge and email.
   - Real-time stat summary cards (Total, Active, Resolved, Pending Actions).
   - Quick action service grid linking to:
     - *File New Grievance / RTI* (activates AI Legal Assistant)
     - *My Cases Workspace* (`/dashboard/my-cases`)
     - *Case Search & Precedents* (`/case-search`)
     - *College Proctor Cell* (`/campus-proctor`)
     - *Live Court News* (`/court-news`)
     - *Track SLA Watchdog* (`/track`)
   - Recent cases table with live status pills and quick link to case details.
   - Tab switching between Overview and AI Legal Assistant (`views/GatewayView.tsx`).

2. **My Cases Workspace (`app/dashboard/my-cases/page.tsx`)**:
   - Search bar filtering by Case ID, subject, and keywords.
   - Status tabs (All, Active, Submitted, Under Inquiry, Hearing Scheduled, Resolved / Closed).
   - Category dropdown (Academic, Hostel, Infrastructure, Disciplinary, RTI, Consumer).
   - Dynamic sorting (Date Created, Last Updated, Status, Category) with ASC/DESC toggling.
   - Pagination controls with total count and page indicators.
   - Informative empty and loading states.

3. **Case Details & Progress Tracker (`app/dashboard/my-cases/[id]/page.tsx`)**:
   - Comprehensive case header: Case ID badge, status pill, category, severity, department, academic year.
   - Full case description and facts card.
   - Official Redressal & Actions section (hearing schedule, official action taken, resolution details).
   - Vertical milestone activity timeline (Submission, Department Assignment, Inquiry Review, Hearing, Resolution).
   - Supporting Documents card with **Secure View / Download** integration:
     - Invokes authorized `/api/campus-proctor/document-url` endpoint.
     - Displays 300-second TTL countdown notice ("Document link expires in 5 minutes for confidentiality").
     - Opens document in sandboxed popup/tab without exposing service-role keys.

4. **Global Navigation (`app/Navbar.tsx`)**:
   - Navigation links updated with *Dashboard*, *My Cases*, *Case Search*, *College Proctor*, *Court News*, and *Track SLA*.
   - Responsive desktop and mobile drawer navigation.

---

## 4. Security Verification

### 4.1 Strict Cross-Tenant & Cross-User Isolation
- **Test:** Citizen A (`student@nit.edu`, UID `...0010`) attempts to read Citizen B's case (`...0020`).
- **Result:** FastAPI strictly returns `403 Forbidden`.
- **Test:** Citizen B attempts to access Citizen A's case document signed URL.
- **Result:** `DocumentAccessManager` strictly rejects with `403 Forbidden` (`access_type="CASE_OWNER"` check failed).

### 4.2 Confidential Officer Notes Isolation
- **Test:** Platform Admin updates a case with `proctor_notes="INTERNAL_CONFIDENTIAL_NOTE: Water filter replaced by vendor ABC Services..."`.
- **Inspection:** Citizen A queries `/api/citizen/cases` and `/api/citizen/cases/{id}`.
- **Result:** `proctor_notes` is absent from all citizen responses. No confidential proctor notes or verification key hashes are transmitted.

### 4.3 Fail-Closed Unauthenticated Handling
- **Test:** Calling `/api/citizen/dashboard-stats`, `/api/citizen/cases`, or `/api/citizen/cases/{id}` without a Bearer token.
- **Result:** Clean `401 Unauthorized` response with no information disclosure.

---

## 5. Test Evidence

### 5.1 Dedicated Citizen Workspace Test Suite (`tests/test_phase21_citizen_workspace.py`)
```
======================================================================
  NYAYPATH PHASE 2.1 CITIZEN WORKSPACE VERIFICATION SUITE
======================================================================

[Test 1] Unauthenticated requests strictly fail closed (HTTP 401)
  [PASS] GET /api/citizen/dashboard-stats rejected with 401.
  [PASS] GET /api/citizen/cases rejected with 401.
  [PASS] GET /api/citizen/cases/{id} rejected with 401.

[Test 2] Citizen & Student Authentication
  [PASS] Authenticated student Aarav logged in successfully.
  [PASS] Invalid password rejected with 401.

  Seeded Test Cases: A1=CAMPUS-3344-CO, A2=CAMPUS-F7E4-ME, B1=CAMPUS-3884-CI

[Test 3] Citizen Dashboard Stats Calculation
  [PASS] Stats computed correctly: Total=4, Active=2, Resolved=2, Pending=0.

[Test 4] My Cases Workspace Listing & Filtering
  [PASS] Citizen A retrieved 4 cases owned by them.
  [PASS] Status filter correctly isolated RESOLVED cases.
  [PASS] Search filter correctly matched keyword 'Evaluation'.
  [PASS] Verified zero proctor_notes or verification_key_hash in case list response.

[Test 5] Strict Cross-Tenant / Cross-User Ownership Isolation
  [PASS] Citizen A rejected with HTTP 403 when attempting to view Citizen B's case.
  [PASS] Citizen B rejected with HTTP 403 when attempting to view Citizen A's case.
  [PASS] Non-existent case correctly returned 404.

[Test 6] Case Details, Chronological Timeline & Confidentiality Isolation
  [PASS] Case details retrieved with official resolution and zero internal proctorial notes leaked.
  [PASS] Case timeline verified with 2 milestones.

[Test 7] Secure Document Access via Authorized Endpoint
  [PASS] Citizen A successfully obtained signed URL (access_type=CASE_OWNER, TTL=300s).
  [PASS] Citizen B strictly blocked with HTTP 403 when requesting Citizen A's document.

======================================================================
  ALL PHASE 2.1 CITIZEN WORKSPACE VERIFICATION TESTS PASSED (7/7)!
======================================================================
```

### 5.2 Full Regression Test Execution Summary

| Test Suite | Focus Area | Result | Notes |
| :--- | :--- | :---: | :--- |
| `test_phase21_citizen_workspace.py` | Citizen Dashboard, My Cases, Stats & Security | **PASS (7/7)** | 100% success against local PostgreSQL |
| `test_phase1315_e2e_api.py` | Committee assignment & identity spoofing | **PASS (10/10)** | Zero regression in RBAC boundaries |
| `test_phase1315_database_failure.py` | Stale cache isolation & DB failure handling | **PASS (6/6)** | Fail-closed signed URL verification |
| `test_phase1315_fallback_safety.py` | Production signed URL fallback safety | **PASS (6/6)** | Fail-closed storage API checks |
| `test_phase1.py` | Phase 1.2–1.3.9 comprehensive platform tests | **PASS (100%)** | Zero regression in legacy mechanisms |
| `test_sql_validation.py` | Static SQL migration dependency checks | **PASS (100%)** | Migrations 001–004 integrity confirmed |
| `npx tsc --noEmit` | Next.js / TypeScript compilation | **PASS (0 errors)** | Clean typecheck across all pages |

---

## 6. Environment Compliance

- **Local Supabase Only:** All tests, database queries, and assertions were executed strictly against local Supabase (`http://127.0.0.1:54321` and PostgreSQL container `supabase_db_micro_project`).
- **No Remote Operations:** No remote database migrations, `supabase db push`, remote API requests, or Vercel deployments were initiated.
- **Zero Secrets Committed:** Cryptographic keys and service-role secrets are managed securely via environment configuration and never exposed to the frontend.

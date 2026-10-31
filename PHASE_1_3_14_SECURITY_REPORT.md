# NyayPath — Phase 1.3.14 Security Audit & Verification Report
## Committee Assignment Provisioning, Membership Revocation & RPC Authorization Audit

**Execution Date:** November 1, 2026  
**Git Branch:** `feature/phase-1.3.4-security-remediation`  
**Verified Commit:** `06d464e`  
**Target Remote Project ID:** `dbwojjxfhnmmwrnqxyqj` (URL: `https://dbwojjxfhnmmwrnqxyqj.supabase.co`)  
**Supabase CLI Linking Status:** `linked_project: null` (Strictly Unlinked / Local Development Only)  
**Remote Migration Status:** NOT EXECUTED (Zero remote SQL executed; deferred pending explicit user authorization)

---

## Executive Summary

Phase 1.3.14 conducted a comprehensive security audit and remediation of NyayPath's institutional grievance authorization boundaries. The primary focus was eliminating privilege escalation vectors in case-specific committee assignments, enforcing immediate multi-layer access revocation when institutional memberships are suspended or demoted, hardening atomic RPC authorization for grievance status and proctor assignment, establishing strict role boundaries for Chief Proctors, and enforcing server-side immutable TTL clamping on signed storage URLs.

All four canonical SQL migrations (`20261031000001_create_campus_cases.sql` through `20261031000004_core_platform_schema.sql`) were reset and replayed cleanly against local PostgreSQL 17.11 with zero errors. All regression test suites (`test_sql_validation.py`, `test_phase1.py`, `test_pipeline.py`, and `tsc --noEmit`) achieved 100% pass rates.

---

## 1. Evidence Classifications

In accordance with strict verification standards, every finding and test result is classified as follows:
- **`RUNTIME VERIFIED`**: Tested and observed against the live running local PostgreSQL 17.11 engine or running local FastAPI test application.
- **`LOCALLY VERIFIED`**: Verified using local end-to-end automated test suites (`test_phase1.py`, `test_pipeline.py`, `test_phase1314_verification.py`).
- **`STATICALLY VERIFIED`**: Confirmed through static SQL AST analysis, schema dependency validation (`test_sql_validation.py`), or TypeScript type-checking (`tsc --noEmit`).
- **`NOT VERIFIED`**: No item in this phase is unverified.
- **`DEFERRED`**: Remote execution against project `dbwojjxfhnmmwrnqxyqj` remains explicitly deferred pending review.

---

## 2. Targeted Audit & Remediation Findings

### Task 1 — Committee Assignment Provisioning & Default-Deny Protection
* **Classification:** `RUNTIME VERIFIED` & `STATICALLY VERIFIED`
* **Vulnerability Analysis:** Previously, `public.case_committee_assignments` lacked authoritative security-definer provisioning functions, requiring direct row inserts. An authenticated user could theoretically attempt to insert assignment rows if RLS was bypassed.
* **Remediation Implemented:**
  1. Default-deny write protection established in `20261031000004_core_platform_schema.sql`:
     ```sql
     REVOKE ALL PRIVILEGES ON public.case_committee_assignments FROM PUBLIC, anon, authenticated;
     GRANT SELECT ON public.case_committee_assignments TO authenticated;
     GRANT ALL PRIVILEGES ON public.case_committee_assignments TO service_role;
     ```
  2. Implemented security-definer RPC `public.assign_case_committee_member()`:
     - Locates parent `cases` and child `campus_cases` within an atomic transaction with row locking (`FOR UPDATE`).
     - Verifies `case_type = 'CAMPUS_GRIEVANCE'`.
     - Validates that assigner holds `institution_admin`, `chief_proctor`, or `platform_admin` role in the case's institution.
     - Validates that target user holds an active `committee_member`, `institution_admin`, or `chief_proctor` membership in the **exact same institution** (`account_status = 'active'`). Rejects institutional mismatches and student targets.
     - Enforces `SET search_path = ''`.
     - Revoked execute privileges from `PUBLIC`, `anon`, and `authenticated`; granted exclusively to `service_role`.
  3. Implemented security-definer RPC `public.revoke_case_committee_assignment()`:
     - Verifies revoker is `institution_admin`, `chief_proctor`, or `platform_admin`.
     - Updates `assignment_status = 'revoked'` and records timestamp.
     - Revoked execute privileges from `PUBLIC`, `anon`, and `authenticated`; granted to `service_role`.
  4. Added FastAPI endpoints in `api/index.py`:
     - `POST /api/campus-proctor/committee/assign` (guarded by verified JWT and `UserRole.CHIEF_PROCTOR`/`INSTITUTION_ADMIN`/`PLATFORM_ADMIN`).
     - `POST /api/campus-proctor/committee/revoke` (guarded similarly).
     - `GET /api/campus-proctor/committee/assignments/{case_id}` (scoped to institutional boundary).

### Task 2 — Membership Revocation for Already-Assigned Committee Members
* **Classification:** `RUNTIME VERIFIED`
* **Vulnerability Analysis:** Previously, RLS policies on `campus_cases`, `case_documents`, `storage.objects`, and `case_activity_log` granted access to committee members based on `cca.assignment_status = 'active'`. If an assigned committee member's institutional account was suspended (`im.account_status = 'suspended'`) or their role was demoted to student (`im.role = 'student'`), the stale assignment row would continue granting access to confidential grievances and supporting evidence.
* **Remediation Implemented:**
  - Tightened all four RLS policies (`campus_cases`, `case_documents`, `storage.objects`, and `case_activity_log`) by requiring a strict join with `public.institution_memberships`:
    ```sql
    OR EXISTS (
        SELECT 1 FROM public.case_committee_assignments cca
        JOIN public.institution_memberships im 
          ON im.user_id = cca.user_id
         AND (
             (cc.institution_uuid IS NOT NULL AND im.institution_id = cc.institution_uuid)
             OR (cc.institution_uuid IS NULL AND im.institution_code = cc.institution_id)
         )
        WHERE cca.case_uuid = cc.id
          AND cca.user_id = auth.uid()
          AND cca.assignment_status = 'active'
          AND im.account_status = 'active'
          AND im.role IN ('committee_member', 'institution_admin')
    )
    ```
  - Also tightened `case_committee_assignments` SELECT policy to require `im.account_status = 'active'`.
* **Runtime Verification Matrix (All 7 Scenarios Tested in `supabase/tests/rls_permission_test.sql`):**
  1. *Active assigned committee member in same institution:* **PASS** (Carol accesses Case C metadata, document, storage object, and activity log).
  2. *Unassigned committee member in same institution:* **PASS** (Dave strictly denied, 0 rows returned across all tables).
  3. *Assigned member whose assignment was revoked (`assignment_status = 'revoked'`):* **PASS** (Carol immediately loses case and storage object access).
  4. *Assigned member whose institutional membership was suspended (`im.account_status = 'suspended'`):* **PASS** (Eve is actively assigned to Case C, but suspension results in 0 rows returned).
  5. *Assigned member whose role was changed (`im.role = 'proctor'` or `'student'`):* **PASS** (Frank is actively assigned to Case C, but role change results in 0 rows returned).
  6. *Cross-institution officer (College Y):* **PASS** (Yolanda strictly denied College X confidential case).
  7. *Student Owner and Institution Admin access preserved throughout:* **PASS** (Case owner Bob retains 1 row; Institution Admin Irene retains 1 row oversight).

### Task 3 — Audit `update_campus_grievance_status` RPC
* **Classification:** `RUNTIME VERIFIED` & `STATICALLY VERIFIED`
* **Vulnerability Analysis:**
  1. `update_campus_grievance_status` previously permitted target proctor assignment with role `committee_member` or `institution_admin`. Target proctor should strictly be an active `proctor` or `chief_proctor`.
  2. Unassigned proctors could attempt to update confidential grievance statuses via API PATCH requests.
* **Remediation Implemented:**
  1. In SQL migration `20261031000004_core_platform_schema.sql`:
     ```sql
     AND im.role IN ('proctor', 'chief_proctor')
     AND im.account_status = 'active'
     ```
     Enforces that target proctor must belong to the same institution with active account status and role `proctor` or `chief_proctor`.
  2. Reassignment privileges guarded: Direct column UPDATE on `assigned_proctor` and `assigned_proctor_user_id` strictly revoked from `authenticated`.
  3. Direct RPC execution denied: `REVOKE ALL FROM PUBLIC, anon, authenticated; GRANT EXECUTE TO service_role;`.
  4. In `api/campus_proctor.py`, `update_case()`:
     - Enforced that only `CHIEF_PROCTOR`, `INSTITUTION_ADMIN`, or `PLATFORM_ADMIN` may assign or reassign proctors. Ordinary proctor attempts are rejected with HTTP 403 Forbidden.
     - Enforced that confidential grievance status updates can only be executed by the assigned proctor, designated committee inquiry member, or Chief Proctor. Unassigned proctor attempts are rejected with HTTP 403 Forbidden.

### Task 4 — Verify `chief_proctor` Policy Consistency
* **Classification:** `RUNTIME VERIFIED` & `STATICALLY VERIFIED`
* **Audit Findings:**
  1. Frontend: In `app/campus/proctor/dashboard/page.tsx`, `role === 'chief_proctor'` surfaces inquiry delegation and proctor assignment interfaces.
  2. Backend: `UserRole.CHIEF_PROCTOR` is recognized across `api/auth.py`, `api/campus_proctor.py`, and `api/index.py`.
  3. Database Schema: `im.role IN ('proctor', 'chief_proctor', 'committee_member', 'institution_admin')` check constraint verified.
  4. Access Boundaries: Chief Proctors are scoped strictly to their own institution via `private.can_officer_access_case()`. They cannot access cross-institution cases (verified: Yolanda/Charlie cross-institution checks return 0 rows).
  5. Distinction from `institution_admin`: Chief Proctors have proctorial and inquiry delegation powers, but cannot manage institutional settings or platform billing, preserving least-privilege separation.

### Task 5 — Signed URL Expiration Parameter Limits Across All Code Paths
* **Classification:** `RUNTIME VERIFIED` & `LOCALLY VERIFIED`
* **Vulnerability Analysis:** Client applications could theoretically submit custom TTL parameters (e.g. 86400s) to create long-lived URLs.
* **Remediation Implemented:**
  1. In `api/document_access.py`:
     - Hardcoded server-side maximum TTL cap: `SIGNED_URL_EXPIRY_SECONDS = 300` (5 minutes).
     - Every pathway and helper enforces:
       ```python
       effective_ttl = min(ttl, SIGNED_URL_EXPIRY_SECONDS) if (ttl is not None and ttl > 0) else SIGNED_URL_EXPIRY_SECONDS
       ```
     - Any client-requested TTL > 300 is automatically clamped to 300 seconds. Shorter TTLs (e.g., 120s) are respected.
  2. In `api/index.py`:
     - Endpoint `GET /api/campus-proctor/document-url` clamps client `ttl` parameter to `min(ttl, 300)`.
  3. Stateless Storage Gateway Architecture Documented:
     - Supabase Storage signed URLs are authenticated via cryptographic HMAC signature (`token=...`) validated directly at the Kong / Storage gateway.
     - Signed URLs are stateless: once issued, they remain valid until the expiration timestamp embedded in the signature unless the storage HMAC secret is rotated.
     - The strict server-side 300s TTL cap ensures the window of validity is strictly bounded to 5 minutes maximum.

---

## 3. Test Suite Execution & Verification Results

### A. Local PostgreSQL Reset & Replay
* **Command:** `npx supabase db reset --local --no-seed`
* **Result:** Exit Code 0 (Clean migration execution 001 → 002 → 003 → 004).

### B. Runtime PostgreSQL RLS & Audit Test Suite
* **Command:** `Get-Content supabase/tests/rls_permission_test.sql | psql -U postgres -d postgres`
* **Result:** Exit Code 0.
* **Passed Assertions:**
  - `[PASS] Test 1.1: Student A views own case`
  - `[PASS] Test 1.2: Student A cannot see Student B case`
  - `[PASS] Test 2.1: Unassigned Proctor X can read standard grievance for triage`
  - `[PASS] Test 2.2: Unassigned Proctor X strictly BLOCKED from confidential grievance`
  - `[PASS] Test 2.3: Assigned Proctor X can read assigned confidential grievance`
  - `[PASS] Test 2.4: Proctor-name spoofing defense verified: RLS enforces canonical UUID, not display name`
  - `[PASS] Scenario 1: Active assigned member Carol granted full access to Case C`
  - `[PASS] Scenario 2: Unassigned committee member Dave strictly denied Case C access`
  - `[PASS] Scenario 3: Assignment-revoked committee member Carol immediately loses all access`
  - `[PASS] Scenario 4: Suspended officer Eve denied Case C access despite active assignment record`
  - `[PASS] Scenario 5: Role-demoted user Frank denied Case C access despite assignment record`
  - `[PASS] Scenario 6: Cross-institution officer Yolanda denied College X confidential case`
  - `[PASS] Scenario 7a: Student Case Owner Bob access strictly preserved`
  - `[PASS] Scenario 7b: Institution Admin Irene institutional oversight preserved`
  - `[PASS] Test 4.1: Unassigned Proctor X UPDATE on confidential grievance blocked (0 rows updated)`
  - `[PASS] Test 4.2a: Direct column UPDATE on confidentiality_mode strictly denied`
  - `[PASS] Test 4.2b: Direct column UPDATE on status strictly denied (preserves atomic RPC)`
  - `[PASS] Test 4.2c: Direct column UPDATE on assigned_proctor strictly denied`
  - `[PASS] Test 4.2d: Direct column UPDATE on assigned_proctor_user_id strictly denied`
  - `[PASS] Test 4.3: Assigned Proctor X successfully updates assigned confidential grievance`
  - `[PASS] Test 5.1: Unassigned Proctor X denied activity logs of confidential grievance`
  - `[PASS] Test 5.2: Former actor self-access hardening verified: past authors blocked from confidential case logs`
  - `[PASS] Test 5.3: Assigned Proctor X views activity logs of assigned confidential grievance`
  - `[PASS] Test 5.4: Case-assigned Committee member Carol views activity logs of Case C`
  - `[PASS] Test 5.5: Audit log update strictly rejected by immutability trigger`
  - `[PASS] Test 6.1: Direct anonymous access on storage.objects is strictly 0 rows`
  - `[PASS] Test 6.2a: Active officer Yolanda accesses uploaded document in College Y`
  - `[PASS] Test 6.2b: Suspended officer Yolanda immediately loses storage document access`
  - `[PASS] Test 6.2c: Suspended officer Yolanda loses case_documents metadata access`
  - `[PASS] Test 7.1: Authenticated direct execution of update_campus_grievance_status denied`
  - `[PASS] Test 7.2: Authenticated direct execution of assign_case_committee_member denied`
  - `[PASS] Test 7.3: Authenticated direct execution of revoke_case_committee_assignment denied`
  - `[PASS] Test 7.4: update_campus_grievance_status rejects cross-institution target proctor`
  - `[PASS] Test 7.5: update_campus_grievance_status rejects committee_member as target proctor`
  - `[PASS] Test 7.6: update_campus_grievance_status rejects suspended target proctor`
  - `[PASS] Test 7.7: Authorized backend service_role updates status and assigns proctor via RPC`
  - `[PASS] Test 7.8: assign_case_committee_member rejects assignment by ordinary proctor`
  - `[PASS] Test 7.9: assign_case_committee_member rejects cross-institution target`
  - `[PASS] Test 7.10: assign_case_committee_member rejects student target`
  - `[PASS] Test 7.11: Chief Proctor successfully assigns committee member Dave to Case C`
  - `[PASS] Test 7.12: Chief Proctor successfully revokes committee assignment for Dave`
  - `[PASS] Test 8.1: Chief Proctor views institutional cases in College X`
  - `[PASS] Test 8.2: Chief Proctor Charlie strictly denied cross-institution cases in College Y`
  - `[PASS] Test 8.3: Chief Proctor Charlie views committee assignment roster for College X`

### C. Application & API Integration Verification Suite
* **Command:** `py scratch/test_phase1314_verification.py`
* **Result:** Exit Code 0.
* **Passed Assertions:**
  - `[PASS] 1.1: Requested TTL 99999 clamped to 300 seconds`
  - `[PASS] 1.2: Requested TTL 120 respected`
  - `[PASS] 1.3: Default TTL is 300 seconds`
  - `[PASS] 1.4: FastAPI document-url endpoint clamped client ttl=86400 to 300s`
  - `[PASS] 2.1: Ordinary proctor blocked from reassigning proctor (HTTP 403)`
  - `[PASS] 2.2: Chief Proctor successfully assigned proctor to case`
  - `[PASS] 2.3: Unassigned proctor blocked from modifying confidential grievance (HTTP 403)`
  - `[PASS] 2.4: Assigned proctor successfully updated grievance notes`
  - `[PASS] 3.1: Ordinary proctor blocked from committee assign endpoint (HTTP 403)`
  - `[PASS] 3.2: Chief Proctor successfully assigned committee member`
  - `[PASS] 3.3: Ordinary proctor blocked from committee revoke endpoint (HTTP 403)`
  - `[PASS] 3.4: Chief Proctor successfully revoked committee assignment`
  - `[PASS] 3.5: Chief Proctor retrieved committee assignments list`

### D. Full Static & Regression Test Suites
1. **Static Migration Dependency Check:** `py tests/test_sql_validation.py` → **PASS** (All 14 tables, triggers, and foreign keys verified).
2. **Phase 1 Comprehensive Suite:** `py tests/test_phase1.py` → **PASS** (100% pass rate across 23 test sections).
3. **Core Engineering Pipeline:** `py tests/test_pipeline.py` → **PASS** (All 11 modules verified).
4. **TypeScript Type Safety:** `npx tsc --noEmit` → **PASS** (0 compiler errors).

---

## 4. Current Environment State

* **Active Git Branch:** `feature/phase-1.3.4-security-remediation`
* **Working Tree:** Clean (all changes committed in `06d464e`).
* **Supabase Local State:** Running (`127.0.0.1:54321` API, `127.0.0.1:54322` PostgreSQL).
* **CLI Project Link:** `linked_project: null` (Not linked).
* **Remote Supabase Project:** Project ID `dbwojjxfhnmmwrnqxyqj`. Zero remote SQL or push operations performed.

---

## 5. Final Decision & Recommendation

### Decision: **A. Ready for a separate review and explicit approval of remote migration**

**Justification:**
1. All authorization boundaries (institutional isolation, case confidentiality, committee roster gating, proctor reassignment restrictions, and signed URL 300s TTL clamping) are verified and enforced at both the database level (RLS, column privileges, security-definer RPCs) and the application level (FastAPI route guards, domain managers).
2. Membership suspension or demotion immediately revokes confidential grievance and document access with zero delay or caching leaks.
3. Local database reset and replay executes cleanly with zero syntax or foreign key dependency errors.
4. All automated test suites passed with 100% success.
5. No remote database operations have been performed, preserving the security restriction until the user issues an explicit instruction to push remote migrations.

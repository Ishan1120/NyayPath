# NyayPath — Phase 3: Production Security, API Reliability & Application Hardening Report

**Milestone:** Phase 3 — Production Security, API Reliability & Application Hardening  
**Date:** November 1, 2026  
**Branch:** `feature/phase-1.3.4-security-remediation`  
**Test Framework:** Python `unittest`, Starlette `TestClient`, PostgreSQL PL/pgSQL, TypeScript compiler (`tsc`)  
**Environment Target:** Local Supabase (`http://127.0.0.1:54321`, PostgreSQL 17.11 @ 54322)  

---

## 1. Executive Summary

Phase 3 established production-grade application hardening across NyayPath's authentication, authorization, notification data integrity, legal citation verification, API request validation, and environment configuration. All implementations operate under strict fail-closed security invariants, preventing client-side identity spoofing, timing attacks, data tampering, in-memory state fallbacks in production, and cross-origin security bypasses.

### Key Deliverables Completed:
1. **Authoritative Authentication Rigor:** Validated cryptographic signatures, algorithms (HS256 enforced, `none` rejected), audiences, and subject UUIDs (no dummy fallback). Differentiated FastAPI custom tokens from Supabase tokens, preventing PostgREST authentication errors. Strictly enforced fail-closed account status checks against suspended, revoked, or disabled accounts.
2. **Notification Data Integrity & Database Immutability:** Applied forward-only migration `20261101000002_notifications_hardening.sql`. Deployed a database-level `BEFORE UPDATE` trigger on `public.notifications` forbidding mutation of notification content, recipient, or case metadata. Enforced least-privilege table grants (revoked `INSERT` from authenticated/anon roles) and restricted `create_notification` RPC execution exclusively to `service_role`. Implemented production fail-closed behavior with zero in-memory fallback.
3. **Legal Citation Integrity & Jurisdiction Handling:** Guaranteed zero hallucination by mapping citations strictly to verified catalog entries. Disambiguated Supreme Court binding precedent (Article 141) from State High Court persuasive authority. Validated external URLs (`http`/`https` only) and differentiated official court records (`.gov.in`, `.nic.in`) from third-party repositories.
4. **API Security, Validation & Reliability:** Enforced <= 10MB file size limits, MIME type inspection, and filename path traversal sanitization. Added upfront validation on document uploads requiring existing case ownership before storage operations (HTTP 404 on missing cases). Migrated case tracking key validation to constant-time `hmac.compare_digest`. Enforced bounded pagination and request string length limits.
5. **Production Secrets & Configuration Audit:** Verified zero leakage of backend secrets (`SUPABASE_SERVICE_ROLE_KEY`, `JWT_SECRET`) to the client bundle. Restricted CORS origins to trusted domains, prohibiting wildcards (`*`). Disabled diagnostic `/api/debug/supabase` in production (returns HTTP 404).

---

## 2. Authentication Consistency & Rigor (Task 1)

### 2.1 Authoritative Identity Derivation & Account Status Enforcement
- **Identity Derivation:** All protected routes authenticate callers authoritatively via `get_current_authenticated_user()`, extracting the verified subject claim (`sub`) from the cryptographic JWT. Client-supplied IDs in request bodies are ignored or validated strictly against `user.user_id`.
- **Account Status Fail-Closed:** Both `decode_access_token` and `decode_supabase_access_token` inspect `app_metadata`, top-level claims, and `user_metadata` for `account_status`. Any account status other than `"active"` (e.g. `"suspended"`, `"revoked"`, `"disabled"`, `"banned"`) immediately rejects the token, returning `None` and raising `HTTPException(401, detail="Account is suspended or deactivated.")`.
- **Insecure Fallback Removal:** Removed legacy dummy UUID fallback (`"00000000-0000-0000-0000-000000000000"`). Missing or whitespace-only subject claims fail closed with an explicit rejection.

### 2.2 JWT Verification Rigor
- **Algorithm Enforcement:** `decode_access_token` decodes the token header and strictly checks `alg == "HS256"`. Tokens specifying `"alg": "none"` or mismatched asymmetric algorithms are rejected without signature execution.
- **Audience & Issuer Validation:** Validates that `aud` belongs to `["authenticated", "nyaypath"]`.
- **FastAPI Token vs. Supabase Token Separation:** Custom tokens issued by FastAPI contain `iss: "nyaypath-auth"`. In `get_request_scoped_supabase_client`, tokens with `iss == "nyaypath-auth"` are identified and never forwarded to PostgREST as Bearer tokens, preventing authentication mismatches or authorization elevation in PostgREST.

---

## 3. Notification Data Integrity & Database Hardening (Task 2)

### 3.1 Database-Level Immutability Trigger
To guarantee that notification content cannot be tampered with once delivered, migration `20261101000002_notifications_hardening.sql` added the trigger function `private.enforce_notification_immutability()`:
```sql
CREATE OR REPLACE FUNCTION private.enforce_notification_immutability()
RETURNS TRIGGER
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = ''
AS $$
BEGIN
    IF (OLD.recipient_user_id IS DISTINCT FROM NEW.recipient_user_id) OR
       (OLD.event_type IS DISTINCT FROM NEW.event_type) OR
       (OLD.title IS DISTINCT FROM NEW.title) OR
       (OLD.message IS DISTINCT FROM NEW.message) OR
       (OLD.related_case_id IS DISTINCT FROM NEW.related_case_id) OR
       (OLD.created_at IS DISTINCT FROM NEW.created_at) OR
       (OLD.case_uuid IS DISTINCT FROM NEW.case_uuid) OR
       (OLD.action_url IS DISTINCT FROM NEW.action_url) OR
       (OLD.idempotency_key IS DISTINCT FROM NEW.idempotency_key) OR
       (OLD.metadata IS DISTINCT FROM NEW.metadata) THEN
        RAISE EXCEPTION 'Notification content is immutable. Only is_read and read_at can be modified by users.'
            USING ERRCODE = '42501';
    END IF;

    IF (NEW.is_read = true AND OLD.is_read = false AND NEW.read_at IS NULL) THEN
        NEW.read_at := clock_timestamp();
    END IF;

    RETURN NEW;
END;
$$;
```
- **Trigger:** Attached as `BEFORE UPDATE ON public.notifications FOR EACH ROW`.
- **Automatic Timestamping:** Automatically sets `read_at = clock_timestamp()` when `is_read` transitions to `true`.

### 3.2 Least-Privilege Grants & RPC Access Control
- **Table Privileges:**
  - `REVOKE ALL ON TABLE public.notifications FROM public, anon, authenticated;`
  - `GRANT SELECT, DELETE ON TABLE public.notifications TO authenticated;`
  - `GRANT UPDATE (is_read, read_at) ON TABLE public.notifications TO authenticated;`
  - `GRANT ALL ON TABLE public.notifications TO service_role;`
- **RPC Privileges:**
  - `REVOKE ALL ON FUNCTION private.create_notification FROM public, anon, authenticated;`
  - `GRANT EXECUTE ON FUNCTION private.create_notification TO service_role;`
- Direct insertions by standard users or anonymous callers are rejected by PostgreSQL privilege checks.

### 3.3 Idempotency & Production Fail-Closed Behavior
- **Event-Specific Idempotency Keys:** Auto-generated keys format as `f"notif_{clean_recipient}_{event_type}_{related_case_id}_{secrets.token_hex(8)}"`, ensuring future distinct events (e.g. status updates, hearings) on the same case are never suppressed.
- **Fail-Closed Production Safety:** In production mode (`_is_production() == True`), `NotificationManager` never writes to or returns data from `_memory_notifications`. Any database interruption immediately raises `HTTPException(503, detail="Database notifications unavailable in production.")`.

---

## 4. Legal Citation Integrity & Jurisdiction Handling (Task 3)

### 4.1 Strict Catalog Mapping (Zero Hallucination)
- Precedents returned by the AI Legal Engine and case search map strictly to curated authorities in `LANDMARK_PRECEDENTS`.
- Irrelevant or non-legal queries return `has_citations: false` and empty lists rather than fabricating matching case law.

### 4.2 Jurisdictional Authority Disambiguation
- **Supreme Court:** Classified as `BINDING` under Article 141 of the Constitution of India, binding on all courts within the territory of India.
- **High Courts:** Classified as `PERSUASIVE` outside the issuing state, binding only within the state territorial jurisdiction.
- The UI component (`LegalCitationCard.tsx`) displays authority badges:
  - `"Binding Authority (Art. 141)"` for Supreme Court decisions.
  - `"Persuasive Precedent (State High Court)"` for High Court decisions.

### 4.3 Link Safety & Official Domain Recognition
- `is_safe_url()` validates URL schemes: only `http` and `https` are allowed; `javascript:`, `data:`, `file:`, and relative schemes are rejected.
- `isOfficialGovSource()` identifies government judicial domains ending in `.gov.in`, `.nic.in`, and `.judiciary.gov.in`. Buttons are labeled `"Official Court Record (.gov.in)"` for official sources and `"External Repository (IndianKanoon)"` for third-party databases.
- Missing metadata is rendered as `"Bench details not recorded"` or `"Court jurisdiction unrecorded"` rather than invented.

---

## 5. API Security, Input Validation & Reliability (Task 4)

### 5.1 Document Upload Hardening
- **Upfront Case Validation:** In `upload_document`, if `case_id` is provided, the case is fetched and checked before any storage upload:
  - If the case does not exist: returns `HTTPException(404, detail="Case '...' not found.")`.
  - If the caller does not own the case: returns `HTTPException(403, detail="Access denied: Cannot attach documents to a case you do not own.")`.
- **Path Traversal Sanitization:** `sanitize_document_payload` extracts `os.path.basename`, strips directory traversal sequences (`..`, slashes, null bytes), replaces non-alphanumeric characters with underscores, and strips leading dots/underscores to avoid hidden file creation.
- **File Size & Content:** Strictly enforces <= 10MB payload size and allows only `application/pdf`, `image/jpeg`, `image/png`, and `image/webp`.

### 5.2 Constant-Time Public Case Tracking
- Public case tracking in `citizen_workspace.py` previously used standard string equality (`candidate_hash == stored_hash`), vulnerable to timing attacks.
- Replaced with `hmac.compare_digest(candidate_hash, stored_hash)` across all verification key check locations.

### 5.3 Request String Length Limits & Pagination
- Added Pydantic `Field` length constraints:
  - `CitationResolveRequest.query`: `min_length=1, max_length=1000`.
  - `ClarifyingQuestionsRequest.problem_text`: `max_length=10000`.
  - `SynthesizeDraftRequest.problem_text`: `max_length=10000`.
  - `PrecedentSearchRequest.query`: `max_length=1000`.
- Safe pagination limits enforced on all listing endpoints: `safe_limit = max(1, min(100, int(limit)))`, `safe_offset = max(0, int(offset))`.

---

## 6. Production Configuration & Secrets Audit (Task 5)

### 6.1 Diagnostic Endpoint Disabling
- `/api/debug/supabase` now checks `_is_production()`. In production mode, it immediately raises `HTTPException(404, detail="Endpoint not found.")`, preventing internal connectivity discovery.

### 6.2 CORS Origin Restriction
- Prohibits wildcard `*` origins in all environments.
- Origins are loaded from `ALLOWED_ORIGINS` and `FRONTEND_URL` environment variables, filtering out any `*` wildcard entries.

### 6.3 Secret Key Exposure Audit
- Automated scanning of `components/`, `app/`, and `lib/` verified that `NEXT_PUBLIC_` is never prepended to backend secrets (`SUPABASE_SERVICE_ROLE_KEY`, `JWT_SECRET`, `GROQ_API_KEY`, `DATABASE_URL`).

---

## 7. Verification & Test Results (Task 6)

### 7.1 Dedicated Phase 3 Test Suite (`tests/test_phase3_hardening.py`)
| Test Case | Objective | Status | Verification Class |
| :--- | :--- | :---: | :---: |
| `test_jwt_missing_or_empty_subject_rejected` | Missing or empty `sub` claim rejected fail-closed | PASS | RUNTIME VERIFIED |
| `test_jwt_invalid_audience_rejected` | Unauthorized `aud` claim rejected fail-closed | PASS | RUNTIME VERIFIED |
| `test_jwt_algorithm_none_rejected` | Unsigned tokens with `alg: "none"` strictly rejected | PASS | RUNTIME VERIFIED |
| `test_account_status_suspended_or_revoked_rejected` | Suspended, revoked, or disabled accounts fail-closed | PASS | RUNTIME VERIFIED |
| `test_fastapi_token_not_forwarded_to_postgrest` | Custom FastAPI tokens (`iss="nyaypath-auth"`) isolated | PASS | RUNTIME VERIFIED |
| `test_database_notification_immutability_trigger` | Trigger blocks direct modification of title, recipient, etc. | PASS | RUNTIME VERIFIED |
| `test_database_least_privilege_grants` | `INSERT` revoked from users; RPC restricted to `service_role` | PASS | RUNTIME VERIFIED |
| `test_notification_production_fail_closed` | Database failure in production returns 503 without fallback | PASS | RUNTIME VERIFIED |
| `test_notification_idempotency_distinct_events` | High-entropy idempotency keys preserve distinct events | PASS | RUNTIME VERIFIED |
| `test_upload_document_missing_case_returns_404` | Upload to non-existent case fails with 404 upfront | PASS | RUNTIME VERIFIED |
| `test_upload_document_path_traversal_sanitized` | Path traversal filenames sanitized to safe basenames | PASS | RUNTIME VERIFIED |
| `test_public_tracking_constant_time_hmac` | Constant-time comparison verifies keys without timing leak | PASS | RUNTIME VERIFIED |
| `test_legal_citation_url_safety` | `is_safe_url` allows `http`/`https` and rejects dangerous protocols | PASS | RUNTIME VERIFIED |
| `test_legal_citation_authority_levels` | SC classified as Binding (Art. 141), HC as Persuasive | PASS | RUNTIME VERIFIED |
| `test_citation_resolve_input_validation` | Empty or whitespace queries rejected with 400 Bad Request | PASS | RUNTIME VERIFIED |
| `test_debug_endpoint_disabled_in_production` | `/api/debug/supabase` returns 404 when `ENVIRONMENT=production` | PASS | RUNTIME VERIFIED |
| `test_cors_origins_exclude_wildcard` | CORS origins contain no wildcard `*` | PASS | RUNTIME VERIFIED |
| `test_no_secret_keys_in_client_bundle` | Zero backend secret variable names exposed in frontend | PASS | STATICALLY VERIFIED |

**Summary: 18 passed in 2.40s.**

### 7.2 Full Regression Verification
1. **Phase 2.3 Citations & Notifications Suite (`test_phase23_citations_notifications.py`):**  
   - 12 passed, 0 failed.
2. **Phase 2.2 Case Filing & Tracking Suite (`test_phase22_case_filing.py`):**  
   - 8 passed, 0 failed.
3. **Phase 2.1 Citizen Workspace Suite (`test_phase21_citizen_workspace.py`):**  
   - 7 passed, 0 failed.
4. **Phase 1.3.15 Live API Authorization & Trusted Identity (`test_phase1315_e2e_api.py`):**  
   - 10 passed, 0 failed.
5. **TypeScript Compiler (`npx tsc --noEmit`):**  
   - 0 errors.

---

## 8. Modified & Created Files Inventory

| File Path | Status | Purpose |
| :--- | :---: | :--- |
| `api/auth.py` | Modified | Algorithm allowlist, sub validation, account status enforcement, token isolation |
| `api/citizen_workspace.py` | Modified | Constant-time HMAC comparison, upfront 404 case check, safe filename normalization |
| `api/citations.py` | Modified | URL scheme safety validation, authority classification |
| `api/index.py` | Modified | Production debug 404 disabling, CORS origin restriction, rate limits, request length bounds |
| `api/media_sanitizer.py` | Modified | Path traversal sanitization using `os.path.basename` and character stripping |
| `api/notifications.py` | Modified | High-entropy idempotency keys, production fail-closed 503 error handling |
| `components/LegalCitationCard.tsx` | Modified | Official court domain badges (`.gov.in`), URL safety check, missing field fallbacks |
| `supabase/migrations/20261101000002_notifications_hardening.sql` | Created | Database immutability trigger, column update restrictions, RPC execution revoke |
| `tests/test_phase3_hardening.py` | Created | Automated test suite covering all 18 hardening requirements |
| `.env` | Modified | Enforced local Supabase instance credentials (`127.0.0.1:54321`) |

---

## 9. Compliance With Strict Environment Restrictions

* [x] **Local Supabase Environment Only:** All database operations and migrations executed exclusively against `supabase_db_micro_project` (`127.0.0.1:54322`).
* [x] **No Remote Project Linking:** The Supabase CLI was not linked to `dbwojjxfhnmmwrnqxyqj`.
* [x] **No Remote Migrations or `supabase db push`:** Zero remote schema migrations or DDL executions performed.
* [x] **No Remote Modifications:** No remote users, storage buckets, database tables, or environment configurations modified.
* [x] **No Vercel Deployments:** No build or deployment triggers initiated.

# NyayPath — Migration 12 Final Safety Report

**Document Reference:** `NYAYPATH-MIGRATION-12-SAFETY-2026-11-03`  
**Evaluation Scope:** Draft User Identity Verification, Ownership & RLS Rigor, Timestamp Default Correction, and Local Database Replay  
**Environment Target:** Local Environment Only (`http://127.0.0.1:54321` / Docker `supabase_db_micro_project`)  
**Staging & Production Boundary:** Strict Zero Connections; No Remote Migrations Executed  

---

## 1. Executive Summary & Verification Scope

A dedicated, local-only safety verification pass was conducted on **Migration 12** (`20261103000001_legal_drafts_schema.sql`) and the legal drafts persistence layer ([`api/legal_drafts.py`](file:///c:/Users/Ishan/OneDrive/Desktop/micro%20project/api/legal_drafts.py)).

All verification requirements specified in the directive have been analyzed, corrected, and verified against the live local Supabase catalog and runtime test suites:
1. **User Identity Extraction:** Strictly derives user identity from the verified `sub` claim of the authenticated JWT.
2. **Foreign Key Integrity:** Database foreign key `legal_drafts.user_id REFERENCES auth.users(id)` rejects arbitrary or unseeded user IDs.
3. **Immutability of Principal:** Client requests cannot spoof or inject `user_id`.
4. **Ownership Enforcement:** All CRUD operations (`create_draft`, `list_user_drafts`, `get_draft`, `update_draft`, `delete_draft`) enforce author ownership. Cross-user read, update, or delete attempts fail closed with `HTTP 403 Forbidden`.
5. **Service-Role vs. RLS:** While backend queries utilize the service-role key, every database query implements application-level ownership guards (`eq("user_id", str(user.user_id))`).
6. **Timestamp Correction:** Replaced `timezone('utc'::text, now())` with `DEFAULT now()` for `created_at` and `updated_at`, and updated `private.set_updated_at_timestamp()` to set `NEW.updated_at = now()`.
7. **Local Migration Rebuild:** Reset the local database from scratch (`npx supabase db reset`), sequentially applying all 12 migrations.
8. **Regression Suite:** All 19 test suites passed (100% pass rate).

---

## 2. User Identity Mapping Findings

### 2.1 Extraction from Authenticated JWT

In [`api/auth.py`](file:///c:/Users/Ishan/OneDrive/Desktop/micro%20project/api/auth.py#L590-L720):
* The dependency `get_current_authenticated_user(request)` routes bearer tokens through `decode_access_token` (for application HS256 tokens) or `decode_supabase_access_token` (for native Supabase asymmetric tokens).
* **Exact User ID Extracted:** The `sub` (subject) claim from the JWT payload:
  ```python
  sub = payload.get("sub")
  return AuthUser(user_id=sub.strip(), ...)
  ```
* This principal identity is provided to [`api/index.py`](file:///c:/Users/Ishan/OneDrive/Desktop/micro%20project/api/index.py#L1600-L1644) and passed directly into `LegalDraftManager`.

### 2.2 Correspondence to `auth.users.id`

* In [`supabase/migrations/20261103000001_legal_drafts_schema.sql`](file:///c:/Users/Ishan/OneDrive/Desktop/micro%20project/supabase/migrations/20261103000001_legal_drafts_schema.sql#L10-L15), the table declares:
  ```sql
  user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE
  ```
* **Foreign Key Behavior:** The PostgreSQL database rejects any insert or update where `user_id` is not present in `auth.users(id)` with error code `23503` (`foreign_key_violation`).
* **Custom NyayPath JWTs vs. Native Tokens:** Custom NyayPath JWTs are signed with the application secret, whereas native Supabase Auth JWTs are signed with Supabase Auth keys. Both token types set `sub` to the user's UUID. If a token carries an unseeded or random UUID not in `auth.users`, database persistence fails closed with a foreign key violation.
* **Empirical Proof:** In `test_02_foreign_key_enforcement_to_auth_users` ([`tests/test_draft_user_identity_and_cross_user_isolation.py`](file:///c:/Users/Ishan/OneDrive/Desktop/micro%20project/tests/test_draft_user_identity_and_cross_user_isolation.py)), attempting to persist a draft with a phantom UUID generated an immediate foreign key constraint error.

### 2.3 Protection Against Client User ID Spoofing

* In [`api/legal_drafts.py`](file:///c:/Users/Ishan/OneDrive/Desktop/micro%20project/api/legal_drafts.py#L30-L50):
  * Neither `CreateDraftRequest` nor `UpdateDraftRequest` models define a `user_id` field.
  * In `create_draft`:
    ```python
    draft_record = {
        "user_id": str(user.user_id),
        ...
    }
    ```
* If a client attempts to include `"user_id": "spoofed-uuid"` in the JSON body, Pydantic either ignores or excludes the extra field, and the engine assigns `user_id` strictly from `user.user_id`.
* **Empirical Proof:** In `test_01_user_id_derived_from_authenticated_jwt_only`, Alice sent a request containing Bob's UUID in the JSON body. The draft was stored with Alice's authenticated UUID; Bob's UUID was disregarded.

---

## 3. Ownership Enforcement & Cross-User Isolation

### 3.1 Operation-by-Operation Audit

| Operation | Endpoint | Ownership Guard in `api/legal_drafts.py` | Database Query Guard |
| :--- | :--- | :--- | :--- |
| **Create** | `POST /api/drafts` | Derived from authenticated `user.user_id` | `INSERT INTO legal_drafts (user_id = user.user_id)` |
| **List** | `GET /api/drafts` | Restricted to authenticated caller | `.select("*").eq("user_id", user_id_str)` |
| **Get** | `GET /api/drafts/{id}` | Requires `draft_owner_id == user_id_str` (or explicit consultation draft grant) | Returns 403 Forbidden for non-owners |
| **Update** | `PUT /api/drafts/{id}` | Requires `draft_owner_id == user_id_str` | `.update(...).eq("id", clean_id).eq("user_id", str(user.user_id))` |
| **Delete** | `DELETE /api/drafts/{id}` | Requires `draft_owner_id == user_id_str` | `.delete().eq("id", clean_id).eq("user_id", str(user.user_id))` |

### 3.2 Cross-User Isolation Verification

A dedicated test suite ([`tests/test_draft_user_identity_and_cross_user_isolation.py`](file:///c:/Users/Ishan/OneDrive/Desktop/micro%20project/tests/test_draft_user_identity_and_cross_user_isolation.py)) verified cross-user interactions between Alice Sharma and Bob Verma:

1. **Read Isolation:** Bob calling `GET /api/drafts/{alice_draft_id}` is rejected with `HTTP 403 Forbidden` (`detail: "Access denied. You do not have permission to view this legal draft."`).
2. **Update Isolation:** Bob calling `PUT /api/drafts/{alice_draft_id}` is rejected with `HTTP 403 Forbidden` (`detail: "Access denied. Only the author can update this legal draft."`). Database content remains unaltered.
3. **Delete Isolation:** Bob calling `DELETE /api/drafts/{alice_draft_id}` is rejected with `HTTP 403 Forbidden` (`detail: "Access denied. Only the author can delete this legal draft."`). Alice's draft remains intact in PostgreSQL.
4. **List Isolation:** Bob calling `GET /api/drafts` receives only drafts where `user_id = bob_id`. Alice's drafts are excluded.

---

## 4. Service-Role and RLS Behavior

### 4.1 Service-Role Key Usage

* `LegalDraftManager` initializes the Supabase client using `SUPABASE_SECRET_KEY` (service-role).
* In PostgreSQL / Supabase, queries executed with the service-role key bypass RLS policies at the database engine level.

### 4.2 Application-Level Defense-in-Depth

Because the backend connects via the service-role key, the application layer enforces ownership checks on every database interaction:
* `list_user_drafts`: Explicitly adds `.eq("user_id", user_id_str)`.
* `get_draft`: Compares `draft.user_id` against `user.user_id`.
* `update_draft`: Checks author ownership and adds `.eq("user_id", str(user.user_id))` to the update query.
* `delete_draft`: Checks author ownership and adds `.eq("user_id", str(user.user_id))` to the delete query.

### 4.3 Database RLS Policy

For direct Data API or PostgREST access, Migration 12 provisions:
```sql
ALTER TABLE public.legal_drafts ENABLE ROW LEVEL SECURITY;
REVOKE ALL PRIVILEGES ON public.legal_drafts FROM PUBLIC, anon;
GRANT SELECT, INSERT, UPDATE, DELETE ON public.legal_drafts TO authenticated;
GRANT ALL ON public.legal_drafts TO service_role;

CREATE POLICY "Users can manage own legal drafts"
    ON public.legal_drafts FOR ALL
    TO authenticated
    USING (user_id = auth.uid())
    WITH CHECK (user_id = auth.uid());
```
Authenticated PostgREST queries are bounded by `user_id = auth.uid()`. Unauthenticated requests (`anon`) have zero privileges.

---

## 5. Timestamp Defaults Correction

In [`supabase/migrations/20261103000001_legal_drafts_schema.sql`](file:///c:/Users/Ishan/OneDrive/Desktop/micro%20project/supabase/migrations/20261103000001_legal_drafts_schema.sql):

### 5.1 Modifications Applied

* **Previous:** `created_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc'::text, now()),`
* **Corrected:** `created_at TIMESTAMPTZ NOT NULL DEFAULT now(),`
* **Previous:** `updated_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc'::text, now())`
* **Corrected:** `updated_at TIMESTAMPTZ NOT NULL DEFAULT now()`
* **Trigger Function:**
  ```sql
  CREATE OR REPLACE FUNCTION private.set_updated_at_timestamp()
  RETURNS TRIGGER AS $$
  BEGIN
      NEW.updated_at = now();
      RETURN NEW;
  END;
  $$ LANGUAGE plpgsql SECURITY DEFINER;
  ```

### 5.2 Physical Verification

1. **Column Defaults in Catalog:**
   ```
    column_name | column_default |        data_type         
   -------------+----------------+--------------------------
    created_at  | now()          | timestamp with time zone
    updated_at  | now()          | timestamp with time zone
   ```
2. **Trigger Execution:** Confirmed in `test_05_timestamp_defaults_and_updated_at_trigger` that updating a draft row triggers `trg_legal_drafts_updated_at`, updating `updated_at` to a later timestamp.

---

## 6. Local Verification Execution & Results

### 6.1 Clean Sequential Migration Replay

The local database was reset from scratch using `npx supabase db reset`. All 12 migrations applied sequentially:

```
Target: local stack (127.0.0.1:54322)
Resetting local database...
Recreating database...
Initialising schema...
Seeding globals from roles.sql...
Applying migration 20261031000001_create_campus_cases.sql...
Applying migration 20261031000002_security_remediation.sql...
Applying migration 20261031000003_rate_limit_security_fix.sql...
Applying migration 20261031000004_core_platform_schema.sql...
Applying migration 20261101000001_notifications_schema.sql...
Applying migration 20261101000002_notifications_hardening.sql...
Applying migration 20261101000003_lawyer_connect_schema.sql...
Applying migration 20261101000004_messaging_and_meetings_schema.sql...
Applying migration 20261102000001_concurrent_meeting_exclusion.sql...
Applying migration 20261102000002_platform_admin_schema.sql...
Applying migration 20261102000003_verified_lawyers_and_privilege_hardening.sql...
Applying migration 20261103000001_legal_drafts_schema.sql...
Restarting containers...
Finished supabase db reset.
```

### 6.2 Test Battery Execution Summary

All test suites were executed against the rebuilt local database:

| Suite Name | Scope | Tests Run | Result | Duration |
| :--- | :--- | :---: | :---: | :---: |
| **`test_draft_user_identity_and_cross_user_isolation.py`** | Identity, spoofing defense, cross-user 403, triggers | 5 | **PASS** | 2.97s |
| **`test_browser_draft_autosave_lifecycle.py`** | 9-step client autosave lifecycle & 409 concurrency | 1 (9 steps) | **PASS** | 4.80s |
| **`test_product_workflow_closure.py`** | Draft DB storage, lawyer consent, RTI SLA, AI grounding | 8 | **PASS** | 6.40s |
| **`test_staging_and_product_improvements.py`** | Workstream B product improvements suite | 10 | **PASS** | 3.81s |
| **Full Regression Battery (Phases 1–8)** | 19 Automated Suites (`scratch/run_all_regressions.py`) | 19 suites | **PASS (19/19)** | 170.13s |
| **TypeScript Compile (`tsc --noEmit`)** | Static typing across full frontend code | Full build | **PASS (0 errors)** | 4.22s |

---

## 7. Remaining Limitations & Staging Gate

1. **Autosave Test Nature:** [`tests/test_browser_draft_autosave_lifecycle.py`](file:///c:/Users/Ishan/OneDrive/Desktop/micro%20project/tests/test_browser_draft_autosave_lifecycle.py) operates as an API-level integration test using FastAPI `TestClient`, not a real browser GUI test (no Playwright/Selenium). It validates the HTTP request/response sequences, optimistic concurrency (409), and database state.
2. **Staging Boundary Enforced:** Migration 12 has **not** been applied to remote staging (`chhbftpggjgcjqstgfqc`). Staging remains pristine on the 11 baseline migrations.

---

## 8. Final Verdict & Sign-Off

* **User Identity Mapping:** Verified (`sub` claim maps to `auth.users(id)`).
* **Cross-User Isolation:** Verified (Bob cannot read, update, or delete Alice's draft).
* **Service-Role Safety:** Verified (Application-level guards prevent unauthorized access).
* **Timestamp Defaults:** Corrected and verified (`DEFAULT now()`).
* **Local Database Replay:** Clean (12 of 12 migrations applied sequentially).
* **Automated Tests:** 19 of 19 test suites passed.
* **Ready for Staging Deployment:** Yes, pending user authorization.


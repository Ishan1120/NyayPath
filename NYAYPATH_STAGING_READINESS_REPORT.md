# NyayPath — Staging Readiness Report

**Document Reference:** `NYAYPATH-STAGING-READINESS-2026-11-03`  
**Evaluation Scope:** Read-Only Staging Database Preflight & Migration 12 Readiness  
**Target Project:** `Nyaypath-staging` (`chhbftpggjgcjqstgfqc`)  
**Assessment Mode:** Strictly Read-Only (`PGOPTIONS='-c default_transaction_read_only=on'` inside `BEGIN READ ONLY; ... ROLLBACK;`)  
**Production Isolation:** Absolute Zero Connections to Production (`dbwojjxfhnmmwrnqxyqj`)  

---

## 1. Verified Staging Project Identity

Direct PostgreSQL catalog inspection was performed using the local pooler connection in enforced read-only transaction mode. The target environment was verified programmatically:

| Identity Attribute | Expected Staging Value | Observed Staging Value | Verification Status |
| :--- | :--- | :--- | :--- |
| **Project Reference** | `chhbftpggjgcjqstgfqc` | `chhbftpggjgcjqstgfqc` | **MATCH (VERIFIED)** |
| **Pooler Hostname** | `aws-0-ap-south-1.pooler.supabase.com` | `aws-0-ap-south-1.pooler.supabase.com` | **MATCH (VERIFIED)** |
| **Pooler Port** | `5432` (Session Pooler) | `5432` (Session Pooler) | **MATCH (VERIFIED)** |
| **Database User** | `postgres.chhbftpggjgcjqstgfqc` | `postgres` (via pooler tenant routing) | **MATCH (VERIFIED)** |
| **Database Name** | `postgres` | `postgres` | **MATCH (VERIFIED)** |
| **Server Address** | `2406:da1a:b00:1300:8f4f:3e3c:6229:ef9` | AWS ap-south-1 (Mumbai) | **MATCH (VERIFIED)** |
| **Transaction Read-Only** | `on` | `on` | **ENFORCED (VERIFIED)** |
| **Production Ref Exclusion** | `dbwojjxfhnmmwrnqxyqj` absent | 0 references to `dbwojjxfhnmmwrnqxyqj` | **ISOLATED (VERIFIED)** |

---

## 2. Actual Migration History and Schema State

### 2.1 Applied Migration History

Inspection of `supabase_migrations.schema_migrations` inside a read-only transaction confirms that **all 11 canonical baseline migrations** are currently applied in the remote staging database:

```sql
SELECT version, name FROM supabase_migrations.schema_migrations ORDER BY version;
```

| # | Version | Migration Name | Applied In Staging |
| :---: | :--- | :--- | :---: |
| 1 | `20261031000001` | `create_campus_cases` | **YES** |
| 2 | `20261031000002` | `security_remediation` | **YES** |
| 3 | `20261031000003` | `rate_limit_security_fix` | **YES** |
| 4 | `20261031000004` | `core_platform_schema` | **YES** |
| 5 | `20261101000001` | `notifications_schema` | **YES** |
| 6 | `20261101000002` | `notifications_hardening` | **YES** |
| 7 | `20261101000003` | `lawyer_connect_schema` | **YES** |
| 8 | `20261101000004` | `messaging_and_meetings_schema` | **YES** |
| 9 | `20261102000001` | `concurrent_meeting_exclusion` | **YES** |
| 10 | `20261102000002` | `platform_admin_schema` | **YES** |
| 11 | `20261102000003` | `verified_lawyers_and_privilege_hardening` | **YES** |

### 2.2 Physical Schema Inventory

* **Public Base Tables:** Exactly 25 base tables exist in `public`, all with Row Level Security enabled (`rowsecurity = true`):
  `audit_actor_mappings`, `campus_cases`, `case_activity_log`, `case_committee_assignments`, `case_documents`, `cases`, `confidential_student_identities`, `consultation_meetings`, `consultation_requests`, `conversation_participants`, `conversations`, `institution_memberships`, `institutions`, `lawyer_availability`, `lawyer_case_access`, `lawyer_profiles`, `legal_precedents`, `message_attachments`, `messages`, `notifications`, `platform_admins`, `platform_audit_logs`, `profiles`, `rate_limit_attempts`, `saved_research`.
* **Public Views:** Exactly 1 view exists: `verified_lawyers` (owner: `postgres`).
* **RLS Policies:** Exactly 38 active RLS policies protect public tables.
* **Exclusion Constraints:** Meeting non-overlap exclusion constraint `exclude_overlapping_confirmed_meetings` on `consultation_meetings` is active using `gist` (`lawyer_user_id WITH =, tstzrange(scheduled_start, scheduled_end, '[)') WITH &&`) WHERE `status = 'CONFIRMED'`.

---

## 3. Storage Bucket State

Querying `storage.buckets` in read-only mode verified that the required storage buckets exist in staging:

| Bucket ID / Name | Public | Size Limit | Allowed MIME Types | Provisioned At (UTC) |
| :--- | :---: | :---: | :--- | :--- |
| **`case-documents`** | `false` (Private) | 10 MB (`10485760`) | `application/pdf`, `image/jpeg`, `image/png`, `image/webp` | `2026-11-03 07:29:46` |
| **`message-attachments`** | `false` (Private) | 10 MB (`10485760`) | `application/pdf`, `image/jpeg`, `image/png`, `image/webp` | `2026-11-03 07:29:46` |

Both buckets are private and enforce the 10 MB upload restriction and verified MIME types.

---

## 4. Migration 12 (`20261103000001_legal_drafts_schema.sql`) Impact Analysis

### 4.1 Schema Objects Created

1. **New Table:** `public.legal_drafts`
   * `id UUID PRIMARY KEY DEFAULT gen_random_uuid()`
   * `user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE`
   * `case_id VARCHAR(100)`
   * `title VARCHAR(255) NOT NULL DEFAULT 'Untitled Draft'`
   * `document_type VARCHAR(100) NOT NULL DEFAULT 'RTI'`
   * `facts TEXT`, `legal_provisions TEXT`, `requested_relief TEXT`
   * `draft_content TEXT NOT NULL`
   * `lawyer_brief TEXT`
   * `status VARCHAR(50) NOT NULL DEFAULT 'DRAFT' CHECK (status IN ('DRAFT', 'SAVED', 'FINALIZED', 'SHARED', 'ARCHIVED'))`
   * `version INTEGER NOT NULL DEFAULT 1 CHECK (version >= 1)`
   * `created_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc'::text, now())`
   * `updated_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc'::text, now())`
2. **Indexes Created:**
   * `idx_legal_drafts_user` ON `public.legal_drafts(user_id)`
   * `idx_legal_drafts_case` ON `public.legal_drafts(case_id)`
   * `idx_legal_drafts_status` ON `public.legal_drafts(status)`
3. **Columns Added to `public.consultation_requests`:**
   * `draft_id UUID REFERENCES public.legal_drafts(id) ON DELETE SET NULL`
   * `include_draft BOOLEAN NOT NULL DEFAULT false`
   * `consent_text TEXT`
   * `consent_timestamp TIMESTAMPTZ`
4. **Constraint Modification on `public.lawyer_case_access`:**
   * Expands check constraint `lawyer_case_access_shared_scope_check` from `('METADATA_ONLY', 'CASE_AND_DOCS')` to `('METADATA_ONLY', 'CASE_AND_DOCS', 'FULL')`.
5. **Triggers & Functions:**
   * Trigger `trg_legal_drafts_updated_at` invoking `private.set_updated_at_timestamp()`.

### 4.2 RLS Policies & Grants

* `ALTER TABLE public.legal_drafts ENABLE ROW LEVEL SECURITY;`
* `REVOKE ALL PRIVILEGES ON public.legal_drafts FROM PUBLIC, anon;`
* `GRANT SELECT, INSERT, UPDATE, DELETE ON public.legal_drafts TO authenticated;`
* `GRANT ALL ON public.legal_drafts TO service_role;`
* **Owner Isolation Policy:** `"Users can manage own legal drafts"` ON `public.legal_drafts` FOR ALL TO `authenticated` USING `(user_id = auth.uid())` WITH CHECK `(user_id = auth.uid())`.
* **Owner Isolation Assessment:** Enforced. Unauthenticated requests (`anon`) receive zero privileges; authenticated users are strictly isolated to rows where `user_id = auth.uid()`.

### 4.3 Safety, Dependencies & Rollback Analysis

* **Dependencies:** Depends on `auth.users`, `public.consultation_requests`, `public.lawyer_case_access`, and `private` schema. All four exist and are verified in staging.
* **Destructive Operations:** None. Uses `CREATE TABLE IF NOT EXISTS`, `CREATE INDEX IF NOT EXISTS`, and additive `DO $$ ... ALTER TABLE ADD COLUMN ... $$` blocks. No existing tables, columns, or data are dropped.
* **Pre-existence Check:** Verified that `legal_drafts` table does not exist in staging (0 rows) and `draft_id` / `include_draft` columns do not exist in `consultation_requests` (0 rows). Migration 12 has **not** been applied, even partially.

---

## 5. Autosave Test Classification

Inspection of [`tests/test_browser_draft_autosave_lifecycle.py`](file:///c:/Users/Ishan/OneDrive/Desktop/micro%20project/tests/test_browser_draft_autosave_lifecycle.py):

* **Test Framework:** Python `unittest` with FastAPI `TestClient(app)`.
* **Test Classification:** **API-Level Integration Simulation** (NOT real browser automation).
* **Specific Clarification:**
  * The test does **not** launch or automate a real web browser (no Playwright, Selenium, Puppeteer, or Chromium/WebKit engine is utilized).
  * It executes direct HTTP calls against the FastAPI application mounted on the local Supabase database.
  * It simulates client behavior (simulating browser page refresh via GET, simulating session logout via dropped authorization headers, simulating React state buffering during network timeout, and simulating competing tabs via concurrent HTTP PUT requests with outdated `expected_version`).
  * Concurrency control (HTTP 409 Conflict) and database versioning are verified, but this is an **API and integration test**, not a browser end-to-end (E2E) test.

---

## 6. Remaining Blockers

There are **zero technical blockers** preventing Migration 12 from being applied to staging:
* Schema dependencies are satisfied in staging.
* No data conflicts or breaking constraint alterations exist.
* All 18 local regression test suites pass (100%).
* Next.js production build compiles all 41 routes with zero TypeScript errors.

The only operational gate is **explicit authorization from the user** to execute the staging migration command.

---

## 7. Exact Staging-Only Migration Command

Based on the installed Supabase CLI version (`3.0.0`), the dry-run preflight was executed and verified:

```json
{"upToDate":false,"dryRun":true,"migrations":["20261103000001_legal_drafts_schema.sql"],"target":{"kind":"db-url","host":"aws-0-ap-south-1.pooler.supabase.com","port":5432}}
```

### Safety Dry-Run Command (Read-Only)
```powershell
npx supabase db push --dry-run --remote="$env:STAGING_DATABASE_URL" --skip-vault
```

### Execution Command (When Authorized)
```powershell
npx supabase db push --remote="$env:STAGING_DATABASE_URL" --skip-vault
```

> [!IMPORTANT]
> The command targets only `--remote="$env:STAGING_DATABASE_URL"`, which is verified to point to `Nyaypath-staging` (`chhbftpggjgcjqstgfqc`). The production project reference (`dbwojjxfhnmmwrnqxyqj`) is not linked and will not be touched.

---

## 8. Preflight Sign-Off

* **Staging Target:** `chhbftpggjgcjqstgfqc` (Verified)
* **Baseline Schema:** 11 migrations applied; 25 base tables; 1 view; 2 private storage buckets (Verified)
* **Migration 12 State:** Unapplied (Clean staging state verified)
* **Next Action:** Awaiting user authorization to apply Migration 12 to staging.


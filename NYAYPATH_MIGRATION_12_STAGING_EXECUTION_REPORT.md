# NyayPath — Migration 12 Staging Execution Report

**Date:** November 3, 2026  
**Target Environment:** Staging (`Nyaypath-staging`)  
**Target Project Reference:** `chhbftpggjgcjqstgfqc`  
**Host:** `aws-0-ap-south-1.pooler.supabase.com:5432`  
**Applied Migration:** `20261103000001_legal_drafts_schema.sql`  
**Production Reference (Untouched):** `dbwojjxfhnmmwrnqxyqj` (Zero Connections)  
**Overall Status:** APPLIED AND 100% VERIFIED  

---

## 1. Executive Summary

In accordance with explicit authorization from the user, Migration 12 (`20261103000001_legal_drafts_schema.sql`) was applied exclusively to the separate staging project `Nyaypath-staging` (`chhbftpggjgcjqstgfqc`).

The original production project (`dbwojjxfhnmmwrnqxyqj`) remained completely untouched with zero connections established. All operations were performed against the staging session pooler on port 5432. Post-migration database catalog inspection confirms the existence of the `legal_drafts` table, foreign key constraints referencing `auth.users(id)`, RLS enablement, owner policies, the `private.set_updated_at_timestamp()` trigger, and all supporting indexes. Live transactional tests confirmed creation, retrieval, timestamp advancement, and cross-user isolation.

---

## 2. Pre-Execution Verification & Dry-Run

### Connection Verification:
- **Variable:** `STAGING_DATABASE_URL`
- **Host:** `aws-0-ap-south-1.pooler.supabase.com:5432`
- **Database User:** `postgres.chhbftpggjgcjqstgfqc`
- **Target Project:** `chhbftpggjgcjqstgfqc` strictly verified.

### CLI Dry-Run:
- **Supabase CLI Version:** `v3.0.0`
- **Command:**
  ```bash
  npx supabase db push --dry-run --remote="$STAGING_DATABASE_URL" --skip-vault
  ```
- **Dry-Run Output:**
  ```text
  Target: custom Postgres (aws-0-ap-south-1.pooler.supabase.com:5432)
  DRY RUN: migrations will *not* be pushed to the database.
  Would push these migrations:
   • 20261103000001_legal_drafts_schema.sql
  {"upToDate":false,"dryRun":true,"migrations":["20261103000001_legal_drafts_schema.sql"],"seeds":[],"roles":[],"message":"Finished supabase db push."}
  ```
- **Confirmation:** Confirmed that ONLY Migration 12 was pending and no other migrations would be pushed.

---

## 3. Migration Execution

The migration push was executed using the non-interactive consent flag (`--yes`):

```bash
npx supabase db push --remote="$STAGING_DATABASE_URL" --skip-vault --yes
```

### Execution Log:
```text
Target: custom Postgres (aws-0-ap-south-1.pooler.supabase.com:5432)
Confirmed by --yes: Apply 1 migration on custom Postgres (aws-0-ap-south-1.pooler.supabase.com:5432)
Applying migration 20261103000001_legal_drafts_schema.sql...
{"upToDate":false,"dryRun":false,"migrations":["20261103000001_legal_drafts_schema.sql"],"seeds":[],"roles":[],"message":"Finished supabase db push."}
```
**Exit Code:** `0` (Success).

Subsequent dry-run confirmed:
```json
{"upToDate":true,"dryRun":true,"migrations":[],"seeds":[],"roles":[],"message":"Remote database is up to date."}
```

---

## 4. Remote Catalog Verification on Staging

Direct query of the remote staging PostgreSQL catalog verified:

### Schema Objects Created:
1. **Table:** `public.legal_drafts` (14 columns)
   - `id`: `uuid DEFAULT gen_random_uuid() PRIMARY KEY`
   - `user_id`: `uuid NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE`
   - `case_id`: `varchar NULL REFERENCES public.cases(case_id)`
   - `title`: `varchar NOT NULL DEFAULT 'Untitled Draft'`
   - `document_type`: `varchar NOT NULL DEFAULT 'RTI'`
   - `facts`: `text NULL`
   - `legal_provisions`: `text NULL`
   - `requested_relief`: `text NULL`
   - `draft_content`: `text NOT NULL`
   - `lawyer_brief`: `text NULL`
   - `status`: `varchar NOT NULL DEFAULT 'DRAFT'` (CHECK in `['DRAFT', 'SAVED', 'FINALIZED', 'SHARED', 'ARCHIVED']`)
   - `version`: `integer NOT NULL DEFAULT 1` (CHECK `version >= 1`)
   - `created_at`: `timestamptz NOT NULL DEFAULT now()`
   - `updated_at`: `timestamptz NOT NULL DEFAULT now()`

2. **Row-Level Security (RLS):**
   - `relrowsecurity`: `true`
   - Policy: `Users can manage own legal drafts`
   - Permissive: `true`
   - Command: `ALL (*)`
   - Qual / Using: `(user_id = auth.uid())`
   - With Check: `(user_id = auth.uid())`

3. **Triggers:**
   - `trg_legal_drafts_updated_at`: `BEFORE UPDATE ON public.legal_drafts FOR EACH ROW EXECUTE FUNCTION private.set_updated_at_timestamp()`

4. **Indexes:**
   - `legal_drafts_pkey` (UNIQUE btree on `id`)
   - `idx_legal_drafts_user` (btree on `user_id`)
   - `idx_legal_drafts_case` (btree on `case_id`)
   - `idx_legal_drafts_status` (btree on `status`)

---

## 5. Live Staging Test Results

Executed end-to-end tests against the live remote staging database:

| Test Case | Operation | Observed Result | Status |
|---|---|---|---|
| **Test 1: User Insertion** | Create staging user in `auth.users` | Inserted test user `f1111111...` | **PASS** |
| **Test 2: Draft Insertion** | Insert draft under `auth.uid() = f1111111...` | Staging draft persisted with ID `d1111111...` | **PASS** |
| **Test 3: Draft Retrieval** | Query draft under Alice's authenticated session | Retrieved draft with exact title, content, and version 1 | **PASS** |
| **Test 4: Cross-User Isolation** | Query Alice's draft as User Bob (`f2222222...`) | Returned 0 rows (`bob_visible_drafts_count = 0`) | **PASS** |
| **Test 5: Cross-User Tamper** | Bob attempts `UPDATE` and `DELETE` on Alice's draft | `UPDATE 0`, `DELETE 0` (0 rows affected) | **PASS** |
| **Test 6: Timestamp Trigger** | Update draft in new transaction | `created_at`: `10:42:33`, `updated_at`: `10:42:35` (`updated_at > created_at`: `true`) | **PASS** |
| **Test 7: Test Cleanup** | Delete test drafts and test auth users | Deleted cleanly; zero test artifacts left in database | **PASS** |

---

## 6. Conclusion

Migration 12 is fully applied and operational on `Nyaypath-staging` (`chhbftpggjgcjqstgfqc`). The staging database is now at 12 canonical migrations, fully prepared to support persistent legal drafts, autosave, and lawyer consultations during the college expo demo.

Zero modifications were made to production (`dbwojjxfhnmmwrnqxyqj`).


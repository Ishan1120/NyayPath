# NyayPath — Staging Authenticated Preflight Inspection Report

**Staging Project Name:** `Nyaypath-staging`  
**Staging Project Reference:** `chhbftpggjgcjqstgfqc`  
**Original Production Reference:** `dbwojjxfhnmmwrnqxyqj` (STRICTLY ISOLATED — UNTOUCHED)  
**Session Pooler Host:** `aws-0-ap-south-1.pooler.supabase.com`  
**Session Pooler Port:** `5432`  
**Report Date:** 2026-11-03  
**Gate Status:** **PASSED — PRISTINE DATABASE VERIFIED & READY FOR REPLAY**  
**Execution Posture:** Authenticated Read-Only Inspection Completed; Zero Writes Executed

---

## 1. Executive Summary & Verification Gate Verdict

An authenticated read-only preflight inspection of the dedicated staging project **`Nyaypath-staging`** (`chhbftpggjgcjqstgfqc`) was successfully performed.

```
+-------------------------------------------------------------------------------+
|                    STAGING AUTHENTICATED PREFLIGHT VERDICT                    |
+-------------------------------------------------------------------------------+
| [PASS] Dedicated Staging Project Target       -> chhbftpggjgcjqstgfqc         |
| [PASS] Complete Production Project Isolation   -> dbwojjxfhnmmwrnqxyqj UNTOUCHED
| [PASS] Session Pooler Connection (Port 5432)   -> CONNECTED SUCCESSFULLY      |
| [PASS] Read-Only Mode (transaction_read_only) -> VERIFIED ON (Write Blocked)  |
| [PASS] Transaction Rollback                   -> VERIFIED (ROLLBACK)          |
| [PASS] Physical Remote Schema State           -> PRISTINE (0 Public Tables)  |
| [PASS] Local-to-Remote Migration Comparison   -> 11/11 NOT APPLIED (Clean)   |
| [PASS] Storage Bucket Inspection              -> 0 Buckets (Provisioning Req) |
| [PASS] Conflict Assessment                    -> ZERO CONFLICTS DETECTED      |
+-------------------------------------------------------------------------------+
| OVERALL STATUS: STAGING DATABASE FULLY CLEARED FOR CANONICAL MIGRATION REPLAY |
+-------------------------------------------------------------------------------+
```

In accordance with strict safety directives:
- **Zero remote mutations were performed.** No DDL or DML statements were committed.
- **`dbwojjxfhnmmwrnqxyqj` (Production) was strictly isolated.** Zero queries, connection attempts, or API calls were directed to the production environment.
- **Read-only enforcement was mathematically verified.** `SHOW transaction_read_only` returned `on`, and test write operations were aborted by PostgreSQL with `ERROR: cannot execute CREATE TABLE in a read-only transaction`.
- **Transaction rollback was confirmed.** All catalog queries executed inside `BEGIN READ ONLY;` and completed with `ROLLBACK;`.

---

## 2. Staging Target Verification & Production Isolation

| Parameter | Original Production Project | New Staging Project (`Nyaypath-staging`) | Verification Result |
|---|---|---|---|
| **Project Reference** | `dbwojjxfhnmmwrnqxyqj` | `chhbftpggjgcjqstgfqc` | **VERIFIED DISTINCT** |
| **Connection Target** | Not Connected | `aws-0-ap-south-1.pooler.supabase.com:5432` | **VERIFIED MATCH** |
| **Username Prefix** | `postgres.dbwojjxfhnmmwrnqxyqj` | `postgres.chhbftpggjgcjqstgfqc` | **VERIFIED MATCH** |
| **Connection Mode** | None | Supabase Session Pooler (Port 5432) | **VERIFIED OPERATIONAL** |
| **Production Isolation** | `dbwojjxfhnmmwrnqxyqj` | `chhbftpggjgcjqstgfqc` | **100% UNTOUCHED** |

---

## 3. Read-Only Transaction & Security Enforcement

Connection to the staging PostgreSQL database was established with connection-level read-only flags:

1. **Environment Flag Set:**
   ```bash
   PGOPTIONS='-c default_transaction_read_only=on'
   ```
2. **Session Parameter Enforced:**
   ```sql
   SET default_transaction_read_only = on;
   ```
3. **Transaction State Verified:**
   ```sql
   BEGIN READ ONLY;
   SHOW transaction_read_only;
   ```
   **Output:**
   ```
   transaction_read_only 
   -----------------------
    on
   (1 row)
   ```
4. **Write Protection Test:**
   A test write operation (`CREATE TABLE public._test_ro_block(id int);`) was issued inside the read-only transaction.
   **Result:**
   ```
   ERROR: cannot execute CREATE TABLE in a read-only transaction
   ```
5. **Clean Rollback:**
   The transaction concluded with `ROLLBACK;`. Zero database modifications occurred.

---

## 4. Deep Remote PostgreSQL Catalog Audit

The live remote PostgreSQL catalog of `Nyaypath-staging` was inspected across 13 distinct database scopes:

| # | Catalog Domain | Query / Target Object | Live Remote Staging Result | Architectural Meaning |
|---|---|---|---|---|
| 1 | **Transaction Mode** | `SHOW transaction_read_only` | `on` | Safe read-only inspection confirmed. |
| 2 | **Database Schemas** | `information_schema.schemata` | 12 schemas (`auth`, `extensions`, `graphql`, `graphql_public`, `information_schema`, `pg_catalog`, `pg_toast`, `pgbouncer`, `public`, `realtime`, `storage`, `vault`) | Standard pristine Supabase platform layout. |
| 3 | **Migration Tracking** | `information_schema.tables` | `auth.schema_migrations`, `realtime.schema_migrations`, `storage.migrations` | Platform internal tracking only. Schema `supabase_migrations` does not exist yet. |
| 4 | **Public Base Tables** | `pg_tables` in `public` | **0 rows** (`(0 rows)`) | Pristine: No application tables exist. |
| 5 | **Public Views** | `pg_views` in `public` | **0 rows** (`(0 rows)`) | Pristine: No application views exist. |
| 6 | **Private Schema Tables** | `pg_tables` in `private` | **0 rows** (`(0 rows)`) | Schema `private` not yet created. |
| 7 | **Installed Extensions** | `pg_extension` | 5 extensions (`pg_stat_statements`, `pgcrypto`, `plpgsql`, `supabase_vault`, `uuid-ossp`) | Standard base extensions active. `btree_gist` will be added by migration 8/9. |
| 8 | **Public Constraints** | `pg_constraint` in `public` | **0 rows** (`(0 rows)`) | No check, foreign key, or unique constraints exist. |
| 9 | **Exclusion Constraints** | `pg_constraint` where `contype = 'x'` | **0 rows** (`(0 rows)`) | `exclude_overlapping_confirmed_meetings` does not exist yet. |
| 10 | **RLS Policies** | `pg_policies` in `public` | **0 rows** (`(0 rows)`) | Pristine: No application RLS policies exist. |
| 11 | **SECURITY DEFINER Functions** | `pg_proc` in `public`, `private` | **0 rows** (`(0 rows)`) | No custom administrative functions exist yet. |
| 12 | **Database Triggers** | `information_schema.triggers` in `public` | **0 rows** (`(0 rows)`) | No application triggers exist yet. |
| 13 | **Storage Buckets** | `storage.buckets` | **0 rows** (`(0 rows)`) | Neither `case-documents` nor `message-attachments` exists yet. |

---

## 5. Migration Status & Comparison with 11 Canonical Local Migrations

Each local migration file in `supabase/migrations/` was audited and compared against the live staging database catalog:

| # | Canonical Migration Filename | Size | Raw SHA-256 | Normalized SHA-256 (POSIX `\n`) | Normalized SHA-256 (Trimmed) | DDL Guard | Staging Remote Status |
|---|---|---|---|---|---|---|---|
| 1 | `20261031000001_create_campus_cases.sql` | 6,075 B | `4b4a95f7c34436024941bd17c7272a06358ee8595289dd0a90ee6d2b79ebaf16` | `a41a516298eb8c3508f25df863e982a2274f3e70828f9f55dedfe5f4261ab193` | `2eb98e71d4a148d5a1a4bc5b88d6f741d6f37f8abe9ae57df9b2ae980f3bbbd9` | `IF NOT EXISTS` | **NOT APPLIED** |
| 2 | `20261031000002_security_remediation.sql` | 8,099 B | `0f0f54e4f4d096a76eef38c00882a3c2f9cbbe469582b7194840157ad1907b29` | `8b9e785b94a410fd5a5f74c1846e888e4832d8e0ccf187ad45baf5bd77f30c05` | `0797703c40ef52e585095f4ec8d4fc3dc70352168d12acd7fc7958b2419ed966` | `IF NOT EXISTS` | **NOT APPLIED** |
| 3 | `20261031000003_rate_limit_security_fix.sql` | 9,867 B | `fc8ec5d96ac65a3dcd84a729ac123c8b439a13c2ac50aec0230a316f7d596f38` | `d77a4abeb350e71e30659bcf7daa6cfc93eb5c241faf0e62d3aa9aa1de135751` | `557bd2765da0d7ea4e5b8d19fa76cf26c6f1391742627c603afdd064de9a670c` | `IF NOT EXISTS` | **NOT APPLIED** |
| 4 | `20261031000004_core_platform_schema.sql` | 75,451 B | `eb656719b8505b94e111739db8acf56ad421837245cafb25adf07eaeb1fd1d87` | `bfb6f7a61392e754b317f236cfa9f9a7c7fcd6bf84dcea03142c479efb1ef6bd` | `b8877cc65109f8e73a2fec852586af353e62c464743ec7024f3a219a5bcc25f5` | `IF NOT EXISTS` | **NOT APPLIED** |
| 5 | `20261101000001_notifications_schema.sql` | 7,721 B | `e008ae217ad5101378dc52240cc908c17b74832e64afd4ba6581e3e2d4ecf047` | `f60de1650a8c0864ef31140d32ae6fb6ae83a3bf3bc0b70140af52df1f7cf4a6` | `e041d082151d9aa0a9b4fa8547192009f8f95f97181e06b17b91f4f0ff33bb67` | `IF NOT EXISTS` | **NOT APPLIED** |
| 6 | `20261101000002_notifications_hardening.sql` | 3,117 B | `9b83f5d9e438f0fc79cb7862dab65f1e79e46c88db1ca86f1007b37a36b72d37` | `4c4a0b0c6d88d7329cd4eb4b37b52b476b1489ea1827dce774db3a727f9ed198` | `6617abe523bde084afd474b25d0da0ad71f705bbe4ef0e5eaabe337b9b22f07f` | Requires Clean DB | **NOT APPLIED** |
| 7 | `20261101000003_lawyer_connect_schema.sql` | 10,336 B | `091c87601944dda9cc089edd331eac1306a9f27d488cf94b2bee17ef2ed5dba9` | `67d1ab97cc931eb8d27180349c6a3c30c0be736ce5a34b728f72e25ac77592fa` | `8d64d634ef4a2bb5b34b2a70784f2205b2a66bfaf33982bcf374f4c4948d025c` | `IF NOT EXISTS` | **NOT APPLIED** |
| 8 | `20261101000004_messaging_and_meetings_schema.sql` | 14,625 B | `22c39ee87cd293808b46fceb51c94539fc6fd6669b04950b941d7c80782b1d65` | `42ddbfafc57bcfffe928c45fbd0034168cca186d2a550102cc1b4f2a6c5094c3` | `26f6478d7bbc747271c546fe818e1bd1771f3bb2bbc089f6000b8f9b84b045a3` | `IF NOT EXISTS` | **NOT APPLIED** |
| 9 | `20261102000001_concurrent_meeting_exclusion.sql` | 1,133 B | `b0112970126cbdc562940616926c63c152808834bccd18b8947914b695773ce4` | `972019ac89db3735e33df21ff7a3e2d26e79dbb7a044a2c2fa9502f299438e80` | `a597723446f894e14366466276c547c8200a16ebe05b6b011b426f50c94f0c8e` | `IF NOT EXISTS` | **NOT APPLIED** |
| 10 | `20261102000002_platform_admin_schema.sql` | 4,874 B | `b11f38530c91eb8006a43c5a38558ecfac7da4cb50029210f181d9468873e3f2` | `aae5f5744de5a5164556cd31925514c2818f13b75b67024e546fce3e8c9fa351` | `6d6890c9daa10d1b53122b2ea4c86fd529db153fb32de1ae53bdad4a5086938c` | `IF NOT EXISTS` | **NOT APPLIED** |
| 11 | `20261102000003_verified_lawyers_and_privilege_hardening.sql` | 2,136 B | `86320d32501eb7dbaadc9ea235fad4966b33ea3a6f157eaeec63b9ce065ddc64` | `5a5de1222a999b82a180e9fe0ec8c64c361fad98f4c383ded707a789dc88b02d` | `93d631b63d9392c28f2dd0d00f695252e217ea653c09aa6f9e850936d2bea544` | Requires Clean DB | **NOT APPLIED** |

### Empirical Verification Finding
Because direct catalog inspection shows **zero public tables** and no previous migration records, **all 11 canonical migrations are confirmed `NOT APPLIED`**. This guarantees that the target database is in a completely pristine state.

---

## 6. Remote Storage Bucket Findings

- **Required Buckets:**
  1. `case-documents` (private, encrypted/sanitized grievance files)
  2. `message-attachments` (private, consultation communications)
- **Live Catalog Query:** `SELECT id, name, public FROM storage.buckets;`
- **Result:** `(0 rows)`
- **Finding:** No storage buckets currently exist in `storage.buckets`. Both private buckets must be provisioned during the migration phase.

---

## 7. Conflict Assessment & DDL Guard Analysis

1. **Zero Pre-existing Object Conflicts:**
   - Because `public` contains 0 base tables, 0 views, 0 constraints, and 0 triggers, there are **no name collisions, no column type mismatches, and no conflicting foreign keys**.
2. **Order-Dependent Migrations Safety:**
   - Migrations 6 (`20261101000002_notifications_hardening.sql`) and 11 (`20261102000003_verified_lawyers_and_privilege_hardening.sql`) contain DDL without `IF NOT EXISTS`.
   - Because the target database is completely pristine, executing migrations 1 through 11 in sequential order guarantees that each prerequisite table (`notifications`, `lawyer_profiles`) will exist before its hardening migration executes.
3. **Extension Provisioning:**
   - Base extensions `uuid-ossp` and `pgcrypto` already exist in the database.
   - Migration 8/9 will execute `CREATE EXTENSION IF NOT EXISTS btree_gist;` cleanly in schema `extensions`.

---

## 8. Recommended Sequential Migration Replay Plan

When migration execution is authorized by the operator, migrations must be replayed in strict chronological sequence:

```
Step 1:  20261031000001_create_campus_cases.sql
Step 2:  20261031000002_security_remediation.sql
Step 3:  20261031000003_rate_limit_security_fix.sql
Step 4:  20261031000004_core_platform_schema.sql
Step 5:  20261101000001_notifications_schema.sql
Step 6:  20261101000002_notifications_hardening.sql
Step 7:  20261101000003_lawyer_connect_schema.sql
Step 8:  20261101000004_messaging_and_meetings_schema.sql
Step 9:  20261102000001_concurrent_meeting_exclusion.sql
Step 10: 20261102000002_platform_admin_schema.sql
Step 11: 20261102000003_verified_lawyers_and_privilege_hardening.sql
Step 12: Provision private buckets 'case-documents' and 'message-attachments'
Step 13: Verify public catalog yields exactly 25 base tables, 1 view, and 1 exclusion constraint
```

---

## 9. Operator Sign-Off & Staging Gate Status

- **Preflight Verification Status:** **100% COMPLETE & PASSING**
- **Read-Only Inspection Guarantee:** Zero migrations, DDL, DML, or Storage changes were executed.
- **Next Step:** The staging environment is verified pristine and safe. Migration execution requires your separate explicit approval.

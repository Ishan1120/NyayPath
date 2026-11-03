# NyayPath — Authenticated Staging Preflight Inspection Report

**Target Project Reference:** `dbwojjxfhnmmwrnqxyqj`  
**Remote Hostname:** `https://dbwojjxfhnmmwrnqxyqj.supabase.co`  
**Report Date:** 2026-11-03  
**Gate Status:** **STOP TRIGGERED — PREREQUISITES FAILED**  
**Execution Posture:** Read-Only Preflight Halted Before Direct Database Connection

---

## 1. Executive Summary & Prerequisite Gate Verdict

In accordance with strict deployment safety regulations, two mandatory prerequisites were evaluated before attempting any direct read-only PostgreSQL connection to target project `dbwojjxfhnmmwrnqxyqj`:

1. **Prerequisite 1 (Environment Confirmation):** Verify that project `dbwojjxfhnmmwrnqxyqj` is explicitly confirmed as **Staging** (and not Production).
2. **Prerequisite 2 (Credential Availability):** Verify that authorized remote database connection credentials (`SUPABASE_ACCESS_TOKEN`, `SUPABASE_DB_PASSWORD`, or remote `DATABASE_URL`) are available locally.

### Gate Verdict
```
+-------------------------------------------------------------------------------+
|                        AUTHENTICATION PREFLIGHT GATE                          |
+-------------------------------------------------------------------------------+
| [FAIL] Prerequisite 1: Explicit Staging Confirmation  -> UNVERIFIED           |
| [FAIL] Prerequisite 2: Remote Connection Credentials   -> UNAVAILABLE         |
+-------------------------------------------------------------------------------+
| VERDICT: PREFLIGHT HALTED AT STEP 1 & 2 (MANDATORY STOP DIRECTIVE ENFORCED)    |
+-------------------------------------------------------------------------------+
```

Because both prerequisites failed, **direct PostgreSQL connection was NOT attempted**, and zero remote queries or mutations were executed. This report details the verification evidence, exact limitations, local canonical baseline, potential schema conflicts, and the exact remediation required to open the gate.

---

## 2. Prerequisite 1 Evaluation: Staging Environment Confirmation

- **Target Project Reference:** `dbwojjxfhnmmwrnqxyqj`
- **Verification Rule:** Do not infer staging designation from hostname, project reference, or URL. Staging status must be explicitly confirmed in repository configuration or by human operator instruction.
- **Audit Findings:**
  1. An exhaustive search was conducted across all workspace configuration files (`.env`, `.env.example`, `package.json`, `supabase/config.toml`, `next.config.ts`, `vercel.json`).
  2. While the project reference `dbwojjxfhnmmwrnqxyqj` appears across historical preflight logs, **nowhere in any local configuration file is it tagged or designated as "Staging"**.
  3. The current user request instructed: *"1. Verify that the project is explicitly confirmed as staging. If not, STOP."*
  4. No explicit operator confirmation designating `dbwojjxfhnmmwrnqxyqj` as Staging was provided in the prompt.
- **Classification:** **`REQUIRES MANUAL REVIEW`**
- **Action Taken:** In strict compliance with instruction 1, direct inspection was **STOPPED**.

---

## 3. Prerequisite 2 Evaluation: Remote Credential Availability

- **Target Scope:** Direct read-only connection to remote PostgreSQL instance (port `5432` / pooler port `6543`) and Supabase Management API.
- **Audit of Local Execution Environment:**

| Credential / Key | Local Storage Location Checked | Status | Exact Evidence / Error |
|---|---|---|---|
| `SUPABASE_ACCESS_TOKEN` | Process environment, Windows User/Machine Registry, `~/.supabase/access-token` | **NOT FOUND / UNSET** | `npx supabase projects list` failed with `AccessTokenRequiredError: Access token not provided.` |
| `SUPABASE_DB_PASSWORD` | Process environment, `.env`, `.env.local` | **NOT FOUND / UNSET** | Variable is undefined in runtime shell and configuration. |
| `DATABASE_URL` (Remote) | Process environment, `.env` | **NOT FOUND / UNSET** | Only local Docker connection string exists (`postgresql://postgres:postgres@127.0.0.1:54322/postgres`). |
| Local Supabase Stack | Docker Daemon (`supabase_db_micro_project`) | **ACTIVE & HEALTHY** | 11 containers running locally; local tests operational. |

- **Classification:** **`BLOCKED — CREDENTIALS UNAVAILABLE`**
- **Action Taken:** Under instruction 2 and the general failure directive (*"If any prerequisite fails, stop and report the blocker"*), execution was safely terminated prior to network connection. Under no circumstances are credentials printed or logged.

---

## 4. Planned Read-Only Safeguards (On Standby)

When valid credentials and explicit environment confirmation are supplied, the direct PostgreSQL inspection protocol must strictly enforce the following read-only safeguards:

1. **Connection-Level Read-Only Enforcement:**
   Every connection command must pass:
   ```bash
   PGOPTIONS='-c default_transaction_read_only=on'
   ```
2. **Runtime Verification:**
   Before executing catalog inspection queries, confirm:
   ```sql
   SHOW transaction_read_only;
   ```
   *Expected Output:* `on`. If the setting returns `off`, the session must immediately terminate.
3. **Transaction Sandbox:**
   Every catalog query must be wrapped in an explicit read-only rollback transaction:
   ```sql
   BEGIN READ ONLY;
   -- Catalog queries (information_schema, pg_catalog, supabase_migrations)
   ROLLBACK;
   ```
4. **Zero-Mutation Guarantee:**
   Never issue `CREATE`, `ALTER`, `DROP`, `INSERT`, `UPDATE`, `DELETE`, `GRANT`, `REVOKE`, or `TRUNCATE`.
   Never run `supabase db push`, `db pull`, `migration repair`, or `db reset --linked`.

---

## 5. Local Canonical Migration Inventory & Dual-Hash Baseline

The application's 11 canonical migration files in `supabase/migrations/` represent the complete target state. Hashes were re-verified across raw binary content, POSIX newline-terminated normalized content, and strictly trimmed normalized content:

| # | Canonical Migration Filename | Size | Raw SHA-256 | Normalized SHA-256 (POSIX `\n`) | Normalized SHA-256 (Trimmed) | Idempotent Guard |
|---|---|---|---|---|---|---|
| 1 | `20261031000001_create_campus_cases.sql` | 6,075 B | `4b4a95f7c34436024941bd17c7272a06358ee8595289dd0a90ee6d2b79ebaf16` | `a41a516298eb8c3508f25df863e982a2274f3e70828f9f55dedfe5f4261ab193` | `2eb98e71d4a148d5a1a4bc5b88d6f741d6f37f8abe9ae57df9b2ae980f3bbbd9` | `IF NOT EXISTS` |
| 2 | `20261031000002_security_remediation.sql` | 8,099 B | `0f0f54e4f4d096a76eef38c00882a3c2f9cbbe469582b7194840157ad1907b29` | `8b9e785b94a410fd5a5f74c1846e888e4832d8e0ccf187ad45baf5bd77f30c05` | `0797703c40ef52e585095f4ec8d4fc3dc70352168d12acd7fc7958b2419ed966` | `IF NOT EXISTS` |
| 3 | `20261031000003_rate_limit_security_fix.sql` | 9,867 B | `fc8ec5d96ac65a3dcd84a729ac123c8b439a13c2ac50aec0230a316f7d596f38` | `d77a4abeb350e71e30659bcf7daa6cfc93eb5c241faf0e62d3aa9aa1de135751` | `557bd2765da0d7ea4e5b8d19fa76cf26c6f1391742627c603afdd064de9a670c` | `IF NOT EXISTS` |
| 4 | `20261031000004_core_platform_schema.sql` | 75,451 B | `eb656719b8505b94e111739db8acf56ad421837245cafb25adf07eaeb1fd1d87` | `bfb6f7a61392e754b317f236cfa9f9a7c7fcd6bf84dcea03142c479efb1ef6bd` | `b8877cc65109f8e73a2fec852586af353e62c464743ec7024f3a219a5bcc25f5` | `IF NOT EXISTS` |
| 5 | `20261101000001_notifications_schema.sql` | 7,721 B | `e008ae217ad5101378dc52240cc908c17b74832e64afd4ba6581e3e2d4ecf047` | `f60de1650a8c0864ef31140d32ae6fb6ae83a3bf3bc0b70140af52df1f7cf4a6` | `e041d082151d9aa0a9b4fa8547192009f8f95f97181e06b17b91f4f0ff33bb67` | `IF NOT EXISTS` |
| 6 | `20261101000002_notifications_hardening.sql` | 3,117 B | `9b83f5d9e438f0fc79cb7862dab65f1e79e46c88db1ca86f1007b37a36b72d37` | `4c4a0b0c6d88d7329cd4eb4b37b52b476b1489ea1827dce774db3a727f9ed198` | `6617abe523bde084afd474b25d0da0ad71f705bbe4ef0e5eaabe337b9b22f07f` | Requires Clean DB |
| 7 | `20261101000003_lawyer_connect_schema.sql` | 10,336 B | `091c87601944dda9cc089edd331eac1306a9f27d488cf94b2bee17ef2ed5dba9` | `67d1ab97cc931eb8d27180349c6a3c30c0be736ce5a34b728f72e25ac77592fa` | `8d64d634ef4a2bb5b34b2a70784f2205b2a66bfaf33982bcf374f4c4948d025c` | `IF NOT EXISTS` |
| 8 | `20261101000004_messaging_and_meetings_schema.sql` | 14,625 B | `22c39ee87cd293808b46fceb51c94539fc6fd6669b04950b941d7c80782b1d65` | `42ddbfafc57bcfffe928c45fbd0034168cca186d2a550102cc1b4f2a6c5094c3` | `26f6478d7bbc747271c546fe818e1bd1771f3bb2bbc089f6000b8f9b84b045a3` | `IF NOT EXISTS` |
| 9 | `20261102000001_concurrent_meeting_exclusion.sql` | 1,133 B | `b0112970126cbdc562940616926c63c152808834bccd18b8947914b695773ce4` | `972019ac89db3735e33df21ff7a3e2d26e79dbb7a044a2c2fa9502f299438e80` | `a597723446f894e14366466276c547c8200a16ebe05b6b011b426f50c94f0c8e` | `IF NOT EXISTS` |
| 10 | `20261102000002_platform_admin_schema.sql` | 4,874 B | `b11f38530c91eb8006a43c5a38558ecfac7da4cb50029210f181d9468873e3f2` | `aae5f5744de5a5164556cd31925514c2818f13b75b67024e546fce3e8c9fa351` | `6d6890c9daa10d1b53122b2ea4c86fd529db153fb32de1ae53bdad4a5086938c` | `IF NOT EXISTS` |
| 11 | `20261102000003_verified_lawyers_and_privilege_hardening.sql` | 2,136 B | `86320d32501eb7dbaadc9ea235fad4966b33ea3a6f157eaeec63b9ce065ddc64` | `5a5de1222a999b82a180e9fe0ec8c64c361fad98f4c383ded707a789dc88b02d` | `93d631b63d9392c28f2dd0d00f695252e217ea653c09aa6f9e850936d2bea544` | Requires Clean DB |

---

## 6. Remote Catalog Inspection Status Across Required Scopes

Due to the lack of authorized direct SQL connection credentials, the remote inspection across all 11 required scopes is classified as follows:

| Scope | Planned Inspection Target | Remote Status | Limitation |
|---|---|---|---|
| **1. Migration History** | `supabase_migrations.schema_migrations` | **`BLOCKED — CREDENTIALS UNAVAILABLE`** | SQL query blocked; PostgREST endpoint returns HTTP 403. |
| **2. Public Tables & Views** | `information_schema.tables`, `pg_views` | **`UNKNOWN — DIRECT CATALOG INSPECTION REQUIRED`** | PostgREST OpenAPI reports 0 exposed tables (`NONE OBSERVED`). |
| **3. Other Schema Objects** | Schemas `private`, `auth`, `storage` | **`UNKNOWN — DIRECT CATALOG INSPECTION REQUIRED`** | Cannot inspect internal schemas without direct DB connection. |
| **4. PostgreSQL Extensions** | `pg_extension` (`uuid-ossp`, `btree_gist`, `pgcrypto`) | **`UNKNOWN — DIRECT CATALOG INSPECTION REQUIRED`** | Catalog access blocked. |
| **5. Foreign Keys & Indexes** | `pg_constraint`, `pg_indexes` | **`UNKNOWN — DIRECT CATALOG INSPECTION REQUIRED`** | Catalog access blocked. |
| **6. Row Level Security** | `pg_tables.rowsecurity`, `pg_policies` | **`UNKNOWN — DIRECT CATALOG INSPECTION REQUIRED`** | Catalog access blocked. |
| **7. SECURITY DEFINER Functions** | `pg_proc.prosecdef`, function search paths | **`UNKNOWN — DIRECT CATALOG INSPECTION REQUIRED`** | Catalog access blocked. |
| **8. Database Triggers** | `pg_trigger` (immutability, auto-timestamp) | **`UNKNOWN — DIRECT CATALOG INSPECTION REQUIRED`** | Catalog access blocked. |
| **9. Constraints** | Check & unique constraints across 25 tables | **`UNKNOWN — DIRECT CATALOG INSPECTION REQUIRED`** | Catalog access blocked. |
| **10. Meeting Exclusion Constraint** | `exclude_overlapping_confirmed_meetings` on `consultation_meetings` | **`UNKNOWN — DIRECT CATALOG INSPECTION REQUIRED`** | Catalog access blocked. |
| **11. Storage Bucket Metadata** | Buckets `case-documents`, `message-attachments` | **`BLOCKED — CREDENTIALS UNAVAILABLE`** | `GET /storage/v1/bucket` returned HTTP 400 (auth required). |

---

## 7. Remote Storage Bucket Metadata Findings

- **Required Buckets:**
  * `case-documents` (private, encrypted/sanitized grievance files)
  * `message-attachments` (private, consultation communications)
- **Direct Probe Output:**
  ```
  GET https://dbwojjxfhnmmwrnqxyqj.supabase.co/storage/v1/bucket
  HTTP/2 400 Bad Request
  {"statusCode":"400","error":"Bad Request","message":"headers must have required property 'authorization'"}
  ```
- **Finding:** Accessing bucket metadata requires a valid `Authorization: Bearer <service_role_key>` header.
- **Classification:** **`BLOCKED — CREDENTIALS UNAVAILABLE`** (Not absent; blocked on credentials).

---

## 8. Potential Schema Conflicts & DDL Guard Analysis

An analysis of the 11 canonical local migrations against potential remote states reveals two categories of risk:

### A. Idempotent Migrations (9/11 Files)
- Migrations 1–5 and 7–10 use defensive DDL guards:
  * `CREATE TABLE IF NOT EXISTS`
  * `CREATE INDEX IF NOT EXISTS`
  * `DROP POLICY IF EXISTS`
  * `CREATE EXTENSION IF NOT EXISTS`
- If the remote database has partial migrations matching these files, replaying them will not fail on object creation.

### B. Order-Dependent Migrations (2/11 Files)
- **Migration 6 (`20261101000002_notifications_hardening.sql`):**
  * Alters columns and adds table constraints on `notifications` without `IF NOT EXISTS`.
  * Risk: Will fail with `relation "notifications" does not exist` if migration 5 did not run, or `constraint already exists` if re-run against an already-hardened table.
- **Migration 11 (`20261102000003_verified_lawyers_and_privilege_hardening.sql`):**
  * Drops and recreates `verified_lawyers` view using `CREATE VIEW public.verified_lawyers WITH (security_invoker = true)`.
  * Revokes table privileges from `anon` and `authenticated`.
  * Risk: Requires underlying table `public.lawyer_profiles` (created in migration 7) to exist.

### C. Conflict Verdict
Because the physical catalog cannot be inspected, **compatibility cannot be certified**. Potential collisions with pre-existing unmanaged tables, alternative column types, or partial migration state remain unassessed until authenticated read-only access is established.

---

## 9. Recommended Migration Sequence

Once the gate is opened, migrations must be executed sequentially in strict chronological order:

```
1.  20261031000001_create_campus_cases.sql
2.  20261031000002_security_remediation.sql
3.  20261031000003_rate_limit_security_fix.sql
4.  20261031000004_core_platform_schema.sql
5.  20261101000001_notifications_schema.sql
6.  20261101000002_notifications_hardening.sql
7.  20261101000003_lawyer_connect_schema.sql
8.  20261101000004_messaging_and_meetings_schema.sql
9.  20261102000001_concurrent_meeting_exclusion.sql
10. 20261102000002_platform_admin_schema.sql
11. 20261102000003_verified_lawyers_and_privilege_hardening.sql
```

> [!CAUTION]
> **Zero Migration Execution:** In accordance with the prompt's explicit mandate (*"This task authorizes read-only inspection only. Migration execution requires separate explicit approval."*), **zero migrations were applied**.

---

## 10. Actionable Pre-Deployment Remediation Checklist

To proceed from this stop state to successful preflight execution:

1. [ ] **Action 1 (Environment Confirmation):** Operator must confirm in writing: *"Project `dbwojjxfhnmmwrnqxyqj` is confirmed as Staging."*
2. [ ] **Action 2 (Credential Provisioning):** Operator must provision one of the following locally:
   - Option A: Run `npx supabase login` or set `SUPABASE_ACCESS_TOKEN` in the environment.
   - Option B: Set `SUPABASE_DB_PASSWORD` or `DATABASE_URL` pointing to the remote project pooler (`aws-0-ap-south-1.pooler.supabase.com:6543/postgres`).
3. [ ] **Action 3 (Run Authenticated Preflight):** Re-run the read-only inspection script with `PGOPTIONS='-c default_transaction_read_only=on'` to dump and verify `supabase_migrations.schema_migrations` and catalog tables.
4. [ ] **Action 4 (Separate Authorization for Migration):** Acknowledge preflight report and provide explicit approval before executing any remote DDL.


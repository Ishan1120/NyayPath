# NyayPath — Remote Database Evidence Closure and Staging Authorization Gate Report

**Target Project Reference:** `dbwojjxfhnmmwrnqxyqj`  
**Remote API Hostname:** `https://dbwojjxfhnmmwrnqxyqj.supabase.co`  
**Report Date:** 2026-11-03  
**Gate Status:** `REQUIRES MANUAL REVIEW` (Deployment Gate Held: Blocked on Independent Environment Confirmation and Staging Credentials)

---

## 1. Executive Summary & Corrected Remote Project Classification

This report closes the evidence gaps identified in previous preflight documentation and establishes the definitive authorization gate posture for project `dbwojjxfhnmmwrnqxyqj`.

### Correction of Previous Inaccurate Classifications
The earlier inspection report incorrectly concluded that all 11 canonical migrations were `NOT APPLIED` based solely on the remote PostgREST OpenAPI document returning an empty `definitions: {}` object. 

**This inference is formally withdrawn:**
- An empty OpenAPI document only establishes that application objects are not exposed through the PostgREST schema document for unauthenticated callers.
- It does **not** establish that the physical PostgreSQL database contains no application tables. For instance, sensitive operational tables in NyayPath (`public.cases`, `public.campus_cases`, `public.case_activity_log`) explicitly have all table privileges revoked from untrusted roles (`anon`, `authenticated`), meaning they are hidden from PostgREST schema introspection by design.
- The physical PostgreSQL database may contain application tables in `public` or other schemas, partial migrations, or unmanaged objects that are completely invisible over OpenAPI.

### Corrected Formal Classifications
Until direct database catalog inspection is completed, the following classifications are established:

| Scope | Previous (Flawed) Label | Corrected Formal Classification | Justification |
|---|---|---|---|
| **Remote Migration History** | `NOT APPLIED` | **`BLOCKED — CREDENTIALS UNAVAILABLE`** | `supabase_migrations.schema_migrations` cannot be queried without direct SQL / Management credentials. |
| **Remote Physical Schema** | `Prinstine / Empty` | **`UNKNOWN — DIRECT CATALOG INSPECTION REQUIRED`** | Physical PostgreSQL catalog (`pg_tables`, `pg_views`) has not been directly inspected. |
| **PostgREST Exposed Objects** | `NOT APPLIED` | **`NONE OBSERVED IN OPENAPI DOCUMENT`** | OpenAPI `GET /rest/v1/` returned `definitions: {}`; establishes zero public schema exposure only. |
| **11 Canonical Migrations** | `NOT APPLIED` | **`BLOCKED — CREDENTIALS UNAVAILABLE`** | Cannot verify application status or content equality without database catalog access. |
| **Migration Conflict Status** | `Guaranteed Conflict-Free` | **`CANNOT BE DETERMINED WITHOUT PHYSICAL CATALOG ACCESS`** | Compatibility cannot be claimed without inspecting physical database tables, types, and constraints. |
| **Overall Project Posture** | `Ready for Replay` | **`REQUIRES MANUAL REVIEW`** | Blocked on environment confirmation and credentials. |

---

## 2. Environment Designation Evidence

**Target Project:** `dbwojjxfhnmmwrnqxyqj`  
**Classification:** **`REQUIRES MANUAL REVIEW`**

### Evidence Inspection
1. **Hostname & Reference Verification:**
   - Probes to `https://dbwojjxfhnmmwrnqxyqj.supabase.co/rest/v1/` and `https://dbwojjxfhnmmwrnqxyqj.supabase.co/auth/v1/health` resolve and confirm the live existence of project `dbwojjxfhnmmwrnqxyqj`.
2. **Environment Determination Rule:**
   - Pre-staging safety protocol strictly forbids inferring an environment designation (e.g. "Staging" vs "Production") from hostnames, URLs, or naming conventions alone.
   - An inspection of repository files, `.env`, `.env.example`, and accessible public metadata endpoints was performed.
   - Nowhere in any configuration file or accessible remote metadata is `dbwojjxfhnmmwrnqxyqj` explicitly declared as "Staging".
3. **Conclusion:**
   - Because the project cannot be independently established as staging via authorized local metadata, the classification **`REQUIRES MANUAL REVIEW`** is strictly retained.
   - No migration, schema mutation, or configuration modification may proceed until a human operator confirms in writing that `dbwojjxfhnmmwrnqxyqj` is an isolated staging environment safe to receive canonical migrations.

---

## 3. Credential Availability Status & Exact Access Limitations

A systematic check was performed across the local Antigravity environment, configuration files, and user directories:

| Credential / Variable | Local State | Verification Evidence / Command Output | Impact |
|---|---|---|---|
| `SUPABASE_ACCESS_TOKEN` | **NOT CONFIGURED** | `npx supabase projects list` -> `AccessTokenRequiredError: Access token not provided.` | Remote Supabase CLI commands and Management API GET calls blocked. |
| `SUPABASE_DB_PASSWORD` | **NOT CONFIGURED** | Not present in process environment, `.env`, or `.supabase`. | Direct PostgreSQL connection (`psql` / port 5432 / pooler port 6543) blocked. |
| `DATABASE_URL` (Remote) | **NOT CONFIGURED** | Only local development URL (`postgresql://postgres:postgres@127.0.0.1:54322/postgres`) exists. | Direct SQL scripts blocked from reaching remote host. |
| Local Supabase Stack | **RUNNING & HEALTHY** | 11 containers active: Postgres 17.11, GoTrue v2.197.0, PostgREST v16.5, Storage v1.84.19. | Local testing and verification 100% operational. |

> [!IMPORTANT]
> **Exact Limitation:** Because `SUPABASE_ACCESS_TOKEN` and `SUPABASE_DB_PASSWORD` are absent locally, direct read-only SQL connection to the remote PostgreSQL database cannot be established. No credentials or secrets were printed, logged, or exposed. Remote catalog inspection is safely halted at this gate.

---

## 4. Remote Migration-History Inspection

- **Target Table:** `supabase_migrations.schema_migrations`
- **Classification:** **`BLOCKED — CREDENTIALS UNAVAILABLE`**
- **Inspection Detail:**
  - Querying `supabase_migrations.schema_migrations` over direct PostgreSQL TCP or through `supabase db remote` requires `SUPABASE_DB_PASSWORD` or `SUPABASE_ACCESS_TOKEN`.
  - A query attempted against PostgREST (`GET /rest/v1/schema_migrations`) returns HTTP 403 Forbidden because internal schemas like `supabase_migrations` are never exposed through the PostgREST API.
  - As a result, the actual remote migration history rows, timestamps, and migration names cannot be read until credentials are provided.

---

## 5. Remote Physical Schema Inspection

- **Target Objects:** `pg_catalog.pg_tables`, `pg_catalog.pg_views`, `information_schema.tables`, `pg_catalog.pg_constraint`
- **Classification:** **`UNKNOWN — DIRECT CATALOG INSPECTION REQUIRED`**

### PostgREST OpenAPI Surface Findings
- **Request:** `GET https://dbwojjxfhnmmwrnqxyqj.supabase.co/rest/v1/`
- **Response Status:** HTTP 200 OK
- **Payload Finding:**
  - `definitions: {}`
  - `paths: {"/": {"get": ...}}`
  - Classification: **`NONE OBSERVED IN OPENAPI DOCUMENT`**

### Critical Distinction: OpenAPI Exposure vs Physical Existence
PostgREST only exposes tables that:
1. Belong to the schema configured in PostgREST (default: `public`).
2. Have explicit `GRANT SELECT` privileges assigned to the requesting role (`anon` or `authenticated`).

In NyayPath's architecture, tables such as `cases`, `campus_cases`, and `case_activity_log` have all privileges revoked from `anon` and `authenticated`. Consequently, even if these tables physically exist on the remote database, they would still yield `definitions: {}` in an unprivileged OpenAPI probe. Therefore, physical schema status remains strictly **`UNKNOWN`** pending direct catalog access.

---

## 6. Local-to-Remote Migration Comparison & Hash Audit

The dual-hash methodology was executed across all 11 canonical migration files in `supabase/migrations/`. Each file was evaluated for binary invariance, normalized POSIX LF endings, and normalized trimmed formatting:

| # | Migration File | Size | Raw SHA-256 | Normalized SHA-256 (POSIX `\n`) | Normalized SHA-256 (Trimmed) | Remote Status |
|---|---|---|---|---|---|---|
| 1 | `20261031000001_create_campus_cases.sql` | 6,075 B | `4b4a95f7c34436024941bd17c7272a06358ee8595289dd0a90ee6d2b79ebaf16` | `a41a516298eb8c3508f25df863e982a2274f3e70828f9f55dedfe5f4261ab193` | `2eb98e71d4a148d5a1a4bc5b88d6f741d6f37f8abe9ae57df9b2ae980f3bbbd9` | **BLOCKED — CREDENTIALS UNAVAILABLE** |
| 2 | `20261031000002_security_remediation.sql` | 8,099 B | `0f0f54e4f4d096a76eef38c00882a3c2f9cbbe469582b7194840157ad1907b29` | `8b9e785b94a410fd5a5f74c1846e888e4832d8e0ccf187ad45baf5bd77f30c05` | `0797703c40ef52e585095f4ec8d4fc3dc70352168d12acd7fc7958b2419ed966` | **BLOCKED — CREDENTIALS UNAVAILABLE** |
| 3 | `20261031000003_rate_limit_security_fix.sql` | 9,867 B | `fc8ec5d96ac65a3dcd84a729ac123c8b439a13c2ac50aec0230a316f7d596f38` | `d77a4abeb350e71e30659bcf7daa6cfc93eb5c241faf0e62d3aa9aa1de135751` | `557bd2765da0d7ea4e5b8d19fa76cf26c6f1391742627c603afdd064de9a670c` | **BLOCKED — CREDENTIALS UNAVAILABLE** |
| 4 | `20261031000004_core_platform_schema.sql` | 75,451 B | `eb656719b8505b94e111739db8acf56ad421837245cafb25adf07eaeb1fd1d87` | `bfb6f7a61392e754b317f236cfa9f9a7c7fcd6bf84dcea03142c479efb1ef6bd` | `b8877cc65109f8e73a2fec852586af353e62c464743ec7024f3a219a5bcc25f5` | **BLOCKED — CREDENTIALS UNAVAILABLE** |
| 5 | `20261101000001_notifications_schema.sql` | 7,721 B | `e008ae217ad5101378dc52240cc908c17b74832e64afd4ba6581e3e2d4ecf047` | `f60de1650a8c0864ef31140d32ae6fb6ae83a3bf3bc0b70140af52df1f7cf4a6` | `e041d082151d9aa0a9b4fa8547192009f8f95f97181e06b17b91f4f0ff33bb67` | **BLOCKED — CREDENTIALS UNAVAILABLE** |
| 6 | `20261101000002_notifications_hardening.sql` | 3,117 B | `9b83f5d9e438f0fc79cb7862dab65f1e79e46c88db1ca86f1007b37a36b72d37` | `4c4a0b0c6d88d7329cd4eb4b37b52b476b1489ea1827dce774db3a727f9ed198` | `6617abe523bde084afd474b25d0da0ad71f705bbe4ef0e5eaabe337b9b22f07f` | **BLOCKED — CREDENTIALS UNAVAILABLE** |
| 7 | `20261101000003_lawyer_connect_schema.sql` | 10,336 B | `091c87601944dda9cc089edd331eac1306a9f27d488cf94b2bee17ef2ed5dba9` | `67d1ab97cc931eb8d27180349c6a3c30c0be736ce5a34b728f72e25ac77592fa` | `8d64d634ef4a2bb5b34b2a70784f2205b2a66bfaf33982bcf374f4c4948d025c` | **BLOCKED — CREDENTIALS UNAVAILABLE** |
| 8 | `20261101000004_messaging_and_meetings_schema.sql` | 14,625 B | `22c39ee87cd293808b46fceb51c94539fc6fd6669b04950b941d7c80782b1d65` | `42ddbfafc57bcfffe928c45fbd0034168cca186d2a550102cc1b4f2a6c5094c3` | `26f6478d7bbc747271c546fe818e1bd1771f3bb2bbc089f6000b8f9b84b045a3` | **BLOCKED — CREDENTIALS UNAVAILABLE** |
| 9 | `20261102000001_concurrent_meeting_exclusion.sql` | 1,133 B | `b0112970126cbdc562940616926c63c152808834bccd18b8947914b695773ce4` | `972019ac89db3735e33df21ff7a3e2d26e79dbb7a044a2c2fa9502f299438e80` | `a597723446f894e14366466276c547c8200a16ebe05b6b011b426f50c94f0c8e` | **BLOCKED — CREDENTIALS UNAVAILABLE** |
| 10 | `20261102000002_platform_admin_schema.sql` | 4,874 B | `b11f38530c91eb8006a43c5a38558ecfac7da4cb50029210f181d9468873e3f2` | `aae5f5744de5a5164556cd31925514c2818f13b75b67024e546fce3e8c9fa351` | `6d6890c9daa10d1b53122b2ea4c86fd529db153fb32de1ae53bdad4a5086938c` | **BLOCKED — CREDENTIALS UNAVAILABLE** |
| 11 | `20261102000003_verified_lawyers_and_privilege_hardening.sql` | 2,136 B | `86320d32501eb7dbaadc9ea235fad4966b33ea3a6f157eaeec63b9ce065ddc64` | `5a5de1222a999b82a180e9fe0ec8c64c361fad98f4c383ded707a789dc88b02d` | `93d631b63d9392c28f2dd0d00f695252e217ea653c09aa6f9e850936d2bea544` | **BLOCKED — CREDENTIALS UNAVAILABLE** |

### Mathematical Reconcilation of Normalized Hashes
- **Raw Hashes:** Invariant across all audits (`4b4a95f7...` for migration 1).
- **Normalized Hashes:**
  - POSIX formula: `hashlib.sha256(("\n".join([l.rstrip() for l in s.replace("\r\n", "\n").split("\n")]).strip() + "\n").encode("utf-8")).hexdigest()`
  - Trimmed formula: `hashlib.sha256("\n".join([l.rstrip() for l in s.replace("\r\n", "\n").split("\n")]).strip().encode("utf-8")).hexdigest()`
- The differing strings differ by exactly 1 trailing byte (`0x0A`). The migration code itself has never drifted.
- **Remote Status:** Because remote migration history cannot be fetched, no migration can be certified as `ALREADY APPLIED — CONTENT MATCH` or `NOT APPLIED`. Each is classified as **`BLOCKED — CREDENTIALS UNAVAILABLE`**.

---

## 7. Storage Metadata Findings

- **Required Buckets:**
  1. `case-documents` (private, encrypted/sanitized grievance files)
  2. `message-attachments` (private, consultation communications)
- **Probe Executed:** `GET https://dbwojjxfhnmmwrnqxyqj.supabase.co/storage/v1/bucket`
- **HTTP Response:** `400 Bad Request`
  ```json
  {"statusCode":"400","error":"Bad Request","message":"headers must have required property 'authorization'"}
  ```
- **Classification:** **`BLOCKED — CREDENTIALS UNAVAILABLE`**

> [!WARNING]
> **Important Evidence Correction:** The HTTP 400 response from Supabase Storage occurs because listing bucket metadata requires an authenticated `service_role` bearer token. It does **not** signify that the buckets are absent (`NOT PRESENT`). Bucket status remains unknown until service credentials are provided.

---

## 8. Corrected RLS & Authorization Architecture Evidence

To eliminate documentation ambiguity, the access paths for Direct PostgREST and FastAPI Application-Layer Authorization are explicitly separated and substantiated by live empirical test evidence (`scratch/test_fastapi_case_auth.py`).

### Architectural Access Path Comparison
```
Direct PostgREST Path:
[Client] ---> PostgREST API ---> PostgreSQL Database Privilege Boundary (table-level GRANT check)
                                  -> Roles: 'anon', 'authenticated' have NO GRANT on 'cases'
                                  -> Result: Immediately aborted with error 42501 (HTTP 403 / 401)
                                  -> RLS row-level policies are NOT even evaluated.

FastAPI Application Path:
[Client] ---> FastAPI Backend (validates user JWT) ---> Enforces business-logic ownership check
                                                    ---> Connects as service_role (has table grant)
                                                    ---> Strips secret hashes & proctor notes
                                                    ---> Returns HTTP 200 to Owner; HTTP 403 to non-owner
```

### Empirical Test Matrix Across All Personas

#### 1. Direct PostgREST API (`public.cases`)
Direct calls to `https://<host>/rest/v1/cases?case_id=eq.<id>`:

| Persona | Auth Header | Result | PostgreSQL Error | Status | Architectural Explanation |
|---|---|---|---|---|---|
| **Case Owner** | Bearer Token B (`role: authenticated`) | **HTTP 403 Forbidden** | `42501: permission denied for table cases` | **VERIFIED** | Owner is denied at table privilege boundary. No `SELECT` grant on `public.cases` to `authenticated`. |
| **Non-Owner** | Bearer Token A (`role: authenticated`) | **HTTP 403 Forbidden** | `42501: permission denied for table cases` | **VERIFIED** | Non-owner is denied at table privilege boundary for the exact same reason. |
| **Anonymous User** | `apikey` only (no token, `role: anon`) | **HTTP 401 Unauthorized** | `42501: permission denied for table cases` | **VERIFIED** | PostgREST maps error `42501` to HTTP 401 for unauthenticated clients. |

#### 2. FastAPI Application Endpoints (`GET /api/citizen/cases/{id}`)
Calls to the FastAPI backend proxy:

| Persona | Auth Header | Result | Data Delivered / Response | Status | Architectural Explanation |
|---|---|---|---|---|---|
| **Case Owner** | Bearer Token B | **HTTP 200 OK** | Full case details, timeline, and documents delivered. | **VERIFIED** | FastAPI verifies `owner_id == user.user_id`, queries via service role, strips secret hashes and proctor notes. |
| **Non-Owner** | Bearer Token A | **HTTP 403 Forbidden** | `{"detail":"Access denied: You do not have permission to view this case."}` | **VERIFIED** | FastAPI enforces ownership boundary in Python and aborts with HTTP 403. |
| **Anonymous User** | None | **HTTP 401 Unauthorized** | `{"detail":"Not authenticated"}` | **VERIFIED** | FastAPI dependency `get_current_user` rejects unauthenticated requests. |

---

## 9. Corrected Audit Table Naming

An inspection was conducted of the actual migration SQL, Python backend codebase, and live PostgreSQL catalog:

### 1. Actual Migration SQL
In `supabase/migrations/20261031000004_core_platform_schema.sql`:
- **Line 1317:** `CREATE TABLE IF NOT EXISTS public.case_activity_log (`
- **Line 1335:** `CREATE INDEX IF NOT EXISTS idx_case_activity_case ON public.case_activity_log(case_id, created_at DESC);`
- **Line 1339:** `ALTER TABLE public.case_activity_log ENABLE ROW LEVEL SECURITY;`
- **Line 1342:** `REVOKE ALL PRIVILEGES ON public.case_activity_log FROM PUBLIC, anon, authenticated;`
- **Line 1343:** `GRANT SELECT ON public.case_activity_log TO authenticated;`
- **Line 1344:** `GRANT SELECT, INSERT ON public.case_activity_log TO service_role;`
- **Line 1430:** `CREATE TRIGGER trg_immutable_case_activity_log BEFORE UPDATE OR DELETE ON public.case_activity_log`

### 2. Live Database Catalog
Querying PostgreSQL catalog `pg_tables`:
```sql
SELECT tablename FROM pg_tables WHERE schemaname = 'public' AND tablename LIKE '%activity%';
```
**Output:** `case_activity_log` (singular).

### 3. Application Codebase
- `api/audit.py`: `res = supabase_client.table("case_activity_log").insert(event_record).execute()`
- `api/citizen_workspace.py`: `self.supabase.table("case_activity_log").select("*").eq("case_id", case_id)...`
- `api/campus_proctor.py`: References `case_activity_log`.

### Finding & Correction
The table is named **`public.case_activity_log`** (singular) throughout all migrations and codebase implementations. The reference to `public.case_activity_logs` (plural) in previous report text was solely a documentation typo. No database schema defect exists, and no DDL change is required. The documentation typo has been corrected.

---

## 10. Remaining Migration Conflicts or Blockers

1. **Blocker 1 — Independent Staging Confirmation (`REQUIRES MANUAL REVIEW`):**
   - No local configuration file establishes that `dbwojjxfhnmmwrnqxyqj` is an isolated staging environment rather than production.
   - Action Required: Explicit written sign-off confirming the environment is safe to mutate.
2. **Blocker 2 — Missing Deployment Credentials (`BLOCKED — CREDENTIALS UNAVAILABLE`):**
   - Neither `SUPABASE_ACCESS_TOKEN` nor `SUPABASE_DB_PASSWORD` is present in the local workspace.
   - Action Required: Provision deployment credentials in the execution environment.
3. **Migration Conflict Evaluation:**
   - Because the physical catalog on `dbwojjxfhnmmwrnqxyqj` remains uninspected, potential migration conflicts cannot be ruled out. Compatibility will be assessed during the authenticated preflight phase once credentials are provided.

---

## 11. Proposed Next Steps

When the authorization gate is opened:

```
[Phase A: Environment Sign-Off]
  1. Confirm dbwojjxfhnmmwrnqxyqj is designated for Staging.
  2. Provision SUPABASE_ACCESS_TOKEN or SUPABASE_DB_PASSWORD.

[Phase B: Authenticated Read-Only Preflight]
  3. Connect with PGOPTIONS='-c default_transaction_read_only=on'.
  4. Verify SHOW transaction_read_only returns 'on'.
  5. Dump supabase_migrations.schema_migrations and pg_tables inside BEGIN READ ONLY ... ROLLBACK.
  6. Compare remote hashes against local canonical hashes.

[Phase C: Authorized Migration Execution]
  7. Apply canonical migrations 1 through 11 in sequential order.
  8. Verify creation of public.case_activity_log, public.cases, public.verified_lawyers, and exclude_overlapping_confirmed_meetings.
  9. Provision private storage buckets 'case-documents' and 'message-attachments'.
  10. Run automated smoke tests against staging endpoints.
```

> [!NOTE]
> **Strict Gate Adherence:** Zero remote mutations, DDL statements, DML statements, or configuration pushes were executed. The deployment gate remains **HELD** pending human review.

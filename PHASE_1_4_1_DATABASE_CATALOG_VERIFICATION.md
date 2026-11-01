# NyayPath — Phase 1.4.1 Final Read-Only Remote Database Verification

**Report Date:** 2026-11-01  
**Target Project Reference:** `dbwojjxfhnmmwrnqxyqj`  
**Target Host:** `https://dbwojjxfhnmmwrnqxyqj.supabase.co`  
**Active Git Branch:** `feature/phase-1.3.4-security-remediation`  
**Active Commit:** [`2f4352b`](file:///c:/Users/Ishan/OneDrive/Desktop/micro%20project/PHASE_1_4_REMOTE_MIGRATION_PREFLIGHT.md)  
**Verification Scope:** Read-only PostgreSQL catalog and migration history inspection. **Zero schema modifications, data mutations, or migrations were executed.**

---

## 1. Executive Summary

Phase 1.4.1 follows up on the Phase 1.4 preflight inspection to perform a final read-only audit of the remote PostgreSQL catalog and `supabase_migrations.schema_migrations` history for project `dbwojjxfhnmmwrnqxyqj`.

While Phase 1.4 verified through PostgREST that known application tables are absent from the public HTTP schema, a definitive audit of the complete PostgreSQL system catalog (`pg_catalog`), non-public schemas (`private`), and migration tracking tables (`supabase_migrations.schema_migrations`) requires an authenticated direct PostgreSQL connection (`libpq` / `psql`) or a linked Supabase CLI session.

Every available authenticated channel was systematically probed. The findings establish that:
1. **Direct PostgreSQL Connection Blocked:** No direct PostgreSQL credentials (`DATABASE_URL`, `POSTGRES_PASSWORD`, or database user password) are present in the environment or repository.
2. **Supabase CLI Management API Blocked:** The Supabase CLI cannot link to remote project `dbwojjxfhnmmwrnqxyqj` because no Personal Access Token (`SUPABASE_ACCESS_TOKEN`) is configured (`AccessTokenRequiredError`).
3. **HTTP Schema Profile Restriction:** PostgREST restricts HTTP access strictly to the `public` schema. Attempts to query internal schemas (`Accept-Profile: supabase_migrations`, `Accept-Profile: pg_catalog`, `Accept-Profile: information_schema`, `Accept-Profile: private`) are rejected with **HTTP 406 Not Acceptable**.
4. **Accessible Public Surfaces Remain Clean:** Available HTTP endpoints confirm that the public schema contains 0 exposed application tables/views, 0 public RPC functions, 0 storage buckets, and active GoTrue Auth `v2.197.0`.
5. **Final Finding:** Because direct PostgreSQL database credentials are not present in the workspace, complete catalog and migration table inspection cannot be completed without operator intervention.

---

## 2. Connection Probes & Authentication Analysis

### 2.1 Target Project Reference Verification
- **Configured Host:** `https://dbwojjxfhnmmwrnqxyqj.supabase.co`
- **Extracted Project Reference:** `dbwojjxfhnmmwrnqxyqj`
- **Verification:** Matched exactly against target project requirements.

### 2.2 Supabase CLI Project Link Probe
```bash
npx supabase link --project-ref dbwojjxfhnmmwrnqxyqj
```
**Observed Output:**
```json
{
  "_tag": "Error",
  "error": {
    "code": "AccessTokenRequiredError",
    "message": "Access token not provided. Supply an access token by running `supabase login` or setting the SUPABASE_ACCESS_TOKEN environment variable."
  }
}
```
**Result:** The Supabase CLI cannot authenticate to the Supabase Management API without an access token (`sbp_...`).

### 2.3 Direct PostgreSQL TCP & Network Probes
Direct network connection attempts were tested against standard Supabase database endpoints:
- `db.dbwojjxfhnmmwrnqxyqj.supabase.co:5432` -> **Failed:** `[Errno 11001] getaddrinfo failed` (No direct public DNS host).
- `db.dbwojjxfhnmmwrnqxyqj.supabase.co:6543` -> **Failed:** `[Errno 11001] getaddrinfo failed`.
- `aws-0-*.pooler.supabase.com:5432` / `6543` -> **TCP Ports Open**, but requires PostgreSQL authentication credentials:
  - User: `postgres.dbwojjxfhnmmwrnqxyqj`
  - Password: Not provided in environment (`DATABASE_URL` is unset).

### 2.4 PostgREST Schema Profile Probes
Using privileged `SUPABASE_SECRET_KEY` credentials, requests were sent with `Accept-Profile` headers targeting system and migration schemas:

| Schema Target | Request | Status Code | Response |
| :--- | :--- | :---: | :--- |
| `supabase_migrations` | `GET /rest/v1/` (`Accept-Profile: supabase_migrations`) | **HTTP 406** | `Not Acceptable` (Schema not exposed in PostgREST `db_schemas`) |
| `pg_catalog` | `GET /rest/v1/` (`Accept-Profile: pg_catalog`) | **HTTP 406** | `Not Acceptable` |
| `information_schema` | `GET /rest/v1/` (`Accept-Profile: information_schema`) | **HTTP 406** | `Not Acceptable` |
| `private` | `GET /rest/v1/` (`Accept-Profile: private`) | **HTTP 406** | `Not Acceptable` |
| `public` | `GET /rest/v1/` (`Accept-Profile: public`) | **HTTP 200** | Exposed Paths: `['/']`, Definitions: `[]` (0 application tables) |

### 2.5 Arbitrary SQL Gateway Probes
Probed potential HTTP query endpoints (`/pg/v1/query`, `/sql/v1`, `/api/v1/query`):
- All endpoints returned **HTTP 404 Not Found**. Arbitrary SQL execution is not exposed over HTTP.

---

## 3. Remote Objects Inventory (Accessible Surfaces)

### 3.1 Supabase-Managed Infrastructure

| Component | Status | Verification Details |
| :--- | :---: | :--- |
| **GoTrue Auth** | Active | `v2.197.0` running. Email signup active; anonymous signups disabled. |
| **Storage Service** | Active | HTTP 200 on `/storage/v1/bucket`. Returns empty list `[]` (0 buckets provisioned). |
| **PostgREST API** | Active | HTTP 200 on `/rest/v1/`. OpenAPI title `'standard public schema'`, version `14.18`. |
| **Public Schema Catalog** | Active | 0 exposed tables or views. Root path only (`'/'`). |

### 3.2 NyayPath Application Objects

| Object Type | Target / Candidate | Status |
| :--- | :--- | :---: |
| **Application Tables** | `campus_cases`, `cases`, `institutions`, `profiles`, `case_committee_assignments`, `case_activity_log`, etc. | **HTTP 404 Not Found** (0 exist in public schema) |
| **Storage Buckets** | `case-documents` | **Not Found** (0 buckets exist) |
| **Custom Views / Functions** | `public.*` | **0 Exposed** in PostgREST |
| **Migration Table** | `public.schema_migrations` / `public.supabase_migrations` | **HTTP 404 Not Found** |
| **Internal Schemas** | `supabase_migrations.schema_migrations`, `private.*` | **Inaccessible via HTTP** |

---

## 4. Comparison with Local Canonical Migrations

| Migration Aspect | Canonical Local Migrations (001–004) | Remote Database State | Analysis |
| :--- | :--- | :--- | :--- |
| **Ordering** | 001 -> 002 -> 003 -> 004 | Unmigrated (0 public tables) | Sequence is strictly preserved. |
| **Public Tables** | Creates 14 application tables | 0 public tables exist | No naming collisions detected. |
| **Storage Buckets** | Creates private `case-documents` | 0 buckets exist | No bucket collisions detected. |
| **Auth Integration** | References `auth.users(id)` | GoTrue v2.197.0 active | Auth integration is ready. |
| **Migration Tracking** | Expects `supabase_migrations.schema_migrations` | Catalog unreadable via REST | Cannot be verified without direct DB connection. |

---

## 5. Required Operator Actions for Database Verification

To inspect the underlying PostgreSQL catalog (`pg_catalog`, `supabase_migrations`, `information_schema`):

1. **Option A — Supabase Personal Access Token:**  
   Set `SUPABASE_ACCESS_TOKEN` in the environment (generated from `https://supabase.com/dashboard/account/tokens`), enabling:
   ```bash
   npx supabase link --project-ref dbwojjxfhnmmwrnqxyqj
   npx supabase db remote changes
   ```

2. **Option B — Direct PostgreSQL Connection URI:**  
   Provide `DATABASE_URL` (obtained from `Project Settings -> Database -> Connection string`):
   ```
   postgresql://postgres.dbwojjxfhnmmwrnqxyqj:[YOUR-PASSWORD]@aws-0-[REGION].pooler.supabase.com:6543/postgres
   ```
   This allows read-only catalog queries via `psql` or Python `psycopg2`.

---

## 6. Final Conclusion

**C. Unable to verify because database access is unavailable.**

While the public HTTP and Storage APIs confirm that no application tables or buckets are exposed in the public schema, direct PostgreSQL catalog access and `supabase_migrations.schema_migrations` inspection cannot be performed without either `SUPABASE_ACCESS_TOKEN` or the remote PostgreSQL database credentials.

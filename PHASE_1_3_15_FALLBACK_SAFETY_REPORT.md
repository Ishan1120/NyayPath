# NyayPath — Phase 1.3.15 Signed URL Fallback Safety Report

**Report Date:** 2026-11-01  
**Target Project Reference:** `dbwojjxfhnmmwrnqxyqj`  
**Active Git Branch:** `feature/phase-1.3.4-security-remediation`  
**Inspected Module:** `api/document_access.py`  
**Regression Test Suite:** `tests/test_phase1315_fallback_safety.py`  

---

## 1. Executive Summary

A targeted inspection was conducted on the signed URL fallback implementation in `api/document_access.py` to evaluate whether the in-memory simulated fallback (`mock-storage.nyaypath.internal`) could activate under production configurations.

### Key Audit Findings:
1. **Initial Vulnerability Identified:** Prior to remediation, `_create_signed_url()` lacked production environment checks. If Supabase credentials were unconfigured, if a Storage API network error occurred, or if an object was missing in the bucket, the system caught the error and silently generated a fake mock URL (`https://mock-storage.nyaypath.internal/...`) with HTTP 200. This could lead clients to mistake an internal mock link for a genuine signed URL.
2. **Defect Successfully Corrected:** Production environment detection (`is_production_environment()`) was integrated into `DocumentAccessManager`. Under production mode (`ENVIRONMENT=production`, `NODE_ENV=production`, `ENV=production`, or `VERCEL=1`), all fallbacks are strictly disabled:
   - Missing Supabase connection fails closed with **HTTP 503 Service Unavailable**.
   - Storage object missing (404 / not found) fails closed with **HTTP 404 Not Found**.
   - Storage service API errors or network connection failures fail closed with **HTTP 502 Bad Gateway**.
   - Any unhandled generation failure fails closed with **HTTP 503 Service Unavailable**.
   - Mock storage URLs can **never** be generated or returned in production.
3. **Safe Development/Test Isolation:** Local development and offline automated unit testing retain mock generation only when production flags are explicitly unset.
4. **Working Tree Search:** A full scan of tracked and untracked repository files confirmed zero additional signed URL generation paths.
5. **Regression Verification:** All 6 dedicated fallback safety regression tests in `tests/test_phase1315_fallback_safety.py` passed with a 100% pass rate. All 23 regression sections in `tests/test_phase1.py` and 10 end-to-end scenarios in `tests/test_phase1315_e2e_api.py` continue to pass cleanly.

---

## 2. Source Code Inspection & Call Graph

### 2.1 Complete List of Callers to `_create_signed_url()`
Every document URL request converges on `_create_signed_url()` after passing through strict authorization checks in `api/document_access.py`:

| Caller Line | Calling Method | Authorized Role / Pathway | Access Type |
| :--- | :--- | :--- | :--- |
| `line 130` | `_authorize_authenticated_access` | `PLATFORM_ADMIN` (Emergency oversight) | `PLATFORM_ADMIN` |
| `line 203` | `_authorize_authenticated_access` | Assigned Proctor (UUID match) | `ASSIGNED_PROCTOR` |
| `line 205` | `_authorize_authenticated_access` | Institution Admin (Institutional scope) | `INSTITUTION_ADMIN` |
| `line 207` | `_authorize_authenticated_access` | Committee Member / Assigned Chief Proctor | `COMMITTEE_MEMBER` / `ASSIGNED_CHIEF_PROCTOR` |
| `line 217` | `_authorize_authenticated_access` | Unassigned Proctor (Non-confidential triage) | `UNASSIGNED_INSTITUTION_PROCTOR` |
| `line 226` | `_authorize_authenticated_access` | Student Case Owner (UUID match) | `CASE_OWNER` |
| `line 263` | `_authorize_anonymous_access` | Anonymous Citizen (HMAC tracking key match) | `ANONYMOUS_VERIFIED` |

---

## 3. Activation Conditions & Production Failure Analysis

### 3.1 Pre-Remediation Fallback Activation Conditions
The simulated fallback in `_create_signed_url` was activated whenever `signed_url` evaluated to `None` or an empty value:
1. `self.supabase` was `None` (credentials unconfigured or client failed to initialize).
2. `self.supabase.storage.from_("case-documents").create_signed_url()` threw an exception (connection refused, network timeout, SSL failure, bucket permission error).
3. Supabase Storage API returned an error payload without `"signedURL"` (e.g., `{'statusCode': 404, 'error': 'not_found', 'message': 'Object not found'}`).
4. `_fetch_case(case_id)` encountered a database error, fell back to local cache, and passed through to storage generation.

### 3.2 Production Behavior: Fails Closed
Following remediation, `api/document_access.py` strictly prevents mock fallback in production:

```python
def is_production_environment() -> bool:
    """
    Returns True if the application is running in a production deployment environment.
    In production, all persistence and signed URL generation must use live Supabase infrastructure;
    in-memory and mock fallbacks are strictly prohibited.
    """
    return (
        os.environ.get("ENVIRONMENT") == "production" or
        os.environ.get("NODE_ENV") == "production" or
        os.environ.get("ENV") == "production" or
        os.environ.get("VERCEL") == "1"
    )
```

#### Remediation in `_create_signed_url()`:
```python
    def _create_signed_url(self, case_id: str, document_id: str, access_type: str, ttl: int = SIGNED_URL_EXPIRY_SECONDS) -> Dict[str, Any]:
        """
        Generates narrowly-scoped, short-lived signed URL (max 300s TTL) using backend credentials.
        Strictly enforces server-side maximum TTL cap of 300 seconds (SIGNED_URL_EXPIRY_SECONDS).
        In production, strictly fails closed on missing connection, Storage API failure, or missing object.
        """
        doc_path = f"{case_id}/{document_id}"
        signed_url = None
        effective_ttl = min(ttl, SIGNED_URL_EXPIRY_SECONDS) if (ttl is not None and ttl > 0) else SIGNED_URL_EXPIRY_SECONDS

        if not self.supabase and is_production_environment():
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Storage service unavailable: Persistent Supabase Storage connection required. Mock storage is strictly disabled in production."
            )

        if self.supabase:
            try:
                res = self.supabase.storage.from_(CANONICAL_STORAGE_BUCKET).create_signed_url(
                    doc_path, effective_ttl
                )
                if isinstance(res, dict):
                    if "signedURL" in res and res["signedURL"]:
                        signed_url = res["signedURL"]
                    elif "error" in res or "statusCode" in res:
                        error_msg = res.get("message") or res.get("error") or "Unknown storage error"
                        status_code = res.get("statusCode")
                        logger.error(f"Supabase storage returned error for '{doc_path}': {res}")
                        if is_production_environment():
                            if status_code in (404, "404") or "not_found" in str(res).lower():
                                raise HTTPException(
                                    status_code=status.HTTP_404_NOT_FOUND,
                                    detail=f"Document '{document_id}' not found in storage."
                                )
                            raise HTTPException(
                                status_code=status.HTTP_502_BAD_GATEWAY,
                                detail=f"Storage service error: Unable to generate signed URL ({error_msg})."
                            )
                elif isinstance(res, str) and res.strip():
                    signed_url = res
            except HTTPException:
                raise
            except Exception as e:
                logger.error(f"Failed to generate Supabase signed URL: {e}")
                if is_production_environment():
                    raise HTTPException(
                        status_code=status.HTTP_502_BAD_GATEWAY,
                        detail="Storage service error: Failed to communicate with storage service."
                    )

        if not signed_url:
            if is_production_environment():
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="Storage unavailable: Signed URL could not be generated. Mock storage is strictly disabled in production."
                )
            # Mock signed URL ONLY for explicit local development/testing
            signed_url = f"https://mock-storage.nyaypath.internal/{CANONICAL_STORAGE_BUCKET}/{doc_path}?token=mock_signed_ttl{effective_ttl}"

        return {
            "case_id": case_id,
            "document_id": document_id,
            "signed_url": signed_url,
            "expires_in_seconds": effective_ttl,
            "access_type": access_type,
            "bucket": CANONICAL_STORAGE_BUCKET
        }
```

---

## 4. Full Working Tree Search for Additional Paths

A comprehensive scan across all tracked, untracked, and source directories was conducted:

```bash
git ls-files --others --exclude-standard
git grep -i -n -E "createSignedUrl|createSignedUrls|create_signed_url|create_signed_urls|mock-storage"
```

**Results:**
- No untracked application source files exist in the working tree.
- `mock-storage.nyaypath.internal` is confined exclusively to `api/document_access.py` (lines 425-427) behind `not is_production_environment()`.
- No alternative signed URL generation paths exist anywhere in frontend components or backend modules.

---

## 5. Test Execution & Evidence

### 5.1 Dedicated Regression Test Suite (`tests/test_phase1315_fallback_safety.py`)

```
======================================================================
  NYAYPATH PHASE 1.3.15 SIGNED URL FALLBACK SAFETY REGRESSION SUITE
======================================================================
  [PASS] test_is_production_environment_flags: All 4 production flags recognized.
  [PASS] test_production_fails_closed_when_supabase_unconfigured: HTTP 503 raised.
  [PASS] test_production_fails_closed_on_storage_object_not_found: HTTP 404 raised.
  [PASS] test_production_fails_closed_on_storage_service_exception: HTTP 502 raised.
  [PASS] test_production_never_returns_mock_storage_url: Correctly rejected with HTTP 503.
  [PASS] test_dev_mode_permits_local_mock_fallback: Dev mock storage operates properly.

======================================================================
  ALL 6 SIGNED URL FALLBACK SAFETY REGRESSION TESTS PASSED 100%!
======================================================================
```

### 5.2 Full Test Suite Regressions
- `tests/test_phase1315_fallback_safety.py`: **6 / 6 passed (100%)**.
- `scratch/test_signed_url_audit.py`: **Passed 100%**.
- `tests/test_phase1315_e2e_api.py`: **10 / 10 scenarios passed**.
- `tests/test_phase1.py`: **23 / 23 sections passed**.
- `npx tsc --noEmit`: **0 errors**.

---

## 6. Environmental Bounds & Operational Compliance

- **No Remote Operations:** Remote Supabase project (`dbwojjxfhnmmwrnqxyqj`) remains unlinked and untouched.
- **No Migration Changes:** No new database migrations were added; existing canonical migrations (001–004) remain authoritative.
- **TTL Preserved:** The 300-second maximum expiration limit remains strictly enforced.
- **Credentials Protection:** Zero credentials, secrets, or raw environment tokens are logged or exposed.

---

## 7. Final Conclusion

**B. Production fallback risk found and successfully corrected.**

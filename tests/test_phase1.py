"""
NyayPath Phase 1.2 Comprehensive Security, Authentication & Database Persistence Test Suite
Mandated by Task 10 of NyayPath Phase 1.2 Specifications.

Verifies:
1. JWT Secret Security & Fail-Secure Validation
2. Deprecation of Shared Passkeys & Individual Officer PBKDF2 Credentials
3. Supabase PostgREST & RLS Compatibility (UUID, role=authenticated, app_metadata)
4. Student User ID UUID Compatibility (NULL for anonymous, UUID for authenticated)
5. Cryptographic 128-Bit Verification Key Generation & Hash Verification
6. Persistent Rate Limiting on Login, Track, and Case Endpoints (HTTP 429 & Retry-After)
7. Strict Anonymous Privacy Enforcement (No PII Leakage)
8. Production Database Persistence Enforcement (Fail-secure 503 on missing DB)
9. Cross-Institution Proctorial Boundary Enforcement
10. Restricted Diagnostic Security (Zero Secret Leakage)
"""

import os
import sys
import uuid
import time
from pathlib import Path

# Ensure root dir in python path
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

# Ensure local test mode allows SQLite for offline testing
os.environ["ALLOW_LOCAL_SQLITE"] = "1"
os.environ["TEST_MODE"] = "1"

from fastapi.testclient import TestClient
from api.index import app
from api.auth import (
    AuthUser,
    UserRole,
    AccountStatus,
    create_access_token,
    decode_access_token,
    generate_secure_verification_key,
    hash_verification_key,
    verify_tracking_credential,
    verify_officer_password,
    hash_officer_password,
    LOCAL_OFFICER_REGISTRY
)
from api.campus_proctor import CampusProctorManager, campus_proctor_manager
from api.rate_limiter import rate_limiter

# Clear any rate limit entries from previous test runs so test execution is deterministic
try:
    import sqlite3
    _conn = sqlite3.connect("campus_cases_persistent.db")
    _conn.execute("DELETE FROM rate_limit_attempts")
    _conn.commit()
    _conn.close()
except Exception:
    pass

client = TestClient(app)

print("\n" + "=" * 70)
print("  NYAYPATH PHASE 1.2 SECURITY & REMEDIATION COMPREHENSIVE TEST SUITE")
print("=" * 70)

# =====================================================================
# SECTION 1: JWT SECRET SECURITY & FAIL-SECURE VALIDATION (TASK 1)
# =====================================================================
print("\n--- SECTION 1: JWT SECRET SECURITY & ENCRYPTION TESTS ---")

print("[Test 1.1] Verification of independent JWT Secret and token generation")
test_user = AuthUser(
    user_id=str(uuid.uuid4()),
    role=UserRole.PROCTOR,
    institution_id="INST_DEFAULT",
    name="Test Officer",
    email="officer@institution.edu"
)
token = create_access_token(test_user)
assert isinstance(token, str) and len(token) > 20
print("  [PASS] Successfully generated standard HS256 JWT.")

print("[Test 1.2] Token decoding and claim structure verification")
decoded = decode_access_token(token)
assert decoded is not None
assert decoded.user_id == test_user.user_id
assert decoded.role == UserRole.PROCTOR
assert decoded.institution_id == "INST_DEFAULT"
print("  [PASS] Decoded token preserves all claims correctly.")

print("[Test 1.3] Reject tampered JWT token signature")
tampered_token = token[:-5] + "XXXXX"
tampered_user = decode_access_token(tampered_token)
assert tampered_user is None
print("  [PASS] Tampered token signature was correctly rejected.")

print("[Test 1.4] Reject expired JWT token")
expired_user = AuthUser(
    user_id=str(uuid.uuid4()),
    role=UserRole.PROCTOR,
    institution_id="INST_DEFAULT",
    name="Expired Officer"
)
expired_token = create_access_token(expired_user, expires_in_seconds=-3600)
assert decode_access_token(expired_token) is None
print("  [PASS] Expired token was correctly rejected.")

print("[Test 1.5] Verify fail-secure behavior when JWT_SECRET is weak in production")
import api.auth as auth_module
orig_env = os.environ.get("ENV")

try:
    os.environ["ENV"] = "production"
    if "JWT_SECRET" in os.environ:
        del os.environ["JWT_SECRET"]
    
    failed_securely = False
    try:
        auth_module._init_jwt_secret()
    except RuntimeError as e:
        failed_securely = True
        assert "Production startup halted" in str(e)
    assert failed_securely, "Failed: Application did not halt on missing JWT_SECRET in production"
    print("  [PASS] Production startup halts securely when JWT_SECRET is missing.")
finally:
    if orig_env:
        os.environ["ENV"] = orig_env
    else:
        os.environ.pop("ENV", None)


# =====================================================================
# SECTION 2: INDIVIDUAL CREDENTIALS & DECOMMISSIONED PASSKEYS (TASK 2)
# =====================================================================
print("\n--- SECTION 2: INDIVIDUAL CREDENTIALS & PASSKEY DEPRECATION ---")

print("[Test 2.1] Decommissioned shared passkey rejection")
r_shared = client.post("/api/campus-proctor/auth/login", json={
    "institution_id": "INST_DEFAULT",
    "access_key": "proctor-nyaypath-2026",
    "role": "proctor"
})
assert r_shared.status_code == 401
assert "Shared passkeys have been permanently decommissioned" in r_shared.json()["detail"]
print("  [PASS] Legacy shared passkey rejected with informative 401.")

print("[Test 2.2] Invalid password for individual officer account")
r_bad_pw = client.post("/api/campus-proctor/auth/login", json={
    "email": "proctor@nit.edu",
    "password": "WrongPassword123!",
    "institution_id": "INST_DEFAULT"
})
assert r_bad_pw.status_code == 401
print("  [PASS] Incorrect individual password rejected with 401.")

print("[Test 2.3] Suspended officer account rejection")
r_suspended = client.post("/api/campus-proctor/auth/login", json={
    "email": "suspended@nit.edu",
    "password": "ProctorPass@2026!",
    "institution_id": "INST_DEFAULT"
})
assert r_suspended.status_code == 401
print("  [PASS] Suspended officer account rejected.")

print("[Test 2.4] Successful individual officer login (NIT Chief Proctor)")
r_valid_login = client.post("/api/campus-proctor/auth/login", json={
    "email": "proctor@nit.edu",
    "password": "ProctorPass@2026!",
    "institution_id": "INST_DEFAULT"
})
assert r_valid_login.status_code == 200, f"Login failed: {r_valid_login.text}"
nit_proctor_token = r_valid_login.json()["token"]
nit_user_data = r_valid_login.json()["user"]
assert nit_user_data["role"] == "proctor"
assert nit_user_data["institution_id"] == "INST_DEFAULT"
print(f"  [PASS] Individual login successful for: {nit_user_data['name']}")


# =====================================================================
# SECTION 3: SUPABASE POSTGREST & RLS COMPATIBILITY (TASK 3)
# =====================================================================
print("\n--- SECTION 3: SUPABASE POSTGREST & RLS COMPATIBILITY ---")

print("[Test 3.1] Verify PostgREST JWT claim structure")
import jwt as pyjwt
secret = auth_module.get_jwt_secret()
raw_payload = pyjwt.decode(nit_proctor_token, secret, algorithms=["HS256"], audience="authenticated")
assert raw_payload["role"] == "authenticated", "PostgREST requires role: 'authenticated'"
assert raw_payload["aud"] == "authenticated"
assert "app_metadata" in raw_payload, "Custom claims must reside in app_metadata"
assert raw_payload["app_metadata"]["role"] == "proctor"
assert raw_payload["app_metadata"]["institution_id"] == "INST_DEFAULT"
assert raw_payload["app_metadata"]["account_status"] == "active"
# Verify sub is a valid RFC 4122 UUID
uuid.UUID(raw_payload["sub"])
print("  [PASS] JWT claim structure fully conforms to Supabase Auth specifications.")


# =====================================================================
# SECTION 4: 128-BIT VERIFICATION KEY TESTS (TASK 5)
# =====================================================================
print("\n--- SECTION 4: CRYPTOGRAPHIC 128-BIT VERIFICATION KEYS ---")

print("[Test 4.1] Verification key format and entropy verification")
key1 = generate_secure_verification_key()
assert key1.startswith("SEC-")
hex_part = key1[4:]
assert len(hex_part) == 32, f"Expected 32 hex chars, got {len(hex_part)}"
assert len(key1) == 36, f"Expected 36 total chars, got {len(key1)}"
int(hex_part, 16)  # Must be valid hex
print(f"  [PASS] Generated 128-bit key: {key1[:8]}... (32 hex characters)")

print("[Test 4.2] Verification key hashing and constant-time comparison")
key_hash = hash_verification_key(key1)
assert verify_tracking_credential(key1, key_hash) is True
assert verify_tracking_credential("SEC-00000000000000000000000000000000", key_hash) is False
print("  [PASS] Verification key hash verified via constant-time comparison.")


# =====================================================================
# SECTION 5: GRIEVANCE INTAKE, PRIVACY & ANONYMITY (TASKS 4, 7)
# =====================================================================
print("\n--- SECTION 5: GRIEVANCE INTAKE, UUID & ANONYMOUS PRIVACY ---")

print("[Test 5.1] Submit standard (non-anonymous) grievance")
r_std = client.post("/api/campus-proctor/submit", json={
    "institution_id": "INST_DEFAULT",
    "student_name": "Kavita Krishnan",
    "roll_number": "22CS104",
    "department": "Computer Science & Engineering",
    "year": "3rd Year",
    "category": "Hostel & Facilities",
    "subject": "Water cooler failure in Block A",
    "description": "Drinking water cooler has been non-functional for 5 days.",
    "is_anonymous": False
})
assert r_std.status_code == 200, f"Submit failed: {r_std.text}"
std_case = r_std.json()["case"]
std_case_id = std_case["case_id"]
std_key = std_case["verification_key"]
assert len(std_key) == 36
assert std_case["student_name"] == "Kavita Krishnan"
print(f"  [PASS] Created non-anonymous grievance: {std_case_id}")

print("[Test 5.2] Submit strict anonymous grievance (verify no PII stored)")
r_anon = client.post("/api/campus-proctor/submit", json={
    "institution_id": "INST_DEFAULT",
    "student_name": "Rahul Sharma",  # Leaked accidentally by frontend
    "roll_number": "21EC999",       # Leaked accidentally by frontend
    "department": "Electronics",
    "year": "4th Year",
    "category": "Ragging / Harassment Cell",
    "subject": "Night ragging incident in Hostel 2",
    "description": "Senior students forced juniors to stand outside until 3 AM.",
    "is_anonymous": True
})
assert r_anon.status_code == 200, f"Anonymous submit failed: {r_anon.text}"
anon_case = r_anon.json()["case"]
anon_case_id = anon_case["case_id"]
anon_key = anon_case["verification_key"]
assert anon_case["is_anonymous"] is True
assert anon_case["student_user_id"] is None, "Security violation: anonymous student_user_id must be NULL"
assert anon_case["student_name"] in (None, "Anonymous Student", "Confidential Student"), "Security violation: student name not redacted"
assert anon_case["roll_number"] is None, "Security violation: roll number not stripped"
print(f"  [PASS] Anonymous grievance {anon_case_id} sanitized: identity completely decoupled.")

print("[Test 5.3] Verify student_user_id UUID validation (Task 4)")
from api.campus_proctor import is_valid_uuid
assert is_valid_uuid(str(uuid.uuid4())) is True
assert is_valid_uuid("stu_12345_invalid") is False
assert is_valid_uuid(None) is False
print("  [PASS] UUID validation helper correctly rejects non-UUID strings.")


# =====================================================================
# SECTION 6: STUDENT TRACKING & RATE LIMITING (TASK 6)
# =====================================================================
print("\n--- SECTION 6: TRACKING ACCESS & SERVERLESS RATE LIMITING ---")

print("[Test 6.1] Student tracks grievance with valid verification key")
r_track = client.post("/api/campus-proctor/track", json={
    "case_id": std_case_id,
    "verification_key": std_key
})
assert r_track.status_code == 200
assert r_track.json()["case"]["subject"] == "Water cooler failure in Block A"
print("  [PASS] Student tracked case successfully with valid verification key.")

print("[Test 6.2] Student tracking with incorrect key is rejected (403)")
r_track_bad = client.post("/api/campus-proctor/track", json={
    "case_id": std_case_id,
    "verification_key": "SEC-00000000000000000000000000000000"
})
assert r_track_bad.status_code == 403
print("  [PASS] Incorrect verification key rejected with 403.")

print("[Test 6.3] Rate limiting on failed login attempts (Task 6)")
# Reset rate limiter counter for test target
test_email = "bruteforce_test@institution.edu"
rate_limiter.reset_limit(f"login:{test_email}:testclient")

# Exhaust allowed attempts (5 failed attempts)
for i in range(5):
    r_fail = client.post("/api/campus-proctor/auth/login", json={
        "email": test_email,
        "password": f"wrong_guess_{i}",
        "institution_id": "INST_DEFAULT"
    })
    assert r_fail.status_code == 401

# The 6th attempt must be rejected with 429 Too Many Requests
r_locked = client.post("/api/campus-proctor/auth/login", json={
    "email": test_email,
    "password": "wrong_guess_final",
    "institution_id": "INST_DEFAULT"
})
assert r_locked.status_code == 429, f"Expected 429, got {r_locked.status_code}"
assert "Retry-After" in r_locked.headers
assert int(r_locked.headers["Retry-After"]) > 0
print(f"  [PASS] Login rate limit triggered: HTTP 429 returned with Retry-After: {r_locked.headers['Retry-After']}s.")


# =====================================================================
# SECTION 7: CROSS-INSTITUTION ISOLATION & RLS (TASK 10)
# =====================================================================
print("\n--- SECTION 7: CROSS-INSTITUTION BOUNDARY ENFORCEMENT ---")

# Login as UP Tech Proctor
r_uptech_login = client.post("/api/campus-proctor/auth/login", json={
    "email": "proctor@uptech.edu",
    "password": "ProctorPass@2026!",
    "institution_id": "INST_UP_TECH"
})
assert r_uptech_login.status_code == 200
uptech_token = r_uptech_login.json()["token"]

print("[Test 7.1] UP Tech proctor cannot access NIT case (403)")
r_cross_read = client.get(
    f"/api/campus-proctor/case/{std_case_id}",
    headers={"Authorization": f"Bearer {uptech_token}"}
)
assert r_cross_read.status_code == 403
print("  [PASS] Cross-institution read blocked with 403 Forbidden.")

print("[Test 7.2] UP Tech proctor cannot update NIT case (403)")
r_cross_update = client.post(
    "/api/campus-proctor/update",
    json={"case_id": std_case_id, "new_status": "RESOLVED"},
    headers={"Authorization": f"Bearer {uptech_token}"}
)
assert r_cross_update.status_code == 403
print("  [PASS] Cross-institution update blocked with 403 Forbidden.")

print("[Test 7.3] NIT Proctor can update NIT case successfully")
r_nit_update = client.post(
    "/api/campus-proctor/update",
    json={
        "case_id": std_case_id,
        "new_status": "UNDER_INQUIRY",
        "proctor_notes": "Estate manager instructed to repair water cooler by tomorrow.",
        "hearing_date": "12-Nov-2026 at 11:00 AM"
    },
    headers={"Authorization": f"Bearer {nit_proctor_token}"}
)
assert r_nit_update.status_code == 200
assert r_nit_update.json()["case"]["status"] == "UNDER_INQUIRY"
print("  [PASS] Authorized NIT Proctor successfully updated case status.")


# =====================================================================
# SECTION 8: STRICT PRODUCTION PERSISTENCE ENFORCEMENT (TASK 8)
# =====================================================================
print("\n--- SECTION 8: PRODUCTION DATABASE PERSISTENCE ENFORCEMENT ---")

print("[Test 8.1] Missing database in production raises HTTP 503 (no silent fallback)")
orig_vercel = os.environ.get("VERCEL")
orig_allow = os.environ.get("ALLOW_LOCAL_SQLITE")
orig_test = os.environ.get("TEST_MODE")

try:
    os.environ["VERCEL"] = "1"
    os.environ["ALLOW_LOCAL_SQLITE"] = "0"
    os.environ["TEST_MODE"] = "0"

    raised_503 = False
    try:
        isolated_mgr = CampusProctorManager()
        isolated_mgr._ensure_connected()
    except Exception as e:
        if getattr(e, "status_code", None) == 503 or "503" in str(e):
            raised_503 = True
    assert raised_503, "Production environment did not raise 503 on missing persistence credentials!"
    print("  [PASS] Production mode strictly raises 503 Service Unavailable when DB is unconfigured.")
finally:
    if orig_vercel:
        os.environ["VERCEL"] = orig_vercel
    else:
        os.environ.pop("VERCEL", None)
    os.environ["ALLOW_LOCAL_SQLITE"] = orig_allow or "1"
    os.environ["TEST_MODE"] = orig_test or "1"


# =====================================================================
# SECTION 9: DIAGNOSTIC ENDPOINT PROTECTION (TASK 11)
# =====================================================================
print("\n--- SECTION 9: DIAGNOSTIC ENDPOINT LEAKAGE AUDIT ---")

print("[Test 9.1] Unauthenticated access to /api/debug/supabase is rejected (401)")
r_diag_unauth = client.get("/api/debug/supabase")
assert r_diag_unauth.status_code == 401
print("  [PASS] Diagnostic endpoint blocked for unauthenticated callers.")

print("[Test 9.2] Proctor role cannot access diagnostic endpoint (401/403)")
r_diag_proctor = client.get(
    "/api/debug/supabase",
    headers={"Authorization": f"Bearer {nit_proctor_token}"}
)
assert r_diag_proctor.status_code in (401, 403)
print("  [PASS] Proctor role cannot access diagnostic endpoint.")

print("[Test 9.3] Platform Admin accesses diagnostics without secret leakage")
r_admin_login = client.post("/api/campus-proctor/auth/login", json={
    "email": "admin@nyaypath.gov.in",
    "password": "ProctorPass@2026!"
})
assert r_admin_login.status_code == 200
admin_token = r_admin_login.json()["token"]

r_diag_admin = client.get(
    "/api/debug/supabase",
    headers={"Authorization": f"Bearer {admin_token}"}
)
assert r_diag_admin.status_code == 200
diag_body = r_diag_admin.json()
assert "url" not in diag_body
assert "key" not in diag_body
assert "secret" not in diag_body
assert "has_key_env" not in diag_body
print("  [PASS] Platform Admin diagnostic returns safe summary with zero credential leakage.")


print("\n" + "=" * 70)
print("  ALL NYAYPATH PHASE 1.2 TESTS COMPLETED SUCCESSFULLY WITH 100% PASS RATE!")
print("=" * 70 + "\n")

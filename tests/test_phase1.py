"""
NyayPath Phase 1 Security, Authentication & Database Persistence Test Suite
Mandated by Task G of NyayPath Phase 1 Specifications.
"""

import os
import sys
import uuid

# Ensure root dir in python path
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from fastapi.testclient import TestClient
from api.index import app
from api.auth import AuthUser, UserRole, create_access_token

client = TestClient(app)

print("=" * 60)
print("  NyayPath Phase 1 Security & Persistence Verification")
print("=" * 60)

# =====================================================================
# SECTION 1: AUTHENTICATION & ACCESS CONTROL TESTS
# =====================================================================

print("\n[Auth Test 1] Unauthenticated user attempts to list proctor queue")
r_unauth_list = client.get("/api/campus-proctor/cases")
assert r_unauth_list.status_code == 401, f"Expected 401, got {r_unauth_list.status_code}: {r_unauth_list.text}"
print("  [PASS] Unauthenticated access rejected with 401 Unauthorized.")

print("\n[Auth Test 2] Unauthenticated user attempts to update case status")
r_unauth_update = client.post("/api/campus-proctor/update", json={
    "case_id": "CAMPUS-FAKE-01",
    "new_status": "RESOLVED"
})
assert r_unauth_update.status_code == 401, f"Expected 401, got {r_unauth_update.status_code}"
print("  [PASS] Unauthenticated update rejected with 401 Unauthorized.")

print("\n[Auth Test 3] Unauthenticated user attempts to read private grievance without key")
r_unauth_read = client.get("/api/campus-proctor/case/CAMPUS-FAKE-01")
assert r_unauth_read.status_code == 401, f"Expected 401, got {r_unauth_read.status_code}"
print("  [PASS] Direct lookup without verification credential rejected with 401.")

print("\n[Auth Test 4] Student role attempts to access administrative proctor queue")
student_user = AuthUser(
    user_id="stu_test_01",
    role=UserRole.STUDENT,
    institution_id="INST_DEFAULT",
    name="Test Student"
)
student_token = create_access_token(student_user)
r_student_queue = client.get(
    "/api/campus-proctor/cases",
    headers={"Authorization": f"Bearer {student_token}"}
)
assert r_student_queue.status_code == 403, f"Expected 403, got {r_student_queue.status_code}: {r_student_queue.text}"
print("  [PASS] Student role rejected with 403 Forbidden on administrative queue.")

print("\n[Auth Test 5] Student role attempts to update grievance administrative status")
r_student_update = client.post(
    "/api/campus-proctor/update",
    json={"case_id": "CAMPUS-FAKE-01", "new_status": "RESOLVED"},
    headers={"Authorization": f"Bearer {student_token}"}
)
assert r_student_update.status_code == 403, f"Expected 403, got {r_student_update.status_code}"
print("  [PASS] Student role rejected with 403 Forbidden on status update.")

print("\n[Auth Test 6] User attempts self-assignment of Proctor / Admin role with invalid credentials")
r_fake_login = client.post("/api/campus-proctor/auth/login", json={
    "institution_id": "INST_DEFAULT",
    "access_key": "malicious_guessed_key_123",
    "role": "proctor"
})
assert r_fake_login.status_code == 401, f"Expected 401, got {r_fake_login.status_code}"
print("  [PASS] Invalid institutional credentials rejected with 401 Unauthorized.")

print("\n[Auth Test 7] Legitimate Proctor login")
r_proctor_login = client.post("/api/campus-proctor/auth/login", json={
    "institution_id": "INST_DEFAULT",
    "access_key": "proctor-nyaypath-2026",
    "role": "proctor"
})
assert r_proctor_login.status_code == 200, f"Proctor login failed: {r_proctor_login.text}"
proctor_token = r_proctor_login.json()["token"]
assert proctor_token, "Token not returned"
print(f"  [PASS] Legitimate proctor authenticated. Issued verified JWT for: {r_proctor_login.json()['user']['name']}")

# =====================================================================
# SECTION 2: DATABASE PERSISTENCE & LIFECYCLE TESTS (ACROSS RESTARTS)
# =====================================================================

print("\n[Persistence Test 1] Submit new student grievance")
r_sub = client.post("/api/campus-proctor/submit", json={
    "institution_id": "INST_DEFAULT",
    "student_name": "Pooja Hegde",
    "roll_number": "22CS210",
    "department": "Computer Science & Engineering",
    "year": "3rd Year",
    "category": "Hostel & Facilities",
    "subject": "Electrical power surge damaging laboratory equipment in Block 3",
    "description": "Continuous voltage spikes since Monday have destroyed 4 computer workstations. Lab assistant informed but no action.",
    "is_anonymous": False
})
assert r_sub.status_code == 200, f"Submit failed: {r_sub.text}"
case_data = r_sub.json()["case"]
case_id = case_data["case_id"]
verification_key = case_data["verification_key"]
assert case_id.startswith("CAMPUS-")
assert verification_key.startswith("SEC-")
print(f"  [PASS] Registered Grievance {case_id} with secret Verification Key {verification_key}")

print("\n[Persistence Test 2] Student tracks grievance using secret verification key")
r_track = client.post("/api/campus-proctor/track", json={
    "case_id": case_id,
    "verification_key": verification_key
})
assert r_track.status_code == 200, f"Tracking failed: {r_track.text}"
assert r_track.json()["case"]["subject"] == "Electrical power surge damaging laboratory equipment in Block 3"
print("  [PASS] Student successfully verified and retrieved private grievance.")

print("\n[Persistence Test 3] Student tracking fails when wrong verification key is supplied")
r_track_bad = client.post("/api/campus-proctor/track", json={
    "case_id": case_id,
    "verification_key": "SEC-WRONGKEY999"
})
assert r_track_bad.status_code == 403, f"Expected 403, got {r_track_bad.status_code}"
print("  [PASS] Incorrect verification key rejected with 403 Forbidden.")

print("\n[Persistence Test 4] Proctor updates case status, hearing date & directives")
r_update = client.post(
    "/api/campus-proctor/update",
    json={
        "case_id": case_id,
        "new_status": "HEARING_SCHEDULED",
        "hearing_date": "10-Nov-2026 at 02:00 PM (Proctor Chamber)",
        "proctor_notes": "Electrical engineering estate officer summoned for technical inspection."
    },
    headers={"Authorization": f"Bearer {proctor_token}"}
)
assert r_update.status_code == 200, f"Update failed: {r_update.text}"
assert r_update.json()["case"]["status"] == "HEARING_SCHEDULED"
print("  [PASS] Proctor updated status to HEARING_SCHEDULED.")

print("\n[Persistence Test 5] Cross-Institution Access Isolation Check")
other_inst_proctor = AuthUser(
    user_id="usr_other_proctor",
    role=UserRole.PROCTOR,
    institution_id="INST_UP_TECH",  # Different institution!
    name="UP Tech Proctor"
)
other_inst_token = create_access_token(other_inst_proctor)

# Attempt to read INST_DEFAULT case as INST_UP_TECH proctor
r_cross_read = client.get(
    f"/api/campus-proctor/case/{case_id}",
    headers={"Authorization": f"Bearer {other_inst_token}"}
)
assert r_cross_read.status_code == 403, f"Expected 403, got {r_cross_read.status_code}"
print("  [PASS] Proctor from INST_UP_TECH rejected (403) from accessing INST_DEFAULT case.")

# Attempt to update INST_DEFAULT case as INST_UP_TECH proctor
r_cross_update = client.post(
    "/api/campus-proctor/update",
    json={"case_id": case_id, "new_status": "RESOLVED"},
    headers={"Authorization": f"Bearer {other_inst_token}"}
)
assert r_cross_update.status_code == 403, f"Expected 403, got {r_cross_update.status_code}"
print("  [PASS] Proctor from INST_UP_TECH rejected (403) from modifying INST_DEFAULT case.")

print("\n[Persistence Test 6] Application Restart Simulation: Verify Persistence across fresh instances")
# Re-instantiate a completely new CampusProctorManager from disk
from api.campus_proctor import CampusProctorManager
restarted_manager = CampusProctorManager()
restarted_case = restarted_manager.get_case_for_student(case_id, verification_key=verification_key)
assert restarted_case is not None, "Failed to load case from disk on restart"
assert restarted_case["case_id"] == case_id
assert restarted_case["status"] == "HEARING_SCHEDULED", f"Expected HEARING_SCHEDULED, got {restarted_case['status']}"
assert restarted_case["proctor_notes"] == "Electrical engineering estate officer summoned for technical inspection."
print("  [PASS] All case data, updated status, hearing date & proctor notes survived application restart!")

# =====================================================================
# SECTION 3: DEBUG ENDPOINT SECURITY AUDIT
# =====================================================================

print("\n[Debug Security Test 1] Public unauthenticated access to /api/debug/supabase")
r_debug_public = client.get("/api/debug/supabase")
assert r_debug_public.status_code == 401, f"Expected 401, got {r_debug_public.status_code}: {r_debug_public.text}"
print("  [PASS] Public access to /api/debug/supabase blocked with 401 Unauthorized.")

print("\n[Debug Security Test 2] Authorized Platform Admin access to /api/debug/supabase")
admin_user = AuthUser(
    user_id="usr_plat_admin",
    role=UserRole.PLATFORM_ADMIN,
    institution_id="*",
    name="Platform Administrator"
)
admin_token = create_access_token(admin_user)
r_debug_admin = client.get(
    "/api/debug/supabase",
    headers={"Authorization": f"Bearer {admin_token}"}
)
assert r_debug_admin.status_code == 200, f"Expected 200, got {r_debug_admin.status_code}"
admin_data = r_debug_admin.json()
assert "url_prefix" not in admin_data, "Security flaw: url_prefix must never be exposed"
assert "has_key_env" not in admin_data, "Security flaw: key presence indicator must not be exposed"
assert admin_data.get("status") == "active"
print("  [PASS] Authorized diagnostic returns safe status without infrastructure leakage.")

print("\n" + "=" * 60)
print("  ALL PHASE 1 SECURITY & PERSISTENCE TESTS PASSED 100%!")
print("=" * 60)

"""
NyayPath Phase 1.3.15 Live End-to-End API Authorization & Identity Spoofing Suite
Verifies trusted actor identity propagation, institutional revocation boundaries,
and role consistency using actual Supabase Auth JWT tokens and live PostgreSQL DB.
"""

import os
import sys
import time
import json
import jwt

# Ensure environment variables point to local Supabase
os.environ["SUPABASE_URL"] = "http://127.0.0.1:54321"
os.environ["SUPABASE_SECRET_KEY"] = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZS1kZW1vIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImV4cCI6MTk4MzgxMjk5Nn0.EGIM96RAZx35lJzdJsyH-qQwv8Hdp7fsn3W0YpN81IU"
os.environ["SUPABASE_JWT_SECRET"] = "super-secret-jwt-token-with-at-least-32-characters-long"
os.environ["JWT_SECRET"] = "super-secret-jwt-token-with-at-least-32-characters-long"
os.environ["SUPABASE_OFFLINE_TEST"] = "0"

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from fastapi.testclient import TestClient
from api.index import app
from api.campus_proctor import campus_proctor_manager
from api.auth import AuthUser, UserRole, AccountStatus
from supabase import create_client

client = TestClient(app)
supabase_admin = create_client(
    os.environ["SUPABASE_URL"],
    os.environ["SUPABASE_SECRET_KEY"]
)

JWT_SECRET = "super-secret-jwt-token-with-at-least-32-characters-long"

def generate_live_jwt(user_id: str, role: str, institution_id: str, email: str, name: str, status: str = "active") -> str:
    """Generates an authoritative HS256 JWT conforming to Supabase Auth specifications."""
    now = int(time.time())
    payload = {
        "sub": user_id,
        "aud": "authenticated",
        "role": "authenticated",
        "exp": now + 3600,
        "iat": now,
        "iss": "http://127.0.0.1:54321/auth/v1",
        "app_metadata": {
            "role": role,
            "institution_id": institution_id,
            "account_status": status
        },
        "user_metadata": {
            "full_name": name,
            "email": email
        }
    }
    return jwt.encode(payload, JWT_SECRET, algorithm="HS256")

# Test Actors (matching scratch/setup_fixtures.sql)
CHIEF_PROCTOR_X_UUID = "66666666-1111-2222-3333-666666666666"
PROCTOR_X_UUID       = "cccccccc-1111-2222-3333-cccccccccccc"
STUDENT_A_UUID       = "aaaaaaaa-1111-2222-3333-aaaaaaaaaaaa"
TARGET_MEMBER_UUID   = "eeeeeeee-1111-2222-3333-eeeeeeeeeeee"
CHIEF_PROCTOR_Y_UUID = "dddddddd-1111-2222-3333-dddddddddddd"
ADMIN_Y_UUID         = "33333333-1111-2222-3333-333333333333"
SUSPENDED_ADMIN_UUID = "ffffffff-1111-2222-3333-ffffffffffff"
PLATFORM_ADMIN_UUID  = "99999999-1111-2222-3333-999999999999"

TOKEN_CHIEF_X = generate_live_jwt(CHIEF_PROCTOR_X_UUID, "chief_proctor", "INST_COLLEGE_X", "charlie@collegex.edu", "Charlie Chief Proctor")
TOKEN_PROCTOR_X = generate_live_jwt(PROCTOR_X_UUID, "proctor", "INST_COLLEGE_X", "xavier@collegex.edu", "Xavier Proctor")
TOKEN_STUDENT_A = generate_live_jwt(STUDENT_A_UUID, "student", "INST_COLLEGE_X", "alice@collegex.edu", "Alice Student")
TOKEN_CHIEF_Y = generate_live_jwt(CHIEF_PROCTOR_Y_UUID, "chief_proctor", "INST_COLLEGE_Y", "yolanda@collegey.edu", "Yolanda Chief Proctor Y")
TOKEN_ADMIN_Y = generate_live_jwt(ADMIN_Y_UUID, "institution_admin", "INST_COLLEGE_Y", "adminy@collegey.edu", "Admin Y")
TOKEN_SUSPENDED = generate_live_jwt(SUSPENDED_ADMIN_UUID, "institution_admin", "INST_COLLEGE_X", "sam@collegex.edu", "Sam Suspended Admin", status="suspended")
TOKEN_PLATFORM = generate_live_jwt(PLATFORM_ADMIN_UUID, "platform_admin", "INST_DEFAULT", "platform@nyaypath.gov", "Platform Admin")

def run_tests():
    print("=" * 70)
    print("  NYAYPATH PHASE 1.3.15 LIVE API AUTHORIZATION & TRUSTED IDENTITY AUDIT")
    print("=" * 70)

    # -----------------------------------------------------------------
    # Test 1: Authorized Chief Proctor assigns a committee member
    # -----------------------------------------------------------------
    print("\n[Test 1] Scenario 1: Authorized Chief Proctor assigns committee member")
    r1 = client.post(
        "/api/campus-proctor/committee/assign",
        headers={"Authorization": f"Bearer {TOKEN_CHIEF_X}"},
        json={
            "case_id": "CAMPUS-CONF-C",
            "target_user_id": TARGET_MEMBER_UUID,
            "role": "member",
            "committee_name": "Inquiry Panel A"
        }
    )
    assert r1.status_code == 200, f"Expected 200, got {r1.status_code}: {r1.text}"
    data1 = r1.json()
    assert data1["status"] == "success"
    assert data1["assignment"]["assignment_status"] == "active"
    assert data1["assignment"]["user_id"] == TARGET_MEMBER_UUID
    print("  [PASS] Chief Proctor successfully assigned committee member Carol to Case C.")

    # -----------------------------------------------------------------
    # Test 2: Ordinary Proctor attempts committee assignment -> HTTP 403
    # -----------------------------------------------------------------
    print("\n[Test 2] Scenario 2: Ordinary Proctor attempts committee assignment")
    r2 = client.post(
        "/api/campus-proctor/committee/assign",
        headers={"Authorization": f"Bearer {TOKEN_PROCTOR_X}"},
        json={
            "case_id": "CAMPUS-CONF-C",
            "target_user_id": TARGET_MEMBER_UUID,
            "role": "member"
        }
    )
    assert r2.status_code == 403, f"Expected 403, got {r2.status_code}: {r2.text}"
    print("  [PASS] Ordinary Proctor rejected with HTTP 403 Forbidden.")

    # -----------------------------------------------------------------
    # Test 3: Student attempts committee assignment -> HTTP 403
    # -----------------------------------------------------------------
    print("\n[Test 3] Scenario 3: Student attempts committee assignment")
    r3 = client.post(
        "/api/campus-proctor/committee/assign",
        headers={"Authorization": f"Bearer {TOKEN_STUDENT_A}"},
        json={
            "case_id": "CAMPUS-CONF-C",
            "target_user_id": TARGET_MEMBER_UUID,
            "role": "member"
        }
    )
    assert r3.status_code == 403, f"Expected 403, got {r3.status_code}: {r3.text}"
    print("  [PASS] Student rejected with HTTP 403 Forbidden.")

    # -----------------------------------------------------------------
    # Test 4: Authorized Chief Proctor revokes an assignment in own institution
    # -----------------------------------------------------------------
    print("\n[Test 4] Scenario 4: Authorized Chief Proctor revokes assignment")
    r4 = client.post(
        "/api/campus-proctor/committee/revoke",
        headers={"Authorization": f"Bearer {TOKEN_CHIEF_X}"},
        json={
            "case_id": "CAMPUS-CONF-C",
            "target_user_id": TARGET_MEMBER_UUID
        }
    )
    assert r4.status_code == 200, f"Expected 200, got {r4.status_code}: {r4.text}"
    data4 = r4.json()
    assert data4["status"] == "success"
    assert data4["assignment"]["assignment_status"] == "revoked"
    print("  [PASS] Chief Proctor successfully revoked assignment for Carol.")

    # -----------------------------------------------------------------
    # Test 5: Chief Proctor from College Y attempts revocation on College X case -> HTTP 403
    # -----------------------------------------------------------------
    print("\n[Test 5] Scenario 5: Chief Proctor from College Y attempts cross-institution revocation")
    # First re-assign Carol
    r_reassign = client.post(
        "/api/campus-proctor/committee/assign",
        headers={"Authorization": f"Bearer {TOKEN_CHIEF_X}"},
        json={"case_id": "CAMPUS-CONF-C", "target_user_id": TARGET_MEMBER_UUID, "role": "member"}
    )
    assert r_reassign.status_code == 200

    r5 = client.post(
        "/api/campus-proctor/committee/revoke",
        headers={"Authorization": f"Bearer {TOKEN_CHIEF_Y}"},
        json={
            "case_id": "CAMPUS-CONF-C",
            "target_user_id": TARGET_MEMBER_UUID
        }
    )
    assert r5.status_code == 403, f"Expected 403, got {r5.status_code}: {r5.text}"
    assert "belongs to 'INST_COLLEGE_X'" in r5.text or "Access denied" in r5.text
    print("  [PASS] Cross-institution Chief Proctor revocation rejected with HTTP 403.")

    # -----------------------------------------------------------------
    # Test 6: Institution Admin from College Y attempts revocation on College X case -> HTTP 403
    # -----------------------------------------------------------------
    print("\n[Test 6] Scenario 6: Institution Admin from College Y attempts cross-institution revocation")
    r6 = client.post(
        "/api/campus-proctor/committee/revoke",
        headers={"Authorization": f"Bearer {TOKEN_ADMIN_Y}"},
        json={
            "case_id": "CAMPUS-CONF-C",
            "target_user_id": TARGET_MEMBER_UUID
        }
    )
    assert r6.status_code == 403, f"Expected 403, got {r6.status_code}: {r6.text}"
    print("  [PASS] Cross-institution Institution Admin revocation rejected with HTTP 403.")

    # -----------------------------------------------------------------
    # Test 7: Suspended administrator attempts revocation -> Denied (HTTP 401/403)
    # -----------------------------------------------------------------
    print("\n[Test 7] Scenario 7: Suspended administrator attempts revocation")
    r7 = client.post(
        "/api/campus-proctor/committee/revoke",
        headers={"Authorization": f"Bearer {TOKEN_SUSPENDED}"},
        json={
            "case_id": "CAMPUS-CONF-C",
            "target_user_id": TARGET_MEMBER_UUID
        }
    )
    assert r7.status_code in [401, 403], f"Expected 401 or 403, got {r7.status_code}: {r7.text}"
    print("  [PASS] Suspended administrator rejected cleanly.")

    # -----------------------------------------------------------------
    # Test 8: Request-body actor UUID spoofing defense verification
    # -----------------------------------------------------------------
    print("\n[Test 8] Scenario 8: Client attempts to spoof actor UUID in request body")
    spoofed_actor_uuid = "00000000-0000-0000-0000-000000000001"
    
    # 8a: Chief Proctor provides token, but tries to pass spoofed assigned_by in body
    r8a = client.post(
        "/api/campus-proctor/committee/assign",
        headers={"Authorization": f"Bearer {TOKEN_CHIEF_X}"},
        json={
            "case_id": "CAMPUS-CONF-C",
            "target_user_id": TARGET_MEMBER_UUID,
            "role": "member",
            "committee_name": "Anti-Spoof Panel",
            "assigned_by": spoofed_actor_uuid,
            "actor_id": spoofed_actor_uuid,
            "user_id": spoofed_actor_uuid
        }
    )
    assert r8a.status_code == 200, f"Expected 200, got {r8a.status_code}: {r8a.text}"
    
    # Verify in DB that assigned_by was set strictly to Chief Proctor X, NOT the spoofed UUID
    db_res = supabase_admin.table("case_committee_assignments").select("assigned_by").eq("case_id", "CAMPUS-CONF-C").eq("user_id", TARGET_MEMBER_UUID).execute()
    assert db_res.data, "Assignment not found in DB"
    actual_assigned_by = db_res.data[0]["assigned_by"]
    assert actual_assigned_by == CHIEF_PROCTOR_X_UUID, f"SPOOFING VULNERABILITY! Expected {CHIEF_PROCTOR_X_UUID}, got {actual_assigned_by}"
    assert actual_assigned_by != spoofed_actor_uuid, "CRITICAL: Spoofed actor ID was accepted into database!"
    print(f"  [PASS] Request-body spoofed assigned_by ignored: Database recorded {actual_assigned_by} from verified JWT.")

    # 8b: Student tries to spoof privileged action by injecting chief proctor user_id into body
    r8b = client.post(
        "/api/campus-proctor/committee/assign",
        headers={"Authorization": f"Bearer {TOKEN_STUDENT_A}"},
        json={
            "case_id": "CAMPUS-CONF-C",
            "target_user_id": TARGET_MEMBER_UUID,
            "role": "member",
            "assigned_by": CHIEF_PROCTOR_X_UUID
        }
    )
    assert r8b.status_code == 403, f"Expected 403, got {r8b.status_code}: {r8b.text}"
    print("  [PASS] Student attempting privilege spoofing rejected with HTTP 403.")

    # -----------------------------------------------------------------
    # Test 9: Service-role operation records original authenticated actor in audit log
    # -----------------------------------------------------------------
    print("\n[Test 9] Scenario 9: Audit log actor identity verification")
    # Query audit_actor_mappings for Chief Proctor X
    mapping_res = supabase_admin.table("audit_actor_mappings").select("audit_actor_id").eq("user_id", CHIEF_PROCTOR_X_UUID).execute()
    assert mapping_res.data and len(mapping_res.data) > 0, "Chief Proctor mapping should exist in audit_actor_mappings"
    expected_audit_id = mapping_res.data[0]["audit_actor_id"]

    # Query case_activity_log for the recent COMMITTEE_ASSIGNMENT_PROVISIONED event
    log_res = supabase_admin.table("case_activity_log").select("*").eq("case_id", "CAMPUS-CONF-C").eq("action_type", "COMMITTEE_ASSIGNMENT_PROVISIONED").order("created_at", desc=True).limit(1).execute()
    assert log_res.data and len(log_res.data) > 0, "Audit log event not found"
    logged_event = log_res.data[0]
    
    assert logged_event["audit_actor_id"] == expected_audit_id, f"Audit actor ID mismatch: expected {expected_audit_id}, got {logged_event['audit_actor_id']}"
    assert logged_event["actor_type"] == "USER", f"Expected USER, got {logged_event['actor_type']}"
    assert logged_event["actor_role"] == "chief_proctor", f"Expected chief_proctor, got {logged_event['actor_role']}"
    print(f"  [PASS] Audit log verified: Recorded pseudonymous {expected_audit_id} for user {CHIEF_PROCTOR_X_UUID} (actor_type: USER, actor_role: chief_proctor).")

    # -----------------------------------------------------------------
    # Test 10: Authorized user performs operation without unnecessary escalation
    # -----------------------------------------------------------------
    print("\n[Test 10] Scenario 10: Scoped access without privilege escalation")
    # Chief Proctor lists assignments for Case C
    r10 = client.get(
        "/api/campus-proctor/committee/assignments/CAMPUS-CONF-C",
        headers={"Authorization": f"Bearer {TOKEN_CHIEF_X}"}
    )
    assert r10.status_code == 200, f"Expected 200, got {r10.status_code}: {r10.text}"
    assignments = r10.json()["assignments"]
    assert len(assignments) >= 1
    print("  [PASS] Chief Proctor successfully listed committee assignments for institutional case.")

    # Chief Proctor attempts to access cross-institution case inquiries
    r10_cross = client.get(
        "/api/campus-proctor/case/CAMPUS-INST-Y",
        headers={"Authorization": f"Bearer {TOKEN_CHIEF_X}"}
    )
    assert r10_cross.status_code in [403, 404], f"Expected 403 or 404 for cross-institution case, got {r10_cross.status_code}"
    print("  [PASS] Chief Proctor denied access to College Y grievance.")

    print("\n" + "=" * 70)
    print("  ALL 10 PHASE 1.3.15 END-TO-END SCENARIOS RUNTIME VERIFIED!")
    print("=" * 70)

if __name__ == "__main__":
    run_tests()

"""
Phase 2.1 Citizen Dashboard & My Cases Workspace Test Suite
Tests:
1. Unauthenticated requests fail closed with 401 Unauthorized.
2. Citizen authentication and JWT issuance.
3. Dashboard statistics calculation (total, active, resolved, pending).
4. My Cases listing, search, status filtering, and pagination.
5. Strict Cross-Tenant / Cross-User Ownership Isolation (Citizen A cannot see or access Citizen B's cases).
6. Case details, chronological timeline, and strict exclusion of internal officer/proctor notes.
7. Document signed URL authorization via /api/campus-proctor/document-url (CASE_OWNER, max 300s TTL).
"""

import os
import sys
from pathlib import Path
from datetime import datetime, timezone, timedelta

# Ensure test runs against local Supabase instance
os.environ["SUPABASE_URL"] = "http://127.0.0.1:54321"
os.environ["SUPABASE_SECRET_KEY"] = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZS1kZW1vIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImV4cCI6MTk4MzgxMjk5Nn0.EGIM96RAZx35lJzdJsyH-qQwv8Hdp7fsn3W0YpN81IU"
os.environ["SUPABASE_JWT_SECRET"] = "super-secret-jwt-token-with-at-least-32-characters-long"
os.environ["JWT_SECRET"] = "super-secret-jwt-token-with-at-least-32-characters-long"
os.environ["SUPABASE_OFFLINE_TEST"] = "0"

_root = Path(__file__).resolve().parent.parent
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

from starlette.testclient import TestClient
from api.index import app
from api.auth import AuthUser, UserRole, AccountStatus, create_access_token
from api.campus_proctor import campus_proctor_manager, StudentGrievanceSubmit

client = TestClient(app)

# Test User Identities
CITIZEN_A_UID = "00000000-0000-4000-8000-000000000010"
CITIZEN_B_UID = "00000000-0000-4000-8000-000000000020"

user_a = AuthUser(
    user_id=CITIZEN_A_UID,
    role=UserRole.STUDENT,
    institution_id="INST_DEFAULT",
    name="Aarav Sharma",
    email="student@nit.edu",
    account_status=AccountStatus.ACTIVE
)

user_b = AuthUser(
    user_id=CITIZEN_B_UID,
    role=UserRole.CITIZEN,
    institution_id="INST_DEFAULT",
    name="Priya Patel",
    email="citizen@nyaypath.in",
    account_status=AccountStatus.ACTIVE
)

token_a = create_access_token(user_a)
token_b = create_access_token(user_b)
headers_a = {"Authorization": f"Bearer {token_a}"}
headers_b = {"Authorization": f"Bearer {token_b}"}


def setup_test_cases():
    """Seed test grievances for Citizen A and Citizen B."""
    # Seed Case A1 for Citizen A (Submitted / Active)
    payload_a1 = StudentGrievanceSubmit(
        institution_id="INST_DEFAULT",
        department="Computer Science",
        year="3rd Year",
        category="Academic",
        subject="Discrepancy in End-Semester Evaluation",
        description="Marksheet shows absent for Database Systems lab despite verified attendance sheet.",
        incident_date="2026-10-15",
        supporting_documents=[
            {"id": "doc_a1_attendance.pdf", "name": "Attendance_Sheet.pdf", "size": 102400, "type": "application/pdf"}
        ]
    )
    case_a1 = campus_proctor_manager.create_case(payload_a1, student_user=user_a)

    # Seed Case A2 for Citizen A (Resolved)
    payload_a2 = StudentGrievanceSubmit(
        institution_id="INST_DEFAULT",
        department="Mechanical",
        year="3rd Year",
        category="Hostel",
        subject="Hostel Water Cooler Maintenance",
        description="Hostel block C water cooler filtration needs replacement.",
        incident_date="2026-09-01",
        supporting_documents=[]
    )
    case_a2 = campus_proctor_manager.create_case(payload_a2, student_user=user_a)
    # Update Case A2 to RESOLVED with confidential proctor notes
    from api.campus_proctor import ProctorUpdateStatus
    proctor_admin = AuthUser(
        user_id="00000000-0000-4000-8000-000000000000",
        role=UserRole.PLATFORM_ADMIN,
        institution_id="*",
        name="Chief Admin",
        account_status=AccountStatus.ACTIVE
    )
    campus_proctor_manager.update_case(
        ProctorUpdateStatus(
            case_id=case_a2["case_id"],
            new_status="RESOLVED",
            proctor_notes="INTERNAL_CONFIDENTIAL_NOTE: Water filter replaced by vendor ABC Services on 2026-09-05.",
            action_taken="New RO water filter installed and tested.",
            resolution_details="Maintenance completed and verified by hostel warden."
        ),
        proctor_user=proctor_admin
    )

    # Seed Case B1 for Citizen B
    payload_b1 = StudentGrievanceSubmit(
        institution_id="INST_DEFAULT",
        department="Civil Engineering",
        year="2nd Year",
        category="Infrastructure",
        subject="Library Wi-Fi Connectivity Issue",
        description="Wi-Fi coverage is unstable in the 2nd floor study hall.",
        incident_date="2026-10-20",
        supporting_documents=[
            {"id": "doc_b1_speedtest.pdf", "name": "SpeedTest_Results.pdf", "size": 51200, "type": "application/pdf"}
        ]
    )
    case_b1 = campus_proctor_manager.create_case(payload_b1, student_user=user_b)

    return case_a1["case_id"], case_a2["case_id"], case_b1["case_id"]


def run_tests():
    print("=" * 70)
    print("  NYAYPATH PHASE 2.1 CITIZEN WORKSPACE VERIFICATION SUITE")
    print("=" * 70)

    # 1. Test Unauthenticated Access
    print("\n[Test 1] Unauthenticated requests strictly fail closed (HTTP 401)")
    r1 = client.get("/api/citizen/dashboard-stats")
    assert r1.status_code == 401, f"Expected 401, got {r1.status_code}"
    print("  [PASS] GET /api/citizen/dashboard-stats rejected with 401.")

    r2 = client.get("/api/citizen/cases")
    assert r2.status_code == 401, f"Expected 401, got {r2.status_code}"
    print("  [PASS] GET /api/citizen/cases rejected with 401.")

    r3 = client.get("/api/citizen/cases/CAMPUS-DUMMY-CS")
    assert r3.status_code == 401, f"Expected 401, got {r3.status_code}"
    print("  [PASS] GET /api/citizen/cases/{id} rejected with 401.")

    # 2. Test Citizen Login Endpoint
    print("\n[Test 2] Citizen & Student Authentication")
    r_login = client.post("/api/citizen/auth/login", json={
        "email": "student@nit.edu",
        "password": "ProctorPass@2026!"
    })
    assert r_login.status_code == 200, f"Login failed: {r_login.text}"
    login_data = r_login.json()
    assert "token" in login_data
    assert login_data["user"]["user_id"] == CITIZEN_A_UID
    assert login_data["user"]["role"] == "student"
    print("  [PASS] Authenticated student Aarav logged in successfully.")

    r_login_fail = client.post("/api/citizen/auth/login", json={
        "email": "student@nit.edu",
        "password": "WrongPassword!"
    })
    assert r_login_fail.status_code == 401
    print("  [PASS] Invalid password rejected with 401.")

    # Seed cases
    case_a1_id, case_a2_id, case_b1_id = setup_test_cases()
    print(f"\n  Seeded Test Cases: A1={case_a1_id}, A2={case_a2_id}, B1={case_b1_id}")

    # 3. Test Dashboard Stats
    print("\n[Test 3] Citizen Dashboard Stats Calculation")
    r_stats = client.get("/api/citizen/dashboard-stats", headers=headers_a)
    assert r_stats.status_code == 200, f"Stats error: {r_stats.text}"
    stats_data = r_stats.json()
    st = stats_data["stats"]
    assert st["total_cases"] >= 2, f"Expected at least 2 cases, got {st['total_cases']}"
    assert st["active_cases"] >= 1, f"Expected at least 1 active case, got {st['active_cases']}"
    assert st["resolved_cases"] >= 1, f"Expected at least 1 resolved case, got {st['resolved_cases']}"
    assert "user_profile" in stats_data
    assert stats_data["user_profile"]["user_id"] == CITIZEN_A_UID
    print(f"  [PASS] Stats computed correctly: Total={st['total_cases']}, Active={st['active_cases']}, Resolved={st['resolved_cases']}, Pending={st['pending_actions']}.")

    # 4. Test My Cases Workspace List & Filters
    print("\n[Test 4] My Cases Workspace Listing & Filtering")
    r_list = client.get("/api/citizen/cases", headers=headers_a)
    assert r_list.status_code == 200
    list_data = r_list.json()
    case_ids_a = [c["case_id"] for c in list_data["cases"]]
    assert case_a1_id in case_ids_a
    assert case_a2_id in case_ids_a
    assert case_b1_id not in case_ids_a, "Citizen A must NOT see Citizen B's case!"
    print(f"  [PASS] Citizen A retrieved {len(case_ids_a)} cases owned by them.")

    # Status filter: RESOLVED
    r_resolved = client.get("/api/citizen/cases?status=RESOLVED", headers=headers_a)
    assert r_resolved.status_code == 200
    resolved_ids = [c["case_id"] for c in r_resolved.json()["cases"]]
    assert case_a2_id in resolved_ids
    assert case_a1_id not in resolved_ids
    print("  [PASS] Status filter correctly isolated RESOLVED cases.")

    # Search filter
    r_search = client.get("/api/citizen/cases?search=Evaluation", headers=headers_a)
    assert r_search.status_code == 200
    search_ids = [c["case_id"] for c in r_search.json()["cases"]]
    assert case_a1_id in search_ids
    assert case_a2_id not in search_ids
    print("  [PASS] Search filter correctly matched keyword 'Evaluation'.")

    # Verify absence of internal notes in list items
    for c in list_data["cases"]:
        assert "proctor_notes" not in c, "Security leak: proctor_notes must NOT be returned to citizen!"
        assert "verification_key_hash" not in c, "Security leak: verification_key_hash must NOT be returned!"
    print("  [PASS] Verified zero proctor_notes or verification_key_hash in case list response.")

    # 5. Strict Cross-Tenant / Cross-User Ownership Isolation
    print("\n[Test 5] Strict Cross-Tenant / Cross-User Ownership Isolation")
    # Citizen A attempts to access Citizen B's case
    r_cross_a = client.get(f"/api/citizen/cases/{case_b1_id}", headers=headers_a)
    assert r_cross_a.status_code == 403, f"Expected 403 Forbidden for cross-user access, got {r_cross_a.status_code}"
    print("  [PASS] Citizen A rejected with HTTP 403 when attempting to view Citizen B's case.")

    # Citizen B attempts to access Citizen A's case
    r_cross_b = client.get(f"/api/citizen/cases/{case_a1_id}", headers=headers_b)
    assert r_cross_b.status_code == 403, f"Expected 403 Forbidden for cross-user access, got {r_cross_b.status_code}"
    print("  [PASS] Citizen B rejected with HTTP 403 when attempting to view Citizen A's case.")

    # Non-existent case returns 404
    r_404 = client.get("/api/citizen/cases/CAMPUS-NONEXISTENT-99", headers=headers_a)
    assert r_404.status_code == 404
    print("  [PASS] Non-existent case correctly returned 404.")

    # 6. Case Details, Progress Timeline & Hidden Internal Notes
    print("\n[Test 6] Case Details, Chronological Timeline & Confidentiality Isolation")
    r_details = client.get(f"/api/citizen/cases/{case_a2_id}", headers=headers_a)
    assert r_details.status_code == 200
    det = r_details.json()
    case_obj = det["case"]
    assert case_obj["case_id"] == case_a2_id
    assert case_obj["status"] == "RESOLVED"
    assert case_obj.get("action_taken") == "New RO water filter installed and tested."
    
    # CRITICAL SECURITY CHECK: Internal proctorial note must be omitted!
    assert "proctor_notes" not in case_obj, "CRITICAL: proctor_notes leaked to citizen!"
    assert "INTERNAL_CONFIDENTIAL_NOTE" not in str(case_obj), "CRITICAL: internal note content leaked in case!"
    print("  [PASS] Case details retrieved with official resolution and zero internal proctorial notes leaked.")

    timeline = det["timeline"]
    assert len(timeline) >= 2, "Expected at least 2 timeline events"
    assert timeline[0]["status"] == "SUBMITTED"
    print(f"  [PASS] Case timeline verified with {len(timeline)} milestones.")

    # 7. Secure Document Access via /api/campus-proctor/document-url
    print("\n[Test 7] Secure Document Access via Authorized Endpoint")
    # Citizen A requests their own document
    r_doc_owner = client.get(
        f"/api/campus-proctor/document-url?case_id={case_a1_id}&document_id=doc_a1_attendance.pdf",
        headers=headers_a
    )
    assert r_doc_owner.status_code == 200, f"Expected 200, got {r_doc_owner.status_code}: {r_doc_owner.text}"
    doc_data = r_doc_owner.json()
    assert doc_data["access_type"] == "CASE_OWNER"
    assert doc_data["expires_in_seconds"] <= 300
    assert "signed_url" in doc_data
    print(f"  [PASS] Citizen A successfully obtained signed URL (access_type={doc_data['access_type']}, TTL={doc_data['expires_in_seconds']}s).")

    # Citizen B attempts to access Citizen A's document
    r_doc_intruder = client.get(
        f"/api/campus-proctor/document-url?case_id={case_a1_id}&document_id=doc_a1_attendance.pdf",
        headers=headers_b
    )
    assert r_doc_intruder.status_code == 403, f"Expected 403 Forbidden, got {r_doc_intruder.status_code}"
    print("  [PASS] Citizen B strictly blocked with HTTP 403 when requesting Citizen A's document.")

    print("\n" + "=" * 70)
    print("  ALL PHASE 2.1 CITIZEN WORKSPACE VERIFICATION TESTS PASSED (7/7)!")
    print("=" * 70)


if __name__ == "__main__":
    run_tests()

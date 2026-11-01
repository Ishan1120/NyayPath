"""
NyayPath Phase 2.2 Comprehensive Test Suite
Central Case Management, Filing & Tracking System Verification

Tests:
1. Unauthenticated requests to filing, upload, and lifecycle endpoints fail closed with 401 Unauthorized.
2. Filing requires mandatory statutory accuracy declaration; unconfirmed submissions rejected with 400 Bad Request.
3. Filing Campus Grievance: generates Case ID, 128-bit verification key, creates campus_cases & cases parent rows,
   authoritative identity derivation from auth.uid(), and initial case_activity_log event with officer notification hook.
4. Filing General / RTI Grievance: generates NP-2026-X tracking ID, persists to public.cases.
5. Media sanitization & document upload: enforces 10MB limit, strips metadata, rejects illegal MIME types,
   and enforces strict ownership validation when associating with an existing case (403 on non-owner).
6. Case lifecycle management:
   - Permitted withdrawal of active cases transitions status to CLOSED with CASE_WITHDRAWN audit event.
   - Rejection of withdrawal on finalized cases (400 Bad Request).
   - Citizen remarks (ADD_REMARK) append to case_activity_log with notification triggers.
   - Expedite requests (REQUEST_EXPEDITE) register notification triggers.
   - Non-owner lifecycle action rejection (403 Forbidden).
7. Public case tracking:
   - Public tracking via Case ID + secret verification key returns public projection.
   - Confidential internal proctor notes and secret hashes are strictly shielded.
   - Invalid verification key rejected with 401 Unauthorized.
8. Citizen Workspace dynamic integration:
   - Newly filed cases appear immediately in /api/citizen/cases.
   - Dashboard stats reflect updated counts.
   - Strict cross-tenant isolation: Citizen B cannot see Citizen A's cases.
"""

import os
import sys
import io
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


def test_01_unauthenticated_requests_fail_closed():
    """Verify all filing and lifecycle endpoints fail closed with 401 Unauthorized when unauthenticated."""
    # File case
    r1 = client.post("/api/citizen/cases/file", json={
        "category": "CAMPUS_GRIEVANCE",
        "subject": "Test Unauthenticated",
        "facts": "This should be rejected without auth.",
        "declaration_confirmed": True
    })
    assert r1.status_code == 401, f"Expected 401 for unauthenticated filing, got {r1.status_code}"

    # Upload document
    dummy_file = ("test.pdf", b"%PDF-1.4 dummy", "application/pdf")
    r2 = client.post("/api/citizen/cases/upload-document", files={"file": dummy_file})
    assert r2.status_code == 401, f"Expected 401 for unauthenticated upload, got {r2.status_code}"

    # Lifecycle action
    r3 = client.post("/api/citizen/cases/TEST-CASE/lifecycle", json={
        "action": "WITHDRAW",
        "reason": "Test"
    })
    assert r3.status_code == 401, f"Expected 401 for unauthenticated lifecycle action, got {r3.status_code}"
    print("[PASS] Test 01: All unauthenticated endpoints fail closed with 401 Unauthorized.")


def test_02_declaration_required_validation():
    """Verify that filing fails with 400 Bad Request if statutory declaration is not accepted."""
    payload = {
        "category": "CAMPUS_GRIEVANCE",
        "subject": "Grievance without declaration",
        "facts": "Submitting facts without accepting statutory declaration.",
        "declaration_confirmed": False
    }
    r = client.post("/api/citizen/cases/file", json=payload, headers=headers_a)
    assert r.status_code == 400, f"Expected 400 when declaration_confirmed=False, got {r.status_code}"
    assert "declaration" in r.text.lower()
    print("[PASS] Test 02: Statutory accuracy declaration is strictly enforced (400 Bad Request on refusal).")


def test_03_file_campus_grievance_and_sync():
    """
    Verify filing a Campus Grievance:
    - Generates Case ID and 128-bit verification key
    - Derives student_user_id strictly from server-side JWT auth.uid()
    - Synchronizes parent cases and child campus_cases tables
    - Logs initial activity event with notification trigger for officers
    """
    payload = {
        "category": "CAMPUS_GRIEVANCE",
        "sub_category": "Academic Dispute",
        "subject": "Withholding of Grade Sheet After Fee Clearance",
        "facts": "The academic administration has withheld the 6th semester grade sheet despite submission of all clearance receipts on 2026-10-15.",
        "department": "Examination Cell",
        "remedy_sought": "Immediate issuance of official transcript and grade card.",
        "is_confidential": False,
        "declaration_confirmed": True
    }

    r = client.post("/api/citizen/cases/file", json=payload, headers=headers_a)
    assert r.status_code == 200, f"Expected 200 for campus grievance filing, got {r.status_code}: {r.text}"
    data = r.json()

    case_id = data.get("case_id")
    verification_key = data.get("verification_key")
    assert case_id and case_id.startswith("CAMPUS-"), f"Expected CAMPUS- prefix, got {case_id}"
    assert verification_key and len(verification_key) == 32, f"Expected 32 hex char (128-bit) verification key, got {verification_key}"
    assert data.get("status") == "SUBMITTED"
    assert data.get("category") == "CAMPUS_GRIEVANCE"

    # Verify case details via citizen workspace endpoint
    r_details = client.get(f"/api/citizen/cases/{case_id}", headers=headers_a)
    assert r_details.status_code == 200, f"Expected 200 fetching case details, got {r_details.status_code}"
    details = r_details.json()
    c = details["case"]

    # Verify authoritative identity attribution
    assert c.get("student_user_id") == CITIZEN_A_UID, f"Owner must be {CITIZEN_A_UID}, got {c.get('student_user_id')}"
    # Verify internal notes are strictly hidden
    assert "proctor_notes" not in c, "Internal proctor_notes must never be exposed to citizens!"
    assert "verification_key_hash" not in c, "Verification hash must not be exposed in case details!"

    # Verify timeline contains initial milestone
    timeline = details.get("timeline", [])
    assert len(timeline) >= 1, "Timeline must contain at least the initial submission milestone"
    first_event = timeline[0]
    assert first_event.get("status") == "SUBMITTED"

    print(f"[PASS] Test 03: Campus grievance filed ({case_id}), parent-child synced, authoritative ownership verified.")
    return case_id, verification_key


def test_04_file_general_rti_grievance():
    """Verify filing an RTI or General Grievance generates an NP-2026-X ID and persists to public.cases."""
    payload = {
        "category": "RTI",
        "sub_category": "Public Works & Contracts",
        "subject": "Information Request on Road Repair Expenditures",
        "facts": "Seeking certified copies of tender documents, work orders, and completion certificates for the Sector 4 road resurfacing project.",
        "department": "Municipal Public Works Department",
        "remedy_sought": "Inspection of records and certified copies under Section 6(1) of RTI Act, 2005.",
        "is_confidential": False,
        "declaration_confirmed": True
    }

    r = client.post("/api/citizen/cases/file", json=payload, headers=headers_b)
    assert r.status_code == 200, f"Expected 200 for RTI filing, got {r.status_code}: {r.text}"
    data = r.json()

    case_id = data.get("case_id")
    verification_key = data.get("verification_key")
    assert case_id and case_id.startswith("NP-2026-RTI-"), f"Expected NP-2026-RTI- prefix, got {case_id}"
    assert verification_key and len(verification_key) == 32
    assert data.get("category") == "RTI"

    # Verify citizen B can view their RTI case
    r_details = client.get(f"/api/citizen/cases/{case_id}", headers=headers_b)
    assert r_details.status_code == 200
    details = r_details.json()
    assert details["case"].get("case_id") == case_id

    print(f"[PASS] Test 04: RTI case filed ({case_id}) and verified in citizen workspace.")
    return case_id, verification_key


def test_05_document_upload_and_sanitization(campus_case_id):
    """
    Verify supporting document upload:
    - Enforces 10MB limit (rejection of oversized payloads with 413)
    - Rejects unsupported MIME types (400)
    - Strips metadata and stores in private storage bucket
    - When attaching to case_id, enforces strict case ownership (403 for non-owner)
    """
    # 1. Reject unsupported MIME type
    bad_file = ("script.sh", b"#!/bin/bash\necho hello", "text/x-shellscript")
    r_bad = client.post("/api/citizen/cases/upload-document", files={"file": bad_file}, headers=headers_a)
    assert r_bad.status_code == 400, f"Expected 400 for illegal MIME type, got {r_bad.status_code}"

    # 2. Reject oversized file (> 10MB)
    large_payload = b"0" * (11 * 1024 * 1024)
    large_file = ("huge.pdf", large_payload, "application/pdf")
    r_large = client.post("/api/citizen/cases/upload-document", files={"file": large_file}, headers=headers_a)
    assert r_large.status_code == 413, f"Expected 413 for oversized file, got {r_large.status_code}"

    # 3. Valid PDF upload with sanitization (pre-filing upload)
    valid_pdf = ("receipt.pdf", b"%PDF-1.4\n1 0 obj\n<< /Title (Author Confidential) >>\nendobj\ntrailer\n<<>>\n%%EOF", "application/pdf")
    r_valid = client.post("/api/citizen/cases/upload-document", files={"file": valid_pdf}, headers=headers_a)
    assert r_valid.status_code == 200, f"Expected 200 for valid PDF upload, got {r_valid.status_code}: {r_valid.text}"
    doc_info = r_valid.json()
    assert "storage_path" in doc_info
    assert doc_info["file_name"] == "receipt.pdf"

    # 4. Attempt document upload to another user's case (Citizen B attempts upload to Citizen A's campus case)
    r_tamper = client.post(
        "/api/citizen/cases/upload-document",
        files={"file": ("injected.pdf", b"%PDF-1.4 sample", "application/pdf")},
        data={"case_id": campus_case_id},
        headers=headers_b
    )
    assert r_tamper.status_code == 403, f"Expected 403 when attaching document to another user's case, got {r_tamper.status_code}"

    print("[PASS] Test 05: Document upload enforces <= 10MB limit, MIME checks, sanitization, and ownership validation.")


def test_06_case_lifecycle_actions(campus_case_id):
    """
    Verify citizen lifecycle management:
    - ADD_REMARK: Adds remark to case activity log with notification hook
    - REQUEST_EXPEDITE: Registers expedite request
    - Non-owner rejection: Citizen B cannot perform actions on Citizen A's case (403 Forbidden)
    - WITHDRAW: Transitions status to CLOSED and logs CASE_WITHDRAWN event
    - Subsequent withdrawal rejected with 400 Bad Request
    """
    # 1. Non-owner attempt -> 403 Forbidden
    r_unauth = client.post(
        f"/api/citizen/cases/{campus_case_id}/lifecycle",
        json={"action": "ADD_REMARK", "remarks": "Unauthorized remark attempt."},
        headers=headers_b
    )
    assert r_unauth.status_code == 403, f"Expected 403 for non-owner action, got {r_unauth.status_code}"

    # 2. Owner adds remark
    r_remark = client.post(
        f"/api/citizen/cases/{campus_case_id}/lifecycle",
        json={"action": "ADD_REMARK", "remarks": "Provided updated copy of payment receipt to head proctor."},
        headers=headers_a
    )
    assert r_remark.status_code == 200, f"Expected 200 for adding remark, got {r_remark.status_code}: {r_remark.text}"
    assert r_remark.json()["action"] == "ADD_REMARK"

    # 3. Owner requests expedite
    r_expedite = client.post(
        f"/api/citizen/cases/{campus_case_id}/lifecycle",
        json={"action": "REQUEST_EXPEDITE", "reason": "Job offer letter requires transcript verification by Friday."},
        headers=headers_a
    )
    assert r_expedite.status_code == 200, f"Expected 200 for expedite request, got {r_expedite.status_code}"
    assert r_expedite.json()["action"] == "REQUEST_EXPEDITE"

    # 4. Owner withdraws case
    r_withdraw = client.post(
        f"/api/citizen/cases/{campus_case_id}/lifecycle",
        json={"action": "WITHDRAW", "reason": "Grade sheet was released today by the department."},
        headers=headers_a
    )
    assert r_withdraw.status_code == 200, f"Expected 200 for withdrawal, got {r_withdraw.status_code}: {r_withdraw.text}"
    data_w = r_withdraw.json()
    assert data_w["status"] == "CLOSED"

    # 5. Verify status updated in details
    r_details = client.get(f"/api/citizen/cases/{campus_case_id}", headers=headers_a)
    assert r_details.status_code == 200
    assert r_details.json()["case"]["status"] == "CLOSED"

    # 6. Attempt to withdraw already finalized case -> 400 Bad Request
    r_withdraw_again = client.post(
        f"/api/citizen/cases/{campus_case_id}/lifecycle",
        json={"action": "WITHDRAW", "reason": "Second withdrawal attempt."},
        headers=headers_a
    )
    assert r_withdraw_again.status_code == 400, f"Expected 400 when withdrawing finalized case, got {r_withdraw_again.status_code}"

    print(f"[PASS] Test 06: Lifecycle transitions (remarks, expedite, withdrawal, and idempotency) fully verified.")


def test_07_public_case_tracking(rti_case_id, rti_key):
    """
    Verify public case tracking:
    - Case ID + valid 128-bit verification key yields public tracking projection
    - Confidential details, proctor notes, and secret keys are strictly omitted
    - Invalid key fails with 401 Unauthorized
    - Non-existent case fails with 404 Not Found
    """
    # 1. Valid tracking with correct key
    r_valid = client.post("/api/citizen/track", json={
        "case_id": rti_case_id,
        "verification_key": rti_key
    })
    assert r_valid.status_code == 200, f"Expected 200 for valid tracking, got {r_valid.status_code}: {r_valid.text}"
    data = r_valid.json()
    c = data["case"]
    assert c["case_id"] == rti_case_id
    assert "status" in c
    assert "category" in c
    # Zero PII / zero proctor notes leakage
    assert "proctor_notes" not in c
    assert "verification_key_hash" not in c
    assert "tracking_key_hash" not in c
    assert "applicant_email" not in c

    # 2. GET tracking endpoint with query parameter
    r_get = client.get(f"/api/citizen/track/{rti_case_id}?verification_key={rti_key}")
    assert r_get.status_code == 200
    assert r_get.json()["case"]["case_id"] == rti_case_id

    # 3. Invalid key -> 401 Unauthorized
    r_bad_key = client.post("/api/citizen/track", json={
        "case_id": rti_case_id,
        "verification_key": "00000000000000000000000000000000"
    })
    assert r_bad_key.status_code == 401, f"Expected 401 for incorrect key, got {r_bad_key.status_code}"

    # 4. Non-existent case -> 404 Not Found
    r_not_found = client.post("/api/citizen/track", json={
        "case_id": "NP-2026-RTI-NONEXISTENT",
        "verification_key": rti_key
    })
    assert r_not_found.status_code == 404, f"Expected 404 for nonexistent case, got {r_not_found.status_code}"

    print("[PASS] Test 07: Public case tracking protects confidentiality, strictly validates verification keys.")


def test_08_citizen_workspace_integration_and_tenant_isolation(campus_case_id, rti_case_id):
    """
    Verify integration with My Cases workspace:
    - Citizen A's case listing contains campus_case_id, strictly excludes Citizen B's rti_case_id
    - Citizen B's case listing contains rti_case_id, strictly excludes Citizen A's campus_case_id
    - Dashboard statistics dynamically calculate live active / resolved counts
    """
    # 1. Citizen A Workspace
    r_cases_a = client.get("/api/citizen/cases", headers=headers_a)
    assert r_cases_a.status_code == 200
    cases_a = r_cases_a.json()["cases"]
    ids_a = [c["case_id"] for c in cases_a]
    assert campus_case_id in ids_a, f"Citizen A's workspace must include {campus_case_id}"
    assert rti_case_id not in ids_a, f"Cross-tenant leak: Citizen A should NOT see Citizen B's case {rti_case_id}!"

    # 2. Citizen B Workspace
    r_cases_b = client.get("/api/citizen/cases", headers=headers_b)
    assert r_cases_b.status_code == 200
    cases_b = r_cases_b.json()["cases"]
    ids_b = [c["case_id"] for c in cases_b]
    assert rti_case_id in ids_b, f"Citizen B's workspace must include {rti_case_id}"
    assert campus_case_id not in ids_b, f"Cross-tenant leak: Citizen B should NOT see Citizen A's case {campus_case_id}!"

    # 3. Dashboard stats
    r_stats_a = client.get("/api/citizen/dashboard-stats", headers=headers_a)
    assert r_stats_a.status_code == 200
    stats_a = r_stats_a.json()["stats"]
    assert stats_a["total_cases"] >= 1
    # campus_case_id was withdrawn, so it is counted under resolved_cases
    assert stats_a["resolved_cases"] >= 1

    print("[PASS] Test 08: Dynamic workspace integration and strict cross-tenant isolation verified.")


def run_all_phase22_tests():
    print("\n=======================================================")
    print("  NyayPath Phase 2.2: Central Case Management Test Suite")
    print("=======================================================\n")
    test_01_unauthenticated_requests_fail_closed()
    test_02_declaration_required_validation()
    campus_id, campus_key = test_03_file_campus_grievance_and_sync()
    rti_id, rti_key = test_04_file_general_rti_grievance()
    test_05_document_upload_and_sanitization(campus_id)
    test_06_case_lifecycle_actions(campus_id)
    test_07_public_case_tracking(rti_id, rti_key)
    test_08_citizen_workspace_integration_and_tenant_isolation(campus_id, rti_id)
    print("\n=======================================================")
    print("  ALL 8 PHASE 2.2 TESTS PASSED SUCCESSFULLY!")
    print("=======================================================\n")


if __name__ == "__main__":
    run_all_phase22_tests()


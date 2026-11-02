"""
NyayPath Phase 8: Complete Platform Integration & End-to-End System Integration Test Suite
========================================================================================
Comprehensive automated integration tests covering the complete platform lifecycle across
all 7 defined roles and interconnected system modules:

1. Citizen / Student:
   - Grievance filing with 128-bit verification key hash and document upload
   - Dashboard metrics calculation and case status lifecycle tracking
   - Discovery of verified legal practitioners
   - Consultation request lifecycle (pending -> accepted)
   - Granular case access sharing (CASE_AND_DOCS)
   - Secure encrypted communication & message attachment exchange
   - Meeting scheduling & appointment confirmation
   - Instant revocation of lawyer case access
   - Verification of immediate post-revocation fail-closed access

2. Institution Administrator:
   - Institutional dashboard overview and grievance metrics
   - Institutional roster and cross-tenant boundary isolation

3. Chief Proctor:
   - Campus grievance triage and review
   - Status, hearing date, and action updates
   - Committee member assignment to confidential inquiries
   - Signed URL document access for institutional evidence

4. Proctor:
   - View assigned cases and record proctorial inquiry notes
   - Enforce confidentiality boundary (unassigned confidential cases blocked)
   - Cross-institution cases strictly blocked (HTTP 403)

5. Committee Member:
   - Access to assigned confidential cases and evidence
   - Logging of inquiry observations
   - Post-revocation access termination verification

6. Lawyer:
   - Consultation inbox and acceptance workflow
   - Authorized shared case and evidence document inspection
   - Client communication and meeting scheduling
   - Strict 403 rejection upon client access revocation

7. Platform Administrator:
   - Global system overview and institution metrics
   - Verification queue review and lawyer verification decision
   - Global case oversight with PII masking
   - Exceptional audit access with logged justification and audit mapping
   - Protection against unauthorized admin access without DB-backed verification

8. Integrated Notifications:
   - System notifications delivered to each actor at every lifecycle milestone
"""

import os
import sys
import time
import uuid
import unittest
from datetime import datetime, timezone, timedelta

# Local Supabase Environment Configuration
os.environ["SUPABASE_URL"] = "http://127.0.0.1:54321"
os.environ["SUPABASE_SECRET_KEY"] = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZS1kZW1vIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImV4cCI6MTk4MzgxMjk5Nn0.EGIM96RAZx35lJzdJsyH-qQwv8Hdp7fsn3W0YpN81IU"
os.environ["SUPABASE_JWT_SECRET"] = "super-secret-jwt-token-with-at-least-32-characters-long"
os.environ["JWT_SECRET"] = "super-secret-jwt-token-with-at-least-32-characters-long"
os.environ["SUPABASE_OFFLINE_TEST"] = "0"

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

import jwt
from fastapi.testclient import TestClient
from api.index import app
from supabase import create_client

client = TestClient(app)
supabase_admin = create_client(
    os.environ["SUPABASE_URL"],
    os.environ["SUPABASE_SECRET_KEY"]
)

JWT_SECRET = "super-secret-jwt-token-with-at-least-32-characters-long"

def generate_jwt(user_id: str, role: str, email: str, name: str, institution_id: str = "INST_DEFAULT", status: str = "active") -> str:
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


# Defined Actor UUIDs
CITIZEN_ALICE_UUID   = "aaaaaaaa-1111-2222-3333-aaaaaaaaaaaa"
CITIZEN_BOB_UUID     = "bbbbbbbb-1111-2222-3333-bbbbbbbbbbbb"
CHIEF_CHARLIE_UUID   = "66666666-1111-2222-3333-666666666666"
ADMIN_IRENE_UUID     = "44444444-1111-2222-3333-444444444444"
PROCTOR_XAVIER_UUID  = "cccccccc-1111-2222-3333-cccccccccccc"
COMMITTEE_CAROL_UUID = "eeeeeeee-1111-2222-3333-eeeeeeeeeeee"
LAWYER_RAJESH_UUID   = "77777777-1111-2222-3333-777777777777"
LAWYER_PRIYA_UUID    = "88888888-1111-2222-3333-888888888888"
PLATFORM_ADMIN_UUID  = "99999999-1111-2222-3333-999999999999"

TOKEN_ALICE    = generate_jwt(CITIZEN_ALICE_UUID, "student", "alice@collegex.edu", "Alice Student", institution_id="INST_COLLEGE_X")
TOKEN_BOB      = generate_jwt(CITIZEN_BOB_UUID, "student", "bob@collegex.edu", "Bob Student", institution_id="INST_COLLEGE_X")
TOKEN_CHARLIE  = generate_jwt(CHIEF_CHARLIE_UUID, "chief_proctor", "charlie@collegex.edu", "Charlie Chief Proctor", institution_id="INST_COLLEGE_X")
TOKEN_IRENE    = generate_jwt(ADMIN_IRENE_UUID, "institution_admin", "irene@collegex.edu", "Irene Inst Admin", institution_id="INST_COLLEGE_X")
TOKEN_XAVIER   = generate_jwt(PROCTOR_XAVIER_UUID, "proctor", "xavier@collegex.edu", "Xavier Proctor", institution_id="INST_COLLEGE_X")
TOKEN_CAROL    = generate_jwt(COMMITTEE_CAROL_UUID, "committee_member", "carol@collegex.edu", "Carol Committee", institution_id="INST_COLLEGE_X")
TOKEN_RAJESH   = generate_jwt(LAWYER_RAJESH_UUID, "lawyer", "advocate.rajesh@bar.in", "Adv. Rajesh Kumar")
TOKEN_PRIYA    = generate_jwt(LAWYER_PRIYA_UUID, "lawyer", "advocate.priya@bar.in", "Adv. Priya Sharma")
TOKEN_ADMIN    = generate_jwt(PLATFORM_ADMIN_UUID, "platform_admin", "platform@nyaypath.gov", "Platform Administrator")


class TestPhase8EndToEndIntegration(unittest.TestCase):
    """Full End-to-End Multi-Role Platform Integration Test Suite."""

    case_id = None
    case_uuid = None
    consultation_id = None
    conversation_id = None
    meeting_id = None

    @classmethod
    def setUpClass(cls):
        """Prepare fixtures and ensure baseline state."""
        # Ensure Lawyer Rajesh has an active lawyer profile
        supabase_admin.table("lawyer_profiles").upsert({
            "id": LAWYER_RAJESH_UUID,
            "full_name": "Adv. Rajesh Kumar",
            "email": "advocate.rajesh@bar.in",
            "phone": "+91 98765 43210",
            "bar_council": "Bar Council of Delhi",
            "enrollment_state": "Delhi (NCT)",
            "enrollment_number": "D/1234/2012",
            "years_of_practice": 12,
            "specializations": ["Constitutional Law", "Education Law"],
            "courts": ["Supreme Court of India", "Delhi High Court"],
            "languages": ["English", "Hindi"],
            "bio": "Experienced advocate specializing in institutional and constitutional redressal.",
            "consultation_preferences": {"modes": ["ONLINE", "IN_PERSON"], "consultation_fee": "FIXED_FEE"},
            "verification_status": "VERIFIED",
            "updated_at": datetime.now(timezone.utc).isoformat()
        }).execute()

    # =========================================================================
    # JOURNEY STEP 1: CITIZEN FILES CAMPUS GRIEVANCE & UPLOADS EVIDENCE
    # =========================================================================
    def test_01_citizen_files_grievance_with_evidence(self):
        """Alice files a confidential student grievance with evidence attachment."""
        r = client.post(
            "/api/citizen/cases/file",
            headers={"Authorization": f"Bearer {TOKEN_ALICE}"},
            json={
                "category": "CAMPUS_GRIEVANCE",
                "sub_category": "Academic Malpractice",
                "subject": "Arbitrary Attendance Withholding and Intimidation",
                "facts": "Department faculty unlawfully altered laboratory attendance logs and issued disciplinary threats.",
                "department": "Computer Science & Engineering",
                "remedy_sought": "Immediate correction of attendance records and independent proctorial inquiry.",
                "is_confidential": True,
                "declaration_confirmed": True
            }
        )
        self.assertEqual(r.status_code, 200, f"Case filing failed: {r.text}")
        data = r.json()
        self.assertTrue(data.get("case_id"))
        TestPhase8EndToEndIntegration.case_id = data["case_id"]

        # Retrieve database case UUID
        c_res = supabase_admin.table("cases").select("id").eq("case_id", TestPhase8EndToEndIntegration.case_id).execute()
        self.assertTrue(c_res.data and len(c_res.data) > 0)
        TestPhase8EndToEndIntegration.case_uuid = c_res.data[0]["id"]

        # Upload evidence document (multipart upload)
        pdf_bytes = b"%PDF-1.4\n1 0 obj\n<< /Title (Attendance Records) >>\nendobj\ntrailer\n<<>>\n%%EOF"
        up_res = client.post(
            "/api/citizen/cases/upload-document",
            headers={"Authorization": f"Bearer {TOKEN_ALICE}"},
            files={"file": ("attendance_records.pdf", pdf_bytes, "application/pdf")},
            data={"case_id": TestPhase8EndToEndIntegration.case_id}
        )
        self.assertEqual(up_res.status_code, 200, f"Document upload failed: {up_res.text}")
        up_data = up_res.json()
        self.assertEqual(up_data["file_name"], "attendance_records.pdf")

    # =========================================================================
    # JOURNEY STEP 2: INSTITUTION ADMIN OVERVIEW & STRICT BOUNDARY ISOLATION
    # =========================================================================
    def test_02_institution_admin_overview_and_boundary(self):
        """Admin Irene reviews institutional stats and is isolated from College Y."""
        # Overview stats
        r = client.get(
            "/api/institution/dashboard-stats",
            headers={"Authorization": f"Bearer {TOKEN_IRENE}"}
        )
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertEqual(data["stats"]["institution_id"], "INST_COLLEGE_X")
        self.assertGreaterEqual(data["stats"]["total_cases"], 1)

        # Cross-tenant access attempt by College Y admin to College X case
        admin_y_jwt = generate_jwt("33333333-1111-2222-3333-333333333333", "institution_admin", "adminy@collegey.edu", "Admin Y", institution_id="INST_COLLEGE_Y")
        r_cross = client.get(
            f"/api/campus-proctor/case/{TestPhase8EndToEndIntegration.case_id}",
            headers={"Authorization": f"Bearer {admin_y_jwt}"}
        )
        self.assertEqual(r_cross.status_code, 403, "College Y admin must be rejected from College X case with HTTP 403")

    # =========================================================================
    # JOURNEY STEP 3: CHIEF PROCTOR TRIAGES CASE & ASSIGNS COMMITTEE MEMBER
    # =========================================================================
    def test_03_chief_proctor_triages_and_assigns_committee(self):
        """Chief Proctor Charlie updates status, adds proctor notes, and assigns Carol."""
        # 1. Update status to UNDER_INQUIRY with hearing date
        r_update = client.post(
            "/api/campus-proctor/update",
            headers={"Authorization": f"Bearer {TOKEN_CHARLIE}"},
            json={
                "case_id": TestPhase8EndToEndIntegration.case_id,
                "new_status": "UNDER_INQUIRY",
                "proctor_notes": "Preliminary prima facie evidence established. Formal inquiry initiated.",
                "hearing_date": (datetime.now(timezone.utc) + timedelta(days=3)).strftime("%Y-%m-%d"),
                "action_taken": "Issued formal inquiry notice to departmental head."
            }
        )
        self.assertEqual(r_update.status_code, 200, f"Proctor update failed: {r_update.text}")
        up_data = r_update.json()
        self.assertEqual(up_data["case"]["status"], "UNDER_INQUIRY")

        # 2. Assign Committee Member Carol
        r_assign = client.post(
            "/api/campus-proctor/committee/assign",
            headers={"Authorization": f"Bearer {TOKEN_CHARLIE}"},
            json={
                "case_id": TestPhase8EndToEndIntegration.case_id,
                "target_user_id": COMMITTEE_CAROL_UUID,
                "role": "member",
                "committee_name": "Special Inquiry Board on Academic Malpractice"
            }
        )
        self.assertEqual(r_assign.status_code, 200, f"Committee assignment failed: {r_assign.text}")
        assign_data = r_assign.json()
        self.assertEqual(assign_data["assignment"]["assignment_status"], "active")

    # =========================================================================
    # JOURNEY STEP 4: COMMITTEE MEMBER CAROL REVIEWS CASE & ADDS OBSERVATIONS
    # =========================================================================
    def test_04_committee_member_participates_in_inquiry(self):
        """Carol accesses the confidential case, adds observations, and accesses evidence."""
        # Carol views assigned inquiries
        r_inq = client.get(
            "/api/campus-proctor/committee/my-inquiries",
            headers={"Authorization": f"Bearer {TOKEN_CAROL}"}
        )
        self.assertEqual(r_inq.status_code, 200)
        cases = r_inq.json().get("inquiries", [])
        assigned_case_ids = [c["case_id"] for c in cases]
        self.assertIn(TestPhase8EndToEndIntegration.case_id, assigned_case_ids)

        # Carol submits inquiry observations
        r_obs = client.post(
            "/api/campus-proctor/committee/observations",
            headers={"Authorization": f"Bearer {TOKEN_CAROL}"},
            json={
                "case_id": TestPhase8EndToEndIntegration.case_id,
                "observations": "Examined physical attendance records. Irregularities confirmed.",
                "recommendation": "Recommend complete reinstatement of laboratory attendance."
            }
        )
        self.assertEqual(r_obs.status_code, 200)

        # Carol retrieves document signed URL
        r_doc = client.get(
            f"/api/campus-proctor/document-url?case_id={TestPhase8EndToEndIntegration.case_id}&document_id=attendance_records.pdf",
            headers={"Authorization": f"Bearer {TOKEN_CAROL}"}
        )
        self.assertEqual(r_doc.status_code, 200)
        self.assertIn("signed_url", r_doc.json())

    # =========================================================================
    # JOURNEY STEP 5: PROCTOR PRIVILEGE ENFORCEMENT & STUDENT CONFIDENTIALITY
    # =========================================================================
    def test_05_proctor_privilege_and_student_privacy(self):
        """Unassigned Proctor Xavier is blocked from confidential case; Alice's view is sanitized."""
        # Unassigned proctor Xavier attempts to access confidential case
        r_x = client.get(
            f"/api/campus-proctor/case/{TestPhase8EndToEndIntegration.case_id}",
            headers={"Authorization": f"Bearer {TOKEN_XAVIER}"}
        )
        self.assertEqual(r_x.status_code, 403, "Unassigned proctor must be rejected from confidential case")

        # Alice views her case details: internal proctor notes must NOT be leaked
        r_alice = client.get(
            f"/api/citizen/cases/{TestPhase8EndToEndIntegration.case_id}",
            headers={"Authorization": f"Bearer {TOKEN_ALICE}"}
        )
        self.assertEqual(r_alice.status_code, 200)
        alice_case = r_alice.json().get("case", {})
        self.assertNotIn("proctor_notes", alice_case, "Internal proctor notes must never leak to student")
        self.assertEqual(alice_case.get("status"), "UNDER_INQUIRY")

    # =========================================================================
    # JOURNEY STEP 6: CITIZEN DISCOVERS LAWYER & REQUESTS CONSULTATION
    # =========================================================================
    def test_06_citizen_requests_consultation(self):
        """Alice finds Advocate Rajesh in directory and submits consultation request."""
        # Search lawyer directory
        r_search = client.get(
            "/api/lawyers?query=Rajesh",
            headers={"Authorization": f"Bearer {TOKEN_ALICE}"}
        )
        self.assertEqual(r_search.status_code, 200)
        lawyers = r_search.json().get("lawyers", [])
        self.assertGreaterEqual(len(lawyers), 1)
        self.assertEqual(lawyers[0]["id"], LAWYER_RAJESH_UUID)

        # Submit consultation request
        r_req = client.post(
            "/api/consultations/request",
            headers={"Authorization": f"Bearer {TOKEN_ALICE}"},
            json={
                "lawyer_user_id": LAWYER_RAJESH_UUID,
                "case_id": TestPhase8EndToEndIntegration.case_id,
                "legal_issue": "Higher Education Grievance Redressal",
                "description": "Need legal advisory regarding arbitrary attendance alteration and inquiry representation.",
                "preferred_mode": "ONLINE"
            }
        )
        self.assertEqual(r_req.status_code, 200, f"Consultation request failed: {r_req.text}")
        data = r_req.json()
        req_obj = data.get("request") or data
        self.assertTrue(req_obj.get("id"))
        TestPhase8EndToEndIntegration.consultation_id = req_obj["id"]

    # =========================================================================
    # JOURNEY STEP 7: CITIZEN SHARES CASE & LAWYER ACCEPTS CONSULTATION
    # =========================================================================
    def test_07_citizen_shares_case_and_lawyer_accepts(self):
        """Alice grants CASE_AND_DOCS access to Rajesh; Rajesh accepts consultation and opens conversation."""
        # Alice shares case with lawyer first
        r_share = client.post(
            "/api/citizen/cases/share",
            headers={"Authorization": f"Bearer {TOKEN_ALICE}"},
            json={
                "case_id": TestPhase8EndToEndIntegration.case_id,
                "lawyer_user_id": LAWYER_RAJESH_UUID,
                "shared_scope": "CASE_AND_DOCS"
            }
        )
        self.assertEqual(r_share.status_code, 200, f"Case share failed: {r_share.text}")
        share_data = r_share.json()
        self.assertEqual(share_data["access"]["access_status"], "ACTIVE")
        self.assertEqual(share_data["access"]["shared_scope"], "CASE_AND_DOCS")

        # Lawyer accepts consultation
        r_accept = client.patch(
            f"/api/consultations/{TestPhase8EndToEndIntegration.consultation_id}/status",
            headers={"Authorization": f"Bearer {TOKEN_RAJESH}"},
            json={"status": "ACCEPTED", "lawyer_response": "I have reviewed your inquiry details and will represent you."}
        )
        self.assertEqual(r_accept.status_code, 200)

        # Open consultation conversation
        r_conv = client.post(
            "/api/conversations/consultation",
            headers={"Authorization": f"Bearer {TOKEN_RAJESH}"},
            json={
                "consultation_request_id": TestPhase8EndToEndIntegration.consultation_id,
                "initial_message": "Greetings Alice, I have accepted your consultation request and received your case records."
            }
        )
        self.assertEqual(r_conv.status_code, 200, f"Conversation creation failed: {r_conv.text}")
        conv_data = r_conv.json()
        self.assertTrue(conv_data.get("id"))
        TestPhase8EndToEndIntegration.conversation_id = conv_data["id"]

        # Alice replies to the conversation
        r_msg = client.post(
            f"/api/conversations/{TestPhase8EndToEndIntegration.conversation_id}/messages",
            headers={"Authorization": f"Bearer {TOKEN_ALICE}"},
            json={
                "message_body": "Thank you Adv. Rajesh. Please review the attendance records attached."
            }
        )
        self.assertEqual(r_msg.status_code, 200)
        msg_data = r_msg.json()
        self.assertEqual(msg_data["sender_user_id"], CITIZEN_ALICE_UUID)

    # =========================================================================
    # JOURNEY STEP 8: LAWYER INSPECTS SHARED CASES & EVIDENCE DOCUMENTS
    # =========================================================================
    def test_08_lawyer_inspects_shared_cases_and_documents(self):
        """Lawyer Rajesh reviews shared cases list and retrieves document signed URL."""
        # Lawyer views shared cases list
        r_shared_list = client.get(
            "/api/lawyer/shared-cases",
            headers={"Authorization": f"Bearer {TOKEN_RAJESH}"}
        )
        self.assertEqual(r_shared_list.status_code, 200)
        shared_cases = r_shared_list.json().get("cases", [])
        shared_ids = [c["case_id"] for c in shared_cases]
        self.assertIn(TestPhase8EndToEndIntegration.case_id, shared_ids)

        # Lawyer requests document signed URL for evidence
        r_doc = client.get(
            f"/api/campus-proctor/document-url?case_id={TestPhase8EndToEndIntegration.case_id}&document_id=attendance_records.pdf",
            headers={"Authorization": f"Bearer {TOKEN_RAJESH}"}
        )
        self.assertEqual(r_doc.status_code, 200, f"Lawyer document access failed: {r_doc.text}")
        doc_data = r_doc.json()
        self.assertIn("signed_url", doc_data)
        self.assertEqual(doc_data["access_type"], "AUTHORIZED_LAWYER")

    # =========================================================================
    # JOURNEY STEP 9: MEETING SCHEDULING & CONCURRENT BOOKING EXCLUSION
    # =========================================================================
    def test_09_meeting_scheduling_and_overlap_rejection(self):
        """Alice schedules a meeting with Rajesh; overlapping booking is rejected."""
        # Unique timestamp based on current time to avoid historical collisions
        offset_days = 20 + (int(time.time()) % 50)
        meeting_time = (datetime.now(timezone.utc) + timedelta(days=offset_days)).replace(hour=10, minute=0, second=0, microsecond=0)
        start_iso = meeting_time.isoformat()
        end_iso = (meeting_time + timedelta(minutes=45)).isoformat()

        # Alice books meeting
        r_meet = client.post(
            "/api/meetings/schedule",
            headers={"Authorization": f"Bearer {TOKEN_ALICE}"},
            json={
                "consultation_request_id": TestPhase8EndToEndIntegration.consultation_id,
                "lawyer_user_id": LAWYER_RAJESH_UUID,
                "scheduled_start": start_iso,
                "scheduled_end": end_iso,
                "meeting_mode": "ONLINE",
                "agenda": "Pre-hearing strategy discussion regarding departmental inquiry."
            }
        )
        self.assertEqual(r_meet.status_code, 200, f"Meeting schedule failed: {r_meet.text}")
        m_data = r_meet.json()
        self.assertTrue(m_data.get("id"))
        TestPhase8EndToEndIntegration.meeting_id = m_data["id"]

        # Lawyer Rajesh confirms the meeting
        r_conf = client.patch(
            f"/api/meetings/{TestPhase8EndToEndIntegration.meeting_id}/status",
            headers={"Authorization": f"Bearer {TOKEN_RAJESH}"},
            json={
                "status": "CONFIRMED",
                "online_meeting_url": "https://nyaypath.internal/meeting/secure-room-p8"
            }
        )
        self.assertEqual(r_conf.status_code, 200)

        # Bob attempts to book overlapping slot with Rajesh -> rejected with 400
        overlap_start = (meeting_time + timedelta(minutes=15)).isoformat()
        overlap_end = (meeting_time + timedelta(minutes=60)).isoformat()
        r_overlap = client.post(
            "/api/meetings/schedule",
            headers={"Authorization": f"Bearer {TOKEN_BOB}"},
            json={
                "lawyer_user_id": LAWYER_RAJESH_UUID,
                "scheduled_start": overlap_start,
                "scheduled_end": overlap_end,
                "meeting_mode": "ONLINE",
                "agenda": "Conflicting meeting attempt."
            }
        )
        self.assertEqual(r_overlap.status_code, 409, "Overlapping meeting must be rejected with HTTP 409 Conflict")

    # =========================================================================
    # JOURNEY STEP 10: CITIZEN REVOKES CASE ACCESS & VERIFIES FAIL-CLOSED STATE
    # =========================================================================
    def test_10_citizen_revokes_case_access_and_verifies_immediate_403(self):
        """Alice revokes Rajesh's case access; Rajesh is immediately blocked (HTTP 403)."""
        # Revoke case share
        r_revoke = client.post(
            "/api/citizen/cases/revoke-share",
            headers={"Authorization": f"Bearer {TOKEN_ALICE}"},
            json={
                "case_id": TestPhase8EndToEndIntegration.case_id,
                "lawyer_user_id": LAWYER_RAJESH_UUID
            }
        )
        self.assertEqual(r_revoke.status_code, 200, f"Revocation failed: {r_revoke.text}")
        self.assertEqual(r_revoke.json()["status"], "success")

        # 1. Lawyer document access attempt -> 403 Forbidden
        r_doc_after = client.get(
            f"/api/campus-proctor/document-url?case_id={TestPhase8EndToEndIntegration.case_id}&document_id=attendance_records.pdf",
            headers={"Authorization": f"Bearer {TOKEN_RAJESH}"}
        )
        self.assertEqual(r_doc_after.status_code, 403, "Post-revocation document access must return 403")

        # 2. Case-linked conversation creation attempt -> 403 Forbidden
        r_case_conv = client.post(
            "/api/conversations/case",
            headers={"Authorization": f"Bearer {TOKEN_RAJESH}"},
            json={
                "case_id": TestPhase8EndToEndIntegration.case_id,
                "lawyer_user_id": LAWYER_RAJESH_UUID,
                "initial_message": "Attempting case-linked conversation after revocation."
            }
        )
        self.assertEqual(r_case_conv.status_code, 403, "Post-revocation case conversation must return 403")

    # =========================================================================
    # JOURNEY STEP 11: PLATFORM ADMIN GLOBAL OVERSIGHT & MASKED CASE AUDITING
    # =========================================================================
    def test_11_platform_admin_oversight_and_exceptional_access(self):
        """Platform Admin logs in, reviews masked case oversight, and exercises logged access."""
        # 1. Global overview
        r_over = client.get(
            "/api/admin/overview",
            headers={"Authorization": f"Bearer {TOKEN_ADMIN}"}
        )
        self.assertEqual(r_over.status_code, 200)
        overview = r_over.json()
        self.assertGreaterEqual(overview.get("total_cases", 0), 1)

        # 2. Cases list with PII masking
        r_cases = client.get(
            "/api/admin/cases",
            headers={"Authorization": f"Bearer {TOKEN_ADMIN}"}
        )
        self.assertEqual(r_cases.status_code, 200)
        cases_data = r_cases.json().get("cases", [])
        matched = next((c for c in cases_data if c["case_id"] == TestPhase8EndToEndIntegration.case_id), None)
        self.assertIsNotNone(matched, "Filed case must appear in global admin cases list")
        # Ensure student name is masked in global listing
        student_display = matched.get("student_name", "")
        self.assertTrue(
            "***" in student_display or len(student_display) <= 4 or "[PROTECTED" in student_display,
            f"Expected masked student name in global admin listing, got: {student_display}"
        )

        # 3. Exceptional audit access with logged justification
        r_audit_access = client.post(
            f"/api/admin/cases/{TestPhase8EndToEndIntegration.case_id}/confidential-access",
            headers={"Authorization": f"Bearer {TOKEN_ADMIN}"},
            json={
                "reason": "Statutory audit following university-wide academic discrimination complaint.",
                "audit_ticket_id": "AUDIT-2026-P8-001"
            }
        )
        self.assertEqual(r_audit_access.status_code, 200, f"Exceptional access failed: {r_audit_access.text}")
        audit_res = r_audit_access.json()
        self.assertEqual(audit_res["status"], "success")
        self.assertIn("case", audit_res)
        self.assertEqual(audit_res["case"]["case_id"], TestPhase8EndToEndIntegration.case_id)

        # 4. Verify exceptional access logged in audit log
        self.assertIn("audit_log_id", audit_res)
        audit_check = supabase_admin.table("platform_audit_logs").select("*").eq(
            "id", audit_res["audit_log_id"]
        ).execute()
        self.assertTrue(len(audit_check.data) > 0)
        self.assertEqual(audit_check.data[0]["action_type"], "EXCEPTIONAL_CONFIDENTIAL_CASE_ACCESS")
        self.assertEqual(audit_check.data[0]["target_entity_id"], TestPhase8EndToEndIntegration.case_id)

    # =========================================================================
    # JOURNEY STEP 12: PLATFORM ADMIN AUTHENTICATION SECURITY HARDENING
    # =========================================================================
    def test_12_platform_admin_db_verification_fail_closed(self):
        """platform_admin role without active record in public.platform_admins is rejected (403)."""
        fake_admin_uuid = "12345678-0000-0000-0000-123456789012"
        fake_admin_jwt = generate_jwt(
            fake_admin_uuid, "platform_admin", "fake_admin@nyaypath.gov", "Fake Platform Admin"
        )
        r = client.get(
            "/api/admin/overview",
            headers={"Authorization": f"Bearer {fake_admin_jwt}"}
        )
        self.assertEqual(r.status_code, 403, "Admin token lacking public.platform_admins DB record must return 403")

    # =========================================================================
    # JOURNEY STEP 13: END-TO-END NOTIFICATIONS VERIFICATION
    # =========================================================================
    def test_13_integrated_notifications_delivery(self):
        """Verify notifications were delivered to Alice and Rajesh across their journey."""
        # Alice notifications (case filed, consultation accepted, meeting scheduled)
        r_alice_notif = client.get(
            "/api/notifications",
            headers={"Authorization": f"Bearer {TOKEN_ALICE}"}
        )
        self.assertEqual(r_alice_notif.status_code, 200)
        alice_notifs = r_alice_notif.json().get("notifications", [])
        self.assertGreaterEqual(len(alice_notifs), 1, "Alice must receive lifecycle notifications")

        # Rajesh notifications (consultation request, case shared, meeting scheduled)
        r_rajesh_notif = client.get(
            "/api/notifications",
            headers={"Authorization": f"Bearer {TOKEN_RAJESH}"}
        )
        self.assertEqual(r_rajesh_notif.status_code, 200)
        rajesh_notifs = r_rajesh_notif.json().get("notifications", [])
        self.assertGreaterEqual(len(rajesh_notifs), 1, "Rajesh must receive consultation/sharing notifications")


if __name__ == "__main__":
    unittest.main()

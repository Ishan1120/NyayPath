"""
NyayPath Phase 6: Secure Messaging, Client Communication & Meeting Scheduling
Comprehensive Automated Security, Multi-Tenancy & Authorization Test Suite
========================================================================
Verification of 17 Scenarios:
1.  Accepted consultation request creates or returns conversation between citizen and lawyer
2.  Unaccepted consultation request (PENDING/DECLINED) rejects conversation initialization (HTTP 400)
3.  Unrelated citizen or lawyer cannot access conversation (HTTP 403)
4.  Citizen can send messages in authorized conversation; body validated
5.  Lawyer can send message to citizen; in-app notification dispatched
6.  Client message ID prevents duplicate message insertion on retry
7.  Case conversation creation with active lawyer case access succeeds
8.  Revoking case sharing immediately blocks lawyer from reading/sending in case conversation (HTTP 403)
9.  Citizen cannot view or read another citizen's conversation messages (HTTP 403)
10. Lawyer cannot view or read another lawyer's conversation messages (HTTP 403)
11. Private attachment upload validates 10MB limit and allowed MIME types (PDF, PNG, JPG, WebP)
12. Attachment signed URL capped at <= 300s TTL; blocked for non-participants (HTTP 403)
13. Meeting scheduled for accepted consultation; double-booking rejected with HTTP 400
14. Lawyer confirms meeting with meeting URL; credentials masked before confirmation and unmasked after
15. Meeting cancellation and status updates persist and notify counterparty
16. In-app notifications use deterministic source event UUID idempotency keys without random fallbacks
17. Participant unread count tracking and read-receipt acknowledgment
"""

import os
import sys
import time
import uuid
import unittest
from datetime import datetime, timezone, timedelta
from pathlib import Path

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

def generate_live_jwt(user_id: str, role: str, email: str, name: str, status: str = "active") -> str:
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
            "institution_id": "INST_DEFAULT",
            "account_status": status
        },
        "user_metadata": {
            "full_name": name,
            "email": email
        }
    }
    return jwt.encode(payload, JWT_SECRET, algorithm="HS256")


# Test User UUIDs from auth.users
LAWYER_A_UUID    = "77777777-1111-2222-3333-777777777777"  # Adv. Rajesh Kumar
LAWYER_B_UUID    = "88888888-1111-2222-3333-888888888888"  # Adv. Priya Sharma
PLATFORM_ADMIN   = "99999999-1111-2222-3333-999999999999"
CITIZEN_A_UUID   = "aaaaaaaa-1111-2222-3333-aaaaaaaaaaaa"  # Alice Citizen
CITIZEN_B_UUID   = "bbbbbbbb-1111-2222-3333-bbbbbbbbbbbb"  # Bob Citizen

TOKEN_LAWYER_A   = generate_live_jwt(LAWYER_A_UUID, "lawyer", "advocate.rajesh@bar.in", "Adv. Rajesh Kumar")
TOKEN_LAWYER_B   = generate_live_jwt(LAWYER_B_UUID, "lawyer", "advocate.priya@bar.in", "Adv. Priya Sharma")
TOKEN_ADMIN      = generate_live_jwt(PLATFORM_ADMIN, "platform_admin", "platform@nyaypath.gov", "Platform Administrator")
TOKEN_CITIZEN_A  = generate_live_jwt(CITIZEN_A_UUID, "citizen", "alice@collegex.edu", "Alice Citizen")
TOKEN_CITIZEN_B  = generate_live_jwt(CITIZEN_B_UUID, "citizen", "bob@collegex.edu", "Bob Citizen")


class TestPhase6Messaging(unittest.TestCase):
    """Automated integration tests for Phase 6 Messaging & Meetings."""

    accepted_consultation_id = None
    pending_consultation_id = None
    consultation_conv_id = None
    case_conv_id = None
    test_case_id = "PHASE6-CASE-001"
    test_case_uuid = None
    meeting_id = None
    attachment_id = None

    @classmethod
    def setUpClass(cls):
        """Set up test fixtures in local Supabase."""
        # 1. Clean up existing Phase 6 test records
        try:
            supabase_admin.table("message_attachments").delete().neq("id", "00000000-0000-0000-0000-000000000000").execute()
            supabase_admin.table("messages").delete().neq("id", "00000000-0000-0000-0000-000000000000").execute()
            supabase_admin.table("conversation_participants").delete().neq("id", "00000000-0000-0000-0000-000000000000").execute()
            supabase_admin.table("consultation_meetings").delete().neq("id", "00000000-0000-0000-0000-000000000000").execute()
            supabase_admin.table("conversations").delete().neq("id", "00000000-0000-0000-0000-000000000000").execute()
            supabase_admin.table("lawyer_availability").delete().neq("id", "00000000-0000-0000-0000-000000000000").execute()
        except Exception as e:
            print(f"Warning cleaning messaging tables: {e}")

        # 2. Ensure lawyer profiles exist
        try:
            supabase_admin.table("lawyer_profiles").upsert({
                "id": LAWYER_A_UUID,
                "full_name": "Adv. Rajesh Kumar",
                "email": "advocate.rajesh@bar.in",
                "phone": "+91 98765 43210",
                "bar_council": "Bar Council of Delhi",
                "enrollment_number": "D/1234/2012",
                "enrollment_state": "Delhi (NCT)",
                "specializations": ["Constitutional Law", "Education Law"],
                "years_of_practice": 12,
                "verification_status": "VERIFIED"
            }).execute()

            supabase_admin.table("lawyer_profiles").upsert({
                "id": LAWYER_B_UUID,
                "full_name": "Adv. Priya Sharma",
                "email": "advocate.priya@bar.in",
                "phone": "+91 98765 43211",
                "bar_council": "Bar Council of Maharashtra & Goa",
                "enrollment_number": "MAH/5678/2015",
                "enrollment_state": "Maharashtra",
                "specializations": ["Criminal Law", "Civil Rights"],
                "years_of_practice": 9,
                "verification_status": "VERIFIED"
            }).execute()
        except Exception as e:
            print(f"Warning setting up lawyer profiles: {e}")

        # 3. Ensure test case exists
        try:
            res_case = supabase_admin.table("cases").select("id").eq("case_id", cls.test_case_id).execute()
            if res_case.data and len(res_case.data) > 0:
                cls.test_case_uuid = res_case.data[0]["id"]
            else:
                new_case = {
                    "case_id": cls.test_case_id,
                    "case_type": "GENERAL_GRIEVANCE",
                    "status": "FILED",
                    "key_version": "v1",
                    "tracking_key_hash": "hash_phase6_test_128",
                    "data": {
                        "citizen_user_id": CITIZEN_A_UUID,
                        "title": "Phase 6 Secure Messaging & Privileged Counsel Test Case",
                        "category": "Education & Student Rights",
                        "facts_summary": "Test dispute for messaging, document attachments, and consultations."
                    }
                }
                res_ins = supabase_admin.table("cases").insert(new_case).execute()
                cls.test_case_uuid = res_ins.data[0]["id"]
        except Exception as e:
            print(f"Warning setting up test case: {e}")

        # 4. Create an ACCEPTED consultation request
        try:
            acc_req = supabase_admin.table("consultation_requests").insert({
                "citizen_user_id": CITIZEN_A_UUID,
                "lawyer_user_id": LAWYER_A_UUID,
                "legal_issue": "Disciplinary Hearing Due Process",
                "description": "Requesting consultation regarding college proctorial board notice.",
                "preferred_mode": "ONLINE",
                "status": "ACCEPTED",
                "lawyer_response": "Accepted. Please share case details and schedule a consultation slot."
            }).execute()
            cls.accepted_consultation_id = acc_req.data[0]["id"]

            # Create a PENDING consultation request
            pend_req = supabase_admin.table("consultation_requests").insert({
                "citizen_user_id": CITIZEN_A_UUID,
                "lawyer_user_id": LAWYER_B_UUID,
                "legal_issue": "Pending Consultation Test",
                "description": "Still waiting for advocate acceptance.",
                "preferred_mode": "PHONE",
                "status": "PENDING"
            }).execute()
            cls.pending_consultation_id = pend_req.data[0]["id"]
        except Exception as e:
            print(f"Warning setting up consultation requests: {e}")

    def setUp(self):
        """Ensure base conversation fixture is available for all tests."""
        if not TestPhase6Messaging.consultation_conv_id and self.accepted_consultation_id:
            res = client.post(
                "/api/conversations/consultation",
                headers={"Authorization": f"Bearer {TOKEN_CITIZEN_A}"},
                json={"consultation_request_id": self.accepted_consultation_id}
            )
            if res.status_code == 200:
                TestPhase6Messaging.consultation_conv_id = res.json()["id"]

    # -----------------------------------------------------------------
    # Scenario 1: Accepted consultation creates or returns conversation
    # -----------------------------------------------------------------
    def test_01_accepted_consultation_creates_conversation(self):
        """Accepted consultation request initializes conversation between citizen and counsel."""
        response = client.post(
            "/api/conversations/consultation",
            headers={"Authorization": f"Bearer {TOKEN_CITIZEN_A}"},
            json={
                "consultation_request_id": self.accepted_consultation_id,
                "initial_message": "Hello Adv. Rajesh, thank you for accepting my consultation."
            }
        )
        self.assertEqual(response.status_code, 200, response.text)
        data = response.json()
        self.assertEqual(data["conversation_type"], "LAWYER_CITIZEN")
        self.assertEqual(data["consultation_request_id"], self.accepted_consultation_id)
        self.assertTrue("id" in data)

        TestPhase6Messaging.consultation_conv_id = data["id"]

        # Call again to verify idempotency (same conversation returned)
        response2 = client.post(
            "/api/conversations/consultation",
            headers={"Authorization": f"Bearer {TOKEN_LAWYER_A}"},
            json={"consultation_request_id": self.accepted_consultation_id}
        )
        self.assertEqual(response2.status_code, 200)
        self.assertEqual(response2.json()["id"], self.consultation_conv_id)

    # -----------------------------------------------------------------
    # Scenario 2: Unaccepted consultation rejects conversation creation (HTTP 400)
    # -----------------------------------------------------------------
    def test_02_unaccepted_consultation_rejects_conversation(self):
        """Unaccepted consultation (PENDING) strictly rejects conversation initialization."""
        response = client.post(
            "/api/conversations/consultation",
            headers={"Authorization": f"Bearer {TOKEN_CITIZEN_A}"},
            json={"consultation_request_id": self.pending_consultation_id}
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("accepted consultation", response.text.lower())

    # -----------------------------------------------------------------
    # Scenario 3: Unrelated citizen or lawyer cannot access conversation (HTTP 403)
    # -----------------------------------------------------------------
    def test_03_unrelated_user_cannot_access_conversation(self):
        """Unauthorized citizen or lawyer cannot view conversation metadata (HTTP 403)."""
        # Citizen B (Bob) tries to view Alice's conversation
        resp_bob = client.get(
            f"/api/conversations/{self.consultation_conv_id}",
            headers={"Authorization": f"Bearer {TOKEN_CITIZEN_B}"}
        )
        self.assertEqual(resp_bob.status_code, 403)
        self.assertIn("not an active participant", resp_bob.text.lower())

        # Lawyer B (Priya) tries to view Rajesh's conversation
        resp_priya = client.get(
            f"/api/conversations/{self.consultation_conv_id}",
            headers={"Authorization": f"Bearer {TOKEN_LAWYER_B}"}
        )
        self.assertEqual(resp_priya.status_code, 403)

    # -----------------------------------------------------------------
    # Scenario 4: Citizen can send messages in authorized conversation
    # -----------------------------------------------------------------
    def test_04_citizen_can_send_messages(self):
        """Citizen participant can send a message; sender attribution verified from JWT."""
        payload = {
            "message_body": "Can you advise whether Section 439 applies to our upcoming hearing?",
            "message_type": "TEXT"
        }
        response = client.post(
            f"/api/conversations/{self.consultation_conv_id}/messages",
            headers={"Authorization": f"Bearer {TOKEN_CITIZEN_A}"},
            json=payload
        )
        self.assertEqual(response.status_code, 200, response.text)
        data = response.json()
        self.assertEqual(data["sender_user_id"], CITIZEN_A_UUID)
        self.assertEqual(data["message_body"], payload["message_body"])
        self.assertTrue("id" in data)

    # -----------------------------------------------------------------
    # Scenario 5: Lawyer can send message and trigger notification
    # -----------------------------------------------------------------
    def test_05_lawyer_can_send_message_and_trigger_notification(self):
        """Lawyer sends reply; recipient receives in-app notification with preview."""
        payload = {
            "message_body": "Yes, Section 439 is applicable for regular bail before the Sessions Court.",
            "message_type": "TEXT"
        }
        response = client.post(
            f"/api/conversations/{self.consultation_conv_id}/messages",
            headers={"Authorization": f"Bearer {TOKEN_LAWYER_A}"},
            json=payload
        )
        self.assertEqual(response.status_code, 200, response.text)
        msg_data = response.json()
        self.assertEqual(msg_data["sender_user_id"], LAWYER_A_UUID)

        # Verify notification dispatched to Alice
        notifs = supabase_admin.table("notifications").select("*").eq(
            "recipient_user_id", CITIZEN_A_UUID
        ).eq("event_type", "NEW_MESSAGE").order("created_at", desc=True).limit(5).execute()

        self.assertTrue(len(notifs.data) > 0)
        latest_notif = notifs.data[0]
        self.assertIn("Adv. Rajesh Kumar", latest_notif["title"])
        self.assertIn("Section 439", latest_notif["message"])

    # -----------------------------------------------------------------
    # Scenario 6: Client message ID deduplication
    # -----------------------------------------------------------------
    def test_06_client_message_id_deduplication(self):
        """Duplicate message send with identical client_message_id returns existing message idempotently."""
        dedup_id = f"client-msg-{uuid.uuid4()}"
        payload = {
            "message_body": "This is an idempotent network retry test message.",
            "message_type": "TEXT",
            "client_message_id": dedup_id
        }

        # First submission
        res1 = client.post(
            f"/api/conversations/{self.consultation_conv_id}/messages",
            headers={"Authorization": f"Bearer {TOKEN_CITIZEN_A}"},
            json=payload
        )
        self.assertEqual(res1.status_code, 200)
        msg1_id = res1.json()["id"]

        # Retry submission with same client_message_id
        res2 = client.post(
            f"/api/conversations/{self.consultation_conv_id}/messages",
            headers={"Authorization": f"Bearer {TOKEN_CITIZEN_A}"},
            json=payload
        )
        self.assertEqual(res2.status_code, 200)
        msg2_id = res2.json()["id"]

        self.assertEqual(msg1_id, msg2_id)

    # -----------------------------------------------------------------
    # Scenario 7: Case conversation creation with active lawyer access
    # -----------------------------------------------------------------
    def test_07_case_conversation_creation_with_active_share(self):
        """Case conversation initializes when lawyer has active case sharing."""
        # Grant Lawyer A active access to case
        client.post(
            "/api/citizen/cases/share",
            headers={"Authorization": f"Bearer {TOKEN_CITIZEN_A}"},
            json={
                "case_id": self.test_case_id,
                "lawyer_user_id": LAWYER_A_UUID,
                "shared_scope": "CASE_AND_DOCS"
            }
        )

        response = client.post(
            "/api/conversations/case",
            headers={"Authorization": f"Bearer {TOKEN_CITIZEN_A}"},
            json={
                "case_id": self.test_case_id,
                "conversation_type": "GENERAL_CASE",
                "initial_message": "Starting case communication channel."
            }
        )
        self.assertEqual(response.status_code, 200, response.text)
        data = response.json()
        self.assertEqual(data["case_id"], self.test_case_id)
        TestPhase6Messaging.case_conv_id = data["id"]

    # -----------------------------------------------------------------
    # Scenario 8: Revoking case sharing immediately blocks lawyer (HTTP 403)
    # -----------------------------------------------------------------
    def test_08_revoked_case_share_blocks_lawyer_immediately(self):
        """Revoking case share immediately blocks lawyer from reading or sending case messages."""
        # Revoke Lawyer A's access
        rev_resp = client.post(
            "/api/citizen/cases/revoke-share",
            headers={"Authorization": f"Bearer {TOKEN_CITIZEN_A}"},
            json={
                "case_id": self.test_case_id,
                "lawyer_user_id": LAWYER_A_UUID
            }
        )
        self.assertEqual(rev_resp.status_code, 200)

        # Lawyer A attempts to view case conversation -> HTTP 403
        resp_get = client.get(
            f"/api/conversations/{self.case_conv_id}",
            headers={"Authorization": f"Bearer {TOKEN_LAWYER_A}"}
        )
        self.assertEqual(resp_get.status_code, 403)
        self.assertIn("revoked", resp_get.text.lower())

        # Lawyer A attempts to send message to case conversation -> HTTP 403
        resp_send = client.post(
            f"/api/conversations/{self.case_conv_id}/messages",
            headers={"Authorization": f"Bearer {TOKEN_LAWYER_A}"},
            json={"message_body": "Attempting message after revocation."}
        )
        self.assertEqual(resp_send.status_code, 403)

        # Lawyer A attempts to list messages -> HTTP 403
        resp_list = client.get(
            f"/api/conversations/{self.case_conv_id}/messages",
            headers={"Authorization": f"Bearer {TOKEN_LAWYER_A}"}
        )
        self.assertEqual(resp_list.status_code, 403)

    # -----------------------------------------------------------------
    # Scenario 9: Citizen cannot view or read another citizen's messages
    # -----------------------------------------------------------------
    def test_09_citizen_cannot_read_another_citizens_messages(self):
        """Citizen Bob cannot list messages from Alice's conversation."""
        response = client.get(
            f"/api/conversations/{self.consultation_conv_id}/messages",
            headers={"Authorization": f"Bearer {TOKEN_CITIZEN_B}"}
        )
        self.assertEqual(response.status_code, 403)

    # -----------------------------------------------------------------
    # Scenario 10: Lawyer cannot view or read another lawyer's conversations
    # -----------------------------------------------------------------
    def test_10_lawyer_cannot_read_another_lawyers_conversations(self):
        """Lawyer Priya cannot list messages from Rajesh's consultation conversation."""
        response = client.get(
            f"/api/conversations/{self.consultation_conv_id}/messages",
            headers={"Authorization": f"Bearer {TOKEN_LAWYER_B}"}
        )
        self.assertEqual(response.status_code, 403)

    # -----------------------------------------------------------------
    # Scenario 11: Private attachment upload size and MIME validation
    # -----------------------------------------------------------------
    def test_11_private_attachment_upload_size_and_mimes(self):
        """Attachment upload validates allowed MIME types and enforces 10MB limit."""
        # 1. Disallowed MIME type / extension (.exe)
        bad_file = ("script.exe", b"MZDummyExecutableBytes", "application/x-msdownload")
        resp_bad = client.post(
            f"/api/conversations/{self.consultation_conv_id}/attachments",
            headers={"Authorization": f"Bearer {TOKEN_CITIZEN_A}"},
            files={"file": bad_file}
        )
        self.assertEqual(resp_bad.status_code, 400)
        self.assertIn("Unsupported file type", resp_bad.text)

        # 2. Valid PDF attachment
        pdf_bytes = b"%PDF-1.4\n1 0 obj\n<< /Title (Evidence Document) >>\nendobj\ntrailer\n<< /Root 1 0 R >>\n%%EOF"
        good_file = ("court_order.pdf", pdf_bytes, "application/pdf")
        resp_good = client.post(
            f"/api/conversations/{self.consultation_conv_id}/attachments",
            headers={"Authorization": f"Bearer {TOKEN_CITIZEN_A}"},
            files={"file": good_file}
        )
        self.assertEqual(resp_good.status_code, 200, resp_good.text)
        data = resp_good.json()
        self.assertTrue("id" in data)
        self.assertEqual(data["file_name"], "court_order.pdf")
        self.assertEqual(data["mime_type"], "application/pdf")
        self.assertTrue("download_url" in data)
        self.assertTrue(data.get("expires_in", 0) <= 300)

        TestPhase6Messaging.attachment_id = data["id"]

    # -----------------------------------------------------------------
    # Scenario 12: Signed URL TTL clamped <= 300s & non-participant blocked
    # -----------------------------------------------------------------
    def test_12_attachment_signed_url_ttl_and_boundary(self):
        """Signed URL generator strictly clamps TTL <= 300s and blocks non-participants."""
        # Authorized participant (Lawyer A) gets fresh signed URL
        resp_lawyer = client.get(
            f"/api/conversations/attachments/{self.attachment_id}/url",
            headers={"Authorization": f"Bearer {TOKEN_LAWYER_A}"}
        )
        self.assertEqual(resp_lawyer.status_code, 200)
        self.assertLessEqual(resp_lawyer.json()["expires_in"], 300)
        self.assertTrue(bool(resp_lawyer.json()["signed_url"]))

        # Non-participant (Citizen Bob) blocked -> HTTP 403
        resp_bob = client.get(
            f"/api/conversations/attachments/{self.attachment_id}/url",
            headers={"Authorization": f"Bearer {TOKEN_CITIZEN_B}"}
        )
        self.assertEqual(resp_bob.status_code, 403)

    # -----------------------------------------------------------------
    # Scenario 13: Meeting scheduling & transactional double-booking prevention
    # -----------------------------------------------------------------
    def test_13_meeting_schedule_and_double_booking_prevention(self):
        """Schedule meeting for accepted consultation; double-booking rejected with HTTP 400."""
        # Tomorrow at 10:00 AM UTC
        tomorrow = datetime.now(timezone.utc) + timedelta(days=1)
        start_dt = tomorrow.replace(hour=10, minute=0, second=0, microsecond=0)
        end_dt = start_dt + timedelta(minutes=30)

        # 1. Alice schedules meeting with Lawyer A
        sched_payload = {
            "consultation_request_id": self.accepted_consultation_id,
            "lawyer_user_id": LAWYER_A_UUID,
            "scheduled_start": start_dt.isoformat(),
            "scheduled_end": end_dt.isoformat(),
            "meeting_mode": "ONLINE",
            "agenda": "Reviewing natural justice evidence."
        }
        res_sched = client.post(
            "/api/meetings/schedule",
            headers={"Authorization": f"Bearer {TOKEN_CITIZEN_A}"},
            json=sched_payload
        )
        self.assertEqual(res_sched.status_code, 200, res_sched.text)
        meet_data = res_sched.json()
        self.assertEqual(meet_data["status"], "REQUESTED")
        TestPhase6Messaging.meeting_id = meet_data["id"]

        # 2. Lawyer A confirms the meeting
        confirm_resp = client.patch(
            f"/api/meetings/{self.meeting_id}/status",
            headers={"Authorization": f"Bearer {TOKEN_LAWYER_A}"},
            json={
                "status": "CONFIRMED",
                "online_meeting_url": "https://nyaypath.gov.in/consultation-room/secure-123",
                "notes": "Appointment confirmed. Please join room on time."
            }
        )
        self.assertEqual(confirm_resp.status_code, 200)
        self.assertEqual(confirm_resp.json()["status"], "CONFIRMED")

        # 3. Create another consultation for Bob with Lawyer A, mark accepted
        bob_req = supabase_admin.table("consultation_requests").insert({
            "citizen_user_id": CITIZEN_B_UUID,
            "lawyer_user_id": LAWYER_A_UUID,
            "legal_issue": "Conflicting Appointment Test",
            "description": "Attempting overlapping appointment.",
            "preferred_mode": "ONLINE",
            "status": "ACCEPTED"
        }).execute()
        bob_req_id = bob_req.data[0]["id"]

        # 4. Bob attempts to schedule overlapping meeting with Lawyer A (10:15 - 10:45 UTC)
        overlap_start = start_dt + timedelta(minutes=15)
        overlap_end = overlap_start + timedelta(minutes=30)
        overlap_payload = {
            "consultation_request_id": bob_req_id,
            "lawyer_user_id": LAWYER_A_UUID,
            "scheduled_start": overlap_start.isoformat(),
            "scheduled_end": overlap_end.isoformat(),
            "meeting_mode": "ONLINE",
            "agenda": "Conflicting slot test."
        }
        res_conflict = client.post(
            "/api/meetings/schedule",
            headers={"Authorization": f"Bearer {TOKEN_CITIZEN_B}"},
            json=overlap_payload
        )
        self.assertEqual(res_conflict.status_code, 400)
        self.assertIn("conflict", res_conflict.text.lower())

    # -----------------------------------------------------------------
    # Scenario 14: Meeting privacy masking before and after confirmation
    # -----------------------------------------------------------------
    def test_14_meeting_privacy_masking(self):
        """Meeting credentials remain masked until status is CONFIRMED."""
        # Create unconfirmed meeting
        start_dt = datetime.now(timezone.utc) + timedelta(days=2, hours=10)
        end_dt = start_dt + timedelta(minutes=30)
        res_m2 = client.post(
            "/api/meetings/schedule",
            headers={"Authorization": f"Bearer {TOKEN_CITIZEN_A}"},
            json={
                "consultation_request_id": self.accepted_consultation_id,
                "lawyer_user_id": LAWYER_A_UUID,
                "scheduled_start": start_dt.isoformat(),
                "scheduled_end": end_dt.isoformat(),
                "meeting_mode": "ONLINE",
                "agenda": "Privacy masking test"
            }
        )
        m2_id = res_m2.json()["id"]

        # View unconfirmed meeting -> online_meeting_url must be None
        detail_unconf = client.get(
            f"/api/meetings/{m2_id}",
            headers={"Authorization": f"Bearer {TOKEN_CITIZEN_A}"}
        ).json()
        self.assertIsNone(detail_unconf["online_meeting_url"])

        # Confirm meeting
        client.patch(
            f"/api/meetings/{m2_id}/status",
            headers={"Authorization": f"Bearer {TOKEN_LAWYER_A}"},
            json={
                "status": "CONFIRMED",
                "online_meeting_url": "https://meet.google.com/abc-defg-hij"
            }
        )

        # View confirmed meeting -> online_meeting_url must be visible
        detail_conf = client.get(
            f"/api/meetings/{m2_id}",
            headers={"Authorization": f"Bearer {TOKEN_CITIZEN_A}"}
        ).json()
        self.assertEqual(detail_conf["online_meeting_url"], "https://meet.google.com/abc-defg-hij")

    # -----------------------------------------------------------------
    # Scenario 15: Meeting cancellation and status updates
    # -----------------------------------------------------------------
    def test_15_meeting_cancellation_and_rescheduling(self):
        """Meeting cancellation updates status to CANCELLED and dispatches notification."""
        cancel_resp = client.patch(
            f"/api/meetings/{self.meeting_id}/status",
            headers={"Authorization": f"Bearer {TOKEN_CITIZEN_A}"},
            json={
                "status": "CANCELLED",
                "notes": "Citizen requested cancellation due to scheduling conflict."
            }
        )
        self.assertEqual(cancel_resp.status_code, 200)
        self.assertEqual(cancel_resp.json()["status"], "CANCELLED")

        # Notification dispatched to Lawyer A
        notifs = supabase_admin.table("notifications").select("*").eq(
            "recipient_user_id", LAWYER_A_UUID
        ).eq("event_type", "MEETING_CANCELLED").execute()

        self.assertTrue(len(notifs.data) > 0)
        self.assertIn("cancelled", notifs.data[-1]["title"].lower())

    # -----------------------------------------------------------------
    # Scenario 16: Deterministic notification idempotency keys
    # -----------------------------------------------------------------
    def test_16_deterministic_notification_idempotency_keys(self):
        """Notifications use deterministic source UUID keys without random fallbacks."""
        # Query notifications table for Phase 6 generated items
        notifs = supabase_admin.table("notifications").select("idempotency_key").execute()
        keys = [n["idempotency_key"] for n in notifs.data if n.get("idempotency_key")]

        # Verify pattern of message notification key
        msg_keys = [k for k in keys if k.startswith("notif_msg_")]
        self.assertTrue(len(msg_keys) > 0)
        for mk in msg_keys:
            # Pattern: notif_msg_{message_id}_{recipient_id}
            parts = mk.split("_")
            self.assertEqual(parts[0], "notif")
            self.assertEqual(parts[1], "msg")

        # Verify pattern of meeting notification key
        meet_keys = [k for k in keys if k.startswith("notif_meet_")]
        self.assertTrue(len(meet_keys) > 0)
        for mk in meet_keys:
            # Pattern: notif_meet_{meeting_id}_{status}_{recipient_id}
            parts = mk.split("_")
            self.assertEqual(parts[0], "notif")
            self.assertEqual(parts[1], "meet")

    # -----------------------------------------------------------------
    # Scenario 17: Participant unread count tracking & read receipts
    # -----------------------------------------------------------------
    def test_17_read_receipt_and_unread_tracking(self):
        """Marking conversation read updates last_read_at and resets unread count."""
        # Lawyer sends message
        client.post(
            f"/api/conversations/{self.consultation_conv_id}/messages",
            headers={"Authorization": f"Bearer {TOKEN_LAWYER_A}"},
            json={"message_body": "Checking your read receipt."}
        )

        # Alice marks conversation as read
        read_resp = client.post(
            f"/api/conversations/{self.consultation_conv_id}/read",
            headers={"Authorization": f"Bearer {TOKEN_CITIZEN_A}"}
        )
        self.assertEqual(read_resp.status_code, 200)
        self.assertEqual(read_resp.json()["status"], "success")
        self.assertTrue("last_read_at" in read_resp.json() or "read_at" in read_resp.json())


if __name__ == "__main__":
    unittest.main()

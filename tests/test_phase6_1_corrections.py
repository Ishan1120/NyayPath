"""
NyayPath Phase 6.1: Case Conversation Revocation & Concurrent Meeting Booking Fixes
Comprehensive Automated Security, Multi-Tenancy & Concurrency Test Suite
================================================================================
Verification of 12 Scenarios:
1.  Lawyer with ACTIVE case access + CASE_AND_DOCS scope succeeds in all conversation operations.
2.  Lawyer with REVOKED case access is strictly rejected with HTTP 403.
3.  Lawyer with MISSING case access record is strictly rejected with HTTP 403 (fail-closed).
4.  Lawyer with INACTIVE case access status is strictly rejected with HTTP 403.
5.  Lawyer with METADATA_ONLY scope cannot upload attachments or get signed URLs (HTTP 403).
6.  Database verification failure fails closed with HTTP 403 without leaking message content.
7.  Citizen case owner and institutional proctor workflows continue working unaffected.
8.  Sequential meeting confirmation: first succeeds (200), overlapping second is rejected (400).
9.  Adjacent non-overlapping bookings both confirm successfully (200).
10. Cancelled appointment unblocks future bookings in that time window.
11. Existing meeting privacy masking remains intact (credentials hidden until CONFIRMED).
12. Concurrent race condition: simultaneous overlapping confirmations result in exactly ONE success and ONE failure.
"""

import os
import sys
import time
import uuid
import unittest
import concurrent.futures
from datetime import datetime, timezone, timedelta
from unittest.mock import patch

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
from api.messaging import communication_manager
from supabase import create_client

client = TestClient(app)
supabase_admin = create_client(
    os.environ["SUPABASE_URL"],
    os.environ["SUPABASE_SECRET_KEY"]
)

JWT_SECRET = "super-secret-jwt-token-with-at-least-32-characters-long"

def generate_live_jwt(user_id: str, role: str, email: str, name: str, institution_id: str = "INST_DEFAULT") -> str:
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
            "account_status": "active"
        },
        "user_metadata": {
            "full_name": name,
            "email": email
        }
    }
    return jwt.encode(payload, JWT_SECRET, algorithm="HS256")


LAWYER_A_UUID    = "77777777-1111-2222-3333-777777777777"
CITIZEN_A_UUID   = "aaaaaaaa-1111-2222-3333-aaaaaaaaaaaa"
CITIZEN_B_UUID   = "bbbbbbbb-1111-2222-3333-bbbbbbbbbbbb"
PROCTOR_X_UUID   = "cccccccc-1111-2222-3333-cccccccccccc"

TOKEN_LAWYER_A   = generate_live_jwt(LAWYER_A_UUID, "lawyer", "advocate.rajesh@bar.in", "Adv. Rajesh Kumar")
TOKEN_CITIZEN_A  = generate_live_jwt(CITIZEN_A_UUID, "citizen", "alice@collegex.edu", "Alice Citizen", "COLLEGEX")
TOKEN_CITIZEN_B  = generate_live_jwt(CITIZEN_B_UUID, "citizen", "bob@collegex.edu", "Bob Citizen", "COLLEGEX")
TOKEN_PROCTOR_X  = generate_live_jwt(PROCTOR_X_UUID, "proctor", "xavier@collegex.edu", "Proctor Xavier", "COLLEGEX")


class TestPhase61Corrections(unittest.TestCase):
    """Integration and concurrency test suite for Phase 6.1 corrections."""

    test_case_id = "PHASE61-CASE-SEC"
    test_case_uuid = None
    case_conv_id = None
    existing_attachment_id = None

    @classmethod
    def setUpClass(cls):
        """Seed fixtures in local Supabase database."""
        # 1. Clean previous meeting and messaging test rows for clean slate
        try:
            supabase_admin.table("consultation_meetings").delete().in_(
                "citizen_user_id", [CITIZEN_A_UUID, CITIZEN_B_UUID]
            ).execute()
        except Exception:
            pass

        # 2. Ensure test case exists
        c_res = supabase_admin.table("cases").select("id").eq("case_id", cls.test_case_id).execute()
        if c_res.data and len(c_res.data) > 0:
            cls.test_case_uuid = c_res.data[0]["id"]
        else:
            ins_res = supabase_admin.table("cases").insert({
                "case_id": cls.test_case_id,
                "case_type": "CAMPUS_GRIEVANCE",
                "status": "FILED",
                "key_version": "v1",
                "tracking_key_hash": "hash_sec_phase61_test",
                "data": {
                    "institution_id": "COLLEGEX",
                    "citizen_user_id": CITIZEN_A_UUID,
                    "student_user_id": CITIZEN_A_UUID,
                    "assigned_proctor_user_id": PROCTOR_X_UUID,
                    "title": "Phase 6.1 Case Revocation & Concurrency Validation Case",
                    "category": "Disciplinary & Natural Justice"
                }
            }).execute()
            cls.test_case_uuid = ins_res.data[0]["id"]

        # 3. Create case conversation
        conv_res = supabase_admin.table("conversations").select("id").eq(
            "related_case_uuid", cls.test_case_uuid
        ).execute()

        if conv_res.data and len(conv_res.data) > 0:
            cls.case_conv_id = conv_res.data[0]["id"]
        else:
            ins_conv = supabase_admin.table("conversations").insert({
                "conversation_type": "GENERAL_CASE",
                "title": f"Case Discussion: {cls.test_case_id}",
                "related_case_uuid": cls.test_case_uuid,
                "related_case_id": cls.test_case_id,
                "created_by": CITIZEN_A_UUID,
                "conversation_status": "ACTIVE"
            }).execute()
            cls.case_conv_id = ins_conv.data[0]["id"]

        # 4. Ensure participants in conversation
        for uid, role in [(CITIZEN_A_UUID, "citizen"), (LAWYER_A_UUID, "lawyer"), (PROCTOR_X_UUID, "proctor")]:
            p_res = supabase_admin.table("conversation_participants").select("id").eq(
                "conversation_id", cls.case_conv_id
            ).eq("user_id", uid).execute()
            if not p_res.data:
                supabase_admin.table("conversation_participants").insert({
                    "conversation_id": cls.case_conv_id,
                    "user_id": uid,
                    "participant_role": role,
                    "participant_status": "ACTIVE"
                }).execute()

        # 5. Upload actual attachment via Citizen A so it physically exists in storage bucket
        pdf_bytes = b"%PDF-1.4\n1 0 obj\n<< /Title (Evidence Document) >>\nendobj\ntrailer\n<< /Root 1 0 R >>\n%%EOF"
        att_resp = client.post(
            f"/api/conversations/{cls.case_conv_id}/attachments",
            headers={"Authorization": f"Bearer {TOKEN_CITIZEN_A}"},
            files={"file": ("evidence_sample.pdf", pdf_bytes, "application/pdf")}
        )
        if att_resp.status_code == 200:
            cls.existing_attachment_id = att_resp.json()["id"]
        else:
            print(f"Warning uploading attachment: {att_resp.text}")

    @classmethod
    def _set_lawyer_access(cls, case_uuid, lawyer_uid, status="ACTIVE", scope="CASE_AND_DOCS"):
        existing = supabase_admin.table("lawyer_case_access").select("id").eq(
            "case_uuid", case_uuid
        ).eq("lawyer_user_id", lawyer_uid).execute()
        if existing.data and len(existing.data) > 0:
            supabase_admin.table("lawyer_case_access").update({
                "access_status": status,
                "shared_scope": scope
            }).eq("id", existing.data[0]["id"]).execute()
        else:
            supabase_admin.table("lawyer_case_access").insert({
                "case_id": cls.test_case_id,
                "case_uuid": case_uuid,
                "citizen_user_id": CITIZEN_A_UUID,
                "lawyer_user_id": lawyer_uid,
                "access_status": status,
                "shared_scope": scope
            }).execute()

    # =========================================================================
    # Task 1: Case Conversation Revocation & Fail-Closed Access Boundaries
    # =========================================================================

    def test_01_lawyer_active_permission_succeeds(self):
        """Active permission + CASE_AND_DOCS scope allows lawyer to access case conversation."""
        # Set permission to ACTIVE with CASE_AND_DOCS scope
        self._set_lawyer_access(self.test_case_uuid, LAWYER_A_UUID, "ACTIVE", "CASE_AND_DOCS")

        # 1. Retrieve conversation
        resp_get = client.get(
            f"/api/conversations/{self.case_conv_id}",
            headers={"Authorization": f"Bearer {TOKEN_LAWYER_A}"}
        )
        self.assertEqual(resp_get.status_code, 200, resp_get.text)

        # 2. List messages
        resp_msgs = client.get(
            f"/api/conversations/{self.case_conv_id}/messages",
            headers={"Authorization": f"Bearer {TOKEN_LAWYER_A}"}
        )
        self.assertEqual(resp_msgs.status_code, 200, resp_msgs.text)

        # 3. Send message
        resp_send = client.post(
            f"/api/conversations/{self.case_conv_id}/messages",
            headers={"Authorization": f"Bearer {TOKEN_LAWYER_A}"},
            json={"message_body": "Counsel acknowledgment: Active access confirmed."}
        )
        self.assertEqual(resp_send.status_code, 200, resp_send.text)

        # 4. Get attachment signed URL
        resp_url = client.get(
            f"/api/conversations/attachments/{self.existing_attachment_id}/url",
            headers={"Authorization": f"Bearer {TOKEN_LAWYER_A}"}
        )
        self.assertEqual(resp_url.status_code, 200, resp_url.text)

    def test_02_lawyer_revoked_permission_denied(self):
        """Revoked permission record strictly blocks lawyer across all endpoints (HTTP 403)."""
        # Update permission to REVOKED
        supabase_admin.table("lawyer_case_access").update({
            "access_status": "REVOKED"
        }).eq("case_uuid", self.test_case_uuid).eq("lawyer_user_id", LAWYER_A_UUID).execute()

        # 1. Conversation retrieval -> 403
        r1 = client.get(
            f"/api/conversations/{self.case_conv_id}",
            headers={"Authorization": f"Bearer {TOKEN_LAWYER_A}"}
        )
        self.assertEqual(r1.status_code, 403)
        self.assertIn("revoked", r1.text.lower())

        # 2. List messages -> 403
        r2 = client.get(
            f"/api/conversations/{self.case_conv_id}/messages",
            headers={"Authorization": f"Bearer {TOKEN_LAWYER_A}"}
        )
        self.assertEqual(r2.status_code, 403)

        # 3. Send message -> 403
        r3 = client.post(
            f"/api/conversations/{self.case_conv_id}/messages",
            headers={"Authorization": f"Bearer {TOKEN_LAWYER_A}"},
            json={"message_body": "Should fail after revocation."}
        )
        self.assertEqual(r3.status_code, 403)

        # 4. Attachment signed URL -> 403
        r4 = client.get(
            f"/api/conversations/attachments/{self.existing_attachment_id}/url",
            headers={"Authorization": f"Bearer {TOKEN_LAWYER_A}"}
        )
        self.assertEqual(r4.status_code, 403)

    def test_03_lawyer_missing_permission_denied(self):
        """Missing permission record strictly blocks lawyer across all endpoints (HTTP 403)."""
        # Delete permission record completely
        supabase_admin.table("lawyer_case_access").delete().eq(
            "case_uuid", self.test_case_uuid
        ).eq("lawyer_user_id", LAWYER_A_UUID).execute()

        # 1. Conversation retrieval -> 403
        r1 = client.get(
            f"/api/conversations/{self.case_conv_id}",
            headers={"Authorization": f"Bearer {TOKEN_LAWYER_A}"}
        )
        self.assertEqual(r1.status_code, 403)
        self.assertIn("no active case sharing authorization", r1.text.lower())

        # 2. List messages -> 403
        r2 = client.get(
            f"/api/conversations/{self.case_conv_id}/messages",
            headers={"Authorization": f"Bearer {TOKEN_LAWYER_A}"}
        )
        self.assertEqual(r2.status_code, 403)

        # 3. Send message -> 403
        r3 = client.post(
            f"/api/conversations/{self.case_conv_id}/messages",
            headers={"Authorization": f"Bearer {TOKEN_LAWYER_A}"},
            json={"message_body": "Should fail when permission record is absent."}
        )
        self.assertEqual(r3.status_code, 403)

        # 4. Attachment signed URL -> 403
        r4 = client.get(
            f"/api/conversations/attachments/{self.existing_attachment_id}/url",
            headers={"Authorization": f"Bearer {TOKEN_LAWYER_A}"}
        )
        self.assertEqual(r4.status_code, 403)

    def test_04_lawyer_inactive_permission_denied(self):
        """Inactive or non-ACTIVE permission record strictly blocks lawyer (HTTP 403)."""
        # Set access_status = 'REVOKED' (non-active status)
        self._set_lawyer_access(self.test_case_uuid, LAWYER_A_UUID, "REVOKED", "CASE_AND_DOCS")

        r = client.get(
            f"/api/conversations/{self.case_conv_id}",
            headers={"Authorization": f"Bearer {TOKEN_LAWYER_A}"}
        )
        self.assertEqual(r.status_code, 403)

    def test_05_lawyer_scope_insufficient_for_attachments(self):
        """Lawyer with METADATA_ONLY scope is blocked from attachments (HTTP 403)."""
        # Active access, but METADATA_ONLY scope
        self._set_lawyer_access(self.test_case_uuid, LAWYER_A_UUID, "ACTIVE", "METADATA_ONLY")

        # 1. Text messaging and metadata retrieval are permitted
        r_get = client.get(
            f"/api/conversations/{self.case_conv_id}",
            headers={"Authorization": f"Bearer {TOKEN_LAWYER_A}"}
        )
        self.assertEqual(r_get.status_code, 200)

        # 2. Attachment download URL is strictly blocked -> HTTP 403
        r_url = client.get(
            f"/api/conversations/attachments/{self.existing_attachment_id}/url",
            headers={"Authorization": f"Bearer {TOKEN_LAWYER_A}"}
        )
        self.assertEqual(r_url.status_code, 403)
        self.assertIn("scope does not permit document attachment access", r_url.text.lower())

        # 3. Attachment upload is strictly blocked -> HTTP 403
        pdf_bytes = b"%PDF-1.4\n1 0 obj\n<< /Title (Test) >>\nendobj\ntrailer\n<< /Root 1 0 R >>\n%%EOF"
        r_upload = client.post(
            f"/api/conversations/{self.case_conv_id}/attachments",
            headers={"Authorization": f"Bearer {TOKEN_LAWYER_A}"},
            files={"file": ("brief.pdf", pdf_bytes, "application/pdf")}
        )
        self.assertEqual(r_upload.status_code, 403)
        self.assertIn("scope does not permit document attachment access", r_upload.text.lower())

    def test_06_database_verification_failure_fails_closed(self):
        """Database verification error strictly fails closed with HTTP 403 without data leakage."""
        original_table = communication_manager.supabase.table

        def mock_table(table_name: str):
            if table_name == "lawyer_case_access":
                raise Exception("Simulated DB connection failure on lawyer_case_access")
            return original_table(table_name)

        with patch.object(communication_manager.supabase, "table", side_effect=mock_table):
            r = client.get(
                f"/api/conversations/{self.case_conv_id}",
                headers={"Authorization": f"Bearer {TOKEN_LAWYER_A}"}
            )
            # Must fail closed with 403
            self.assertEqual(r.status_code, 403)
            self.assertIn("unable to verify case sharing authorization", r.text.lower())

    def test_07_citizen_and_proctor_workflows_unaffected(self):
        """Citizen case owner and institutional proctors continue working unaffected."""
        # Citizen A accesses case conversation
        r_cit = client.get(
            f"/api/conversations/{self.case_conv_id}",
            headers={"Authorization": f"Bearer {TOKEN_CITIZEN_A}"}
        )
        self.assertEqual(r_cit.status_code, 200)

        # Citizen A gets attachment URL
        r_cit_url = client.get(
            f"/api/conversations/attachments/{self.existing_attachment_id}/url",
            headers={"Authorization": f"Bearer {TOKEN_CITIZEN_A}"}
        )
        self.assertEqual(r_cit_url.status_code, 200)

        # Proctor Xavier accesses case conversation
        r_proc = client.get(
            f"/api/conversations/{self.case_conv_id}",
            headers={"Authorization": f"Bearer {TOKEN_PROCTOR_X}"}
        )
        self.assertEqual(r_proc.status_code, 200)

    # =========================================================================
    # Task 2: Meeting Concurrency & Atomic Database Protection
    # =========================================================================

    def test_08_meeting_first_confirmed_and_second_rejected_sequential(self):
        """Sequential test: First confirmed appointment succeeds; overlapping second is rejected."""
        base_time = datetime.now(timezone.utc) + timedelta(days=5, hours=10)
        start_1 = base_time.replace(minute=0, second=0, microsecond=0)
        end_1 = start_1 + timedelta(minutes=30)

        # Meeting 1
        m1 = client.post(
            "/api/meetings/schedule",
            headers={"Authorization": f"Bearer {TOKEN_CITIZEN_A}"},
            json={
                "lawyer_user_id": LAWYER_A_UUID,
                "scheduled_start": start_1.isoformat(),
                "scheduled_end": end_1.isoformat(),
                "meeting_mode": "ONLINE",
                "agenda": "Meeting 1"
            }
        ).json()

        # Meeting 2 (overlapping: 10:15 - 10:45)
        start_2 = start_1 + timedelta(minutes=15)
        end_2 = start_2 + timedelta(minutes=30)
        m2 = client.post(
            "/api/meetings/schedule",
            headers={"Authorization": f"Bearer {TOKEN_CITIZEN_B}"},
            json={
                "lawyer_user_id": LAWYER_A_UUID,
                "scheduled_start": start_2.isoformat(),
                "scheduled_end": end_2.isoformat(),
                "meeting_mode": "ONLINE",
                "agenda": "Meeting 2"
            }
        ).json()

        # Confirm Meeting 1 -> 200 OK
        r1 = client.patch(
            f"/api/meetings/{m1['id']}/status",
            headers={"Authorization": f"Bearer {TOKEN_LAWYER_A}"},
            json={"status": "CONFIRMED", "online_meeting_url": "https://meet.jit.si/nyaypath-room-1"}
        )
        self.assertEqual(r1.status_code, 200)
        self.assertEqual(r1.json()["status"], "CONFIRMED")

        # Attempt to confirm Meeting 2 -> Rejected with 400
        r2 = client.patch(
            f"/api/meetings/{m2['id']}/status",
            headers={"Authorization": f"Bearer {TOKEN_LAWYER_A}"},
            json={"status": "CONFIRMED", "online_meeting_url": "https://meet.jit.si/nyaypath-room-2"}
        )
        self.assertEqual(r2.status_code, 400)
        self.assertIn("overlapping confirmed meeting", r2.text.lower())

        # Cleanup
        supabase_admin.table("consultation_meetings").delete().in_("id", [m1["id"], m2["id"]]).execute()

    def test_09_meeting_non_overlapping_bookings_both_succeed(self):
        """Adjacent non-overlapping bookings (10:00-10:30 and 10:30-11:00) both confirm successfully."""
        base_time = datetime.now(timezone.utc) + timedelta(days=6, hours=10)
        slot1_start = base_time.replace(minute=0, second=0, microsecond=0)
        slot1_end = slot1_start + timedelta(minutes=30)

        slot2_start = slot1_end  # Starts exactly when slot 1 ends (adjacent)
        slot2_end = slot2_start + timedelta(minutes=30)

        m1 = client.post(
            "/api/meetings/schedule",
            headers={"Authorization": f"Bearer {TOKEN_CITIZEN_A}"},
            json={
                "lawyer_user_id": LAWYER_A_UUID,
                "scheduled_start": slot1_start.isoformat(),
                "scheduled_end": slot1_end.isoformat(),
                "meeting_mode": "ONLINE",
                "agenda": "Adjacent Slot 1"
            }
        ).json()

        m2 = client.post(
            "/api/meetings/schedule",
            headers={"Authorization": f"Bearer {TOKEN_CITIZEN_B}"},
            json={
                "lawyer_user_id": LAWYER_A_UUID,
                "scheduled_start": slot2_start.isoformat(),
                "scheduled_end": slot2_end.isoformat(),
                "meeting_mode": "ONLINE",
                "agenda": "Adjacent Slot 2"
            }
        ).json()

        # Confirm both
        r1 = client.patch(
            f"/api/meetings/{m1['id']}/status",
            headers={"Authorization": f"Bearer {TOKEN_LAWYER_A}"},
            json={"status": "CONFIRMED"}
        )
        r2 = client.patch(
            f"/api/meetings/{m2['id']}/status",
            headers={"Authorization": f"Bearer {TOKEN_LAWYER_A}"},
            json={"status": "CONFIRMED"}
        )

        self.assertEqual(r1.status_code, 200)
        self.assertEqual(r2.status_code, 200)

        # Cleanup
        supabase_admin.table("consultation_meetings").delete().in_("id", [m1["id"], m2["id"]]).execute()

    def test_10_cancelled_appointment_unblocks_future_booking(self):
        """Cancelling a confirmed appointment unblocks future bookings for that time window."""
        base_time = datetime.now(timezone.utc) + timedelta(days=7, hours=11)
        start = base_time.replace(minute=0, second=0, microsecond=0)
        end = start + timedelta(minutes=30)

        m1 = client.post(
            "/api/meetings/schedule",
            headers={"Authorization": f"Bearer {TOKEN_CITIZEN_A}"},
            json={
                "lawyer_user_id": LAWYER_A_UUID,
                "scheduled_start": start.isoformat(),
                "scheduled_end": end.isoformat(),
                "meeting_mode": "ONLINE",
                "agenda": "Booking to be cancelled"
            }
        ).json()

        # Confirm m1
        client.patch(
            f"/api/meetings/{m1['id']}/status",
            headers={"Authorization": f"Bearer {TOKEN_LAWYER_A}"},
            json={"status": "CONFIRMED"}
        )

        # Cancel m1
        r_cancel = client.patch(
            f"/api/meetings/{m1['id']}/status",
            headers={"Authorization": f"Bearer {TOKEN_CITIZEN_A}"},
            json={"status": "CANCELLED"}
        )
        self.assertEqual(r_cancel.status_code, 200)

        # Now book overlapping slot
        m2 = client.post(
            "/api/meetings/schedule",
            headers={"Authorization": f"Bearer {TOKEN_CITIZEN_B}"},
            json={
                "lawyer_user_id": LAWYER_A_UUID,
                "scheduled_start": start.isoformat(),
                "scheduled_end": end.isoformat(),
                "meeting_mode": "ONLINE",
                "agenda": "Booking after cancellation"
            }
        ).json()

        r_conf2 = client.patch(
            f"/api/meetings/{m2['id']}/status",
            headers={"Authorization": f"Bearer {TOKEN_LAWYER_A}"},
            json={"status": "CONFIRMED"}
        )
        self.assertEqual(r_conf2.status_code, 200)
        self.assertEqual(r_conf2.json()["status"], "CONFIRMED")

        # Cleanup
        supabase_admin.table("consultation_meetings").delete().in_("id", [m1["id"], m2["id"]]).execute()

    def test_11_meeting_privacy_masking_intact(self):
        """Unconfirmed meetings mask sensitive credentials; confirmed meetings reveal them."""
        base_time = datetime.now(timezone.utc) + timedelta(days=8, hours=14)
        start = base_time.replace(minute=0, second=0, microsecond=0)
        end = start + timedelta(minutes=30)

        m = client.post(
            "/api/meetings/schedule",
            headers={"Authorization": f"Bearer {TOKEN_CITIZEN_A}"},
            json={
                "lawyer_user_id": LAWYER_A_UUID,
                "scheduled_start": start.isoformat(),
                "scheduled_end": end.isoformat(),
                "meeting_mode": "ONLINE",
                "agenda": "Privacy test"
            }
        ).json()

        # Before confirmation -> masked
        detail_unconf = client.get(
            f"/api/meetings/{m['id']}",
            headers={"Authorization": f"Bearer {TOKEN_CITIZEN_A}"}
        ).json()
        self.assertIsNone(detail_unconf["online_meeting_url"])
        self.assertIsNone(detail_unconf["location_details"])
        self.assertIsNone(detail_unconf["phone_contact"])

        # Confirm meeting
        client.patch(
            f"/api/meetings/{m['id']}/status",
            headers={"Authorization": f"Bearer {TOKEN_LAWYER_A}"},
            json={
                "status": "CONFIRMED",
                "online_meeting_url": "https://nyaypath.gov.in/room/court-42"
            }
        )

        # After confirmation -> revealed
        detail_conf = client.get(
            f"/api/meetings/{m['id']}",
            headers={"Authorization": f"Bearer {TOKEN_CITIZEN_A}"}
        ).json()
        self.assertEqual(detail_conf["online_meeting_url"], "https://nyaypath.gov.in/room/court-42")

        # Cleanup
        supabase_admin.table("consultation_meetings").delete().eq("id", m["id"]).execute()

    def test_12_concurrent_simultaneous_confirmations_race_condition(self):
        """Two simultaneous confirmation requests for overlapping slots result in exactly ONE success."""
        base_time = datetime.now(timezone.utc) + timedelta(days=9, hours=10)
        start_1 = base_time.replace(minute=0, second=0, microsecond=0)
        end_1 = start_1 + timedelta(minutes=45)

        # Create Meeting A and Meeting B with overlapping intervals
        m_a = client.post(
            "/api/meetings/schedule",
            headers={"Authorization": f"Bearer {TOKEN_CITIZEN_A}"},
            json={
                "lawyer_user_id": LAWYER_A_UUID,
                "scheduled_start": start_1.isoformat(),
                "scheduled_end": end_1.isoformat(),
                "meeting_mode": "ONLINE",
                "agenda": "Concurrent Meeting A"
            }
        ).json()

        # Overlapping Meeting B (15 minutes into Meeting A's slot)
        start_2 = start_1 + timedelta(minutes=15)
        end_2 = start_2 + timedelta(minutes=45)
        m_b = client.post(
            "/api/meetings/schedule",
            headers={"Authorization": f"Bearer {TOKEN_CITIZEN_B}"},
            json={
                "lawyer_user_id": LAWYER_A_UUID,
                "scheduled_start": start_2.isoformat(),
                "scheduled_end": end_2.isoformat(),
                "meeting_mode": "ONLINE",
                "agenda": "Concurrent Meeting B"
            }
        ).json()

        meeting_a_id = m_a["id"]
        meeting_b_id = m_b["id"]

        def confirm_meeting(meeting_id: str):
            thread_client = TestClient(app)
            return thread_client.patch(
                f"/api/meetings/{meeting_id}/status",
                headers={"Authorization": f"Bearer {TOKEN_LAWYER_A}"},
                json={"status": "CONFIRMED", "notes": f"Confirmed concurrently: {meeting_id}"}
            )

        # Simultaneously fire both confirmation requests
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
            fut_a = executor.submit(confirm_meeting, meeting_a_id)
            fut_b = executor.submit(confirm_meeting, meeting_b_id)
            res_a = fut_a.result()
            res_b = fut_b.result()

        status_codes = [res_a.status_code, res_b.status_code]
        print(f"\n  [Concurrency Test] Status codes returned: {status_codes}")

        # Verification: Exactly ONE must be 200, and exactly ONE must be 400
        self.assertEqual(sorted(status_codes), [200, 400], f"Expected [200, 400], got {status_codes}")

        # Database Verification: Verify only 1 row in PostgreSQL is CONFIRMED
        db_rows = supabase_admin.table("consultation_meetings").select("id, status").in_(
            "id", [meeting_a_id, meeting_b_id]
        ).execute()

        statuses = [row["status"] for row in db_rows.data]
        self.assertEqual(statuses.count("CONFIRMED"), 1, f"Expected exactly 1 confirmed meeting in DB, found: {statuses}")
        self.assertEqual(statuses.count("REQUESTED"), 1, f"Expected 1 unconfirmed meeting, found: {statuses}")

        # Cleanup
        supabase_admin.table("consultation_meetings").delete().in_("id", [meeting_a_id, meeting_b_id]).execute()


if __name__ == "__main__":
    unittest.main()

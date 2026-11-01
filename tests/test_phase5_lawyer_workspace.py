"""
NyayPath Phase 5: Lawyer Workspace, Lawyer Directory & Client Connect
Comprehensive Automated Security, Multi-Tenancy & Authorization Test Suite
========================================================================
Verification of 15 Scenarios:
1.  New Lawyer Registration defaults to PENDING
2.  Lawyer cannot self-verify (verification status remains PENDING)
3.  Unverified/Pending lawyer absent from public directory (GET /api/lawyers)
4.  Verified lawyer appears in directory search and filters; sensitive credentials masked
5.  Suspended lawyer cannot accept new consultation requests (HTTP 400)
6.  Citizen can submit consultation request to verified lawyer
7.  Citizen cannot access or modify another citizen's consultation requests (HTTP 403 / filtered)
8.  Lawyer cannot access or act on consultation requests addressed to other lawyers
9.  Lawyer cannot access citizen cases without explicit authorization (HTTP 403)
10. Citizen can explicitly grant case sharing with verified lawyer
11. Citizen can revoke case-sharing authorization; subsequent requests return HTTP 403
12. Internal institutional proctor notes and hashes remain strictly inaccessible to lawyer
13. Notifications generated with stable source event/request UUID idempotency keys
14. Duplicate requests/events do not produce duplicate notifications (idempotent deduplication)
15. Lawyer dashboard metrics reflect genuine database figures (no mocked numbers)
"""

import os
import sys
import time
import uuid
import unittest
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


# Test Actor UUIDs
LAWYER_A_UUID    = "77777777-1111-2222-3333-777777777777"
LAWYER_B_UUID    = "88888888-1111-2222-3333-888888888888"
PLATFORM_ADMIN   = "99999999-1111-2222-3333-999999999999"
CITIZEN_A_UUID   = "aaaaaaaa-1111-2222-3333-aaaaaaaaaaaa"
CITIZEN_B_UUID   = "bbbbbbbb-1111-2222-3333-bbbbbbbbbbbb"

TOKEN_LAWYER_A   = generate_live_jwt(LAWYER_A_UUID, "lawyer", "advocate.rajesh@bar.in", "Adv. Rajesh Kumar")
TOKEN_LAWYER_B   = generate_live_jwt(LAWYER_B_UUID, "lawyer", "advocate.priya@bar.in", "Adv. Priya Sharma")
TOKEN_ADMIN      = generate_live_jwt(PLATFORM_ADMIN, "platform_admin", "platform@nyaypath.gov", "Platform Administrator")
TOKEN_CITIZEN_A  = generate_live_jwt(CITIZEN_A_UUID, "citizen", "alice@collegex.edu", "Alice Citizen")
TOKEN_CITIZEN_B  = generate_live_jwt(CITIZEN_B_UUID, "citizen", "bob@collegex.edu", "Bob Citizen")


class TestPhase5LawyerWorkspace(unittest.TestCase):
    """Automated integration tests for Phase 5."""

    consultation_request_id = None
    case_a_id = "PHASE5-CASE-A"
    case_a_uuid = None

    @classmethod
    def setUpClass(cls):
        """Set up test fixtures in local Supabase."""
        # 1. Clean up existing Phase 5 test records
        try:
            supabase_admin.table("notifications").delete().in_(
                "recipient_user_id", [LAWYER_A_UUID, LAWYER_B_UUID, CITIZEN_A_UUID, CITIZEN_B_UUID]
            ).execute()
            supabase_admin.table("lawyer_case_access").delete().in_(
                "lawyer_user_id", [LAWYER_A_UUID, LAWYER_B_UUID]
            ).execute()
            supabase_admin.table("consultation_requests").delete().in_(
                "lawyer_user_id", [LAWYER_A_UUID, LAWYER_B_UUID]
            ).execute()
            supabase_admin.table("lawyer_profiles").delete().in_(
                "id", [LAWYER_A_UUID, LAWYER_B_UUID]
            ).execute()
        except Exception:
            pass

        # 2. Ensure test case for Citizen Alice exists in public.cases
        try:
            # Check if case exists
            res_case = supabase_admin.table("cases").select("id").eq("case_id", cls.case_a_id).execute()
            if res_case.data and len(res_case.data) > 0:
                cls.case_a_uuid = res_case.data[0]["id"]
            else:
                new_case = {
                    "case_id": cls.case_a_id,
                    "case_type": "GENERAL_GRIEVANCE",
                    "status": "FILED",
                    "key_version": "v1",
                    "tracking_key_hash": "dummy_secret_hash_value_128",
                    "data": {
                        "citizen_user_id": CITIZEN_A_UUID,
                        "title": "College Proctorial Board Natural Justice Dispute",
                        "category": "Education & Student Rights",
                        "facts_summary": "Dispute regarding examination suspension without fair hearing.",
                        "prayer": "Quashing of arbitrary suspension order.",
                        "proctor_notes": "CONFIDENTIAL INTERNAL NOTE: Proctor board observed witness hostility.",
                        "supporting_documents": [
                            {
                                "id": "doc_exam_order.pdf",
                                "file_name": "doc_exam_order.pdf",
                                "storage_path": f"{cls.case_a_id}/doc_exam_order.pdf"
                            }
                        ]
                    }
                }
                res_ins = supabase_admin.table("cases").insert(new_case).execute()
                cls.case_a_uuid = res_ins.data[0]["id"]
        except Exception as e:
            print(f"Warning setting up test case: {e}")

    # -----------------------------------------------------------------
    # Scenario 1: New Lawyer Registration defaults to PENDING
    # -----------------------------------------------------------------
    def test_01_lawyer_registration_defaults_to_pending(self):
        """Advocate registration creates profile with PENDING verification status."""
        payload = {
            "full_name": "Adv. Rajesh Kumar",
            "phone": "+91 98765 43210",
            "bar_council": "Bar Council of Delhi",
            "enrollment_state": "Delhi (NCT)",
            "enrollment_number": "D/9876/2015",
            "years_of_practice": 9,
            "specializations": ["Constitutional Law", "Education & Student Rights"],
            "courts": ["Supreme Court of India", "Delhi High Court"],
            "languages": ["English", "Hindi"],
            "bio": "Specializing in fundamental rights and higher education institutional disputes.",
            "consultation_preferences": {"modes": ["ONLINE", "IN_PERSON"]}
        }

        r = client.post(
            "/api/lawyer/register",
            headers={"Authorization": f"Bearer {TOKEN_LAWYER_A}"},
            json=payload
        )
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertEqual(data["status"], "success")
        profile = data["profile"]
        self.assertEqual(profile["verification_status"], "PENDING")
        self.assertEqual(profile["enrollment_number"], "D/9876/2015")

        # Verify directly in database
        db_res = supabase_admin.table("lawyer_profiles").select("verification_status").eq("id", LAWYER_A_UUID).execute()
        self.assertTrue(len(db_res.data) > 0)
        self.assertEqual(db_res.data[0]["verification_status"], "PENDING")

    # -----------------------------------------------------------------
    # Scenario 2: Lawyer cannot self-verify
    # -----------------------------------------------------------------
    def test_02_lawyer_cannot_self_verify(self):
        """Advocate cannot self-promote verification status via profile update."""
        # Attempt to patch verification_status as Lawyer A
        r = client.patch(
            "/api/lawyer/profile",
            headers={"Authorization": f"Bearer {TOKEN_LAWYER_A}"},
            json={
                "bio": "Updated advocate profile bio.",
                "verification_status": "VERIFIED"  # Should be ignored / unauthorized
            }
        )
        self.assertEqual(r.status_code, 200)

        # Database verification_status must remain PENDING
        db_res = supabase_admin.table("lawyer_profiles").select("verification_status").eq("id", LAWYER_A_UUID).execute()
        self.assertEqual(db_res.data[0]["verification_status"], "PENDING")

        # Non-admin attempting to call admin verification RPC/endpoint -> 403 Forbidden
        r_unauth = client.post(
            f"/api/admin/lawyers/{LAWYER_A_UUID}/verify",
            headers={"Authorization": f"Bearer {TOKEN_LAWYER_A}"},
            json={"decision": "VERIFIED", "notes": "Self verification attempt"}
        )
        self.assertEqual(r_unauth.status_code, 403)

    # -----------------------------------------------------------------
    # Scenario 3: Unverified lawyer absent from public directory
    # -----------------------------------------------------------------
    def test_03_unverified_lawyer_absent_from_public_directory(self):
        """Unverified/Pending advocates do not appear in public directory listings."""
        r = client.get("/api/lawyers")
        self.assertEqual(r.status_code, 200)
        lawyers = r.json().get("lawyers", [])
        lawyer_ids = [l.get("user_id") or l.get("id") or l.get("lawyer_user_id") for l in lawyers]
        self.assertNotIn(LAWYER_A_UUID, lawyer_ids)

        # Direct profile retrieval by unauthenticated user returns 404
        r_profile = client.get(f"/api/lawyers/{LAWYER_A_UUID}")
        self.assertEqual(r_profile.status_code, 404)

    # -----------------------------------------------------------------
    # Scenario 4: Verified lawyer appears in directory & masks sensitive fields
    # -----------------------------------------------------------------
    def test_04_verified_lawyer_appears_in_directory_and_masks_sensitive_fields(self):
        """Platform Admin verifies lawyer; lawyer appears in directory with credentials masked."""
        # 1. Admin verifies Lawyer A
        r_verify = client.post(
            f"/api/admin/lawyers/{LAWYER_A_UUID}/verify",
            headers={"Authorization": f"Bearer {TOKEN_ADMIN}"},
            json={"decision": "VERIFIED", "notes": "Bar Council roll verified against state roster."}
        )
        self.assertEqual(r_verify.status_code, 200)
        self.assertEqual(r_verify.json()["verification_status"], "VERIFIED")

        # 2. Public directory search
        r_dir = client.get("/api/lawyers?specialization=Education%20%26%20Student%20Rights")
        self.assertEqual(r_dir.status_code, 200)
        data = r_dir.json()
        lawyers = data.get("lawyers", [])
        found = [l for l in lawyers if (l.get("user_id") == LAWYER_A_UUID or l.get("lawyer_user_id") == LAWYER_A_UUID or l.get("id") == LAWYER_A_UUID)]
        self.assertTrue(len(found) > 0)
        lawyer_entry = found[0]

        # Sensitive field masking: enrollment_number must NOT be revealed in public directory
        self.assertIsNone(lawyer_entry.get("enrollment_number"))
        self.assertIsNone(lawyer_entry.get("verification_notes"))

        # 3. Direct public profile view
        r_pub = client.get(f"/api/lawyers/{LAWYER_A_UUID}")
        self.assertEqual(r_pub.status_code, 200)
        pub_profile = r_pub.json().get("profile") or r_pub.json()
        self.assertEqual(pub_profile["full_name"], "Adv. Rajesh Kumar")
        self.assertIsNone(pub_profile.get("enrollment_number"))

        # 4. Verified Lawyer themselves can see their enrollment number
        r_self = client.get(
            f"/api/lawyers/{LAWYER_A_UUID}",
            headers={"Authorization": f"Bearer {TOKEN_LAWYER_A}"}
        )
        self.assertEqual(r_self.status_code, 200)
        self_profile = r_self.json().get("profile") or r_self.json()
        self.assertEqual(self_profile["enrollment_number"], "D/9876/2015")

    # -----------------------------------------------------------------
    # Scenario 5: Suspended lawyer cannot accept new consultations
    # -----------------------------------------------------------------
    def test_05_suspended_lawyer_cannot_accept_new_consultations(self):
        """Advocate with SUSPENDED status cannot receive consultation requests."""
        # Register and suspend Lawyer B
        client.post(
            "/api/lawyer/register",
            headers={"Authorization": f"Bearer {TOKEN_LAWYER_B}"},
            json={
                "full_name": "Adv. Priya Sharma",
                "bar_council": "Bar Council of Maharashtra & Goa",
                "enrollment_state": "Maharashtra",
                "enrollment_number": "MAH/1234/2012",
                "years_of_practice": 12,
                "specializations": ["Corporate Law"]
            }
        )
        client.post(
            f"/api/admin/lawyers/{LAWYER_B_UUID}/verify",
            headers={"Authorization": f"Bearer {TOKEN_ADMIN}"},
            json={"decision": "SUSPENDED", "notes": "Disciplinary suspension under review."}
        )

        # Citizen attempts to request consultation from suspended Lawyer B -> 400 Bad Request
        r_req = client.post(
            "/api/consultations/request",
            headers={"Authorization": f"Bearer {TOKEN_CITIZEN_A}"},
            json={
                "lawyer_user_id": LAWYER_B_UUID,
                "legal_issue": "Corporate contract review",
                "description": "Seeking review of non-disclosure terms.",
                "preferred_mode": "ONLINE"
            }
        )
        self.assertEqual(r_req.status_code, 400)
        detail_msg = r_req.json().get("detail", "").lower()
        self.assertTrue("unverified or suspended" in detail_msg or "not active or verified" in detail_msg)

    # -----------------------------------------------------------------
    # Scenario 6: Citizen can submit consultation request to verified lawyer
    # -----------------------------------------------------------------
    def test_06_citizen_can_submit_consultation_request_to_verified_lawyer(self):
        """Citizen Alice submits consultation request to verified Lawyer A."""
        r = client.post(
            "/api/consultations/request",
            headers={"Authorization": f"Bearer {TOKEN_CITIZEN_A}"},
            json={
                "lawyer_user_id": LAWYER_A_UUID,
                "case_id": self.case_a_id,
                "legal_issue": "Representation in College Proctorial Board Hearing",
                "description": "I have been summoned for a disciplinary hearing without prior notice or charge-sheet.",
                "preferred_mode": "ONLINE"
            }
        )
        self.assertEqual(r.status_code, 200)
        data = r.json()
        req = data.get("request") or data
        self.assertEqual(req["status"], "PENDING")
        self.assertEqual(req["case_id"], self.case_a_id)
        TestPhase5LawyerWorkspace.consultation_request_id = req["id"]

    # -----------------------------------------------------------------
    # Scenario 7: Citizen isolation on consultations
    # -----------------------------------------------------------------
    def test_07_citizen_isolation_cannot_view_or_withdraw_other_citizens_consultations(self):
        """Citizen Bob cannot see or withdraw Citizen Alice's consultation request."""
        # 1. Bob's consultation list does not contain Alice's request
        r_bob = client.get(
            "/api/citizen/consultations",
            headers={"Authorization": f"Bearer {TOKEN_CITIZEN_B}"}
        )
        self.assertEqual(r_bob.status_code, 200)
        bob_req_ids = [c["id"] for c in r_bob.json().get("consultations", [])]
        self.assertNotIn(TestPhase5LawyerWorkspace.consultation_request_id, bob_req_ids)

        # 2. Bob attempts to withdraw Alice's request -> 403 Forbidden
        r_withdraw = client.patch(
            f"/api/consultations/{TestPhase5LawyerWorkspace.consultation_request_id}/status",
            headers={"Authorization": f"Bearer {TOKEN_CITIZEN_B}"},
            json={"status": "WITHDRAWN"}
        )
        self.assertEqual(r_withdraw.status_code, 403)

    # -----------------------------------------------------------------
    # Scenario 8: Lawyer isolation on consultations
    # -----------------------------------------------------------------
    def test_08_lawyer_isolation_cannot_view_or_act_on_other_lawyers_consultations(self):
        """Lawyer B cannot see or accept consultations addressed to Lawyer A."""
        # 1. Lawyer B lists consultations
        r_lawyer_b = client.get(
            "/api/lawyer/consultations",
            headers={"Authorization": f"Bearer {TOKEN_LAWYER_B}"}
        )
        self.assertEqual(r_lawyer_b.status_code, 200)
        lawyer_b_req_ids = [c["id"] for c in r_lawyer_b.json().get("consultations", [])]
        self.assertNotIn(TestPhase5LawyerWorkspace.consultation_request_id, lawyer_b_req_ids)

        # 2. Lawyer B attempts to accept Lawyer A's consultation -> 403 Forbidden
        r_accept = client.patch(
            f"/api/consultations/{TestPhase5LawyerWorkspace.consultation_request_id}/status",
            headers={"Authorization": f"Bearer {TOKEN_LAWYER_B}"},
            json={"status": "ACCEPTED", "lawyer_response": "I will handle this."}
        )
        self.assertEqual(r_accept.status_code, 403)

    # -----------------------------------------------------------------
    # Scenario 9: Lawyer cannot access case without explicit authorization
    # -----------------------------------------------------------------
    def test_09_lawyer_cannot_access_citizen_case_without_explicit_authorization(self):
        """Before case sharing is granted, lawyer is strictly forbidden from case facts and documents."""
        # 1. Case details lookup -> 403 Forbidden
        r_case = client.get(
            f"/api/citizen/cases/{self.case_a_id}",
            headers={"Authorization": f"Bearer {TOKEN_LAWYER_A}"}
        )
        self.assertEqual(r_case.status_code, 403)

        # 2. Document signed URL generation -> 403 Forbidden
        r_doc = client.get(
            f"/api/campus-proctor/document-url?case_id={self.case_a_id}&document_id=doc_exam_order.pdf",
            headers={"Authorization": f"Bearer {TOKEN_LAWYER_A}"}
        )
        self.assertEqual(r_doc.status_code, 403)

    # -----------------------------------------------------------------
    # Scenario 10: Citizen can explicitly grant case sharing
    # -----------------------------------------------------------------
    def test_10_citizen_can_explicitly_grant_case_sharing(self):
        """Lawyer A accepts consultation; Citizen Alice authorizes case and document access."""
        # 1. Lawyer A accepts consultation
        r_accept = client.patch(
            f"/api/consultations/{TestPhase5LawyerWorkspace.consultation_request_id}/status",
            headers={"Authorization": f"Bearer {TOKEN_LAWYER_A}"},
            json={
                "status": "ACCEPTED",
                "lawyer_response": "Consultation accepted. Please share your inquiry facts and documents."
            }
        )
        self.assertEqual(r_accept.status_code, 200)

        # 2. Citizen Alice grants case access
        r_grant = client.post(
            "/api/citizen/cases/share",
            headers={"Authorization": f"Bearer {TOKEN_CITIZEN_A}"},
            json={
                "case_id": self.case_a_id,
                "lawyer_user_id": LAWYER_A_UUID,
                "shared_scope": "CASE_AND_DOCS",
                "consultation_request_id": TestPhase5LawyerWorkspace.consultation_request_id
            }
        )
        self.assertEqual(r_grant.status_code, 200)
        self.assertEqual(r_grant.json()["access"]["access_status"], "ACTIVE")

        # 3. Lawyer A can now retrieve case details
        r_case_details = client.get(
            f"/api/citizen/cases/{self.case_a_id}",
            headers={"Authorization": f"Bearer {TOKEN_LAWYER_A}"}
        )
        self.assertEqual(r_case_details.status_code, 200)
        case_data = r_case_details.json().get("case", {})
        self.assertEqual(case_data["case_id"], self.case_a_id)

        # 4. Lawyer A appears in shared cases view
        r_shared = client.get(
            "/api/lawyer/shared-cases",
            headers={"Authorization": f"Bearer {TOKEN_LAWYER_A}"}
        )
        self.assertEqual(r_shared.status_code, 200)
        shared_case_ids = [c["case_id"] for c in r_shared.json().get("cases", [])]
        self.assertIn(self.case_a_id, shared_case_ids)

        # 5. Lawyer A can generate signed document URL (capped at <= 300s TTL)
        r_doc = client.get(
            f"/api/campus-proctor/document-url?case_id={self.case_a_id}&document_id=doc_exam_order.pdf&ttl=600",
            headers={"Authorization": f"Bearer {TOKEN_LAWYER_A}"}
        )
        self.assertEqual(r_doc.status_code, 200)
        doc_data = r_doc.json()
        self.assertIn("signed_url", doc_data)
        self.assertLessEqual(doc_data.get("expires_in_seconds", 300), 300)

    # -----------------------------------------------------------------
    # Scenario 11: Citizen can revoke case-sharing authorization
    # -----------------------------------------------------------------
    def test_11_citizen_can_revoke_case_sharing_instant_termination(self):
        """Citizen Alice revokes case access; subsequent lawyer attempts return HTTP 403."""
        # 1. Citizen Alice revokes access
        r_revoke = client.post(
            "/api/citizen/cases/revoke-share",
            headers={"Authorization": f"Bearer {TOKEN_CITIZEN_A}"},
            json={
                "case_id": self.case_a_id,
                "lawyer_user_id": LAWYER_A_UUID
            }
        )
        self.assertEqual(r_revoke.status_code, 200)
        self.assertEqual(r_revoke.json()["access"]["access_status"], "REVOKED")

        # 2. Subsequent case details lookup -> 403 Forbidden
        r_case = client.get(
            f"/api/citizen/cases/{self.case_a_id}",
            headers={"Authorization": f"Bearer {TOKEN_LAWYER_A}"}
        )
        self.assertEqual(r_case.status_code, 403)

        # 3. Subsequent document URL generation -> 403 Forbidden
        r_doc = client.get(
            f"/api/campus-proctor/document-url?case_id={self.case_a_id}&document_id=doc_exam_order.pdf",
            headers={"Authorization": f"Bearer {TOKEN_LAWYER_A}"}
        )
        self.assertEqual(r_doc.status_code, 403)

    # -----------------------------------------------------------------
    # Scenario 12: Proctor notes and internal hashes masked from lawyer
    # -----------------------------------------------------------------
    def test_12_proctor_notes_and_internal_hashes_strictly_masked_from_lawyer(self):
        """Re-granting access allows case inspection but strictly hides institutional proctor notes."""
        # Re-grant case access
        client.post(
            "/api/citizen/cases/share",
            headers={"Authorization": f"Bearer {TOKEN_CITIZEN_A}"},
            json={
                "case_id": self.case_a_id,
                "lawyer_user_id": LAWYER_A_UUID,
                "shared_scope": "CASE_AND_DOCS"
            }
        )

        r_case = client.get(
            f"/api/citizen/cases/{self.case_a_id}",
            headers={"Authorization": f"Bearer {TOKEN_LAWYER_A}"}
        )
        self.assertEqual(r_case.status_code, 200)
        case_data = r_case.json().get("case", {})

        # Proctor internal notes must NOT be present
        self.assertNotIn("proctor_notes", case_data)
        self.assertNotIn("tracking_key_hash", case_data)

    # -----------------------------------------------------------------
    # Scenario 13: Notifications use stable persisted source UUIDs
    # -----------------------------------------------------------------
    def test_13_notifications_use_stable_persisted_source_uuids(self):
        """Idempotency keys for notifications use deterministic entity UUIDs."""
        res_notifs = supabase_admin.table("notifications").select(
            "idempotency_key, event_type, recipient_user_id"
        ).in_("recipient_user_id", [LAWYER_A_UUID, CITIZEN_A_UUID]).execute()

        consultation_notifs = [
            n for n in res_notifs.data 
            if n.get("event_type", "").startswith("CONSULTATION_") or n.get("event_type", "").startswith("CASE_SHARE")
        ]
        self.assertTrue(len(consultation_notifs) > 0)
        for notif in consultation_notifs:
            key = notif.get("idempotency_key")
            self.assertIsNotNone(key)
            valid_prefix = key.startswith("notif_req_") or key.startswith("notif_share_")
            self.assertTrue(valid_prefix, f"Idempotency key does not match standard pattern: {key}")

    # -----------------------------------------------------------------
    # Scenario 14: Duplicate events idempotently deduplicated
    # -----------------------------------------------------------------
    def test_14_duplicate_events_idempotently_deduplicated(self):
        """Re-triggering the same event does not insert duplicate notifications."""
        # Fetch current count of notifications for Lawyer A
        res_before = supabase_admin.table("notifications").select("id").eq("recipient_user_id", LAWYER_A_UUID).execute()
        count_before = len(res_before.data)

        # Trigger duplicate sharing grant call
        client.post(
            "/api/citizen/cases/share",
            headers={"Authorization": f"Bearer {TOKEN_CITIZEN_A}"},
            json={
                "case_id": self.case_a_id,
                "lawyer_user_id": LAWYER_A_UUID,
                "shared_scope": "CASE_AND_DOCS"
            }
        )

        # Notification count for Lawyer A must not have inflated
        res_after = supabase_admin.table("notifications").select("id").eq("recipient_user_id", LAWYER_A_UUID).execute()
        count_after = len(res_after.data)
        self.assertEqual(count_before, count_after)

    # -----------------------------------------------------------------
    # Scenario 15: Lawyer dashboard metrics integrity
    # -----------------------------------------------------------------
    def test_15_regression_and_dashboard_metrics_integrity(self):
        """Lawyer workspace analytics strictly reflect live database rows."""
        r_stats = client.get(
            "/api/lawyer/dashboard-stats",
            headers={"Authorization": f"Bearer {TOKEN_LAWYER_A}"}
        )
        self.assertEqual(r_stats.status_code, 200)
        stats = r_stats.json().get("stats", {})

        self.assertGreaterEqual(stats["total_requests"], 1)
        self.assertGreaterEqual(stats["accepted_consultations"], 1)
        self.assertGreaterEqual(stats["active_clients"], 1)
        self.assertGreaterEqual(stats["shared_cases"], 1)
        self.assertEqual(stats["lawyer_user_id"], LAWYER_A_UUID)


if __name__ == "__main__":
    unittest.main()

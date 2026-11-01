"""
NyayPath Phase 7 Integration Test Suite
=======================================
Validates Platform Administration, Global Oversight, User Management,
Institution Management, Lawyer Verification, Global Case Oversight,
Immutable Audit Trails, and System Health.
"""

import os
import sys
import time
import uuid
import unittest
from datetime import datetime, timezone

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
from api.platform_admin import platform_admin_manager
from supabase import create_client

client = TestClient(app)
supabase_admin = create_client(
    os.environ["SUPABASE_URL"],
    os.environ["SUPABASE_SECRET_KEY"]
)

JWT_SECRET = "super-secret-jwt-token-with-at-least-32-characters-long"

def generate_live_jwt(user_id: str, role: str, email: str, name: str, institution_id: str = "INST_DEFAULT", account_status: str = "active") -> str:
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
            "account_status": account_status
        },
        "user_metadata": {
            "full_name": name,
            "email": email
        }
    }
    return jwt.encode(payload, JWT_SECRET, algorithm="HS256")


PLATFORM_ADMIN_UUID = "99999999-1111-2222-3333-999999999999"
INST_ADMIN_UUID     = "44444444-1111-2222-3333-444444444444"
CITIZEN_A_UUID      = "aaaaaaaa-1111-2222-3333-aaaaaaaaaaaa"
LAWYER_A_UUID       = "77777777-1111-2222-3333-777777777777"
FAKE_ADMIN_UUID     = "12345678-0000-0000-0000-123456789012"

TOKEN_ADMIN      = generate_live_jwt(PLATFORM_ADMIN_UUID, "platform_admin", "platform@nyaypath.gov", "Platform Administrator", "*")
TOKEN_INST_ADMIN = generate_live_jwt(INST_ADMIN_UUID, "institution_admin", "irene@collegex.edu", "Irene Inst Admin", "INST_COLLEGE_X")
TOKEN_CITIZEN    = generate_live_jwt(CITIZEN_A_UUID, "citizen", "alice@collegex.edu", "Alice Citizen", "INST_COLLEGE_X")
TOKEN_LAWYER     = generate_live_jwt(LAWYER_A_UUID, "lawyer", "advocate.rajesh@bar.in", "Adv. Rajesh Kumar")
TOKEN_FAKE_ADMIN = generate_live_jwt(FAKE_ADMIN_UUID, "platform_admin", "attacker@evil.com", "Forged Admin", "*")


class TestPhase7PlatformAdmin(unittest.TestCase):
    """Integration test suite for Phase 7 Platform Administration."""

    @classmethod
    def setUpClass(cls):
        """Ensure baseline fixtures are seeded in local Supabase."""
        # Ensure platform admin exists and is active
        admin_check = supabase_admin.table("platform_admins").select("id").eq("user_id", PLATFORM_ADMIN_UUID).execute()
        if not admin_check.data:
            supabase_admin.table("platform_admins").insert({
                "user_id": PLATFORM_ADMIN_UUID,
                "email": "platform@nyaypath.gov",
                "account_status": "active"
            }).execute()

        # Ensure citizen test case exists
        case_res = supabase_admin.table("cases").select("id").eq("case_id", "PHASE7-CASE-001").execute()
        if not case_res.data:
            supabase_admin.table("cases").insert({
                "case_id": "PHASE7-CASE-001",
                "case_type": "CAMPUS_GRIEVANCE",
                "status": "UNDER_INQUIRY",
                "key_version": "v1",
                "tracking_key_hash": "hash_phase7_test",
                "data": {
                    "institution_id": "INST_COLLEGE_X",
                    "student_name": "Confidential Student Alice",
                    "roll_number": "CS-2026-9999",
                    "category": "Academic & Evaluation",
                    "severity": "HIGH",
                    "confidentiality_mode": "CONFIDENTIAL",
                    "proctor_notes": "Internal committee notes regarding inquiry."
                }
            }).execute()

    # =========================================================================
    # 1 & 2. Role Isolation & Authoritative Access Checks
    # =========================================================================

    def test_01_non_admin_cannot_access_platform_admin_endpoints(self):
        """Citizens, lawyers, and anonymous users are blocked from admin APIs (HTTP 401 / 403)."""
        # Anonymous -> 401
        r_anon = client.get("/api/admin/overview")
        self.assertEqual(r_anon.status_code, 401)

        # Citizen -> 403
        r_cit = client.get("/api/admin/overview", headers={"Authorization": f"Bearer {TOKEN_CITIZEN}"})
        self.assertEqual(r_cit.status_code, 403)
        self.assertIn("lacks platform administrator privileges", r_cit.text.lower())

        # Lawyer -> 403
        r_law = client.get("/api/admin/users", headers={"Authorization": f"Bearer {TOKEN_LAWYER}"})
        self.assertEqual(r_law.status_code, 403)

    def test_02_institution_admin_cannot_access_platform_admin(self):
        """Institution administrators are strictly denied access to platform-wide admin (HTTP 403)."""
        resp = client.get(
            "/api/admin/overview",
            headers={"Authorization": f"Bearer {TOKEN_INST_ADMIN}"}
        )
        self.assertEqual(resp.status_code, 403)
        self.assertIn("lacks platform administrator privileges", resp.text.lower())

    def test_03_forged_platform_admin_jwt_rejected_by_database_check(self):
        """A JWT with role='platform_admin' but no active row in public.platform_admins is rejected (HTTP 403)."""
        resp = client.get(
            "/api/admin/overview",
            headers={"Authorization": f"Bearer {TOKEN_FAKE_ADMIN}"}
        )
        self.assertEqual(resp.status_code, 403)
        self.assertIn("no authoritative platform administrator record found", resp.text.lower())

    # =========================================================================
    # 3. Global Statistics & Telemetry
    # =========================================================================

    def test_04_authorized_admin_views_global_statistics(self):
        """Authorized Platform Administrator can view global platform statistics."""
        resp = client.get(
            "/api/admin/overview",
            headers={"Authorization": f"Bearer {TOKEN_ADMIN}"}
        )
        self.assertEqual(resp.status_code, 200, resp.text)
        data = resp.json()

        # Check required fields
        for field in ["total_users", "citizens", "students", "lawyers", "institutions", "total_cases", "active_cases"]:
            self.assertIn(field, data)
            self.assertIsInstance(data[field], int)
            self.assertGreaterEqual(data[field], 0)

    def test_05_admin_views_activity_overview(self):
        """Platform Administrator can view recent activity feed."""
        resp = client.get(
            "/api/admin/activity?limit=5",
            headers={"Authorization": f"Bearer {TOKEN_ADMIN}"}
        )
        self.assertEqual(resp.status_code, 200)
        self.assertIn("activities", resp.json())
        self.assertIsInstance(resp.json()["activities"], list)

    # =========================================================================
    # 4 & 5. User Management & Anti-Self-Modification
    # =========================================================================

    def test_06_admin_lists_users_with_filtering(self):
        """Platform Administrator can list users with role and status filtering."""
        resp = client.get(
            "/api/admin/users?role=citizen",
            headers={"Authorization": f"Bearer {TOKEN_ADMIN}"}
        )
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertIn("users", body)
        self.assertIn("total", body)
        for u in body["users"]:
            self.assertEqual(u["role"], "citizen")

    def test_07_admin_cannot_alter_own_account_status(self):
        """Administrator cannot modify their own account status (Anti-privilege escalation)."""
        resp = client.patch(
            f"/api/admin/users/{PLATFORM_ADMIN_UUID}/status",
            headers={"Authorization": f"Bearer {TOKEN_ADMIN}"},
            json={"new_status": "suspended", "reason": "Self test violation"}
        )
        self.assertEqual(resp.status_code, 400)
        self.assertIn("cannot alter their own account status", resp.text.lower())

    def test_08_user_account_suspension_and_reinstatement_lifecycle(self):
        """User account suspension immediately affects access; reinstatement restores access."""
        test_uid = CITIZEN_A_UUID

        # 1. Suspend citizen
        r_susp = client.patch(
            f"/api/admin/users/{test_uid}/status",
            headers={"Authorization": f"Bearer {TOKEN_ADMIN}"},
            json={"new_status": "suspended", "reason": "Regulatory audit non-compliance."}
        )
        self.assertEqual(r_susp.status_code, 200)
        self.assertEqual(r_susp.json()["account_status"], "suspended")

        # 2. Verify protected citizen action is rejected
        token_suspended_citizen = generate_live_jwt(test_uid, "citizen", "alice@collegex.edu", "Alice Citizen", account_status="suspended")
        r_blocked = client.get(
            "/api/citizen/cases",
            headers={"Authorization": f"Bearer {token_suspended_citizen}"}
        )
        # Should be rejected with 401 (token decoded returns None for suspended status)
        self.assertEqual(r_blocked.status_code, 401)

        # 3. Reinstate citizen
        r_reinst = client.patch(
            f"/api/admin/users/{test_uid}/status",
            headers={"Authorization": f"Bearer {TOKEN_ADMIN}"},
            json={"new_status": "active", "reason": "Verification completed. Access restored."}
        )
        self.assertEqual(r_reinst.status_code, 200)
        self.assertEqual(r_reinst.json()["account_status"], "active")

    # =========================================================================
    # 6. Institution Management & Boundary Isolation
    # =========================================================================

    def test_09_institution_registration_and_activation_toggle(self):
        """Platform Administrator registers an institution and toggles active status."""
        test_code = f"TEST_INST_{uuid.uuid4().hex[:6].upper()}"

        # 1. Register institution
        r_reg = client.post(
            "/api/admin/institutions",
            headers={"Authorization": f"Bearer {TOKEN_ADMIN}"},
            json={
                "code": test_code,
                "name": "Institute of Advanced Legal Science",
                "city": "Bengaluru",
                "state": "Karnataka",
                "type": "autonomous_institute",
                "is_active": True
            }
        )
        self.assertEqual(r_reg.status_code, 200)
        inst_id = r_reg.json()["institution"]["id"]

        # 2. Unique code constraint: duplicate registration fails
        r_dup = client.post(
            "/api/admin/institutions",
            headers={"Authorization": f"Bearer {TOKEN_ADMIN}"},
            json={
                "code": test_code,
                "name": "Duplicate Institution",
                "city": "Bengaluru",
                "state": "Karnataka"
            }
        )
        self.assertEqual(r_dup.status_code, 400)
        self.assertIn("already registered", r_dup.text.lower())

        # 3. Deactivate institution
        r_deact = client.patch(
            f"/api/admin/institutions/{inst_id}/status",
            headers={"Authorization": f"Bearer {TOKEN_ADMIN}"},
            json={"is_active": False, "reason": "Periodic campus accreditation review."}
        )
        self.assertEqual(r_deact.status_code, 200)
        self.assertFalse(r_deact.json()["is_active"])

        # 4. Re-activate institution
        r_act = client.patch(
            f"/api/admin/institutions/{inst_id}/status",
            headers={"Authorization": f"Bearer {TOKEN_ADMIN}"},
            json={"is_active": True, "reason": "Accreditation approved."}
        )
        self.assertEqual(r_act.status_code, 200)
        self.assertTrue(r_act.json()["is_active"])

    # =========================================================================
    # 7 & 8. Lawyer Verification Workflow
    # =========================================================================

    def test_10_lawyer_verification_queue_and_decision_processing(self):
        """Administrator processes lawyer verification via existing admin_verify_lawyer RPC."""
        # 1. Inspect queue
        r_queue = client.get(
            "/api/admin/lawyers/queue",
            headers={"Authorization": f"Bearer {TOKEN_ADMIN}"}
        )
        self.assertEqual(r_queue.status_code, 200)
        self.assertIn("lawyers", r_queue.json())

        # 2. Execute verification decision
        r_dec = client.post(
            f"/api/admin/lawyers/{LAWYER_A_UUID}/decision",
            headers={"Authorization": f"Bearer {TOKEN_ADMIN}"},
            json={"decision": "VERIFIED", "notes": "Bar Council roll verified against state ledger."}
        )
        self.assertEqual(r_dec.status_code, 200)
        self.assertEqual(r_dec.json().get("verification_status"), "VERIFIED")

        # 3. Verify public discovery returns lawyer
        r_disc = client.get("/api/lawyers")
        self.assertEqual(r_disc.status_code, 200)
        lawyer_ids = [l["id"] for l in r_disc.json().get("lawyers", [])]
        self.assertIn(LAWYER_A_UUID, lawyer_ids)

    # =========================================================================
    # 9 & 10. Global Case Oversight & Audited Exceptional Access
    # =========================================================================

    def test_11_global_case_listing_masks_sensitive_information(self):
        """Default global case listings mask student PII and proctor deliberations."""
        resp = client.get(
            "/api/admin/cases",
            headers={"Authorization": f"Bearer {TOKEN_ADMIN}"}
        )
        self.assertEqual(resp.status_code, 200)
        cases = resp.json().get("cases", [])
        self.assertTrue(len(cases) > 0)

        for c in cases:
            # Privacy masking assertions
            self.assertEqual(c["student_name"], "[PROTECTED / ANONYMOUS]")
            self.assertEqual(c["roll_number"], "[PROTECTED]")
            self.assertEqual(c["proctor_notes"], "[DELIBERATION PROTECTED]")

    def test_12_exceptional_confidential_case_access_mandates_reason_and_audits(self):
        """Exceptional confidential case access enforces justification and records audit trail."""
        case_id = "PHASE7-CASE-001"

        # 1. Reject without sufficient reason (< 10 chars)
        r_short = client.post(
            f"/api/admin/cases/{case_id}/confidential-access",
            headers={"Authorization": f"Bearer {TOKEN_ADMIN}"},
            json={"reason": "audit"}
        )
        self.assertEqual(r_short.status_code, 400)
        self.assertIn("minimum 10 characters", r_short.text.lower())

        # 2. Grant access with valid justification
        valid_reason = "Statutory University Ombudsperson appellate inspection mandate."
        r_grant = client.post(
            f"/api/admin/cases/{case_id}/confidential-access",
            headers={"Authorization": f"Bearer {TOKEN_ADMIN}"},
            json={"reason": valid_reason}
        )
        self.assertEqual(r_grant.status_code, 200)
        data = r_grant.json()
        self.assertEqual(data["status"], "success")
        self.assertIn("audit_log_id", data)
        self.assertIn("case", data)

        # 3. Verify audit record was created in platform_audit_logs
        audit_res = supabase_admin.table("platform_audit_logs").select("*").eq(
            "id", data["audit_log_id"]
        ).execute()
        self.assertTrue(len(audit_res.data) > 0)
        log = audit_res.data[0]
        self.assertEqual(log["action_type"], "EXCEPTIONAL_CONFIDENTIAL_CASE_ACCESS")
        self.assertEqual(log["reason"], valid_reason)
        self.assertEqual(log["target_entity_id"], case_id)

    # =========================================================================
    # 11. Immutable Audit Trail Enforcement
    # =========================================================================

    def test_13_platform_audit_logs_cannot_be_updated_or_deleted(self):
        """Database trigger prohibits UPDATE and DELETE on platform_audit_logs."""
        # 1. Read existing audit logs via admin endpoint
        resp = client.get(
            "/api/admin/audit-logs",
            headers={"Authorization": f"Bearer {TOKEN_ADMIN}"}
        )
        self.assertEqual(resp.status_code, 200)
        self.assertIn("audit_logs", resp.json())

        # 2. Attempt direct database UPDATE
        with self.assertRaises(Exception) as ctx_update:
            supabase_admin.table("platform_audit_logs").update({
                "action_type": "TAMPERED_EVENT"
            }).eq("actor_user_id", PLATFORM_ADMIN_UUID).execute()
        self.assertIn("strictly immutable", str(ctx_update.exception).lower())

        # 3. Attempt direct database DELETE
        with self.assertRaises(Exception) as ctx_delete:
            supabase_admin.table("platform_audit_logs").delete().eq(
                "actor_user_id", PLATFORM_ADMIN_UUID
            ).execute()
        self.assertIn("strictly immutable", str(ctx_delete.exception).lower())

    # =========================================================================
    # 12. Operational System Health Telemetry
    # =========================================================================

    def test_14_system_health_endpoint_returns_metrics_without_leaking_secrets(self):
        """Health endpoint returns status and latency without exposing credentials or internal traces."""
        resp = client.get(
            "/api/admin/system/health",
            headers={"Authorization": f"Bearer {TOKEN_ADMIN}"}
        )
        self.assertEqual(resp.status_code, 200)
        h = resp.json()
        self.assertEqual(h["status"], "healthy")
        self.assertIn("services", h)

        # Assert no secrets in output string
        body_text = resp.text.lower()
        self.assertNotIn("password", body_text)
        self.assertNotIn("postgres://", body_text)
        self.assertNotIn("jwt_secret", body_text)
        self.assertNotIn("gsk_", body_text)  # Groq API key prefix

    # =========================================================================
    # 13. Admin Notification Dispatch
    # =========================================================================

    def test_15_admin_notification_dispatch_idempotent(self):
        """Admin notification alerts only authoritative platform administrators with deterministic keys."""
        test_entity = f"ALERT-SYS-{uuid.uuid4().hex[:6]}"
        dispatched_ids = platform_admin_manager.dispatch_admin_notification(
            event_type="SYS_TEST",
            title="System Alert Test",
            message="Test broadcast to platform administrators.",
            entity_id=test_entity
        )
        self.assertTrue(len(dispatched_ids) > 0)

        # Query notifications table for this recipient
        notif_res = supabase_admin.table("notifications").select("*").in_("id", dispatched_ids).execute()
        for n in notif_res.data:
            self.assertEqual(n["recipient_user_id"], PLATFORM_ADMIN_UUID)
            self.assertIn("admin_alert_", n["idempotency_key"])


if __name__ == "__main__":
    unittest.main()


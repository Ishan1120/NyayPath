"""
NyayPath Phase 4: Multi-Institution Architecture & Complete Institution/Proctor Workspace
Automated Security, Multi-Tenancy & Authorization Test Suite
========================================================================================
Verification of 15 Scenarios:
1.  Institution Admin accesses only their institution
2.  Chief Proctor accesses authorized institutional workflows
3.  Ordinary proctor sees assigned cases
4.  Ordinary proctor cannot reassign cases (403)
5.  Committee member sees only actively assigned confidential cases
6.  Revoked committee member immediately loses access
7.  Suspended member loses access (401/403)
8.  Cross-institution requests rejected (403)
9.  Citizens cannot access institutional internal notes
10. Case assignments generate notifications with activity ID idempotency
11. Hearing scheduling generates notifications
12. Assignment and revocation generate audit activity records
13. Unauthorized users cannot modify protected fields
14. Institution analytics reflect genuine database figures
15. Existing citizen filing and tracking regression passes
"""

import os
import sys
import time
import uuid
import unittest
from pathlib import Path

# Local Supabase Environment Variables
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

def generate_live_jwt(user_id: str, role: str, institution_id: str, email: str, name: str, status: str = "active") -> str:
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

# Test Actors from database fixtures
INST_X_UUID = "11111111-0000-0000-0000-111111111111"
INST_Y_UUID = "22222222-0000-0000-0000-222222222222"

CHIEF_PROCTOR_X_UUID = "66666666-1111-2222-3333-666666666666"
ADMIN_X_UUID         = "44444444-1111-2222-3333-444444444444"
PROCTOR_X_UUID       = "cccccccc-1111-2222-3333-cccccccccccc"
COMMITTEE_CAROL_UUID = "eeeeeeee-1111-2222-3333-eeeeeeeeeeee"
SUSPENDED_ADMIN_UUID = "ffffffff-1111-2222-3333-ffffffffffff"
STUDENT_A_UUID       = "aaaaaaaa-1111-2222-3333-aaaaaaaaaaaa"
STUDENT_B_UUID       = "bbbbbbbb-1111-2222-3333-bbbbbbbbbbbb"

CHIEF_PROCTOR_Y_UUID = "dddddddd-1111-2222-3333-dddddddddddd"
ADMIN_Y_UUID         = "33333333-1111-2222-3333-333333333333"

TOKEN_CHIEF_X   = generate_live_jwt(CHIEF_PROCTOR_X_UUID, "chief_proctor", "INST_COLLEGE_X", "charlie@collegex.edu", "Charlie Chief Proctor")
TOKEN_ADMIN_X   = generate_live_jwt(ADMIN_X_UUID, "institution_admin", "INST_COLLEGE_X", "irene@collegex.edu", "Irene Admin")
TOKEN_PROCTOR_X = generate_live_jwt(PROCTOR_X_UUID, "proctor", "INST_COLLEGE_X", "xavier@collegex.edu", "Xavier Proctor")
TOKEN_CAROL_X   = generate_live_jwt(COMMITTEE_CAROL_UUID, "committee_member", "INST_COLLEGE_X", "carol@collegex.edu", "Carol Committee")
TOKEN_SUSPENDED = generate_live_jwt(SUSPENDED_ADMIN_UUID, "institution_admin", "INST_COLLEGE_X", "sam@collegex.edu", "Sam Suspended", status="suspended")
TOKEN_STUDENT_A = generate_live_jwt(STUDENT_A_UUID, "student", "INST_COLLEGE_X", "alice@collegex.edu", "Alice Student")

TOKEN_CHIEF_Y   = generate_live_jwt(CHIEF_PROCTOR_Y_UUID, "chief_proctor", "INST_COLLEGE_Y", "yolanda@collegey.edu", "Yolanda Chief Proctor Y")
TOKEN_ADMIN_Y   = generate_live_jwt(ADMIN_Y_UUID, "institution_admin", "INST_COLLEGE_Y", "adminy@collegey.edu", "Admin Y")


class TestPhase4InstitutionAndProctor(unittest.TestCase):
    """Automated integration tests for Phase 4."""

    @classmethod
    def setUpClass(cls):
        # Ensure fixtures are initialized
        # 1. Ensure test case in College X
        cls.case_x_id = "CAMPUS-CONF-C"
        cls.case_y_id = "CAMPUS-INST-Y"

    # -----------------------------------------------------------------
    # Scenario 1: Institution Admin accesses only their institution
    # -----------------------------------------------------------------
    def test_01_institution_admin_accesses_only_own_institution(self):
        """Admin Irene of College X only accesses College X cases and stats."""
        # Stats
        r = client.get("/api/institution/dashboard-stats", headers={"Authorization": f"Bearer {TOKEN_ADMIN_X}"})
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertEqual(data["stats"]["institution_id"], "INST_COLLEGE_X")

        # Cases list: all cases must belong to INST_COLLEGE_X
        r_cases = client.get("/api/institution/cases", headers={"Authorization": f"Bearer {TOKEN_ADMIN_X}"})
        self.assertEqual(r_cases.status_code, 200)
        cases_data = r_cases.json()
        self.assertEqual(cases_data["institution_id"], "INST_COLLEGE_X")
        for c in cases_data.get("cases", []):
            self.assertEqual(c.get("institution_id"), "INST_COLLEGE_X")

        # Attempt to inspect College Y case -> 403 Forbidden
        r_foreign = client.get(f"/api/campus-proctor/case/{self.case_y_id}", headers={"Authorization": f"Bearer {TOKEN_ADMIN_X}"})
        self.assertEqual(r_foreign.status_code, 403)

    # -----------------------------------------------------------------
    # Scenario 2: Chief Proctor accesses authorized institutional workflows
    # -----------------------------------------------------------------
    def test_02_chief_proctor_workflows(self):
        """Chief Proctor can view triage queue, assign proctors, schedule hearings."""
        # 1. Triage queue
        r_triage = client.get("/api/campus-proctor/chief/triage", headers={"Authorization": f"Bearer {TOKEN_CHIEF_X}"})
        self.assertEqual(r_triage.status_code, 200)
        triage_data = r_triage.json()
        self.assertIn("cases", triage_data)

        # 2. Committee roster
        r_roster = client.get("/api/institution/committee-roster", headers={"Authorization": f"Bearer {TOKEN_CHIEF_X}"})
        self.assertEqual(r_roster.status_code, 200)
        roster_data = r_roster.json()
        self.assertIn("roster", roster_data)

        # 3. Schedule hearing & update status
        r_upd = client.post(
            "/api/campus-proctor/update",
            headers={"Authorization": f"Bearer {TOKEN_CHIEF_X}"},
            json={
                "case_id": self.case_x_id,
                "new_status": "HEARING_SCHEDULED",
                "proctor_notes": "Formal hearing scheduled by Chief Proctor Charlie.",
                "hearing_date": "2026-11-20"
            }
        )
        self.assertEqual(r_upd.status_code, 200)
        self.assertEqual(r_upd.json()["case"]["status"], "HEARING_SCHEDULED")

    # -----------------------------------------------------------------
    # Scenario 3: Ordinary proctor sees assigned cases
    # -----------------------------------------------------------------
    def test_03_ordinary_proctor_sees_assigned_cases(self):
        """Ordinary proctor Xavier sees cases assigned to him."""
        # Assign Xavier to Case C first via Chief Proctor
        client.post(
            "/api/campus-proctor/update",
            headers={"Authorization": f"Bearer {TOKEN_CHIEF_X}"},
            json={
                "case_id": self.case_x_id,
                "new_status": "UNDER_INQUIRY",
                "proctor_notes": "Assigned to Xavier for preliminary investigation.",
                "assigned_proctor_user_id": PROCTOR_X_UUID
            }
        )

        r = client.get("/api/campus-proctor/my-cases", headers={"Authorization": f"Bearer {TOKEN_PROCTOR_X}"})
        self.assertEqual(r.status_code, 200)
        my_cases = r.json().get("cases", [])
        assigned_ids = [c["case_id"] for c in my_cases]
        self.assertIn(self.case_x_id, assigned_ids)

    # -----------------------------------------------------------------
    # Scenario 4: Ordinary proctor cannot reassign cases (403)
    # -----------------------------------------------------------------
    def test_04_ordinary_proctor_cannot_reassign_cases(self):
        """Ordinary proctor cannot assign or reassign a proctor."""
        r = client.post(
            "/api/campus-proctor/update",
            headers={"Authorization": f"Bearer {TOKEN_PROCTOR_X}"},
            json={
                "case_id": self.case_x_id,
                "new_status": "UNDER_INQUIRY",
                "proctor_notes": "Attempting arbitrary reassignment",
                "assigned_proctor_user_id": CHIEF_PROCTOR_X_UUID
            }
        )
        self.assertEqual(r.status_code, 403)
        self.assertIn("Only Chief Proctors, Institution Administrators", r.json()["detail"])

    # -----------------------------------------------------------------
    # Scenario 5: Committee member sees only actively assigned confidential cases
    # -----------------------------------------------------------------
    def test_05_committee_member_active_assignment_and_observations(self):
        """Active committee member Carol can inspect case and record observations."""
        # 1. Chief Proctor appoints Carol to Case C
        r_asgn = client.post(
            "/api/campus-proctor/committee/assign",
            headers={"Authorization": f"Bearer {TOKEN_CHIEF_X}"},
            json={
                "case_id": self.case_x_id,
                "target_user_id": COMMITTEE_CAROL_UUID,
                "role": "investigator",
                "committee_name": "Disciplinary Committee X"
            }
        )
        self.assertEqual(r_asgn.status_code, 200)

        # 2. Carol lists inquiries -> Case C present
        r_inq = client.get("/api/campus-proctor/committee/my-inquiries", headers={"Authorization": f"Bearer {TOKEN_CAROL_X}"})
        self.assertEqual(r_inq.status_code, 200)
        inquiries = r_inq.json().get("inquiries", [])
        inq_ids = [c["case_id"] for c in inquiries]
        self.assertIn(self.case_x_id, inq_ids)

        # 3. Carol records committee observations
        r_obs = client.post(
            "/api/campus-proctor/committee/observations",
            headers={"Authorization": f"Bearer {TOKEN_CAROL_X}"},
            json={
                "case_id": self.case_x_id,
                "observations": "Complainant corroborated dates and witness testimony.",
                "findings": "Prima facie violation of campus code of conduct.",
                "recommendations": "Issue formal written warning to respondent."
            }
        )
        self.assertEqual(r_obs.status_code, 200)
        self.assertEqual(r_obs.json()["status"], "success")

    # -----------------------------------------------------------------
    # Scenario 6: Revoked committee member immediately loses access
    # -----------------------------------------------------------------
    def test_06_revoked_committee_member_loses_access_immediately(self):
        """Revoking committee appointment terminates access immediately."""
        # Revoke Carol
        r_rev = client.post(
            "/api/campus-proctor/committee/revoke",
            headers={"Authorization": f"Bearer {TOKEN_CHIEF_X}"},
            json={
                "case_id": self.case_x_id,
                "target_user_id": COMMITTEE_CAROL_UUID
            }
        )
        self.assertEqual(r_rev.status_code, 200)

        # Inquiries list must no longer show Case C
        r_inq = client.get("/api/campus-proctor/committee/my-inquiries", headers={"Authorization": f"Bearer {TOKEN_CAROL_X}"})
        self.assertEqual(r_inq.status_code, 200)
        inq_ids = [c["case_id"] for c in r_inq.json().get("inquiries", [])]
        self.assertNotIn(self.case_x_id, inq_ids)

        # Attempting observation on Case C -> 403 Forbidden
        r_obs = client.post(
            "/api/campus-proctor/committee/observations",
            headers={"Authorization": f"Bearer {TOKEN_CAROL_X}"},
            json={
                "case_id": self.case_x_id,
                "observations": "Post-revocation unauthorized observation"
            }
        )
        self.assertEqual(r_obs.status_code, 403)

    # -----------------------------------------------------------------
    # Scenario 7: Suspended member loses access (401/403)
    # -----------------------------------------------------------------
    def test_07_suspended_member_loses_access(self):
        """Suspended member token is denied across institutional endpoints."""
        r_stats = client.get("/api/institution/dashboard-stats", headers={"Authorization": f"Bearer {TOKEN_SUSPENDED}"})
        self.assertIn(r_stats.status_code, [401, 403])

        r_cases = client.get("/api/institution/cases", headers={"Authorization": f"Bearer {TOKEN_SUSPENDED}"})
        self.assertIn(r_cases.status_code, [401, 403])

    # -----------------------------------------------------------------
    # Scenario 8: Cross-institution requests rejected (403)
    # -----------------------------------------------------------------
    def test_08_cross_institution_requests_rejected(self):
        """Admin or Proctor from College X cannot access College Y workflows."""
        # Admin X attempts to assign committee member on College Y case
        r = client.post(
            "/api/campus-proctor/committee/assign",
            headers={"Authorization": f"Bearer {TOKEN_ADMIN_X}"},
            json={
                "case_id": self.case_y_id,
                "target_user_id": COMMITTEE_CAROL_UUID,
                "role": "member"
            }
        )
        self.assertEqual(r.status_code, 403)

        # Admin Y attempts to access College X cases
        r_y = client.get(f"/api/campus-proctor/case/{self.case_x_id}", headers={"Authorization": f"Bearer {TOKEN_ADMIN_Y}"})
        self.assertEqual(r_y.status_code, 403)

    # -----------------------------------------------------------------
    # Scenario 9: Citizens cannot access institutional internal notes
    # -----------------------------------------------------------------
    def test_09_citizens_cannot_access_internal_notes_or_queue(self):
        """Student or Citizen accessing case cannot see confidential proctorial internal fields."""
        # Student cannot access /api/campus-proctor/cases
        r = client.get("/api/campus-proctor/cases", headers={"Authorization": f"Bearer {TOKEN_STUDENT_A}"})
        self.assertEqual(r.status_code, 403)

        # Student cannot access /api/institution/dashboard-stats
        r_stats = client.get("/api/institution/dashboard-stats", headers={"Authorization": f"Bearer {TOKEN_STUDENT_A}"})
        self.assertEqual(r_stats.status_code, 403)

    # -----------------------------------------------------------------
    # Scenario 10: Case assignments generate notifications with activity ID idempotency
    # -----------------------------------------------------------------
    def test_10_assignment_generates_notification_with_activity_id(self):
        """Proctor assignment triggers a notification using 'notif_act_{activity_id}_assign_' idempotency key."""
        r = client.post(
            "/api/campus-proctor/update",
            headers={"Authorization": f"Bearer {TOKEN_CHIEF_X}"},
            json={
                "case_id": self.case_x_id,
                "new_status": "UNDER_INQUIRY",
                "proctor_notes": "Assigned proctor notification test",
                "assigned_proctor_user_id": PROCTOR_X_UUID
            }
        )
        self.assertEqual(r.status_code, 200)

        # Inspect database notifications table
        notifs = supabase_admin.table("notifications").select("id, idempotency_key, title").eq(
            "recipient_user_id", PROCTOR_X_UUID
        ).order("created_at", desc=True).limit(5).execute()
        self.assertTrue(len(notifs.data) > 0)
        found_key = False
        for n in notifs.data:
            key = n.get("idempotency_key") or ""
            if key.startswith("notif_act_") and "assign" in key:
                found_key = True
                break
        self.assertTrue(found_key, "Notification with notif_act_ idempotency key not found.")

    # -----------------------------------------------------------------
    # Scenario 11: Hearing scheduling generates notifications
    # -----------------------------------------------------------------
    def test_11_hearing_scheduling_generates_notification(self):
        """Scheduling a hearing creates a notification with 'notif_act_' idempotency."""
        r = client.post(
            "/api/campus-proctor/update",
            headers={"Authorization": f"Bearer {TOKEN_CHIEF_X}"},
            json={
                "case_id": self.case_x_id,
                "new_status": "HEARING_SCHEDULED",
                "proctor_notes": "Hearing scheduled for complainant.",
                "hearing_date": "2026-11-28"
            }
        )
        self.assertEqual(r.status_code, 200)

        # Complainant of Case C is Student B
        notifs = supabase_admin.table("notifications").select("id, idempotency_key, title").eq(
            "recipient_user_id", STUDENT_B_UUID
        ).order("created_at", desc=True).limit(5).execute()
        found_hearing = False
        for n in notifs.data:
            key = n.get("idempotency_key") or ""
            if key.startswith("notif_act_") and "hearing" in key:
                found_hearing = True
                break
        self.assertTrue(found_hearing, "Hearing notification with notif_act_ idempotency not found.")

    # -----------------------------------------------------------------
    # Scenario 12: Assignment and revocation generate audit activity records
    # -----------------------------------------------------------------
    def test_12_assignment_and_revocation_generate_audit_logs(self):
        """Case committee assignment and revocation produce immutable case_activity_log entries."""
        # Assign
        client.post(
            "/api/campus-proctor/committee/assign",
            headers={"Authorization": f"Bearer {TOKEN_CHIEF_X}"},
            json={
                "case_id": self.case_x_id,
                "target_user_id": COMMITTEE_CAROL_UUID,
                "role": "investigator"
            }
        )
        # Revoke
        client.post(
            "/api/campus-proctor/committee/revoke",
            headers={"Authorization": f"Bearer {TOKEN_CHIEF_X}"},
            json={
                "case_id": self.case_x_id,
                "target_user_id": COMMITTEE_CAROL_UUID
            }
        )

        acts = supabase_admin.table("case_activity_log").select("id, action_type").eq("case_id", self.case_x_id).order("created_at", desc=True).execute()
        action_types = [a["action_type"] for a in acts.data]
        self.assertIn("COMMITTEE_ASSIGNMENT_PROVISIONED", action_types)
        self.assertIn("COMMITTEE_ASSIGNMENT_REVOKED", action_types)

    # -----------------------------------------------------------------
    # Scenario 13: Unauthorized users cannot modify protected fields
    # -----------------------------------------------------------------
    def test_13_unauthorized_users_cannot_modify_protected_fields(self):
        """Student or unauthorized user cannot update campus case."""
        r = client.post(
            "/api/campus-proctor/update",
            headers={"Authorization": f"Bearer {TOKEN_STUDENT_A}"},
            json={
                "case_id": self.case_x_id,
                "new_status": "CLOSED"
            }
        )
        self.assertEqual(r.status_code, 403)

    # -----------------------------------------------------------------
    # Scenario 14: Institution analytics reflect genuine database figures
    # -----------------------------------------------------------------
    def test_14_institution_analytics_reflect_genuine_db_records(self):
        """Dashboard statistics match actual counts from the database."""
        r = client.get("/api/institution/dashboard-stats", headers={"Authorization": f"Bearer {TOKEN_ADMIN_X}"})
        self.assertEqual(r.status_code, 200)
        stats = r.json()["stats"]

        # Count actual cases for INST_COLLEGE_X in Supabase
        db_cases = supabase_admin.table("campus_cases").select("id", count="exact").eq("institution_id", "INST_COLLEGE_X").execute()
        expected_total = db_cases.count if db_cases.count is not None else len(db_cases.data)
        self.assertEqual(stats["total_cases"], expected_total)

        # Count actual members
        db_members = supabase_admin.table("institution_memberships").select("id", count="exact").eq("institution_code", "INST_COLLEGE_X").execute()
        expected_members = db_members.count if db_members.count is not None else len(db_members.data)
        self.assertEqual(stats["total_members"], expected_members)

    # -----------------------------------------------------------------
    # Scenario 15: Existing citizen filing and tracking regression passes
    # -----------------------------------------------------------------
    def test_15_citizen_filing_and_tracking_regression(self):
        """Citizen filing and tracking endpoints operate without regressions."""
        # 1. File a case
        r_file = client.post(
            "/api/citizen/cases/file",
            headers={"Authorization": f"Bearer {TOKEN_STUDENT_A}"},
            json={
                "category": "RTI",
                "subject": "Regression Test Filing Phase 4",
                "facts": "Verifying citizen filing integrity in Phase 4.",
                "declaration_confirmed": True
            }
        )
        self.assertEqual(r_file.status_code, 200)
        filed_case = r_file.json()
        case_id = filed_case["case_id"]
        verif_key = filed_case.get("verification_key")

        # 2. Track case publicly with verification key
        r_track = client.get(f"/api/citizen/track/{case_id}?verification_key={verif_key}")
        self.assertEqual(r_track.status_code, 200)
        track_data = r_track.json()
        self.assertEqual(track_data["case"]["case_id"], case_id)


if __name__ == "__main__":
    unittest.main()

"""
NyayPath Draft User Identity & Cross-User Isolation Test Suite
Validates:
1. User ID extraction strictly from authenticated JWT 'sub' claim.
2. Rejection of draft persistence when user_id is not in auth.users (foreign key constraint).
3. Inability of client to spoof user_id in CreateDraftRequest / UpdateDraftRequest.
4. Comprehensive cross-user isolation:
   - User B cannot read User A's draft (HTTP 403 Forbidden).
   - User B cannot update User A's draft (HTTP 403 Forbidden).
   - User B cannot delete User A's draft (HTTP 403 Forbidden).
   - User B's list_drafts never includes User A's drafts.
5. Service-role database operations enforce equivalent application-level ownership checks.
6. Timestamp defaults: created_at and updated_at use now(), trigger updates updated_at on modification.
"""

import unittest
import os
import time
import uuid
from fastapi import HTTPException
from fastapi.testclient import TestClient

# Ensure local test runs against live local Supabase instance
os.environ["SUPABASE_URL"] = "http://127.0.0.1:54321"
os.environ["SUPABASE_SECRET_KEY"] = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZS1kZW1vIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImV4cCI6MTk4MzgxMjk5Nn0.EGIM96RAZx35lJzdJsyH-qQwv8Hdp7fsn3W0YpN81IU"
os.environ["SUPABASE_OFFLINE_TEST"] = "0"
os.environ["ENV"] = "development"

from api.index import app
from api.auth import AuthUser, UserRole, AccountStatus, create_access_token
from api.legal_drafts import (
    LegalDraftManager,
    legal_draft_manager,
    CreateDraftRequest,
    UpdateDraftRequest
)


class TestDraftUserIdentityAndCrossUserIsolation(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)

        # Seeded user A: Alice Sharma
        cls.alice_id = "aaaaaaaa-1111-2222-3333-aaaaaaaaaaaa"
        cls.alice_user = AuthUser(
            user_id=cls.alice_id,
            email="alice@collegex.edu",
            role=UserRole.CITIZEN,
            account_status=AccountStatus.ACTIVE,
            institution_id="INST_DEFAULT"
        )
        cls.alice_token = create_access_token(cls.alice_user)
        cls.alice_headers = {"Authorization": f"Bearer {cls.alice_token}"}

        # Seeded user B: Bob Verma
        cls.bob_id = "bbbbbbbb-1111-2222-3333-bbbbbbbbbbbb"
        cls.bob_user = AuthUser(
            user_id=cls.bob_id,
            email="bob@collegex.edu",
            role=UserRole.CITIZEN,
            account_status=AccountStatus.ACTIVE,
            institution_id="INST_DEFAULT"
        )
        cls.bob_token = create_access_token(cls.bob_user)
        cls.bob_headers = {"Authorization": f"Bearer {cls.bob_token}"}

    def setUp(self):
        self._cleanup()

    def tearDown(self):
        self._cleanup()

    def _cleanup(self):
        sb = getattr(legal_draft_manager, "supabase", None)
        if sb:
            try:
                sb.table("legal_drafts").delete().in_("user_id", [self.alice_id, self.bob_id]).execute()
            except Exception:
                pass
        if hasattr(legal_draft_manager, "_in_memory_drafts"):
            legal_draft_manager._in_memory_drafts.clear()

    # =========================================================================
    # Test 1: User ID derived strictly from JWT principal (cannot be spoofed)
    # =========================================================================
    def test_01_user_id_derived_from_authenticated_jwt_only(self):
        """
        Verifies:
        1. User ID is derived from the verified JWT 'sub' claim.
        2. Attempting to pass user_id in client JSON body is ignored / not accepted.
        3. Stored draft strictly belongs to Alice's authenticated user ID.
        """
        spoofed_user_id = self.bob_id
        payload_with_spoof = {
            "title": "Legitimate Draft by Alice",
            "document_type": "RTI",
            "draft_content": "Official petition under RTI Act Section 6(1)",
            "user_id": spoofed_user_id  # Client attempt to spoof Bob's identity
        }

        res = self.client.post("/api/drafts", json=payload_with_spoof, headers=self.alice_headers)
        self.assertEqual(res.status_code, 200)
        draft = res.json()

        # Must be assigned to Alice, NOT Bob!
        self.assertEqual(str(draft["user_id"]).lower(), self.alice_id.lower())
        self.assertNotEqual(str(draft["user_id"]).lower(), spoofed_user_id.lower())

        # Direct database verification
        sb = legal_draft_manager.supabase
        db_res = sb.table("legal_drafts").select("user_id").eq("id", draft["id"]).execute()
        self.assertEqual(db_res.data[0]["user_id"], self.alice_id)

    # =========================================================================
    # Test 2: Foreign key enforcement to auth.users.id
    # =========================================================================
    def test_02_foreign_key_enforcement_to_auth_users(self):
        """
        Verifies that an unseeded or arbitrary user_id not present in auth.users
        is rejected by the PostgreSQL database foreign key constraint.
        """
        phantom_user_id = str(uuid.uuid4())
        phantom_user = AuthUser(
            user_id=phantom_user_id,
            email="phantom@nowhere.in",
            role=UserRole.CITIZEN,
            account_status=AccountStatus.ACTIVE,
            institution_id="INST_DEFAULT"
        )
        phantom_token = create_access_token(phantom_user)
        phantom_headers = {"Authorization": f"Bearer {phantom_token}"}

        # Attempting to insert a draft for a non-existent auth.users row
        # In development mode, the database raises foreign key violation (error code 23503)
        sb = legal_draft_manager.supabase
        with self.assertRaises(Exception) as ctx:
            sb.table("legal_drafts").insert({
                "user_id": phantom_user_id,
                "title": "Phantom Draft",
                "draft_content": "Content",
                "status": "SAVED"
            }).execute()
        self.assertIn("violates foreign key constraint", str(ctx.exception).lower())

    # =========================================================================
    # Test 3: Comprehensive Cross-User Isolation (Read, Update, Delete)
    # =========================================================================
    def test_03_cross_user_isolation_strictly_enforced(self):
        """
        Verifies that Bob (User B) cannot read, update, or delete Alice's (User A's) draft.
        All cross-user operations fail with HTTP 403 Forbidden.
        """
        # Alice creates a confidential draft
        res_alice = self.client.post(
            "/api/drafts",
            json={
                "title": "Alice Confidential Medical Malpractice Petition",
                "document_type": "CONSUMER",
                "draft_content": "Privileged communication and facts regarding treatment."
            },
            headers=self.alice_headers
        )
        self.assertEqual(res_alice.status_code, 200)
        alice_draft_id = res_alice.json()["id"]

        # 1. Bob attempts to GET Alice's draft -> 403 Forbidden
        res_bob_get = self.client.get(
            f"/api/drafts/{alice_draft_id}",
            headers=self.bob_headers
        )
        self.assertEqual(res_bob_get.status_code, 403)
        self.assertIn("Access denied", res_bob_get.json()["detail"])

        # 2. Bob attempts to UPDATE Alice's draft -> 403 Forbidden
        res_bob_update = self.client.put(
            f"/api/drafts/{alice_draft_id}",
            json={
                "title": "Bob Tampered Title",
                "draft_content": "Bob malicious overwrite",
                "expected_version": 1
            },
            headers=self.bob_headers
        )
        self.assertEqual(res_bob_update.status_code, 403)
        self.assertIn("Access denied", res_bob_update.json()["detail"])

        # Verify database content was NOT tampered with
        db_draft = legal_draft_manager.get_draft(self.alice_user, alice_draft_id)
        self.assertEqual(db_draft["title"], "Alice Confidential Medical Malpractice Petition")
        self.assertNotIn("Tampered", db_draft["title"])

        # 3. Bob attempts to DELETE Alice's draft -> 403 Forbidden
        res_bob_delete = self.client.delete(
            f"/api/drafts/{alice_draft_id}",
            headers=self.bob_headers
        )
        self.assertEqual(res_bob_delete.status_code, 403)
        self.assertIn("Access denied", res_bob_delete.json()["detail"])

        # Verify draft still exists in database
        db_draft_after = legal_draft_manager.get_draft(self.alice_user, alice_draft_id)
        self.assertEqual(db_draft_after["id"], alice_draft_id)

        # 4. Bob calls list_drafts -> Alice's draft is completely excluded
        res_bob_list = self.client.get("/api/drafts", headers=self.bob_headers)
        self.assertEqual(res_bob_list.status_code, 200)
        bob_drafts = res_bob_list.json()["drafts"]
        bob_draft_ids = [d["id"] for d in bob_drafts]
        self.assertNotIn(alice_draft_id, bob_draft_ids)

    # =========================================================================
    # Test 4: Service-Role Application-Level Ownership Enforcement
    # =========================================================================
    def test_04_service_role_application_ownership_guards(self):
        """
        Verifies that even though LegalDraftManager uses service_role key to access Supabase,
        every method implements application-level ownership checks preventing privilege bypass.
        """
        mgr = LegalDraftManager()

        # Alice creates draft
        d = mgr.create_draft(
            self.alice_user,
            CreateDraftRequest(title="Owner Security Draft", draft_content="Owner Content")
        )
        draft_id = d["id"]

        # Bob calling mgr.get_draft raises 403
        with self.assertRaises(HTTPException) as ctx_get:
            mgr.get_draft(self.bob_user, draft_id)
        self.assertEqual(ctx_get.exception.status_code, 403)

        # Bob calling mgr.update_draft raises 403
        with self.assertRaises(HTTPException) as ctx_up:
            mgr.update_draft(self.bob_user, draft_id, UpdateDraftRequest(title="Hacked"))
        self.assertEqual(ctx_up.exception.status_code, 403)

        # Bob calling mgr.delete_draft raises 403
        with self.assertRaises(HTTPException) as ctx_del:
            mgr.delete_draft(self.bob_user, draft_id)
        self.assertEqual(ctx_del.exception.status_code, 403)

        # Alice calling delete_draft succeeds
        del_res = mgr.delete_draft(self.alice_user, draft_id)
        self.assertEqual(del_res["status"], "success")

    # =========================================================================
    # Test 5: Timestamp Defaults and Trigger Verification
    # =========================================================================
    def test_05_timestamp_defaults_and_updated_at_trigger(self):
        """
        Verifies:
        1. Column defaults created_at and updated_at use DEFAULT now().
        2. Database trigger trg_legal_drafts_updated_at automatically updates updated_at.
        3. Values are correctly stored and retrieved as valid ISO UTC timestamps.
        """
        # Create draft
        res = self.client.post(
            "/api/drafts",
            json={"title": "Timestamp Test", "draft_content": "Timestamp content"},
            headers=self.alice_headers
        )
        self.assertEqual(res.status_code, 200)
        d = res.json()
        draft_id = d["id"]
        c_at_str = d["created_at"]
        u_at_str = d["updated_at"]

        self.assertIsNotNone(c_at_str)
        self.assertIsNotNone(u_at_str)

        # Wait briefly before updating to ensure timestamp delta
        time.sleep(1)

        res_update = self.client.put(
            f"/api/drafts/{draft_id}",
            json={"title": "Updated Title", "expected_version": 1},
            headers=self.alice_headers
        )
        self.assertEqual(res_update.status_code, 200)
        d_updated = res_update.json()

        u_at_updated_str = d_updated["updated_at"]
        self.assertGreater(u_at_updated_str, c_at_str)

        # Verify PostgreSQL database row directly
        sb = legal_draft_manager.supabase
        db_res = sb.table("legal_drafts").select("created_at, updated_at").eq("id", draft_id).execute()
        row = db_res.data[0]
        self.assertGreater(row["updated_at"], row["created_at"])


if __name__ == "__main__":
    unittest.main()


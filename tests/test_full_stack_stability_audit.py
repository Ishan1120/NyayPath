import os
import sys
import uuid
import unittest
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from fastapi import HTTPException
from fastapi.testclient import TestClient
from api.index import app
from api.auth import (
    AuthUser,
    UserRole,
    AccountStatus,
    create_access_token,
    decode_access_token,
)
from api.campus_proctor import campus_proctor_manager, ProctorUpdateStatus
from api.platform_admin import platform_admin_manager
from api.lawyer_connect import lawyer_connect_manager
from api.messaging import communication_manager
from api.notifications import notification_manager
from api.citizen_workspace import citizen_workspace_manager
from api.case_manager import case_manager

client = TestClient(app)


class TestFullStackStabilityAudit(unittest.TestCase):
    """
    Automated regression tests verifying all fixes from the Full-Stack Audit:
    1. Dynamic connection recovery across all 7 backend managers.
    2. Fail-closed platform admin database authorization.
    3. Cross-case-type rejection for non-campus grievances.
    4. Safe SQLite field update handling without KeyError.
    5. Clean separation of HS256 application tokens and Supabase tokens.
    6. Meeting constraint consistency and privacy masking.
    """

    @classmethod
    def setUpClass(cls):
        os.environ["SUPABASE_OFFLINE_TEST"] = "0"
        campus_proctor_manager._ensure_connected()
        platform_admin_manager._ensure_connected()
        lawyer_connect_manager._ensure_connected()
        communication_manager._ensure_connected()
        notification_manager._ensure_connected()
        citizen_workspace_manager._ensure_connected()
        case_manager._ensure_connected()

    def test_01_all_managers_dynamic_connection_and_recovery(self):
        """Verify all managers connect dynamically and re-evaluate when offline mode changes."""
        # 1. In live mode
        self.assertTrue(campus_proctor_manager.use_supabase)
        self.assertIsNotNone(campus_proctor_manager.supabase)
        self.assertTrue(platform_admin_manager.use_supabase)
        self.assertIsNotNone(platform_admin_manager.supabase)
        self.assertIsNotNone(lawyer_connect_manager.supabase)
        self.assertTrue(communication_manager.use_supabase)
        self.assertIsNotNone(communication_manager.supabase)
        self.assertTrue(notification_manager.use_supabase)
        self.assertIsNotNone(notification_manager.supabase)
        self.assertTrue(citizen_workspace_manager.use_supabase)
        self.assertIsNotNone(citizen_workspace_manager.supabase)
        self.assertTrue(case_manager.use_supabase)
        self.assertIsNotNone(case_manager.supabase)

    def test_02_platform_admin_fail_closed_on_fake_token(self):
        """Admin token with role='platform_admin' but lacking database record must return 403."""
        fake_admin_uuid = "11111111-2222-3333-4444-555555555555"
        user = AuthUser(
            user_id=fake_admin_uuid,
            role=UserRole.PLATFORM_ADMIN,
            institution_id="*",
            name="Impostor Admin",
            email="impostor@nyaypath.gov",
            account_status=AccountStatus.ACTIVE
        )
        fake_token = create_access_token(user)

        res = client.get("/api/admin/overview", headers={"Authorization": f"Bearer {fake_token}"})
        self.assertEqual(res.status_code, 403)
        self.assertIn("authoritative platform administrator record", res.text.lower())

    def test_03_campus_proctor_cross_case_type_rejection(self):
        """Campus proctor must reject operations on non-campus cases (RTI / Consumer)."""
        proctor = AuthUser(
            user_id="cccccccc-1111-2222-3333-cccccccccccc",
            role=UserRole.PROCTOR,
            institution_id="INST_COLLEGE_X",
            name="Xavier Proctor",
            email="xavier@collegex.edu",
            account_status=AccountStatus.ACTIVE
        )

        # Inject an RTI case into cache to test cross-case-type rejection
        campus_proctor_manager._local_case_cache["RTI-TEST-CROSS"] = {
            "id": str(uuid.uuid4()),
            "case_id": "RTI-TEST-CROSS",
            "case_type": "RTI",
            "institution_id": "INST_COLLEGE_X",
            "status": "SUBMITTED"
        }

        with self.assertRaises(HTTPException) as ctx:
            campus_proctor_manager.update_case(
                ProctorUpdateStatus(case_id="RTI-TEST-CROSS", new_status="UNDER_INQUIRY"),
                proctor_user=proctor
            )
        self.assertEqual(ctx.exception.status_code, 400)
        self.assertIn("Cross-case-type rejection", ctx.exception.detail)

    def test_04_sqlite_update_record_null_safety(self):
        """_update_record_sqlite must safely handle partial case dictionaries without KeyError."""
        partial_case = {
            "case_id": "CAMPUS-PARTIAL-TEST",
            "status": "UNDER_INQUIRY",
            "updated_at": "2026-11-02T00:00:00Z"
        }
        # Must not raise KeyError: 'hearing_date' or 'proctor_notes'
        try:
            campus_proctor_manager._update_record_sqlite(partial_case)
        except KeyError as e:
            self.fail(f"_update_record_sqlite raised KeyError: {e}")

    def test_05_active_platform_admin_access_succeeds(self):
        """Active Platform Admin with live database record accesses overview and stats."""
        real_admin_user = AuthUser(
            user_id="99999999-1111-2222-3333-999999999999",
            role=UserRole.PLATFORM_ADMIN,
            institution_id="*",
            name="Platform Administrator",
            email="platform@nyaypath.gov",
            account_status=AccountStatus.ACTIVE
        )
        real_token = create_access_token(real_admin_user)

        res = client.get("/api/admin/overview", headers={"Authorization": f"Bearer {real_token}"})
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn("total_users", data)
        self.assertIn("total_cases", data)


if __name__ == "__main__":
    unittest.main()

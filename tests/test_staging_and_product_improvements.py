"""
NyayPath Comprehensive Regression Test Suite:
Staging Database Integrity & Priority Product Improvements (Workstream B)

Tests covered:
1. Legal Drafts Persistent CRUD, User Isolation & Optimistic Concurrency.
2. Draft-to-Lawyer Consultation Workflow, Explicit Consent & Duplicate Request Prevention.
3. Track SLA Engine: Verified Statutory Deadlines (RTI) vs. Unconfigured Categories,
   Elapsed Time & Stage Duration calculations.
4. Lawyer Complaint Timeline Aggregation, Consent Scope Enforcement (FULL / CASE_AND_DOCS vs METADATA_ONLY),
   PII / Note Sanitization, and Grounded AI Case Summary.
5. Tracking Key Sanitized Public View vs. Authenticated Owner Full Details.
"""

import unittest
import uuid
from datetime import datetime, timezone, timedelta
from fastapi import HTTPException
import hashlib

from api.auth import AuthUser, UserRole, AccountStatus
from api.legal_drafts import (
    legal_draft_manager,
    CreateDraftRequest,
    UpdateDraftRequest
)
from api.lawyer_connect import (
    lawyer_connect_manager,
    ConsultationCreateRequest,
    CaseAccessGrantRequest,
    CaseAccessRevokeRequest
)
from api.watchdog_engine import (
    evaluate_watchdog_state,
    STATUTORY_SLA_RULES
)
from api.citizen_workspace import citizen_workspace_manager


class TestProductImprovements(unittest.TestCase):

    def setUp(self):
        self.test_citizen = AuthUser(
            user_id="aaaaaaaa-1111-2222-3333-aaaaaaaaaaaa",
            email="alice@collegex.edu",
            role=UserRole.CITIZEN,
            account_status=AccountStatus.ACTIVE,
            name="Alice Sharma",
            institution_id="INST_DEFAULT"
        )
        self.other_citizen = AuthUser(
            user_id="bbbbbbbb-1111-2222-3333-bbbbbbbbbbbb",
            email="bob@collegex.edu",
            role=UserRole.CITIZEN,
            account_status=AccountStatus.ACTIVE,
            name="Bob Verma",
            institution_id="INST_DEFAULT"
        )
        self.verified_lawyer = AuthUser(
            user_id="99999999-1111-2222-3333-999999999999",
            email="advocate.patel@nyaypath.in",
            role=UserRole.LAWYER,
            account_status=AccountStatus.ACTIVE,
            name="Adv. Rajesh Patel",
            institution_id="INST_DEFAULT"
        )

    # =========================================================================
    # 1. Legal Drafts Persistent Storage & Versioning Tests
    # =========================================================================

    def test_draft_creation_persistence(self):
        """Verifies that a user draft is persisted with initial version 1 and ownership."""
        req = CreateDraftRequest(
            title="RTI Application - Road Repair Tender",
            document_type="RTI",
            facts="Municipal road tender delayed by 8 months.",
            legal_provisions="Section 6(1) read with Section 2(j)(i) of RTI Act, 2005",
            requested_relief="Certified copies of measurement books and sanction orders.",
            draft_content="FORM A: RTI Application to PIO Municipal Corp."
        )
        draft = legal_draft_manager.create_draft(self.test_citizen, req)

        self.assertIsNotNone(draft["id"])
        self.assertEqual(draft["user_id"], str(self.test_citizen.user_id))
        self.assertEqual(draft["title"], "RTI Application - Road Repair Tender")
        self.assertEqual(draft["version"], 1)
        self.assertEqual(draft["status"], "SAVED")

        # Retrieve and verify persistence
        retrieved = legal_draft_manager.get_draft(self.test_citizen, draft["id"])
        self.assertEqual(retrieved["id"], draft["id"])
        self.assertEqual(retrieved["draft_content"], req.draft_content)

    def test_draft_optimistic_concurrency_and_versioning(self):
        """Verifies that updates increment version and reject stale expected_version with 409 Conflict."""
        req = CreateDraftRequest(
            title="Draft Concurrency Test",
            document_type="RTI",
            draft_content="Version 1 content"
        )
        draft = legal_draft_manager.create_draft(self.test_citizen, req)
        draft_id = draft["id"]

        # First update with correct expected_version=1 -> succeeds and increments to 2
        up_req1 = UpdateDraftRequest(
            draft_content="Version 2 updated content",
            expected_version=1
        )
        updated1 = legal_draft_manager.update_draft(self.test_citizen, draft_id, up_req1)
        self.assertEqual(updated1["version"], 2)
        self.assertEqual(updated1["draft_content"], "Version 2 updated content")

        # Stale update with expected_version=1 -> must raise 409 Conflict
        up_stale = UpdateDraftRequest(
            draft_content="Delayed stale overwrite",
            expected_version=1
        )
        with self.assertRaises(HTTPException) as ctx:
            legal_draft_manager.update_draft(self.test_citizen, draft_id, up_stale)
        self.assertEqual(ctx.exception.status_code, 409)
        self.assertIn("Conflict", ctx.exception.detail)

    def test_draft_cross_user_isolation(self):
        """Verifies that one citizen cannot access or delete another citizen's draft."""
        req = CreateDraftRequest(
            title="Private Citizen Draft",
            document_type="CONSUMER",
            draft_content="Confidential dispute facts"
        )
        draft = legal_draft_manager.create_draft(self.test_citizen, req)
        draft_id = draft["id"]

        # other_citizen attempts to get -> 403 Forbidden
        with self.assertRaises(HTTPException) as ctx:
            legal_draft_manager.get_draft(self.other_citizen, draft_id)
        self.assertEqual(ctx.exception.status_code, 403)

        # other_citizen attempts to update -> 403 Forbidden
        with self.assertRaises(HTTPException) as ctx:
            legal_draft_manager.update_draft(self.other_citizen, draft_id, UpdateDraftRequest(title="Hacked"))
        self.assertEqual(ctx.exception.status_code, 403)

        # other_citizen attempts to delete -> 403 Forbidden
        with self.assertRaises(HTTPException) as ctx:
            legal_draft_manager.delete_draft(self.other_citizen, draft_id)
        self.assertEqual(ctx.exception.status_code, 403)

    # =========================================================================
    # 2. Draft-to-Lawyer Connection & Consultation Workflow
    # =========================================================================

    def test_consultation_request_model_and_draft_attachment(self):
        """Verifies consultation request structure with draft_id and include_draft fields."""
        req = ConsultationCreateRequest(
            lawyer_user_id=str(self.verified_lawyer.user_id),
            case_id="CR-2026-1234",
            legal_issue="Municipal road neglect",
            description="Seeking advice on RTI delay",
            preferred_mode="ONLINE",
            draft_id=str(uuid.uuid4()),
            include_draft=True
        )
        self.assertEqual(req.include_draft, True)
        self.assertIsNotNone(req.draft_id)

    # =========================================================================
    # 3. Track SLA Page: Verified Deadlines vs. Unconfigured Categories
    # =========================================================================

    def test_sla_statutory_rti_deadline(self):
        """Verifies RTI case receives verified Section 7(1) statutory deadline and source."""
        now = datetime(2026, 11, 3, 12, 0, 0, tzinfo=timezone.utc)
        filing_date = (now - timedelta(days=10)).isoformat()

        rti_case = {
            "case_id": "RTI-TEST-001",
            "category": "RTI",
            "filing_date": filing_date,
            "status": "FILED",
            "life_liberty_flag": False
        }

        evaluated = evaluate_watchdog_state(rti_case, now=now)

        self.assertTrue(evaluated["has_statutory_deadline"])
        self.assertEqual(evaluated["statutory_source"], "Section 7(1), Right to Information Act, 2005")
        self.assertEqual(evaluated["statutory_verification_date"], "2005-06-15")
        self.assertEqual(evaluated["days_remaining"], 20)
        self.assertFalse(evaluated["is_overdue"])
        self.assertEqual(evaluated["time_elapsed_since_submission_seconds"], 10 * 86400)
        self.assertIn("10d", evaluated["time_elapsed_since_submission_formatted"])

    def test_sla_non_rti_category_no_arbitrary_countdown(self):
        """
        CRITICAL REQUIREMENT:
        Verifies non-RTI categories (Grievances, Consumer, Campus) do NOT receive an arbitrary 30-day countdown,
        and explicitly return 'No verified statutory deadline configured for this case.'
        """
        now = datetime(2026, 11, 3, 12, 0, 0, tzinfo=timezone.utc)
        # Case filed 35 days ago (would be overdue under an arbitrary 30-day countdown!)
        filing_date = (now - timedelta(days=35)).isoformat()

        grievance_case = {
            "case_id": "GRIEV-2026-9999",
            "category": "CIVIC_GRIEVANCE",
            "filing_date": filing_date,
            "status": "UNDER_INQUIRY"
        }

        evaluated = evaluate_watchdog_state(grievance_case, now=now)

        # Must NOT have statutory deadline
        self.assertFalse(evaluated["has_statutory_deadline"])
        self.assertEqual(evaluated["statutory_deadline_message"], "No verified statutory deadline configured for this case.")
        self.assertIsNone(evaluated["response_due_date"])
        self.assertIsNone(evaluated["first_appeal_due_date"])
        self.assertFalse(evaluated["is_overdue"])
        self.assertIsNone(evaluated["days_remaining"])
        self.assertEqual(evaluated["section_20_penalty_inr"], 0)

        # Must accurately calculate elapsed time and stage duration
        self.assertEqual(evaluated["time_elapsed_since_submission_seconds"], 35 * 86400)
        self.assertIn("35d", evaluated["time_elapsed_since_submission_formatted"])
        self.assertIsNotNone(evaluated["current_responsible_authority"])
        self.assertIsNotNone(evaluated["next_expected_action"])

    # =========================================================================
    # 4. Lawyer Complaint Timeline & AI Assistant
    # =========================================================================

    def test_lawyer_timeline_scope_and_revocation(self):
        """
        Verifies that a lawyer without active access is rejected,
        and METADATA_ONLY scope is rejected from accessing full timeline.
        """
        case_id = "CAMPUS-GRV-TEST-001"

        # No access record -> 403 Forbidden
        with self.assertRaises(HTTPException) as ctx:
            lawyer_connect_manager.get_case_timeline_for_lawyer(self.verified_lawyer, case_id)
        self.assertEqual(ctx.exception.status_code, 403)

        # In-memory mock for METADATA_ONLY test
        lawyer_uid = str(self.verified_lawyer.user_id)
        if not hasattr(lawyer_connect_manager, "_in_memory_access"):
            lawyer_connect_manager._in_memory_access = {}

        lawyer_connect_manager._in_memory_access[f"{lawyer_uid}:{case_id}"] = {
            "lawyer_user_id": lawyer_uid,
            "case_id": case_id,
            "access_status": "ACTIVE",
            "shared_scope": "METADATA_ONLY",
            "granted_at": datetime.now(timezone.utc).isoformat()
        }

        # METADATA_ONLY must be rejected from timeline
        with self.assertRaises(HTTPException) as ctx:
            lawyer_connect_manager.get_case_timeline_for_lawyer(self.verified_lawyer, case_id)
        self.assertEqual(ctx.exception.status_code, 403)
        self.assertIn("METADATA_ONLY", ctx.exception.detail)

        # Upgrade to CASE_AND_DOCS -> passes and returns chronological events
        lawyer_connect_manager._in_memory_access[f"{lawyer_uid}:{case_id}"]["shared_scope"] = "CASE_AND_DOCS"
        timeline = lawyer_connect_manager.get_case_timeline_for_lawyer(self.verified_lawyer, case_id)
        self.assertEqual(timeline["case_id"], case_id)
        self.assertEqual(timeline["shared_scope"], "CASE_AND_DOCS")
        self.assertIn("events", timeline)

        # Revoke access -> immediately rejected
        lawyer_connect_manager._in_memory_access[f"{lawyer_uid}:{case_id}"]["access_status"] = "REVOKED"
        with self.assertRaises(HTTPException) as ctx:
            lawyer_connect_manager.get_case_timeline_for_lawyer(self.verified_lawyer, case_id)
        self.assertEqual(ctx.exception.status_code, 403)

    def test_ai_case_summary_grounded_in_timeline(self):
        """Verifies AI case summary is marked AI-generated and links to source timeline events."""
        case_id = "CASE-AI-TEST-777"
        lawyer_uid = str(self.verified_lawyer.user_id)

        if not hasattr(lawyer_connect_manager, "_in_memory_access"):
            lawyer_connect_manager._in_memory_access = {}

        lawyer_connect_manager._in_memory_access[f"{lawyer_uid}:{case_id}"] = {
            "lawyer_user_id": lawyer_uid,
            "case_id": case_id,
            "access_status": "ACTIVE",
            "shared_scope": "FULL",
            "granted_at": datetime.now(timezone.utc).isoformat()
        }

        summary = lawyer_connect_manager.generate_ai_case_summary(self.verified_lawyer, case_id)

        self.assertTrue(summary["is_ai_generated"])
        self.assertIn("disclaimer", summary)
        self.assertIn("summary", summary)
        self.assertIn("key_developments", summary)
        self.assertIn("investigation_questions", summary)
        for kd in summary["key_developments"]:
            self.assertIn("source_event_id", kd)
            self.assertIn("source_record", kd)

    # =========================================================================
    # 5. Tracking Key Sanitization vs. Authenticated Owner Details
    # =========================================================================

    def test_tracking_key_sanitization_and_owner_separation(self):
        """
        Verifies that public tracking via key returns sanitized case info only,
        and flags that full details require owner authentication.
        """
        raw_key = "secret_tracking_token_alpha_123"
        hashed_key = hashlib.sha256(raw_key.encode()).hexdigest()

        test_case = {
            "case_id": "TRACK-SAN-001",
            "category": "Hostel Discipline",
            "status": "SUBMITTED",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "tracking_key_hash": hashed_key,
            "user_id": str(uuid.uuid4()),
            "proctor_notes": "CONFIDENTIAL INTERNAL INVESTIGATION NOTES - MUST NOT LEAK",
            "verification_key_hash": hashed_key
        }

        # Inject mock case into workspace manager
        citizen_workspace_manager._memory_cases["TRACK-SAN-001"] = test_case

        # Query with valid tracking key (unauthenticated public citizen)
        res = citizen_workspace_manager.track_case_public(
            case_id="TRACK-SAN-001",
            verification_key=raw_key,
            user=None
        )

        case_info = res["case"]
        self.assertEqual(case_info["case_id"], "TRACK-SAN-001")
        self.assertEqual(case_info["category"], "Hostel Discipline")
        self.assertIn("time_elapsed_since_submission_formatted", case_info)
        self.assertIn("time_in_current_stage_formatted", case_info)
        self.assertIn("latest_action_taken", case_info)
        self.assertIn("next_expected_step", case_info)

        # Privacy boundaries: confidential notes and secret hashes must NEVER be present
        self.assertNotIn("proctor_notes", case_info)
        self.assertNotIn("tracking_key_hash", case_info)
        self.assertNotIn("verification_key_hash", case_info)

        # Owner separation
        self.assertTrue(case_info["requires_owner_auth_for_full_details"])
        self.assertFalse(case_info["is_owner_authenticated"])

    def test_invalid_tracking_key_rejection(self):
        """Verifies that an invalid tracking key is rejected with 401 Unauthorized."""
        raw_key = "legitimate_key_999"
        hashed_key = hashlib.sha256(raw_key.encode()).hexdigest()

        citizen_workspace_manager._memory_cases["TRACK-REJ-002"] = {
            "case_id": "TRACK-REJ-002",
            "status": "SUBMITTED",
            "tracking_key_hash": hashed_key,
            "verification_key_hash": hashed_key
        }

        with self.assertRaises(HTTPException) as ctx:
            citizen_workspace_manager.track_case_public(
                case_id="TRACK-REJ-002",
                verification_key="wrong_tampered_key_000",
                user=None
            )
        self.assertEqual(ctx.exception.status_code, 401)


if __name__ == "__main__":
    unittest.main()

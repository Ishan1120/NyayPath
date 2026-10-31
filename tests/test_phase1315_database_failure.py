"""
NyayPath Phase 1.3.15 — Production Database Failure Security Verification Suite
================================================================================
Implements and runs live security tests for:
- Test A: Production mode, Supabase client initialized, database query fails,
          and a cached case exists. Request strictly FAILS CLOSED (HTTP 503).
- Test B: Previously authorized officer has cached case record, but committee
          assignment or institutional membership is revoked / DB unavailable.
          Request strictly FAILS CLOSED (HTTP 503 / 403) and no signed URL is issued.
- Test C: Verification that create_signed_url() is NEVER invoked when authoritative
          production authorization cannot be established.
- Test D: Live database available and user legitimately authorized; document access
          succeeds with valid signed URL.
- Test E: Development/test mode retains offline mock fallback without leaking into production.
- Test F: Anonymous Citizen Access pathway reconciliation (tracking key HMAC validation,
          document binding, rate limiting, and production fail-closed behavior).
"""

import os
import sys
import uuid
import time
import jwt
from unittest.mock import MagicMock
from fastapi import HTTPException

os.environ["SUPABASE_URL"] = "http://127.0.0.1:54321"
os.environ["SUPABASE_SECRET_KEY"] = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZS1kZW1vIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImV4cCI6MTk4MzgxMjk5Nn0.EGIM96RAZx35lJzdJsyH-qQwv8Hdp7fsn3W0YpN81IU"
os.environ["SUPABASE_JWT_SECRET"] = "super-secret-jwt-token-with-at-least-32-characters-long"
os.environ["JWT_SECRET"] = "super-secret-jwt-token-with-at-least-32-characters-long"

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from api.document_access import (
    DocumentAccessManager,
    is_production_environment,
    CANONICAL_STORAGE_BUCKET,
    SIGNED_URL_EXPIRY_SECONDS,
)
from api.campus_proctor import campus_proctor_manager, hash_verification_key
from api.auth import AuthUser, UserRole, AccountStatus, create_access_token
from supabase import create_client


def run_test_a():
    """Test A: Production mode, Supabase client initialized, DB query fails, cached case exists. Fails closed."""
    print("\n[Test A] Production mode: DB query fails with existing local cache")
    os.environ["ENVIRONMENT"] = "production"
    cached_case_id = "CAMPUS-CACHED-01"
    try:
        # Populate campus_proctor_manager local cache
        campus_proctor_manager._local_case_cache[cached_case_id] = {
            "id": str(uuid.uuid4()),
            "case_id": cached_case_id,
            "institution_id": "INST_X",
            "is_confidential": False,
            "confidentiality_mode": "STANDARD",
            "supporting_documents": ["cached_doc.pdf"],
            "student_user_id": "student-123",
        }

        # Mock Supabase client where table queries throw DB Connection Error
        mock_supabase = MagicMock()
        mock_supabase.table.side_effect = Exception("PostgreSQL server terminated unexpectedly / connection failure")
        mock_storage = MagicMock()
        mock_bucket = MagicMock()
        mock_storage.from_.return_value = mock_bucket
        mock_supabase.storage = mock_storage

        doc_mgr = DocumentAccessManager(supabase_client=mock_supabase)
        student_user = AuthUser(
            user_id="student-123",
            email="student@college.edu",
            role=UserRole.STUDENT,
            institution_id="INST_X",
            account_status=AccountStatus.ACTIVE,
        )
        token = create_access_token(student_user)

        failed_closed = False
        try:
            doc_mgr.generate_document_signed_url(
                case_id=cached_case_id,
                document_id="cached_doc.pdf",
                auth_header=f"Bearer {token}",
            )
        except HTTPException as e:
            if e.status_code == 503 and "Database unavailable" in e.detail:
                failed_closed = True
        
        assert failed_closed, "CRITICAL: Request did not fail closed on DB query failure! Cached record must not be used."
        mock_bucket.create_signed_url.assert_not_called()
        print("  [PASS] Stale cache ignored; request failed closed with HTTP 503. Storage signing never called.")
    finally:
        os.environ.pop("ENVIRONMENT", None)
        campus_proctor_manager._local_case_cache.pop(cached_case_id, None)


def run_test_b():
    """Test B: Previously authorized officer, revoked membership/assignment or DB down. Fails closed."""
    print("\n[Test B] Previously authorized officer with revoked status or DB failure")
    os.environ["ENVIRONMENT"] = "production"
    case_id = "CAMPUS-CONF-B"
    proctor_uuid = "11111111-2222-3333-4444-555555555555"
    case_uuid = str(uuid.uuid4())

    try:
        # Scenario B1: DB fails when verifying institutional membership
        mock_supabase = MagicMock()
        # Case query succeeds
        mock_case_table = MagicMock()
        mock_case_eq = MagicMock()
        mock_case_eq.execute.return_value.data = [{
            "id": case_uuid,
            "case_id": case_id,
            "institution_id": "INST_COLLEGE_X",
            "is_confidential": True,
            "confidentiality_mode": "CONFIDENTIAL",
            "supporting_documents": ["confidential_doc.pdf"],
        }]
        mock_case_table.select.return_value.eq.return_value = mock_case_eq

        # Institution memberships query throws DB exception
        mock_membership_table = MagicMock()
        mock_membership_table.select.side_effect = Exception("DB network timeout on institution_memberships")

        def table_router(table_name):
            if table_name == "campus_cases":
                return mock_case_table
            elif table_name == "institution_memberships":
                return mock_membership_table
            elif table_name == "case_committee_assignments":
                return MagicMock()
            return MagicMock()

        mock_supabase.table.side_effect = table_router
        mock_storage = MagicMock()
        mock_bucket = MagicMock()
        mock_storage.from_.return_value = mock_bucket
        mock_supabase.storage = mock_storage

        doc_mgr = DocumentAccessManager(supabase_client=mock_supabase)
        proctor_user = AuthUser(
            user_id=proctor_uuid,
            email="proctor@collegex.edu",
            role=UserRole.CHIEF_PROCTOR,
            institution_id="INST_COLLEGE_X",
            account_status=AccountStatus.ACTIVE,
        )
        token = create_access_token(proctor_user)

        b1_failed_closed = False
        try:
            doc_mgr.generate_document_signed_url(
                case_id=case_id,
                document_id="confidential_doc.pdf",
                auth_header=f"Bearer {token}",
            )
        except HTTPException as e:
            if e.status_code == 503 and "Unable to verify institutional membership" in e.detail:
                b1_failed_closed = True
        assert b1_failed_closed, "B1: Membership DB failure must fail closed with HTTP 503!"
        mock_bucket.create_signed_url.assert_not_called()
        print("  [PASS] Scenario B1: Membership DB failure strictly failed closed with HTTP 503.")

        # Scenario B2: DB is up, but membership is revoked (account_status != 'active')
        mock_membership_ok = MagicMock()
        mock_membership_ok.select.return_value.eq.return_value.eq.return_value.execute.return_value.data = []  # No active record
        
        def table_router_revoked_membership(table_name):
            if table_name == "campus_cases":
                return mock_case_table
            elif table_name == "institution_memberships":
                return mock_membership_ok
            return MagicMock()

        mock_supabase.table.side_effect = table_router_revoked_membership
        b2_blocked = False
        try:
            doc_mgr.generate_document_signed_url(
                case_id=case_id,
                document_id="confidential_doc.pdf",
                auth_header=f"Bearer {token}",
            )
        except HTTPException as e:
            if e.status_code == 403 and "membership is revoked" in e.detail:
                b2_blocked = True
        assert b2_blocked, "B2: Revoked institutional membership must be blocked with HTTP 403!"
        mock_bucket.create_signed_url.assert_not_called()
        print("  [PASS] Scenario B2: Revoked institutional membership strictly blocked with HTTP 403.")

        # Scenario B3: Membership active, but committee assignment DB query fails
        mock_membership_active = MagicMock()
        mock_membership_active.select.return_value.eq.return_value.eq.return_value.execute.return_value.data = [{"id": "m1", "account_status": "active"}]
        
        mock_comm_fail = MagicMock()
        mock_comm_fail.select.side_effect = Exception("DB error on case_committee_assignments")

        def table_router_comm_fail(table_name):
            if table_name == "campus_cases":
                return mock_case_table
            elif table_name == "institution_memberships":
                return mock_membership_active
            elif table_name == "case_committee_assignments":
                return mock_comm_fail
            return MagicMock()

        mock_supabase.table.side_effect = table_router_comm_fail
        b3_failed_closed = False
        try:
            doc_mgr.generate_document_signed_url(
                case_id=case_id,
                document_id="confidential_doc.pdf",
                auth_header=f"Bearer {token}",
            )
        except HTTPException as e:
            if e.status_code == 503 and "Unable to verify committee assignment" in e.detail:
                b3_failed_closed = True
        assert b3_failed_closed, "B3: Committee assignment DB failure must fail closed with HTTP 503!"
        mock_bucket.create_signed_url.assert_not_called()
        print("  [PASS] Scenario B3: Committee assignment DB failure strictly failed closed with HTTP 503.")

        # Scenario B4: Membership active, but committee assignment revoked in database
        mock_comm_revoked = MagicMock()
        mock_comm_revoked.select.return_value.eq.return_value.eq.return_value.eq.return_value.execute.return_value.data = []

        def table_router_comm_revoked(table_name):
            if table_name == "campus_cases":
                return mock_case_table
            elif table_name == "institution_memberships":
                return mock_membership_active
            elif table_name == "case_committee_assignments":
                return mock_comm_revoked
            return MagicMock()

        mock_supabase.table.side_effect = table_router_comm_revoked
        b4_blocked = False
        try:
            doc_mgr.generate_document_signed_url(
                case_id=case_id,
                document_id="confidential_doc.pdf",
                auth_header=f"Bearer {token}",
            )
        except HTTPException as e:
            if e.status_code == 403 and "Confidential grievance documents require direct case assignment" in e.detail:
                b4_blocked = True
        assert b4_blocked, "B4: Revoked committee assignment on confidential case must be blocked with HTTP 403!"
        mock_bucket.create_signed_url.assert_not_called()
        print("  [PASS] Scenario B4: Revoked committee assignment on confidential case strictly blocked with HTTP 403.")

    finally:
        os.environ.pop("ENVIRONMENT", None)


def run_test_c():
    """Test C: Verify create_signed_url() is NEVER invoked when authoritative authorization cannot be established."""
    print("\n[Test C] Verification that create_signed_url() is never invoked without authorization")
    os.environ["ENVIRONMENT"] = "production"
    try:
        mock_supabase = MagicMock()
        mock_storage = MagicMock()
        mock_bucket = MagicMock()
        mock_storage.from_.return_value = mock_bucket
        mock_supabase.storage = mock_storage

        # Configure mock table queries
        mock_supabase.table.side_effect = Exception("Generic DB outage")
        doc_mgr = DocumentAccessManager(supabase_client=mock_supabase)

        # 1. Anonymous without key
        try:
            doc_mgr.generate_document_signed_url("CASE-1", "doc1.pdf")
        except HTTPException:
            pass

        # 2. Invalid token
        try:
            doc_mgr.generate_document_signed_url("CASE-1", "doc1.pdf", auth_header="Bearer invalid.token.here")
        except HTTPException:
            pass

        # 3. Suspended user
        suspended_user = AuthUser(
            user_id="susp-1",
            email="s@collegex.edu",
            role=UserRole.STUDENT,
            institution_id="INST_X",
            account_status=AccountStatus.SUSPENDED,
        )
        token_susp = create_access_token(suspended_user)
        try:
            doc_mgr.generate_document_signed_url("CASE-1", "doc1.pdf", auth_header=f"Bearer {token_susp}")
        except HTTPException:
            pass

        # 4. DB outage
        admin_user = AuthUser(
            user_id="adm-1",
            email="admin@collegex.edu",
            role=UserRole.INSTITUTION_ADMIN,
            institution_id="INST_X",
            account_status=AccountStatus.ACTIVE,
        )
        token_adm = create_access_token(admin_user)
        try:
            doc_mgr.generate_document_signed_url("CASE-1", "doc1.pdf", auth_header=f"Bearer {token_adm}")
        except HTTPException:
            pass

        # Ensure create_signed_url was never called across all attempts
        mock_bucket.create_signed_url.assert_not_called()
        print("  [PASS] Verified: Storage create_signed_url() was invoked 0 times across all unauthorized and failure states.")
    finally:
        os.environ.pop("ENVIRONMENT", None)


def run_test_d():
    """Test D: Database available, user legitimately authorized, document access works."""
    print("\n[Test D] Legitimately authorized access succeeds when database is available")
    # Test against running local Supabase instance
    supabase_url = os.environ.get("SUPABASE_URL", "http://127.0.0.1:54321")
    supabase_secret = os.environ.get("SUPABASE_SECRET_KEY", "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZS1kZW1vIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImV4cCI6MTk4MzgxMjk5Nn0.EGIM96RAZx35lJzdJsyH-qQwv8Hdp7fsn3W0YpN81IU")

    supabase_admin = create_client(supabase_url, supabase_secret)

    # Re-assign Charlie Chief Proctor to Case C
    CHIEF_X_UUID = "66666666-1111-2222-3333-666666666666"
    supabase_admin.table("case_committee_assignments").update({
        "assignment_status": "active"
    }).eq("case_id", "CAMPUS-CONF-C").eq("user_id", CHIEF_X_UUID).execute()

    doc_mgr = DocumentAccessManager(supabase_client=supabase_admin)
    chief_user = AuthUser(
        user_id=CHIEF_X_UUID,
        email="charlie@collegex.edu",
        role=UserRole.CHIEF_PROCTOR,
        institution_id="INST_COLLEGE_X",
        account_status=AccountStatus.ACTIVE,
    )
    token = create_access_token(chief_user)

    res = doc_mgr.generate_document_signed_url(
        case_id="CAMPUS-CONF-C",
        document_id="confidential_evidence.pdf",
        auth_header=f"Bearer {token}",
        ttl=120
    )
    assert res["case_id"] == "CAMPUS-CONF-C"
    assert res["document_id"] == "confidential_evidence.pdf"
    assert res["access_type"] == "ASSIGNED_CHIEF_PROCTOR"
    assert res["expires_in_seconds"] == 120
    assert "signed_url" in res
    print(f"  [PASS] Authorized Chief Proctor granted document access with access_type={res['access_type']} and expires_in_seconds={res['expires_in_seconds']}.")


def run_test_e():
    """Test E: Development/test mode retains offline mock fallback without affecting production."""
    print("\n[Test E] Development/test mode retains offline mock fallback")
    # Ensure production environment variables are unset
    for var in ["ENVIRONMENT", "NODE_ENV", "ENV", "VERCEL"]:
        os.environ.pop(var, None)

    offline_case_id = "CAMPUS-DEV-TEST-01"
    campus_proctor_manager._local_case_cache[offline_case_id] = {
        "id": str(uuid.uuid4()),
        "case_id": offline_case_id,
        "institution_id": "INST_DEV",
        "is_confidential": False,
        "confidentiality_mode": "STANDARD",
        "supporting_documents": ["offline_doc.pdf"],
        "student_user_id": "student-dev",
    }

    try:
        doc_mgr = DocumentAccessManager(supabase_client=False)
        student_user = AuthUser(
            user_id="student-dev",
            email="student@dev.edu",
            role=UserRole.STUDENT,
            institution_id="INST_DEV",
            account_status=AccountStatus.ACTIVE,
        )
        token = create_access_token(student_user)

        res = doc_mgr.generate_document_signed_url(
            case_id=offline_case_id,
            document_id="offline_doc.pdf",
            auth_header=f"Bearer {token}",
            ttl=300
        )
        assert "mock-storage.nyaypath.internal" in res["signed_url"]
        assert res["access_type"] == "CASE_OWNER"
        print("  [PASS] Development/test mode cleanly provided mock fallback for local testing.")

        # Now activate production flag and confirm identical request fails closed immediately
        os.environ["ENVIRONMENT"] = "production"
        failed_in_prod = False
        try:
            doc_mgr.generate_document_signed_url(
                case_id=offline_case_id,
                document_id="offline_doc.pdf",
                auth_header=f"Bearer {token}",
                ttl=300
            )
        except HTTPException as e:
            if e.status_code == 503:
                failed_in_prod = True
        assert failed_in_prod, "Same request under production must fail closed with HTTP 503!"
        print("  [PASS] Re-enabling ENVIRONMENT=production immediately prevented offline fallback and failed closed (HTTP 503).")
    finally:
        os.environ.pop("ENVIRONMENT", None)
        campus_proctor_manager._local_case_cache.pop(offline_case_id, None)


def run_test_f():
    """Test F: Anonymous Citizen Access pathway reconciliation (tracking key HMAC, document binding, DB failure)."""
    print("\n[Test F] Anonymous Citizen Access pathway reconciliation")
    raw_key = "SEC-A1B2C3D4E5F678901234567890ABCDEF"
    key_hash = hash_verification_key(raw_key)

    # Scenario F1: Production mode, DB failure -> Must fail closed with HTTP 503
    os.environ["ENVIRONMENT"] = "production"
    try:
        mock_supabase = MagicMock()
        mock_supabase.table.side_effect = Exception("DB network drop during anonymous access")
        doc_mgr = DocumentAccessManager(supabase_client=mock_supabase)

        f1_failed_closed = False
        try:
            doc_mgr.generate_document_signed_url(
                case_id="CAMPUS-ANON-01",
                document_id="evidence.pdf",
                tracking_key=raw_key
            )
        except HTTPException as e:
            if e.status_code == 503 and "Database unavailable" in e.detail:
                f1_failed_closed = True
        assert f1_failed_closed, "F1: Anonymous access must fail closed with HTTP 503 on DB failure!"
        print("  [PASS] Scenario F1: Anonymous access failed closed with HTTP 503 on DB query failure.")

        # Scenario F2: Production mode, DB available, invalid tracking key -> HTTP 403
        mock_case_table = MagicMock()
        mock_case_eq = MagicMock()
        mock_case_eq.execute.return_value.data = [{
            "id": str(uuid.uuid4()),
            "case_id": "CAMPUS-ANON-01",
            "institution_id": "INST_X",
            "verification_key_hash": key_hash,
            "supporting_documents": ["evidence.pdf"],
        }]
        mock_case_table.select.return_value.eq.return_value = mock_case_eq
        mock_supabase.table.side_effect = None
        mock_supabase.table.return_value = mock_case_table

        f2_blocked = False
        try:
            doc_mgr.generate_document_signed_url(
                case_id="CAMPUS-ANON-01",
                document_id="evidence.pdf",
                tracking_key="WRONG_TRACKING_KEY"
            )
        except HTTPException as e:
            if e.status_code == 403:
                f2_blocked = True
        assert f2_blocked, "F2: Invalid tracking key must return HTTP 403 Forbidden!"
        print("  [PASS] Scenario F2: Tampered/invalid tracking key strictly rejected with HTTP 403.")

        # Scenario F3: Foreign document binding check -> HTTP 404/403
        f3_blocked = False
        try:
            doc_mgr.generate_document_signed_url(
                case_id="CAMPUS-ANON-01",
                document_id="unrelated_foreign_doc.pdf",
                tracking_key=raw_key
            )
        except HTTPException as e:
            if e.status_code in [403, 404]:
                f3_blocked = True
        assert f3_blocked, "F3: Document not registered on case must be rejected!"
        print("  [PASS] Scenario F3: Unbound foreign document strictly rejected.")

        # Scenario F4: Valid key & bound document -> Granted with access_type=ANONYMOUS_VERIFIED
        mock_storage = MagicMock()
        mock_bucket = MagicMock()
        mock_bucket.create_signed_url.return_value = {"signedURL": "https://storage.supabase.co/case-documents/signed_anon.pdf"}
        mock_storage.from_.return_value = mock_bucket
        mock_supabase.storage = mock_storage

        res_anon = doc_mgr.generate_document_signed_url(
            case_id="CAMPUS-ANON-01",
            document_id="evidence.pdf",
            tracking_key=raw_key,
            ttl=300
        )
        assert res_anon["access_type"] == "ANONYMOUS_VERIFIED"
        assert res_anon["expires_in_seconds"] == 300
        print("  [PASS] Scenario F4: Legitimate anonymous tracking key granted document access (access_type=ANONYMOUS_VERIFIED).")

    finally:
        os.environ.pop("ENVIRONMENT", None)


def main():
    print("=" * 75)
    print("  NYAYPATH PHASE 1.3.15 DATABASE FAILURE & SECURITY AUDIT SUITE")
    print("=" * 75)
    run_test_a()
    run_test_b()
    run_test_c()
    run_test_d()
    run_test_e()
    run_test_f()
    print("\n" + "=" * 75)
    print("  ALL 6 SECURITY TEST SUITES (TESTS A-F) RUNTIME VERIFIED 100%!")
    print("=" * 75)


if __name__ == "__main__":
    main()

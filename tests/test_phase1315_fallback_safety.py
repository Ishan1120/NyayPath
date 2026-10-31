"""
NyayPath Phase 1.3.15 — Signed URL Production Fallback Safety Regression Test
=============================================================================
Verifies that:
1. In production mode (ENVIRONMENT=production, NODE_ENV=production, ENV=production, or VERCEL=1):
   - Disconnected Supabase strictly raises HTTP 503 (fails closed).
   - Supabase Storage 404 (Object not found) strictly raises HTTP 404.
   - Supabase Storage 5xx / connection exception strictly raises HTTP 502 Bad Gateway.
   - No mock URL (https://mock-storage.nyaypath.internal/...) can ever be generated or returned.
2. In non-production development/test mode:
   - Local testing fallback operates safely for test fixtures.
3. Production persistence and storage isolation are strictly maintained.
"""

import os
import sys
import uuid
from unittest.mock import MagicMock
from fastapi import HTTPException

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from api.document_access import (
    DocumentAccessManager,
    is_production_environment,
    CANONICAL_STORAGE_BUCKET,
    SIGNED_URL_EXPIRY_SECONDS,
)
from api.auth import AuthUser, UserRole, AccountStatus, create_access_token


def test_is_production_environment_flags():
    """Verify production environment detection across all recognized flags."""
    prod_flags = [
        ("ENVIRONMENT", "production"),
        ("NODE_ENV", "production"),
        ("ENV", "production"),
        ("VERCEL", "1"),
    ]
    # Clean baseline
    for var, _ in prod_flags:
        os.environ.pop(var, None)
    assert not is_production_environment(), "Default test environment should not be detected as production"

    for var, val in prod_flags:
        os.environ[var] = val
        assert is_production_environment(), f"Flag {var}={val} must activate production mode"
        os.environ.pop(var, None)
    print("  [PASS] test_is_production_environment_flags: All 4 production flags recognized.")


def test_production_fails_closed_when_supabase_unconfigured():
    """Verify HTTP 503 is raised in production when Supabase is disconnected."""
    os.environ["ENVIRONMENT"] = "production"
    try:
        doc_mgr = DocumentAccessManager(supabase_client=False)

        admin_user = AuthUser(
            user_id=str(uuid.uuid4()),
            email="admin@nyaypath.gov.in",
            role=UserRole.PLATFORM_ADMIN,
            institution_id="PLATFORM",
            account_status=AccountStatus.ACTIVE,
        )
        token = create_access_token(admin_user)

        raised_503 = False
        try:
            doc_mgr.generate_document_signed_url(
                case_id="CAMPUS-TEST-01",
                document_id="evidence.pdf",
                auth_header=f"Bearer {token}",
            )
        except HTTPException as e:
            if e.status_code == 503 and "Persistent Supabase Storage connection required" in e.detail:
                raised_503 = True
        assert raised_503, "Production environment must fail closed with HTTP 503 when Supabase is unconfigured!"
        print("  [PASS] test_production_fails_closed_when_supabase_unconfigured: HTTP 503 raised.")
    finally:
        os.environ.pop("ENVIRONMENT", None)


def test_production_fails_closed_on_storage_object_not_found():
    """Verify HTTP 404 is raised in production when document is missing from Supabase Storage."""
    os.environ["ENVIRONMENT"] = "production"
    try:
        mock_supabase = MagicMock()
        # Mock table lookup for case
        mock_table = MagicMock()
        mock_select = MagicMock()
        mock_eq = MagicMock()
        mock_eq.execute.return_value.data = [{
            "id": str(uuid.uuid4()),
            "case_id": "CAMPUS-TEST-01",
            "institution_id": "INST_X",
            "confidentiality_mode": "STANDARD",
            "is_confidential": False,
            "supporting_documents": ["evidence.pdf"],
        }]
        mock_select.eq.return_value = mock_eq
        mock_table.select.return_value = mock_select
        mock_supabase.table.return_value = mock_table

        # Mock storage returning 404 Object Not Found
        mock_storage = MagicMock()
        mock_bucket = MagicMock()
        mock_bucket.create_signed_url.return_value = {
            "statusCode": 404,
            "error": "not_found",
            "message": "Object not found",
        }
        mock_storage.from_.return_value = mock_bucket
        mock_supabase.storage = mock_storage

        doc_mgr = DocumentAccessManager(supabase_client=mock_supabase)
        admin_user = AuthUser(
            user_id=str(uuid.uuid4()),
            email="admin@nyaypath.gov.in",
            role=UserRole.PLATFORM_ADMIN,
            institution_id="PLATFORM",
            account_status=AccountStatus.ACTIVE,
        )
        token = create_access_token(admin_user)

        raised_404 = False
        try:
            doc_mgr.generate_document_signed_url(
                case_id="CAMPUS-TEST-01",
                document_id="evidence.pdf",
                auth_header=f"Bearer {token}",
            )
        except HTTPException as e:
            if e.status_code == 404 and "Document 'evidence.pdf' not found in storage" in e.detail:
                raised_404 = True
        assert raised_404, "Production environment must fail closed with HTTP 404 when object is missing in storage!"
        print("  [PASS] test_production_fails_closed_on_storage_object_not_found: HTTP 404 raised.")
    finally:
        os.environ.pop("ENVIRONMENT", None)


def test_production_fails_closed_on_storage_service_exception():
    """Verify HTTP 502 is raised in production when Supabase Storage encounters network or API error."""
    os.environ["ENVIRONMENT"] = "production"
    try:
        mock_supabase = MagicMock()
        # Mock storage throwing ConnectionError
        mock_storage = MagicMock()
        mock_bucket = MagicMock()
        mock_bucket.create_signed_url.side_effect = ConnectionError("Supabase Storage service unreachable")
        mock_storage.from_.return_value = mock_bucket
        mock_supabase.storage = mock_storage

        doc_mgr = DocumentAccessManager(supabase_client=mock_supabase)
        admin_user = AuthUser(
            user_id=str(uuid.uuid4()),
            email="admin@nyaypath.gov.in",
            role=UserRole.PLATFORM_ADMIN,
            institution_id="PLATFORM",
            account_status=AccountStatus.ACTIVE,
        )
        token = create_access_token(admin_user)

        raised_502 = False
        try:
            doc_mgr.generate_document_signed_url(
                case_id="CAMPUS-TEST-01",
                document_id="evidence.pdf",
                auth_header=f"Bearer {token}",
            )
        except HTTPException as e:
            if e.status_code == 502 and "Storage service error" in e.detail:
                raised_502 = True
        assert raised_502, "Production environment must fail closed with HTTP 502 when storage communication fails!"
        print("  [PASS] test_production_fails_closed_on_storage_service_exception: HTTP 502 raised.")
    finally:
        os.environ.pop("ENVIRONMENT", None)


def test_production_never_returns_mock_storage_url():
    """Verify that under NO circumstances can a production response contain mock-storage URL."""
    os.environ["VERCEL"] = "1"
    try:
        doc_mgr = DocumentAccessManager(supabase_client=False)
        admin_user = AuthUser(
            user_id=str(uuid.uuid4()),
            email="admin@nyaypath.gov.in",
            role=UserRole.PLATFORM_ADMIN,
            institution_id="PLATFORM",
            account_status=AccountStatus.ACTIVE,
        )
        token = create_access_token(admin_user)

        try:
            res = doc_mgr.generate_document_signed_url(
                case_id="CAMPUS-TEST-01",
                document_id="evidence.pdf",
                auth_header=f"Bearer {token}",
            )
            assert "mock-storage.nyaypath.internal" not in res.get("signed_url", ""), "CRITICAL: Mock storage URL leaked in production!"
            assert False, "Should have raised an HTTP exception in production mode"
        except HTTPException as e:
            assert e.status_code in (502, 503, 404), f"Unexpected status code {e.status_code}"
            print(f"  [PASS] test_production_never_returns_mock_storage_url: Correctly rejected with HTTP {e.status_code}.")
    finally:
        os.environ.pop("VERCEL", None)


def test_dev_mode_permits_local_mock_fallback():
    """Verify that development/test mode still permits the mock signed URL fallback for offline testing."""
    for var in ["ENVIRONMENT", "NODE_ENV", "ENV", "VERCEL"]:
        os.environ.pop(var, None)

    doc_mgr = DocumentAccessManager(supabase_client=None)
    admin_user = AuthUser(
        user_id=str(uuid.uuid4()),
        email="admin@nyaypath.gov.in",
        role=UserRole.PLATFORM_ADMIN,
        institution_id="PLATFORM",
        account_status=AccountStatus.ACTIVE,
    )
    token = create_access_token(admin_user)

    res = doc_mgr.generate_document_signed_url(
        case_id="CAMPUS-DEV-01",
        document_id="dev_evidence.pdf",
        auth_header=f"Bearer {token}",
    )
    assert res["case_id"] == "CAMPUS-DEV-01"
    assert res["document_id"] == "dev_evidence.pdf"
    assert res["bucket"] == CANONICAL_STORAGE_BUCKET
    assert "mock-storage.nyaypath.internal" in res["signed_url"]
    assert res["expires_in_seconds"] == SIGNED_URL_EXPIRY_SECONDS
    print("  [PASS] test_dev_mode_permits_local_mock_fallback: Dev mock storage operates properly.")


def main():
    print("=" * 70)
    print("  NYAYPATH PHASE 1.3.15 SIGNED URL FALLBACK SAFETY REGRESSION SUITE")
    print("=" * 70)
    test_is_production_environment_flags()
    test_production_fails_closed_when_supabase_unconfigured()
    test_production_fails_closed_on_storage_object_not_found()
    test_production_fails_closed_on_storage_service_exception()
    test_production_never_returns_mock_storage_url()
    test_dev_mode_permits_local_mock_fallback()
    print("\n" + "=" * 70)
    print("  ALL 6 SIGNED URL FALLBACK SAFETY REGRESSION TESTS PASSED 100%!")
    print("=" * 70)


if __name__ == "__main__":
    main()

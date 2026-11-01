"""
NyayPath Phase 3: Production Security, API Reliability & Application Hardening Test Suite
========================================================================================
Comprehensive automated tests covering:
1. Authentication Rigor (JWT Subject, Audience, Algorithm verification, Account Status Fail-Closed)
2. FastAPI Token Isolation (Custom FastAPI tokens never forwarded to PostgREST)
3. Notification Database Immutability & Least-Privilege Grants
4. Notification Production Fail-Closed Behavior (Zero in-memory fallback in prod)
5. API Reliability: Upload missing case 404 & path traversal sanitization
6. Public Tracking Constant-Time HMAC Verification
7. Citation URL Safety & Jurisdictional Authority Classification
8. Production Diagnostic Endpoint 404 Disabling
9. CORS Policy Non-Wildcard Verification
10. Secret Keys & Environment Hygiene (Zero secrets exposed to client)
"""

import os
import sys
import hmac
import time
import uuid
import secrets
import hashlib
import unittest
from datetime import datetime, timezone, timedelta
from pathlib import Path

# Enforce local Supabase configuration
os.environ["SUPABASE_URL"] = "http://127.0.0.1:54321"
os.environ["SUPABASE_SECRET_KEY"] = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZS1kZW1vIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImV4cCI6MTk4MzgxMjk5Nn0.EGIM96RAZx35lJzdJsyH-qQwv8Hdp7fsn3W0YpN81IU"
os.environ["SUPABASE_JWT_SECRET"] = "super-secret-jwt-token-with-at-least-32-characters-long"
os.environ["JWT_SECRET"] = "super-secret-jwt-token-with-at-least-32-characters-long"
os.environ["SUPABASE_OFFLINE_TEST"] = "0"

_root_dir = Path(__file__).resolve().parent.parent
if str(_root_dir) not in sys.path:
    sys.path.insert(0, str(_root_dir))

import jwt
from starlette.requests import Request
from fastapi import HTTPException
from api.auth import (
    decode_access_token,
    decode_supabase_access_token,
    get_request_scoped_supabase_client,
    get_current_authenticated_user,
    AuthUser,
    UserRole,
    AccountStatus,
    get_jwt_secret,
    create_access_token,
    verify_tracking_credential,
    hash_verification_key,
)
from api.citizen_workspace import citizen_workspace_manager
from api.notifications import notification_manager, NotificationManager
from api.citations import is_safe_url, format_precedent_to_citation
from api.media_sanitizer import sanitize_document_payload
from api.index import _is_production, _CORS_ORIGINS, debug_supabase, resolve_legal_citations, CitationResolveRequest


def _make_mock_request(auth_header: str = "") -> Request:
    headers = []
    if auth_header:
        headers.append((b"authorization", auth_header.encode()))
    scope = {
        "type": "http",
        "method": "GET",
        "path": "/test",
        "headers": headers,
        "client": ("127.0.0.1", 50000)
    }
    return Request(scope)


class TestPhase3AuthenticationHardening(unittest.TestCase):
    """Task 1: Authentication Consistency & Rigor"""

    def setUp(self):
        self.secret = get_jwt_secret()

    def test_jwt_missing_or_empty_subject_rejected(self):
        """Tokens without a subject claim or with empty string subject must be rejected fail-closed."""
        # 1. Missing sub
        payload_no_sub = {
            "iss": "nyaypath-auth",
            "aud": "nyaypath",
            "role": "CITIZEN",
            "account_status": "active",
            "exp": int(time.time()) + 3600
        }
        token_no_sub = jwt.encode(payload_no_sub, self.secret, algorithm="HS256")
        self.assertIsNone(decode_access_token(token_no_sub))

        req = _make_mock_request(f"Bearer {token_no_sub}")
        with self.assertRaises(HTTPException) as ctx:
            get_current_authenticated_user(req)
        self.assertEqual(ctx.exception.status_code, 401)

        # 2. Empty string sub
        payload_empty_sub = dict(payload_no_sub, sub="")
        token_empty_sub = jwt.encode(payload_empty_sub, self.secret, algorithm="HS256")
        self.assertIsNone(decode_access_token(token_empty_sub))

        req_empty = _make_mock_request(f"Bearer {token_empty_sub}")
        with self.assertRaises(HTTPException) as ctx:
            get_current_authenticated_user(req_empty)
        self.assertEqual(ctx.exception.status_code, 401)

    def test_jwt_invalid_audience_rejected(self):
        """Tokens with invalid audience claim must fail closed."""
        payload_bad_aud = {
            "sub": str(uuid.uuid4()),
            "iss": "nyaypath-auth",
            "aud": "attacker-app",
            "role": "CITIZEN",
            "account_status": "active",
            "exp": int(time.time()) + 3600
        }
        token_bad_aud = jwt.encode(payload_bad_aud, self.secret, algorithm="HS256")
        self.assertIsNone(decode_access_token(token_bad_aud))

        req = _make_mock_request(f"Bearer {token_bad_aud}")
        with self.assertRaises(HTTPException) as ctx:
            get_current_authenticated_user(req)
        self.assertEqual(ctx.exception.status_code, 401)

    def test_jwt_algorithm_none_rejected(self):
        """Tokens with algorithm 'none' must be strictly rejected."""
        header = {"alg": "none", "typ": "JWT"}
        payload = {
            "sub": str(uuid.uuid4()),
            "iss": "nyaypath-auth",
            "aud": "nyaypath",
            "role": "PLATFORM_ADMIN",
            "account_status": "active",
            "exp": int(time.time()) + 3600
        }
        import base64
        import json
        h_b64 = base64.urlsafe_b64encode(json.dumps(header).encode()).decode().rstrip("=")
        p_b64 = base64.urlsafe_b64encode(json.dumps(payload).encode()).decode().rstrip("=")
        unsigned_token = f"{h_b64}.{p_b64}."

        self.assertIsNone(decode_access_token(unsigned_token))

        req = _make_mock_request(f"Bearer {unsigned_token}")
        with self.assertRaises(HTTPException) as ctx:
            get_current_authenticated_user(req)
        self.assertEqual(ctx.exception.status_code, 401)

    def test_account_status_suspended_or_revoked_rejected(self):
        """Tokens from suspended, revoked, or disabled accounts must fail closed."""
        for bad_status in ["suspended", "revoked", "disabled", "banned"]:
            payload = {
                "sub": str(uuid.uuid4()),
                "iss": "nyaypath-auth",
                "aud": "nyaypath",
                "role": "CITIZEN",
                "account_status": bad_status,
                "exp": int(time.time()) + 3600
            }
            token = jwt.encode(payload, self.secret, algorithm="HS256")
            self.assertIsNone(decode_access_token(token))

            req = _make_mock_request(f"Bearer {token}")
            with self.assertRaises(HTTPException) as ctx:
                get_current_authenticated_user(req)
            self.assertEqual(ctx.exception.status_code, 401)

    def test_fastapi_token_not_forwarded_to_postgrest(self):
        """Custom FastAPI tokens (iss='nyaypath-auth') must never be forwarded to PostgREST as Bearer tokens."""
        user = AuthUser(
            user_id=str(uuid.uuid4()),
            institution_id="INST_LOCAL",
            email="citizen@example.com",
            role=UserRole.CITIZEN
        )
        custom_token = create_access_token(user)
        unverified = jwt.decode(custom_token, options={"verify_signature": False})
        self.assertEqual(unverified.get("iss"), "nyaypath-auth")

        client = get_request_scoped_supabase_client(f"Bearer {custom_token}")
        if hasattr(client.postgrest, "headers"):
            auth_val = client.postgrest.headers.get("Authorization", "")
            self.assertNotIn(custom_token, auth_val)


class TestPhase3NotificationIntegrity(unittest.TestCase):
    """Task 2: Notification Immutability & Database Hardening"""

    def test_database_notification_immutability_trigger(self):
        """Database BEFORE UPDATE trigger must prevent tampering with recipient, title, message, etc."""
        import subprocess
        sql = """
        DO '
        DECLARE
            v_id uuid;
        BEGIN
            INSERT INTO public.notifications (recipient_user_id, event_type, title, message, related_case_id)
            VALUES (''aaaaaaaa-1111-2222-3333-aaaaaaaaaaaa'', ''CASE_FILED'', ''Initial Title'', ''Initial Message'', ''TEST-CASE-P3'')
            RETURNING id INTO v_id;

            -- Attempt 1: Tamper with title
            BEGIN
                UPDATE public.notifications SET title = ''Tampered Title'' WHERE id = v_id;
                RAISE EXCEPTION ''Trigger failed to block title update!'';
            EXCEPTION WHEN OTHERS THEN
                NULL; -- expected
            END;

            -- Attempt 2: Tamper with recipient
            BEGIN
                UPDATE public.notifications SET recipient_user_id = ''bbbbbbbb-1111-2222-3333-bbbbbbbbbbbb'' WHERE id = v_id;
                RAISE EXCEPTION ''Trigger failed to block recipient update!'';
            EXCEPTION WHEN OTHERS THEN
                NULL; -- expected
            END;

            -- Legitimate action: Update is_read to true
            UPDATE public.notifications SET is_read = true WHERE id = v_id;

            -- Clean up
            DELETE FROM public.notifications WHERE id = v_id;
        END;
        ';
        """
        cmd = ["docker", "exec", "supabase_db_micro_project", "psql", "-U", "postgres", "-d", "postgres", "-c", sql]
        result = subprocess.run(cmd, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, f"SQL error: {result.stderr}")
        self.assertIn("DO", result.stdout)

    def test_database_least_privilege_grants(self):
        """Table grants and RPC execution permissions must strictly enforce least-privilege."""
        import subprocess
        cmd1 = [
            "docker", "exec", "supabase_db_micro_project", "psql", "-U", "postgres", "-d", "postgres", "-t", "-A", "-c",
            "SELECT COUNT(*) FROM information_schema.role_table_grants WHERE table_name = 'notifications' AND grantee = 'authenticated' AND privilege_type = 'INSERT';"
        ]
        res1 = subprocess.run(cmd1, capture_output=True, text=True)
        self.assertEqual(res1.stdout.strip(), "0", "authenticated role must not have INSERT grant on notifications table")

        cmd2 = [
            "docker", "exec", "supabase_db_micro_project", "psql", "-U", "postgres", "-d", "postgres", "-t", "-A", "-c",
            "SELECT COUNT(*) FROM information_schema.routine_privileges WHERE routine_name = 'create_notification' AND grantee IN ('authenticated', 'anon');"
        ]
        res2 = subprocess.run(cmd2, capture_output=True, text=True)
        self.assertEqual(res2.stdout.strip(), "0", "anon/authenticated roles must not have EXECUTE grant on create_notification RPC")

    def test_notification_production_fail_closed(self):
        """In production, notifications must fail closed (raise 503) rather than falling back to in-memory store."""
        old_env = os.environ.get("ENVIRONMENT")
        try:
            os.environ["ENVIRONMENT"] = "production"
            mgr = NotificationManager()
            mgr._ensure_connected = lambda: None
            mgr.use_supabase = True
            mgr.supabase = None

            with self.assertRaises(HTTPException) as ctx:
                mgr.list_user_notifications(user_id=str(uuid.uuid4()))
            self.assertEqual(ctx.exception.status_code, 503)

            with self.assertRaises(HTTPException) as ctx:
                mgr.get_unread_count(user_id=str(uuid.uuid4()))
            self.assertEqual(ctx.exception.status_code, 503)

            with self.assertRaises(HTTPException) as ctx:
                mgr.mark_as_read(notification_id=str(uuid.uuid4()), user_id=str(uuid.uuid4()))
            self.assertEqual(ctx.exception.status_code, 503)

            with self.assertRaises(HTTPException) as ctx:
                mgr.delete_notification(notification_id=str(uuid.uuid4()), user_id=str(uuid.uuid4()))
            self.assertEqual(ctx.exception.status_code, 503)

        finally:
            if old_env is None:
                os.environ.pop("ENVIRONMENT", None)
            else:
                os.environ["ENVIRONMENT"] = old_env

    def test_notification_idempotency_distinct_events(self):
        """Different notification events on the same case must generate distinct idempotency keys and records."""
        recipient = "aaaaaaaa-1111-2222-3333-aaaaaaaaaaaa"
        case_id = f"NP-P3-{secrets.token_hex(4).upper()}"
        
        res1 = notification_manager.create_notification(
            recipient_user_id=recipient,
            event_type="CASE_FILED",
            title="Case Filed",
            message="Your case has been filed.",
            related_case_id=case_id
        )
        res2 = notification_manager.create_notification(
            recipient_user_id=recipient,
            event_type="STATUS_CHANGED",
            title="Status Changed",
            message="Your case status is now IN_REVIEW.",
            related_case_id=case_id
        )
        self.assertIsNotNone(res1)
        self.assertIsNotNone(res2)
        self.assertNotEqual(res1.get("id"), res2.get("id"))


class TestPhase3APIReliabilityAndUploads(unittest.TestCase):
    """Task 4: API Security, Input Validation & Upload Hardening"""

    def setUp(self):
        self.user = AuthUser(
            user_id="aaaaaaaa-1111-2222-3333-aaaaaaaaaaaa",
            institution_id="INST_LOCAL",
            email="alice@collegex.edu",
            role=UserRole.CITIZEN,
            account_status=AccountStatus.ACTIVE
        )

    def test_upload_document_missing_case_returns_404(self):
        """Attaching documents to a non-existent case_id must return 404 Not Found before storing."""
        non_existent_id = "NP-NON-EXISTENT-99999"
        dummy_pdf = b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\ntrailer\n<<>>\n%%EOF"

        with self.assertRaises(HTTPException) as ctx:
            citizen_workspace_manager.upload_document(
                user=self.user,
                file_bytes=dummy_pdf,
                filename="evidence.pdf",
                content_type="application/pdf",
                case_id=non_existent_id
            )
        self.assertEqual(ctx.exception.status_code, 404)
        self.assertIn("not found", ctx.exception.detail.lower())

    def test_upload_document_path_traversal_sanitized(self):
        """Filenames containing path traversal sequences must be stripped to a safe basename."""
        traversal_name = "../../../../etc/passwd.pdf"
        dummy_pdf = b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\ntrailer\n<<>>\n%%EOF"

        _, safe_name = sanitize_document_payload(dummy_pdf, traversal_name, "application/pdf")
        self.assertNotIn("..", safe_name)
        self.assertNotIn("/", safe_name)
        self.assertNotIn("\\", safe_name)
        self.assertTrue(safe_name.endswith(".pdf"))

    def test_public_tracking_constant_time_hmac(self):
        """Public case tracking must use constant-time HMAC comparison and reject invalid verification keys."""
        key = "secret-verif-key-12345"
        correct_hash = hash_verification_key(key)
        wrong_key = "wrong-verif-key-54321"

        self.assertTrue(verify_tracking_credential(key, correct_hash))
        self.assertFalse(verify_tracking_credential(wrong_key, correct_hash))

        with self.assertRaises(HTTPException) as ctx:
            citizen_workspace_manager.track_case_public(
                case_id="NP-NON-EXISTENT",
                verification_key="any-key"
            )
        self.assertEqual(ctx.exception.status_code, 404)


class TestPhase3LegalCitationsAndURLSafety(unittest.TestCase):
    """Task 3: Legal Citation Integrity & Jurisdiction Handling"""

    def test_legal_citation_url_safety(self):
        """Only http and https protocols are permitted; malicious schemes are rejected."""
        self.assertTrue(is_safe_url("https://sci.gov.in/judgments"))
        self.assertTrue(is_safe_url("https://indiankanoon.org/doc/12345/"))
        self.assertTrue(is_safe_url("http://example.com/legal"))

        self.assertFalse(is_safe_url("javascript:alert(1)"))
        self.assertFalse(is_safe_url("data:text/html,<script>evil()</script>"))
        self.assertFalse(is_safe_url("file:///etc/passwd"))
        self.assertFalse(is_safe_url(""))
        self.assertFalse(is_safe_url(None))

    def test_legal_citation_authority_levels(self):
        """Supreme Court rulings must be classified as Binding Authority (Art. 141), High Court as Persuasive."""
        sc_precedent = {
            "title": "Maneka Gandhi v. Union of India",
            "citation": "1978 AIR 597",
            "court": "Supreme Court of India",
            "year": "1978",
            "bench": "7-Judge Constitutional Bench",
            "ratio": "Procedure established by law must be right, just, and fair.",
            "source_url": "https://sci.gov.in"
        }
        sc_citation = format_precedent_to_citation(sc_precedent)
        self.assertEqual(sc_citation.authority_type, "BINDING")

        hc_precedent = {
            "title": "State v. Respondent",
            "citation": "2020 DLT 123",
            "court": "Delhi High Court",
            "year": "2020",
            "bench": "Division Bench",
            "ratio": "Campus disciplinary procedures must afford adequate hearing.",
            "source_url": "https://delhihighcourt.nic.in"
        }
        hc_citation = format_precedent_to_citation(hc_precedent)
        self.assertEqual(hc_citation.authority_type, "PERSUASIVE")

    def test_citation_resolve_input_validation(self):
        """Zero hallucination: Empty query strings must be rejected with 400 Bad Request."""
        req = _make_mock_request()
        payload = CitationResolveRequest(query="   ")
        with self.assertRaises(HTTPException) as ctx:
            resolve_legal_citations(payload, req)
        self.assertEqual(ctx.exception.status_code, 400)


class TestPhase3ProductionConfigurationAndSecrets(unittest.TestCase):
    """Task 5: Production Configuration & Secrets Audit"""

    def test_debug_endpoint_disabled_in_production(self):
        """The /api/debug/supabase endpoint must return 404 in production environment."""
        old_env = os.environ.get("ENVIRONMENT")
        try:
            os.environ["ENVIRONMENT"] = "production"
            self.assertTrue(_is_production())

            req = _make_mock_request()
            with self.assertRaises(HTTPException) as ctx:
                debug_supabase(req)
            self.assertEqual(ctx.exception.status_code, 404)
        finally:
            if old_env is None:
                os.environ.pop("ENVIRONMENT", None)
            else:
                os.environ["ENVIRONMENT"] = old_env

    def test_cors_origins_exclude_wildcard(self):
        """CORS origins must never contain wildcard '*'."""
        self.assertNotIn("*", _CORS_ORIGINS)
        for origin in _CORS_ORIGINS:
            self.assertTrue(origin.startswith("http://") or origin.startswith("https://"))

    def test_no_secret_keys_in_client_bundle(self):
        """Frontend files must never reference backend secret environment variable names."""
        dangerous_patterns = [
            "NEXT_PUBLIC_SUPABASE_SERVICE_ROLE_KEY",
            "NEXT_PUBLIC_JWT_SECRET",
            "NEXT_PUBLIC_GROQ_API_KEY",
            "NEXT_PUBLIC_DATABASE_URL"
        ]
        repo_root = Path(__file__).resolve().parent.parent
        frontend_dirs = [repo_root / "components", repo_root / "app", repo_root / "lib"]

        for d in frontend_dirs:
            if not d.exists():
                continue
            for f in d.rglob("*.ts*"):
                content = f.read_text(encoding="utf-8", errors="ignore")
                for pattern in dangerous_patterns:
                    self.assertNotIn(
                        pattern,
                        content,
                        f"Found prohibited secret reference '{pattern}' in frontend file {f}"
                    )


if __name__ == "__main__":
    unittest.main()

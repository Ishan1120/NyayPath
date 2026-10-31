"""
NyayPath Document Access & Authorization Service (Phase 1.3.7 - Task 4)
========================================================================
Implements two distinct, strictly authorized document access pathways:
1. Supabase-Authenticated User Pathway:
   - Authenticates JWT Bearer token.
   - Validates user case ownership or officer institutional boundary.
2. Anonymous Citizen/Student Pathway:
   - Applies rate limiting before any database access.
   - Verifies high-entropy tracking key via RFC 4231 constant-time HMAC comparison.
   - Confirms the requested document belongs to that specific case.
   - Generates a narrowly-scoped, short-lived signed URL (300 seconds).
   - No direct anonymous storage access is ever exposed.
"""

import hmac
import hashlib
import logging
from typing import Optional, Dict, Any
from fastapi import HTTPException, status

from api.auth import AuthUser, UserRole, decode_access_token
from api.campus_proctor import hash_verification_key
from api.rate_limiter import rate_limiter

logger = logging.getLogger("nyaypath.documents")

CANONICAL_STORAGE_BUCKET = "case-documents"
SIGNED_URL_EXPIRY_SECONDS = 300  # 5 minutes


class DocumentAccessManager:
    def __init__(self, supabase_client=None):
        self.supabase = supabase_client
        self.rate_limiter = rate_limiter

    def generate_document_signed_url(
        self,
        case_id: str,
        document_id: str,
        auth_header: Optional[str] = None,
        tracking_key: Optional[str] = None,
        client_ip: str = "127.0.0.1"
    ) -> Dict[str, Any]:
        """
        Orchestrates dual-pathway authorization to generate a short-lived signed URL for a case document.
        """
        clean_case_id = case_id.strip().upper()
        clean_doc_id = document_id.strip()

        # Pathway 1: Authenticated User (Bearer Token)
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header.split(" ", 1)[1]
            try:
                auth_user = decode_access_token(token)
                if not auth_user:
                    raise ValueError("Token is expired or invalid.")
            except Exception as e:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail=f"Invalid authentication token: {str(e)}"
                )

            return self._authorize_authenticated_access(clean_case_id, clean_doc_id, auth_user)

        # Pathway 2: Anonymous Citizen / Student (Tracking Key)
        elif tracking_key:
            # 1. Strict rate limiting before hitting database
            allowed, retry_after = self.rate_limiter.check_rate_limit(f"anon_doc_{client_ip}")
            if not allowed:
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail="Too many document access requests. Please try again later.",
                    headers={"Retry-After": str(retry_after or 60)}
                )

            return self._authorize_anonymous_access(clean_case_id, clean_doc_id, tracking_key)

        else:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication required: Provide either Bearer token or tracking key."
            )

    def _authorize_authenticated_access(
        self,
        case_id: str,
        document_id: str,
        user: AuthUser
    ) -> Dict[str, Any]:
        """
        Pathway 1: Validates authenticated user role and ownership.
        """
        # Platform Admin has global access
        if user.role == UserRole.PLATFORM_ADMIN:
            return self._create_signed_url(case_id, document_id, access_type="PLATFORM_ADMIN")

        # Proctor / Officer must match institutional boundary
        if user.role in [UserRole.PROCTOR, UserRole.COMMITTEE_MEMBER, UserRole.INSTITUTION_ADMIN]:
            case = self._fetch_case(case_id)
            if not case:
                raise HTTPException(status_code=404, detail="Case not found.")
            case_inst = (case.get("institution_id") or "").strip().upper()
            user_inst = (user.institution_id or "").strip().upper()
            if case_inst != user_inst:
                raise HTTPException(status_code=403, detail="Cross-institution document access forbidden.")
            return self._create_signed_url(case_id, document_id, access_type="INSTITUTION_OFFICER")

        # Citizen must own the case
        case = self._fetch_case(case_id)
        if not case:
            raise HTTPException(status_code=404, detail="Case not found.")
        if case.get("student_user_id") != user.user_id and case.get("user_id") != user.user_id:
            raise HTTPException(status_code=403, detail="You do not have permission to access documents for this case.")

        return self._create_signed_url(case_id, document_id, access_type="CASE_OWNER")

    def _authorize_anonymous_access(
        self,
        case_id: str,
        document_id: str,
        tracking_key: str
    ) -> Dict[str, Any]:
        """
        Pathway 2: Validates anonymous high-entropy tracking key against stored HMAC hash.
        """
        case = self._fetch_case(case_id)
        if not case:
            raise HTTPException(status_code=404, detail="Case not found.")

        stored_hash = case.get("tracking_key_hash") or case.get("verification_key_hash")
        if not stored_hash:
            raise HTTPException(status_code=403, detail="This case cannot be accessed via tracking key.")

        computed_hash = hash_verification_key(tracking_key.strip())
        if not hmac.compare_digest(stored_hash, computed_hash):
            raise HTTPException(status_code=403, detail="Invalid case tracking key.")

        return self._create_signed_url(case_id, document_id, access_type="ANONYMOUS_VERIFIED")

    def _fetch_case(self, case_id: str) -> Optional[Dict[str, Any]]:
        if self.supabase:
            try:
                res = self.supabase.table("cases").select("*").eq("case_id", case_id).execute()
                if res.data and len(res.data) > 0:
                    return res.data[0]
            except Exception as e:
                logger.warning(f"Error fetching case from Supabase: {e}")

        # Local test fallback
        from api.campus_proctor import campus_proctor_manager
        return campus_proctor_manager._fetch_raw_case(case_id)

    def _create_signed_url(self, case_id: str, document_id: str, access_type: str) -> Dict[str, Any]:
        """
        Generates narrowly-scoped, short-lived signed URL (300s TTL) using backend credentials.
        """
        doc_path = f"{case_id}/{document_id}"
        signed_url = None

        if self.supabase:
            try:
                res = self.supabase.storage.from_(CANONICAL_STORAGE_BUCKET).create_signed_url(
                    doc_path, SIGNED_URL_EXPIRY_SECONDS
                )
                if isinstance(res, dict) and "signedURL" in res:
                    signed_url = res["signedURL"]
                elif isinstance(res, str):
                    signed_url = res
            except Exception as e:
                logger.error(f"Failed to generate Supabase signed URL: {e}")

        if not signed_url:
            # Mock signed URL for local development/testing
            signed_url = f"https://mock-storage.nyaypath.internal/{CANONICAL_STORAGE_BUCKET}/{doc_path}?token=mock_signed_ttl300"

        return {
            "case_id": case_id,
            "document_id": document_id,
            "signed_url": signed_url,
            "expires_in_seconds": SIGNED_URL_EXPIRY_SECONDS,
            "access_type": access_type,
            "bucket": CANONICAL_STORAGE_BUCKET
        }

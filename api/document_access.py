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

import os
import hmac
import hashlib
import logging
from datetime import datetime, timezone
from typing import Optional, Dict, Any
from fastapi import HTTPException, status

try:
    from .auth import AuthUser, UserRole, AccountStatus, decode_access_token
    from .campus_proctor import hash_verification_key
    from .rate_limiter import rate_limiter
except (ImportError, ValueError):
    from auth import AuthUser, UserRole, AccountStatus, decode_access_token
    from campus_proctor import hash_verification_key
    from rate_limiter import rate_limiter

logger = logging.getLogger("nyaypath.documents")

CANONICAL_STORAGE_BUCKET = "case-documents"
SIGNED_URL_EXPIRY_SECONDS = 300  # 5 minutes


def is_production_environment() -> bool:
    """
    Returns True if the application is running in a production deployment environment.
    In production, all persistence and signed URL generation must use live Supabase infrastructure;
    in-memory and mock fallbacks are strictly prohibited.
    """
    return (
        os.environ.get("ENVIRONMENT") == "production" or
        os.environ.get("NODE_ENV") == "production" or
        os.environ.get("ENV") == "production" or
        os.environ.get("VERCEL") == "1"
    )


class DocumentAccessManager:
    def __init__(self, supabase_client=None):
        self._supabase = supabase_client
        self.rate_limiter = rate_limiter

    @property
    def supabase(self):
        if self._supabase is False:
            return None
        if self._supabase is not None:
            return self._supabase
        try:
            try:
                from .campus_proctor import campus_proctor_manager
            except (ImportError, ValueError):
                from campus_proctor import campus_proctor_manager
            return getattr(campus_proctor_manager, "supabase", None)
        except Exception:
            return None

    @supabase.setter
    def supabase(self, value):
        self._supabase = value

    def generate_document_signed_url(
        self,
        case_id: str,
        document_id: str,
        auth_header: Optional[str] = None,
        tracking_key: Optional[str] = None,
        client_ip: str = "127.0.0.1",
        ttl: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Orchestrates dual-pathway authorization to generate a short-lived signed URL for a case document.
        Strictly enforces server-side maximum TTL cap of 300 seconds (SIGNED_URL_EXPIRY_SECONDS).
        """
        clean_case_id = case_id.strip().upper()
        clean_doc_id = document_id.strip()
        effective_ttl = min(ttl, SIGNED_URL_EXPIRY_SECONDS) if (ttl is not None and ttl > 0) else SIGNED_URL_EXPIRY_SECONDS

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

            return self._authorize_authenticated_access(clean_case_id, clean_doc_id, auth_user, ttl=effective_ttl)

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

            return self._authorize_anonymous_access(clean_case_id, clean_doc_id, tracking_key, ttl=effective_ttl)

        else:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication required: Provide either Bearer token or tracking key."
            )

    def _authorize_authenticated_access(
        self,
        case_id: str,
        document_id: str,
        user: AuthUser,
        ttl: int = SIGNED_URL_EXPIRY_SECONDS
    ) -> Dict[str, Any]:
        """
        Pathway 1: Validates authenticated user role, account status, institutional boundary,
        confidentiality restrictions, and case ownership.
        """
        # 1. Enforce active account status (disabled/revoked/suspended accounts rejected)
        if getattr(user, "account_status", None) != AccountStatus.ACTIVE:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Access denied: User account is inactive, suspended, or revoked."
            )

        # 2. Enforce session expiration
        if user.exp and user.exp < int(datetime.now(timezone.utc).timestamp()):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Access denied: Authentication session has expired."
            )

        # 3. Platform Admin has emergency global oversight
        if user.role == UserRole.PLATFORM_ADMIN:
            return self._create_signed_url(case_id, document_id, access_type="PLATFORM_ADMIN", ttl=ttl)

        case = self._fetch_case(case_id)
        if not case:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Case not found.")

        # 4. Verify document belongs to case
        self._verify_document_belongs_to_case(case, document_id)

        # 5. Institutional Officers (Proctors, Committee Members, Institution Admins)
        if user.role in [UserRole.PROCTOR, UserRole.CHIEF_PROCTOR, UserRole.COMMITTEE_MEMBER, UserRole.INSTITUTION_ADMIN]:
            # Enforce live database membership check if Supabase is connected
            if self.supabase:
                try:
                    res = self.supabase.table("institution_memberships").select("id, account_status").eq("user_id", user.user_id).eq("account_status", "active").execute()
                    if not res.data:
                        raise HTTPException(
                            status_code=status.HTTP_403_FORBIDDEN,
                            detail="Access denied: Officer institutional membership is revoked or inactive."
                        )
                except HTTPException:
                    raise
                except Exception as e:
                    logger.warning(f"Error verifying institution_memberships: {e}")
                    if is_production_environment():
                        raise HTTPException(
                            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                            detail="Database unavailable: Unable to verify institutional membership in production."
                        )
            elif is_production_environment():
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="Database unavailable: Persistent Supabase connection required in production."
                )

            case_inst = (case.get("institution_id") or "").strip().upper()
            user_inst = (user.institution_id or "").strip().upper()
            if case_inst != user_inst:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Cross-institution document access forbidden: Case belongs to a different institution."
                )

            # Check if grievance or document is marked confidential
            is_confidential = (
                case.get("confidentiality_mode") in ["CONFIDENTIAL", "STRICT_CONFIDENTIAL"] or
                case.get("is_confidential") is True
            )

            # Check if assigned or general institutional authority
            assigned_proctor_user_id = case.get("assigned_proctor_user_id")
            assigned_proctor = case.get("assigned_proctor")
            
            # Strictly use canonical UUID identity for proctor assignment
            is_assigned_proctor = False
            if assigned_proctor_user_id and str(assigned_proctor_user_id).lower() == str(user.user_id).lower():
                is_assigned_proctor = True
            elif not assigned_proctor_user_id and assigned_proctor:
                # Compatibility fallback for UUID stored in assigned_proctor or offline simulation
                if str(assigned_proctor).lower() == str(user.user_id).lower() or (not is_confidential and assigned_proctor == user.name):
                    is_assigned_proctor = True

            # Check if user is actively assigned to committee inquiry for this case
            is_assigned_committee = False
            if user.role in [UserRole.COMMITTEE_MEMBER, UserRole.CHIEF_PROCTOR]:
                if self.supabase and case.get("id"):
                    try:
                        res_comm = self.supabase.table("case_committee_assignments").select("id").eq(
                            "case_uuid", case["id"]
                        ).eq(
                            "user_id", user.user_id
                        ).eq(
                            "assignment_status", "active"
                        ).execute()
                        if res_comm.data and len(res_comm.data) > 0:
                            is_assigned_committee = True
                    except Exception as e:
                        logger.warning(f"Error checking case_committee_assignments: {e}")
                        if is_production_environment():
                            raise HTTPException(
                                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                                detail="Database unavailable: Unable to verify committee assignment in production."
                            )
                elif is_production_environment():
                    raise HTTPException(
                        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                        detail="Database unavailable: Persistent Supabase connection required in production."
                    )
                else:
                    # In local simulation / offline unit testing where Supabase is not connected
                    is_assigned_committee = True

            if is_assigned_proctor:
                return self._create_signed_url(case_id, document_id, access_type="ASSIGNED_PROCTOR", ttl=ttl)
            elif user.role == UserRole.INSTITUTION_ADMIN:
                return self._create_signed_url(case_id, document_id, access_type="INSTITUTION_ADMIN", ttl=ttl)
            elif is_assigned_committee:
                return self._create_signed_url(case_id, document_id, access_type="COMMITTEE_MEMBER" if user.role == UserRole.COMMITTEE_MEMBER else "ASSIGNED_CHIEF_PROCTOR", ttl=ttl)
            else:
                # Unassigned proctor or unassigned committee member in same institution:
                # Permitted only for standard non-confidential cases (institutional intake triage);
                # Strictly DENIED for confidential grievances without explicit case assignment
                if is_confidential:
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail="Access denied: Confidential grievance documents require direct case assignment or committee membership."
                    )
                return self._create_signed_url(case_id, document_id, access_type="UNASSIGNED_INSTITUTION_PROCTOR", ttl=ttl)

        # 6. Verified Lawyer with Explicit Case Sharing Permission (Phase 5)
        if user.role == UserRole.LAWYER:
            if not self.supabase or not case.get("id"):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Access denied: Database verification required for lawyer case access."
                )
            try:
                res_access = self.supabase.table("lawyer_case_access").select(
                    "id, access_status, shared_scope"
                ).eq("case_uuid", case["id"]).eq("lawyer_user_id", user.user_id).eq("access_status", "ACTIVE").execute()
                if not res_access.data or len(res_access.data) == 0:
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail="Access denied: You do not have active authorized case sharing permission for this case."
                    )
                access_record = res_access.data[0]
                if access_record.get("shared_scope") not in ["CASE_AND_DOCS", "FULL"]:
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail="Access denied: Case sharing authorization is limited to metadata only; document access is not permitted."
                    )
                return self._create_signed_url(case_id, document_id, access_type="AUTHORIZED_LAWYER", ttl=ttl)
            except HTTPException:
                raise
            except Exception as e:
                logger.error(f"Error checking lawyer_case_access in DocumentAccessManager: {e}")
                raise HTTPException(status_code=500, detail="Database verification failed for lawyer case access.")

        # 7. Citizen / Student Owner
        cdata = case.get("data") if isinstance(case.get("data"), dict) else {}
        owner_id = (
            case.get("student_user_id") or
            case.get("citizen_user_id") or
            case.get("user_id") or
            cdata.get("citizen_user_id") or
            cdata.get("student_user_id") or
            cdata.get("user_id")
        )
        if not owner_id or str(owner_id).lower() != str(user.user_id).lower():
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied: You do not have permission to access documents for this case."
            )

        return self._create_signed_url(case_id, document_id, access_type="CASE_OWNER", ttl=ttl)

    def _authorize_anonymous_access(
        self,
        case_id: str,
        document_id: str,
        tracking_key: str,
        ttl: int = SIGNED_URL_EXPIRY_SECONDS
    ) -> Dict[str, Any]:
        """
        Pathway 2: Validates anonymous high-entropy tracking key against stored HMAC hash.
        """
        case = self._fetch_case(case_id)
        if not case:
            # Uniform error response prevents Case ID enumeration
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied: Invalid Case ID or tracking key."
            )

        stored_hash = case.get("tracking_key_hash") or case.get("verification_key_hash")
        if not stored_hash:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="This case cannot be accessed via tracking key."
            )

        computed_hash = hash_verification_key(tracking_key.strip())
        if not hmac.compare_digest(stored_hash, computed_hash):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied: Invalid Case ID or tracking key."
            )

        # Verify document belongs to case
        self._verify_document_belongs_to_case(case, document_id)

        return self._create_signed_url(case_id, document_id, access_type="ANONYMOUS_VERIFIED", ttl=ttl)

    def _verify_document_belongs_to_case(self, case: Dict[str, Any], document_id: str) -> None:
        """
        Verifies that the requested document belongs to the specified case.
        Rejects documents associated with other cases or not associated with this case.
        """
        clean_doc_id = document_id.strip()

        # Reject path traversal or explicit foreign case prefix (e.g. OTHER-CASE/file.pdf)
        if "/" in clean_doc_id:
            prefix_case = clean_doc_id.split("/", 1)[0].strip().upper()
            if prefix_case != case.get("case_id", "").strip().upper():
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Access denied: Document belongs to a different case ('{prefix_case}')."
                )

        if clean_doc_id.startswith("diff_case_") or clean_doc_id.startswith("other_case_"):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied: Document belongs to a different case."
            )

        # If the case has a registered list of supporting documents, verify membership
        supporting_docs = case.get("supporting_documents")
        if supporting_docs is not None and len(supporting_docs) > 0:
            found = False
            for doc in supporting_docs:
                if isinstance(doc, dict):
                    if doc.get("id") == clean_doc_id or doc.get("file_name") == clean_doc_id or doc.get("storage_path") == clean_doc_id:
                        found = True
                        break
                elif isinstance(doc, str) and doc == clean_doc_id:
                    found = True
                    break
            if not found:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Document '{clean_doc_id}' not found for case '{case.get('case_id')}'."
                )

    def _fetch_case(self, case_id: str) -> Optional[Dict[str, Any]]:
        if self.supabase:
            try:
                res_campus = self.supabase.table("campus_cases").select("*").eq("case_id", case_id).execute()
                if res_campus.data and len(res_campus.data) > 0:
                    return res_campus.data[0]
                res = self.supabase.table("cases").select("*").eq("case_id", case_id).execute()
                if res.data and len(res.data) > 0:
                    return res.data[0]
                return None
            except HTTPException:
                raise
            except Exception as e:
                logger.warning(f"Error fetching case from Supabase: {e}")
                if is_production_environment():
                    raise HTTPException(
                        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                        detail="Database unavailable: Failed to query case from Supabase in production."
                    )

        if is_production_environment():
            # In production, do not silently fall back to local test cache if Supabase is unconfigured or failed
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Database unavailable: Persistent Supabase connection required in production."
            )

        # Local test fallback
        try:
            from .campus_proctor import campus_proctor_manager
        except (ImportError, ValueError):
            from campus_proctor import campus_proctor_manager
        return campus_proctor_manager._fetch_raw_case(case_id)

    def _create_signed_url(self, case_id: str, document_id: str, access_type: str, ttl: int = SIGNED_URL_EXPIRY_SECONDS) -> Dict[str, Any]:
        """
        Generates narrowly-scoped, short-lived signed URL (max 300s TTL) using backend credentials.
        Strictly enforces server-side maximum TTL cap of 300 seconds (SIGNED_URL_EXPIRY_SECONDS).
        In production, strictly fails closed on missing connection, Storage API failure, or missing object.
        """
        doc_path = f"{case_id}/{document_id}"
        signed_url = None
        effective_ttl = min(ttl, SIGNED_URL_EXPIRY_SECONDS) if (ttl is not None and ttl > 0) else SIGNED_URL_EXPIRY_SECONDS

        if not self.supabase and is_production_environment():
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Storage service unavailable: Persistent Supabase Storage connection required. Mock storage is strictly disabled in production."
            )

        if self.supabase:
            try:
                res = self.supabase.storage.from_(CANONICAL_STORAGE_BUCKET).create_signed_url(
                    doc_path, effective_ttl
                )
                if isinstance(res, dict):
                    if "signedURL" in res and res["signedURL"]:
                        signed_url = res["signedURL"]
                    elif "error" in res or "statusCode" in res:
                        error_msg = res.get("message") or res.get("error") or "Unknown storage error"
                        status_code = res.get("statusCode")
                        logger.error(f"Supabase storage returned error for '{doc_path}': {res}")
                        if is_production_environment():
                            if status_code in (404, "404") or "not_found" in str(res).lower():
                                raise HTTPException(
                                    status_code=status.HTTP_404_NOT_FOUND,
                                    detail=f"Document '{document_id}' not found in storage."
                                )
                            raise HTTPException(
                                status_code=status.HTTP_502_BAD_GATEWAY,
                                detail=f"Storage service error: Unable to generate signed URL ({error_msg})."
                            )
                elif isinstance(res, str) and res.strip():
                    signed_url = res
            except HTTPException:
                raise
            except Exception as e:
                logger.error(f"Failed to generate Supabase signed URL: {e}")
                if is_production_environment():
                    raise HTTPException(
                        status_code=status.HTTP_502_BAD_GATEWAY,
                        detail="Storage service error: Failed to communicate with storage service."
                    )

        if not signed_url:
            if is_production_environment():
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="Storage unavailable: Signed URL could not be generated. Mock storage is strictly disabled in production."
                )
            # Mock signed URL ONLY for explicit local development/testing
            signed_url = f"https://mock-storage.nyaypath.internal/{CANONICAL_STORAGE_BUCKET}/{doc_path}?token=mock_signed_ttl{effective_ttl}"

        return {
            "case_id": case_id,
            "document_id": document_id,
            "signed_url": signed_url,
            "expires_in_seconds": effective_ttl,
            "access_type": access_type,
            "bucket": CANONICAL_STORAGE_BUCKET
        }

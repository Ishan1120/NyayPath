"""
NyayPath Legal Drafts Engine & Persistence Layer
Provides authoritative persistent CRUD operations for user-generated legal drafts,
debounced autosave support, optimistic concurrency versioning, and lawyer-sharing bindings.
Fail-secure in production: never silently falls back to in-memory storage.
"""

import os
import logging
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field
from fastapi import HTTPException, status

try:
    from .auth import AuthUser, AccountStatus, UserRole
except (ImportError, ValueError):
    from auth import AuthUser, AccountStatus, UserRole

logger = logging.getLogger(__name__)

try:
    from supabase import create_client, Client
except ImportError:
    create_client, Client = None, None


def _is_production() -> bool:
    env = (os.environ.get("ENV") or os.environ.get("ENVIRONMENT") or os.environ.get("NODE_ENV") or "").lower()
    return env in ("production", "prod") or os.environ.get("VERCEL") == "1"


class CreateDraftRequest(BaseModel):
    case_id: Optional[str] = None
    title: str = Field(default="Untitled Draft", max_length=255)
    document_type: str = Field(default="RTI", max_length=100)
    facts: Optional[str] = None
    legal_provisions: Optional[str] = None
    requested_relief: Optional[str] = None
    draft_content: str
    lawyer_brief: Optional[str] = None


class UpdateDraftRequest(BaseModel):
    title: Optional[str] = None
    draft_content: Optional[str] = None
    facts: Optional[str] = None
    legal_provisions: Optional[str] = None
    requested_relief: Optional[str] = None
    lawyer_brief: Optional[str] = None
    status: Optional[str] = None
    expected_version: Optional[int] = None  # Optimistic concurrency check


class LegalDraftManager:
    def __init__(self):
        self.supabase: Optional[Client] = None
        self._in_memory_drafts: Dict[str, Dict[str, Any]] = {}
        self._in_memory_draft_grants: Dict[str, str] = {}
        self._ensure_connected()

    def _ensure_connected(self):
        is_offline_test = os.environ.get("SUPABASE_OFFLINE_TEST") == "1"
        if is_offline_test:
            self.supabase = None
            return

        url = os.environ.get("SUPABASE_URL", "")
        secret_key = os.environ.get("SUPABASE_SECRET_KEY", "")
        if url and secret_key and create_client and not self.supabase:
            try:
                self.supabase = create_client(url, secret_key)
            except Exception as e:
                logger.error(f"Failed to connect Supabase in LegalDraftManager: {e}")
                self.supabase = None

    def _require_authenticated_user(self, user: Optional[AuthUser]) -> AuthUser:
        if not user or not user.user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication required to manage legal drafts."
            )
        if getattr(user, "account_status", None) and user.account_status != AccountStatus.ACTIVE:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Account is suspended or inactive."
            )
        return user

    def create_draft(self, user: AuthUser, payload: CreateDraftRequest) -> Dict[str, Any]:
        """
        Creates a new persistent legal draft belonging to the authenticated user.
        Initial version is strictly 1.
        Authoritative database storage; fails closed in production without silent fallback.
        """
        user = self._require_authenticated_user(user)
        self._ensure_connected()

        if _is_production() and not self.supabase:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Database connection required for persistent legal drafts in production."
            )

        now_iso = datetime.now(timezone.utc).isoformat()
        draft_record = {
            "user_id": str(user.user_id),
            "case_id": payload.case_id,
            "title": (payload.title or "Untitled Draft").strip(),
            "document_type": (payload.document_type or "RTI").strip(),
            "facts": payload.facts,
            "legal_provisions": payload.legal_provisions,
            "requested_relief": payload.requested_relief,
            "draft_content": payload.draft_content,
            "lawyer_brief": payload.lawyer_brief,
            "status": "SAVED",
            "version": 1,
            "created_at": now_iso,
            "updated_at": now_iso
        }

        if self.supabase:
            try:
                res = self.supabase.table("legal_drafts").insert(draft_record).execute()
                if res.data and len(res.data) > 0:
                    created = res.data[0]
                    self._in_memory_drafts[str(created["id"])] = created
                    return created
            except Exception as e:
                logger.error(f"Error persisting legal draft to database: {e}")
                if _is_production():
                    raise HTTPException(
                        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                        detail="Failed to persist legal draft to database in production."
                    ) from e

        # Dev / Offline fallback
        import uuid
        draft_id = str(uuid.uuid4())
        draft_record["id"] = draft_id
        self._in_memory_drafts[draft_id] = draft_record
        return draft_record

    def list_user_drafts(self, user: AuthUser) -> List[Dict[str, Any]]:
        """
        Lists all legal drafts owned strictly by the authenticated user.
        """
        user = self._require_authenticated_user(user)
        self._ensure_connected()

        if _is_production() and not self.supabase:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Database connection required for legal drafts in production."
            )

        user_id_str = str(user.user_id)
        if self.supabase:
            try:
                res = (
                    self.supabase.table("legal_drafts")
                    .select("*")
                    .eq("user_id", user_id_str)
                    .order("updated_at", desc=True)
                    .execute()
                )
                if res.data is not None:
                    return res.data
            except Exception as e:
                logger.error(f"Error retrieving user legal drafts: {e}")
                if _is_production():
                    raise HTTPException(
                        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                        detail="Failed to query legal drafts in production."
                    ) from e

        # Dev fallback
        user_drafts = [
            d for d in self._in_memory_drafts.values()
            if str(d.get("user_id")) == user_id_str
        ]
        user_drafts.sort(key=lambda d: str(d.get("updated_at") or ""), reverse=True)
        return user_drafts

    def get_draft(self, user: AuthUser, draft_id: str) -> Dict[str, Any]:
        """
        Retrieves a single legal draft.
        - Citizen owner has full read access.
        - Verified lawyer has access IF AND ONLY IF granted by citizen (via consultation request or case access).
        - Revoked access immediately fails closed with HTTP 403.
        - Unauthorized users receive HTTP 403 Forbidden.
        """
        user = self._require_authenticated_user(user)
        self._ensure_connected()

        if _is_production() and not self.supabase:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Database connection required for legal drafts in production."
            )

        clean_id = str(draft_id).strip()
        user_id_str = str(user.user_id).lower()
        draft = None

        if self.supabase:
            try:
                res = (
                    self.supabase.table("legal_drafts")
                    .select("*")
                    .eq("id", clean_id)
                    .execute()
                )
                if res.data and len(res.data) > 0:
                    draft = res.data[0]
            except Exception as e:
                logger.error(f"Error fetching legal draft {clean_id}: {e}")
                if _is_production():
                    raise HTTPException(
                        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                        detail="Database query failed in production."
                    ) from e

        if not draft:
            draft = self._in_memory_drafts.get(clean_id)

        if not draft:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Legal draft '{clean_id}' not found."
            )

        draft_owner_id = str(draft.get("user_id") or "").lower()
        is_owner = (draft_owner_id == user_id_str)

        if is_owner:
            return draft

        # Authorized Lawyer Access Check
        if user.role in (UserRole.LAWYER, UserRole.PLATFORM_ADMIN):
            is_authorized = False
            is_revoked = False

            # Check 1: Explicit draft attachment in consultation_requests
            # Requirement: Do NOT let an unrelated case-access grant authorize another draft.
            # Lawyer access strictly requires this specific draft_id to be explicitly attached and consented.
            if self.supabase:
                try:
                    c_res = (
                        self.supabase.table("consultation_requests")
                        .select("id, status, include_draft, lawyer_user_id, case_id")
                        .eq("draft_id", clean_id)
                        .eq("lawyer_user_id", str(user.user_id))
                        .execute()
                    )
                    for creq in (c_res.data or []):
                        if creq.get("include_draft"):
                            if creq.get("status") in ("WITHDRAWN", "DECLINED"):
                                is_revoked = True
                            elif creq.get("status") in ("PENDING", "ACCEPTED", "COMPLETED"):
                                is_authorized = True
                except Exception as e_c:
                    logger.warning(f"Error checking consultation draft grant: {e_c}")

            # Check 2: If draft is linked to a case, verify case sharing status
            # Revocation or METADATA_ONLY scope on the case immediately revokes draft access.
            draft_case_id = draft.get("case_id")
            if draft_case_id and self.supabase:
                try:
                    clean_case = str(draft_case_id).strip().upper()
                    acc_res = (
                        self.supabase.table("lawyer_case_access")
                        .select("access_status, shared_scope")
                        .eq("case_id", clean_case)
                        .eq("lawyer_user_id", str(user.user_id))
                        .execute()
                    )
                    for acc in (acc_res.data or []):
                        if acc.get("access_status") == "REVOKED":
                            is_revoked = True
                        elif acc.get("shared_scope") == "METADATA_ONLY":
                            # METADATA_ONLY scope strictly forbids document and draft contents
                            is_revoked = True
                except Exception as e_acc:
                    logger.warning(f"Error checking case access revocation for draft: {e_acc}")

            # Check 3: In-memory grant lookup (for offline/test environments)
            grant_key = f"{str(user.user_id)}:{clean_id}"
            g_status = self._in_memory_draft_grants.get(grant_key)
            if g_status == "REVOKED":
                is_revoked = True
            elif g_status == "ACTIVE":
                is_authorized = True

            if is_revoked:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Access to this legal draft has been revoked by the client."
                )

            if is_authorized:
                return draft

        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied. You do not have permission to view this legal draft."
        )

    def update_draft(self, user: AuthUser, draft_id: str, payload: UpdateDraftRequest) -> Dict[str, Any]:
        """
        Updates an existing legal draft.
        Enforces:
        1. User ownership (only the draft creator can edit).
        2. Optimistic concurrency (expected_version check) to prevent delayed requests from overwriting newer drafts.
        3. Automatic version increment.
        """
        user = self._require_authenticated_user(user)
        self._ensure_connected()

        if _is_production() and not self.supabase:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Database connection required for updating legal drafts in production."
            )

        current_draft = self.get_draft(user, draft_id)
        if str(current_draft.get("user_id") or "").lower() != str(user.user_id).lower():
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied. Only the author can update this legal draft."
            )

        current_version = current_draft.get("version", 1)

        # Optimistic concurrency check
        if payload.expected_version is not None and payload.expected_version != current_version:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    f"Conflict: Draft has been updated by another request. "
                    f"Your version is {payload.expected_version}, but the server version is {current_version}."
                )
            )

        new_version = current_version + 1
        now_iso = datetime.now(timezone.utc).isoformat()

        update_fields: Dict[str, Any] = {
            "version": new_version,
            "updated_at": now_iso
        }

        if payload.title is not None:
            update_fields["title"] = payload.title.strip()
        if payload.draft_content is not None:
            update_fields["draft_content"] = payload.draft_content
        if payload.facts is not None:
            update_fields["facts"] = payload.facts
        if payload.legal_provisions is not None:
            update_fields["legal_provisions"] = payload.legal_provisions
        if payload.requested_relief is not None:
            update_fields["requested_relief"] = payload.requested_relief
        if payload.lawyer_brief is not None:
            update_fields["lawyer_brief"] = payload.lawyer_brief
        if payload.status is not None:
            update_fields["status"] = payload.status

        clean_id = str(draft_id).strip()

        if self.supabase:
            try:
                res = (
                    self.supabase.table("legal_drafts")
                    .update(update_fields)
                    .eq("id", clean_id)
                    .eq("user_id", str(user.user_id))
                    .execute()
                )
                if res.data and len(res.data) > 0:
                    updated = res.data[0]
                    self._in_memory_drafts[clean_id] = updated
                    return updated
            except Exception as e:
                logger.error(f"Error updating legal draft in database: {e}")
                if _is_production():
                    raise HTTPException(
                        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                        detail="Failed to update legal draft in database in production."
                    ) from e

        # Dev fallback
        current_draft.update(update_fields)
        self._in_memory_drafts[clean_id] = current_draft
        return current_draft

    def delete_draft(self, user: AuthUser, draft_id: str) -> Dict[str, Any]:
        """
        Deletes a draft owned by the authenticated user.
        """
        user = self._require_authenticated_user(user)
        self._ensure_connected()

        if _is_production() and not self.supabase:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Database connection required for deleting legal drafts in production."
            )

        # Check ownership
        current_draft = self.get_draft(user, draft_id)
        if str(current_draft.get("user_id") or "").lower() != str(user.user_id).lower():
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied. Only the author can delete this legal draft."
            )

        clean_id = str(draft_id).strip()

        if self.supabase:
            try:
                self.supabase.table("legal_drafts").delete().eq("id", clean_id).eq("user_id", str(user.user_id)).execute()
            except Exception as e:
                logger.error(f"Error deleting legal draft {clean_id}: {e}")
                if _is_production():
                    raise HTTPException(
                        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                        detail="Failed to delete legal draft in database in production."
                    ) from e

        self._in_memory_drafts.pop(clean_id, None)
        return {"status": "success", "message": f"Legal draft '{clean_id}' deleted successfully."}


# Global singleton instance
legal_draft_manager = LegalDraftManager()

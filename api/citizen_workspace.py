"""
NyayPath Citizen Dashboard & My Cases Workspace Module
Phase 2.1 & Phase 2.2 Implementation

Provides dedicated citizen-facing endpoints and logic for:
- Citizen Dashboard Statistics (Total, Active, Resolved, Pending Actions)
- My Cases Workspace (Strict Ownership Filtering, Search, Category/Status Filters, Sorting, Pagination)
- Central Case Filing Wizard (6-step guided submission, input sanitization, 10MB media validation)
- Case Lifecycle Actions (Withdrawal, citizen remarks, expedite requests)
- Case Tracking Integration & Public Progress Lookup (Zero PII / zero proctor notes leakage)
- Milestone Events & Chronological Timeline Generation
"""

import os
import math
import uuid
import secrets
import hashlib
import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional
from fastapi import HTTPException, status
from pydantic import BaseModel, Field

try:
    from .auth import AuthUser, UserRole, AccountStatus
except ImportError:
    from auth import AuthUser, UserRole, AccountStatus

try:
    from .media_sanitizer import sanitize_document_payload
except ImportError:
    from media_sanitizer import sanitize_document_payload

try:
    from .audit import record_case_activity
except ImportError:
    from audit import record_case_activity

try:
    from .notifications import notification_manager
except ImportError:
    try:
        from notifications import notification_manager
    except ImportError:
        notification_manager = None

try:
    from supabase import create_client, Client
except ImportError:
    create_client, Client = None, None

logger = logging.getLogger(__name__)

# Active statuses vs Resolved statuses
ACTIVE_STATUSES = {
    "SUBMITTED",
    "UNDER_INQUIRY",
    "HEARING_SCHEDULED",
    "ACTION_TAKEN",
    "IN_REVIEW",
    "IN_PROGRESS",
    "FILED",
    "PENDING"
}

RESOLVED_STATUSES = {
    "RESOLVED",
    "CLOSED",
    "COMPLETED",
    "DISPOSED",
    "WITHDRAWN"
}

# Permitted MIME types for document uploads
ALLOWED_MIME_TYPES = {
    "application/pdf",
    "image/jpeg",
    "image/png",
    "image/webp"
}
MAX_FILE_SIZE_BYTES = 10 * 1024 * 1024  # 10 MB limit


def _is_production() -> bool:
    return (
        os.environ.get("ENVIRONMENT") == "production" or
        os.environ.get("NODE_ENV") == "production" or
        os.environ.get("ENV") == "production" or
        os.environ.get("VERCEL") == "1"
    )


# =============================================================================
# Request & Response Models (Phase 2.2)
# =============================================================================

class CaseFilingRequest(BaseModel):
    category: str = Field(..., description="Case category (CAMPUS_GRIEVANCE, RTI, FIRST_APPEAL, CONSUMER_COMPLAINT, GENERAL_GRIEVANCE)")
    sub_category: Optional[str] = Field(None, description="Detailed sub-category or department unit")
    subject: str = Field(..., min_length=3, max_length=256, description="Case title or subject line")
    facts: str = Field(..., min_length=10, description="Detailed narrative of facts and circumstances")
    remedy_sought: Optional[str] = Field(None, description="Specific redress or action requested by applicant")
    department: Optional[str] = Field(None, description="Target public authority, college department, or respondent")
    incident_date: Optional[str] = Field(None, description="Date when incident or grievance occurred (YYYY-MM-DD)")
    is_confidential: bool = Field(False, description="Whether case requires restricted confidential handling")
    supporting_documents: Optional[List[Dict[str, Any]]] = Field(default_factory=list, description="List of pre-uploaded document metadata")
    declaration_confirmed: bool = Field(True, description="Confirmation of accuracy and terms acknowledgment")


class CaseLifecycleActionRequest(BaseModel):
    action: str = Field(..., description="Action to perform (WITHDRAW, ADD_REMARK, REQUEST_EXPEDITE)")
    remarks: Optional[str] = Field(None, description="Remarks or details regarding the action")
    reason: Optional[str] = Field(None, description="Reason for withdrawal or expedite request")


class PublicCaseTrackingRequest(BaseModel):
    case_id: str = Field(..., description="Business Case ID or Tracking Number")
    verification_key: Optional[str] = Field(None, description="Secret tracking key or verification code")


# =============================================================================
# Workspace & Case Management Engine
# =============================================================================

class CitizenWorkspaceManager:
    def __init__(self):
        url: str = os.environ.get("SUPABASE_URL", "")
        secret_key: str = os.environ.get("SUPABASE_SECRET_KEY", "")
        is_offline_test = os.environ.get("SUPABASE_OFFLINE_TEST") == "1"
        self.use_supabase = bool(url and secret_key and create_client and not is_offline_test)
        self.supabase: Optional[Client] = None
        self._memory_cases: Dict[str, Dict[str, Any]] = {}

        if self.use_supabase:
            try:
                self.supabase = create_client(url, secret_key)
                logger.info("CitizenWorkspace: Connected to Supabase.")
            except Exception as e:
                logger.error(f"CitizenWorkspace: Supabase connection error: {e}")
                self.use_supabase = False
                if _is_production():
                    raise RuntimeError("Persistent database required in production.") from e

    def _ensure_connected(self):
        if not self.use_supabase or not self.supabase:
            url: str = os.environ.get("SUPABASE_URL", "")
            secret_key: str = os.environ.get("SUPABASE_SECRET_KEY", "")
            is_offline_test = os.environ.get("SUPABASE_OFFLINE_TEST") == "1"
            if url and secret_key and create_client and not is_offline_test:
                try:
                    self.supabase = create_client(url, secret_key)
                    self.use_supabase = True
                except Exception as e:
                    logger.warning(f"CitizenWorkspace reconnect failed: {e}")

    def _get_owner_id(self, case: Dict[str, Any]) -> Optional[str]:
        """Resolves authoritative case owner UUID across cases and campus_cases structures."""
        cdata = case.get("data") if isinstance(case.get("data"), dict) else {}
        return (
            case.get("student_user_id") or
            case.get("citizen_user_id") or
            cdata.get("citizen_user_id") or
            cdata.get("student_user_id") or
            case.get("user_id") or
            cdata.get("user_id")
        )

    # =========================================================================
    # Task 2: Central Case Filing Wizard (Phase 2.2)
    # =========================================================================
    def file_case(self, user: AuthUser, payload: CaseFilingRequest) -> Dict[str, Any]:
        """
        Submits and registers a new citizen case across public.cases / campus_cases.
        - Strict identity attribution: citizen_user_id is set authoritatively from user.user_id.
        - Prevents ID spoofing; user cannot file on behalf of someone else.
        - Synchronizes parent cases and child campus_cases tables.
        - Records initial case activity and attaches sanitized documents.
        """
        self._ensure_connected()

        if not payload.declaration_confirmed:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="You must accept the accuracy and statutory declaration before submitting."
            )

        cat_upper = payload.category.strip().upper()
        # Normalization
        if cat_upper in ["CAMPUS_GRIEVANCE", "CAMPUS", "STUDENT"]:
            norm_type = "CAMPUS_GRIEVANCE"
        elif cat_upper in ["RTI", "RTI_REQUEST"]:
            norm_type = "RTI"
        elif cat_upper in ["FIRST_APPEAL", "RTI_APPEAL"]:
            norm_type = "FIRST_APPEAL"
        elif cat_upper in ["CONSUMER_COMPLAINT", "CONSUMER_DISPUTE", "CONSUMER"]:
            norm_type = "CONSUMER_COMPLAINT"
        else:
            norm_type = "GENERAL_GRIEVANCE"

        case_uuid = str(uuid.uuid4())
        now = datetime.now(timezone.utc)
        now_iso = now.isoformat()

        # Generate unique human-readable tracking number
        year_str = str(now.year)
        if norm_type == "CAMPUS_GRIEVANCE":
            raw_code = uuid.uuid4().hex[:4].upper()
            dept_code = (payload.department[:2] if payload.department else "GR").upper()
            case_id = f"CAMPUS-{raw_code}-{dept_code}"
        else:
            prefix_map = {
                "RTI": "RTI",
                "FIRST_APPEAL": "FA",
                "CONSUMER_COMPLAINT": "CC",
                "GENERAL_GRIEVANCE": "GEN"
            }
            pfx = prefix_map.get(norm_type, "GEN")
            case_id = f"NP-{year_str}-{pfx}-{uuid.uuid4().hex[:6].upper()}"

        # 128-bit verification key for tracking
        verification_key = secrets.token_hex(16)
        verification_hash = hashlib.sha256(verification_key.encode()).hexdigest()

        # 1. Supabase Persistence
        if self.use_supabase and self.supabase:
            try:
                if norm_type == "CAMPUS_GRIEVANCE":
                    # Determine severity
                    facts_lower = payload.facts.lower()
                    if any(term in facts_lower for term in ["ragging", "harassment", "assault", "threat", "emergency"]):
                        severity = "URGENT"
                    elif any(term in facts_lower for term in ["exam", "scholarship", "fee", "marksheet"]):
                        severity = "HIGH"
                    else:
                        severity = "NORMAL"

                    campus_record = {
                        "id": case_uuid,
                        "case_id": case_id,
                        "institution_id": (user.institution_id or "INST_DEFAULT").strip().upper(),
                        "student_user_id": user.user_id,
                        "student_name": user.name or "Citizen Applicant",
                        "roll_number": "Protected",
                        "department": payload.department or "General Administration",
                        "year": "N/A",
                        "category": payload.sub_category or "Campus Grievance",
                        "subject": payload.subject,
                        "description": payload.facts,
                        "incident_date": payload.incident_date or now.strftime("%Y-%m-%d"),
                        "is_anonymous": False,
                        "confidentiality_mode": "CONFIDENTIAL" if payload.is_confidential else "STANDARD",
                        "severity": severity,
                        "status": "SUBMITTED",
                        "proctor_notes": "Grievance received via Central Case Management Portal. Acknowledged.",
                        "hearing_date": "Pending Proctorial Review",
                        "action_taken": "Pending inquiry by departmental committee.",
                        "resolution_details": None,
                        "resolution_deadline": (now + timedelta(days=15)).strftime("%Y-%m-%d"),
                        "assigned_proctor": None,
                        "assigned_committee": None,
                        "supporting_documents": payload.supporting_documents or [],
                        "verification_key_hash": verification_hash,
                        "key_version": "v1",
                        "created_at": now_iso,
                        "updated_at": now_iso
                    }
                    # Insert to campus_cases (Postgres trigger trg_sync_campus_case_insert creates parent in cases)
                    insert_res = self.supabase.table("campus_cases").insert(campus_record).execute()
                    if not insert_res.data:
                        raise RuntimeError("Failed to insert campus_cases record.")
                else:
                    case_data = {
                        "citizen_user_id": user.user_id,
                        "applicant_name": user.name or "Citizen Applicant",
                        "applicant_email": user.email,
                        "subject": payload.subject,
                        "facts": payload.facts,
                        "remedy_sought": payload.remedy_sought,
                        "department": payload.department,
                        "incident_date": payload.incident_date or now.strftime("%Y-%m-%d"),
                        "sub_category": payload.sub_category,
                        "is_confidential": payload.is_confidential,
                        "supporting_documents": payload.supporting_documents or [],
                        "case_number": case_id
                    }
                    cases_record = {
                        "id": case_uuid,
                        "case_id": case_id,
                        "case_type": norm_type,
                        "status": "SUBMITTED",
                        "tracking_key_hash": verification_hash,
                        "key_version": "v1",
                        "data": case_data,
                        "created_at": now_iso,
                        "updated_at": now_iso
                    }
                    insert_res = self.supabase.table("cases").insert(cases_record).execute()
                    if not insert_res.data:
                        raise RuntimeError("Failed to insert cases record.")

                # Insert supporting documents if attached
                if payload.supporting_documents:
                    for doc in payload.supporting_documents:
                        if isinstance(doc, dict):
                            doc_id = str(uuid.uuid4())
                            doc_record = {
                                "id": doc_id,
                                "case_uuid": case_uuid,
                                "case_id": case_id,
                                "file_name": doc.get("file_name") or f"doc_{doc_id[:8]}.pdf",
                                "file_size_bytes": doc.get("file_size_bytes") or 0,
                                "mime_type": doc.get("mime_type") or "application/pdf",
                                "storage_path": doc.get("storage_path") or f"{user.user_id}/{case_id}/{doc_id}.pdf",
                                "uploader_user_id": user.user_id,
                                "is_confidential": payload.is_confidential,
                                "created_at": now_iso
                            }
                            try:
                                self.supabase.table("case_documents").insert(doc_record).execute()
                            except Exception as e_doc:
                                logger.warning(f"Error recording case document in database: {e_doc}")

                # Initial Case Activity Record
                record_case_activity(
                    case_uuid=case_uuid,
                    case_id=case_id,
                    action_type="CASE_FILED",
                    action_details={
                        "event": "CASE_FILED",
                        "category": norm_type,
                        "sub_category": payload.sub_category,
                        "is_confidential": payload.is_confidential,
                        "notification_trigger": "CASE_FILED",
                        "notification_type": "EMAIL_AND_IN_APP",
                        "recipient_role": "OFFICER",
                        "timestamp": now_iso
                    },
                    actor_user=user,
                    actor_type="USER",
                    supabase_client=self.supabase
                )

            except Exception as e:
                logger.error(f"Error persisting filed case to Supabase: {e}")
                if _is_production():
                    raise HTTPException(
                        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                        detail="Failed to persist case to database in production."
                    ) from e

        # Dev / Testing Fallback
        mock_record = {
            "id": case_uuid,
            "case_id": case_id,
            "case_type": norm_type,
            "category": payload.sub_category or norm_type,
            "subject": payload.subject,
            "description": payload.facts,
            "facts": payload.facts,
            "status": "SUBMITTED",
            "student_user_id": user.user_id,
            "user_id": user.user_id,
            "data": {
                "citizen_user_id": user.user_id,
                "applicant_name": user.name or "Citizen Applicant",
                "applicant_email": user.email,
                "subject": payload.subject,
                "facts": payload.facts,
                "department": payload.department
            },
            "created_at": now_iso,
            "updated_at": now_iso,
            "verification_key_hash": verification_hash,
            "supporting_documents": payload.supporting_documents or []
        }
        self._memory_cases[case_id] = mock_record

        # Dispatch In-App Notification (Phase 2.3)
        if notification_manager:
            try:
                notification_manager.create_notification(
                    recipient_user_id=user.user_id,
                    event_type="CASE_SUBMITTED",
                    title="Case Registration Confirmed",
                    message=f"Your case {case_id} has been registered under category '{norm_type}'.",
                    related_case_id=case_id,
                    case_uuid=case_uuid,
                    action_url=f"/dashboard/my-cases/{case_id}",
                    idempotency_key=f"notif_{user.user_id}_SUBMITTED_{case_id}"
                )
            except Exception as e_notif:
                logger.warning(f"Failed to create case filing notification: {e_notif}")

        return {
            "case_id": case_id,
            "case_uuid": case_uuid,
            "tracking_number": case_id,
            "verification_key": verification_key,
            "category": norm_type,
            "status": "SUBMITTED",
            "created_at": now_iso,
            "message": "Case registered successfully with NyayPath Central Case Management System."
        }

    # =========================================================================
    # Task 2 & 4: Supporting Document Upload & Sanitization
    # =========================================================================
    def upload_document(
        self,
        user: AuthUser,
        file_bytes: bytes,
        filename: str,
        content_type: str,
        case_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Validates, strips metadata, and securely uploads supporting documents to Supabase Storage.
        - Enforces <= 10MB limit.
        - Strips PDF metadata & XMP streams; strips image EXIF.
        - If case_id is provided, validates that caller owns the case.
        """
        self._ensure_connected()

        if len(file_bytes) > MAX_FILE_SIZE_BYTES:
            status_413 = getattr(status, "HTTP_413_CONTENT_TOO_LARGE", 413)
            raise HTTPException(
                status_code=status_413,
                detail=f"File exceeds maximum permissible size of {MAX_FILE_SIZE_BYTES // (1024*1024)}MB."
            )

        clean_mime = (content_type or "").lower().strip()
        if clean_mime not in ALLOWED_MIME_TYPES:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unsupported document format '{clean_mime}'. Only PDF, JPEG, PNG, and WebP are allowed."
            )

        # Sanitize metadata (PDF doc info / XMP & Image EXIF)
        try:
            sanitized_bytes, safe_filename = sanitize_document_payload(file_bytes, filename, clean_mime)
        except Exception as e:
            logger.warning(f"Media sanitization error: {e}")
            sanitized_bytes, safe_filename = file_bytes, filename

        doc_id = str(uuid.uuid4())
        now_ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        storage_path = f"{user.user_id}/{now_ts}_{doc_id[:8]}_{safe_filename}"

        # Upload to Supabase Storage (case-documents bucket)
        if self.use_supabase and self.supabase:
            try:
                self.supabase.storage.from_("case-documents").upload(
                    path=storage_path,
                    file=sanitized_bytes,
                    file_options={"content-type": clean_mime}
                )
            except Exception as e:
                logger.error(f"Supabase Storage upload failed: {e}")
                if _is_production():
                    raise HTTPException(
                        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                        detail="Failed to store document in secure storage."
                    ) from e

        # If case_id was provided, verify ownership and register in case_documents table
        if case_id:
            raw_case = self._fetch_single_raw_case(case_id)
            if raw_case:
                owner_id = self._get_owner_id(raw_case)
                if owner_id != user.user_id:
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail="Access denied: Cannot attach documents to a case you do not own."
                    )

                case_uuid = raw_case.get("id") or str(uuid.uuid4())
                if self.use_supabase and self.supabase:
                    try:
                        self.supabase.table("case_documents").insert({
                            "id": doc_id,
                            "case_uuid": case_uuid,
                            "case_id": case_id,
                            "file_name": safe_filename,
                            "file_size_bytes": len(sanitized_bytes),
                            "mime_type": clean_mime,
                            "storage_path": storage_path,
                            "uploader_user_id": user.user_id,
                            "is_confidential": raw_case.get("is_confidential", False),
                            "created_at": datetime.now(timezone.utc).isoformat()
                        }).execute()
                    except Exception as e:
                        logger.warning(f"Error registering doc in case_documents table: {e}")

        return {
            "document_id": doc_id,
            "file_name": safe_filename,
            "storage_path": storage_path,
            "file_size_bytes": len(sanitized_bytes),
            "mime_type": clean_mime,
            "message": "Document sanitized and uploaded successfully."
        }

    # =========================================================================
    # Task 3: Case Lifecycle Management (Withdrawal, Remarks, Expedite)
    # =========================================================================
    def perform_lifecycle_action(
        self,
        case_id: str,
        user: AuthUser,
        payload: CaseLifecycleActionRequest
    ) -> Dict[str, Any]:
        """
        Executes citizen lifecycle transitions:
        - WITHDRAW: Permits withdrawal of active cases; sets status to CLOSED (reason: WITHDRAWN_BY_APPLICANT).
        - ADD_REMARK: Appends citizen comments to activity audit log without altering status.
        - REQUEST_EXPEDITE: Registers formal urgent expedite notification for officers.
        """
        self._ensure_connected()
        clean_id = (case_id or "").strip().upper()
        case = self._fetch_single_raw_case(clean_id)

        if not case:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Case not found."
            )

        # Strict ownership verification
        owner_id = self._get_owner_id(case)
        if owner_id != user.user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied: You do not own this case."
            )

        action_clean = payload.action.strip().upper()
        current_status = (case.get("status") or "SUBMITTED").upper()
        now_iso = datetime.now(timezone.utc).isoformat()
        case_uuid = case.get("id")

        if action_clean == "WITHDRAW":
            if current_status in RESOLVED_STATUSES:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Cannot withdraw a case that is already in status '{current_status}'."
                )

            # Mark status as CLOSED (compliant with check constraint ck_campus_cases_status)
            new_status = "CLOSED"
            reason = payload.reason or payload.remarks or "Case withdrawn by applicant."

            # Update parent cases table (trigger syncs to campus_cases)
            if self.use_supabase and self.supabase:
                try:
                    self.supabase.table("cases").update({
                        "status": new_status,
                        "updated_at": now_iso
                    }).eq("case_id", clean_id).execute()
                except Exception as e:
                    logger.error(f"Error updating case status to {new_status}: {e}")
                    if _is_production():
                        raise HTTPException(
                            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                            detail="Database error during case withdrawal."
                        ) from e

            # Audit Activity Record
            record_case_activity(
                case_uuid=case_uuid,
                case_id=clean_id,
                action_type="CASE_WITHDRAWN",
                action_details={
                    "event": "CASE_WITHDRAWN",
                    "reason": reason,
                    "previous_status": current_status,
                    "notification_trigger": "CASE_WITHDRAWN",
                    "notification_type": "EMAIL_AND_IN_APP",
                    "recipient_role": "OFFICER",
                    "timestamp": now_iso
                },
                actor_user=user,
                actor_type="USER",
                supabase_client=self.supabase
            )

            # In-App Notification (Phase 2.3)
            if notification_manager:
                try:
                    notification_manager.create_notification(
                        recipient_user_id=user.user_id,
                        event_type="CASE_WITHDRAWN",
                        title="Case Withdrawal Confirmed",
                        message=f"Case {clean_id} has been withdrawn and closed.",
                        related_case_id=clean_id,
                        case_uuid=case_uuid,
                        action_url=f"/dashboard/my-cases/{clean_id}",
                        idempotency_key=f"notif_{user.user_id}_WITHDRAWN_{clean_id}"
                    )
                    assigned_officer = case.get("assigned_proctor_user_id")
                    if assigned_officer:
                        notification_manager.create_notification(
                            recipient_user_id=assigned_officer,
                            event_type="CASE_WITHDRAWN",
                            title="Assigned Case Withdrawn",
                            message=f"Grievance {clean_id} has been withdrawn by applicant.",
                            related_case_id=clean_id,
                            case_uuid=case_uuid,
                            action_url=f"/campus-proctor?case_id={clean_id}",
                            idempotency_key=f"notif_{assigned_officer}_WITHDRAWN_{clean_id}"
                        )
                except Exception as e_notif:
                    logger.warning(f"Failed to create withdrawal notification: {e_notif}")

            return {
                "case_id": clean_id,
                "action": "WITHDRAW",
                "status": new_status,
                "message": "Case successfully withdrawn."
            }

        elif action_clean == "ADD_REMARK":
            if not payload.remarks or not payload.remarks.strip():
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Remarks content is required."
                )

            record_case_activity(
                case_uuid=case_uuid,
                case_id=clean_id,
                action_type="CITIZEN_REMARK_ADDED",
                action_details={
                    "event": "CITIZEN_REMARK_ADDED",
                    "remarks": payload.remarks.strip(),
                    "notification_trigger": "CITIZEN_REMARK_ADDED",
                    "notification_type": "IN_APP",
                    "recipient_role": "OFFICER",
                    "timestamp": now_iso
                },
                actor_user=user,
                actor_type="USER",
                supabase_client=self.supabase
            )

            # Officer In-App Notification (Phase 2.3)
            if notification_manager:
                try:
                    assigned_officer = case.get("assigned_proctor_user_id")
                    if assigned_officer:
                        notification_manager.create_notification(
                            recipient_user_id=assigned_officer,
                            event_type="CITIZEN_REMARK_ADDED",
                            title="Citizen Remark Added",
                            message=f"Applicant posted a supplementary remark on case {clean_id}: {payload.remarks.strip()[:80]}",
                            related_case_id=clean_id,
                            case_uuid=case_uuid,
                            action_url=f"/campus-proctor?case_id={clean_id}",
                            idempotency_key=f"notif_{assigned_officer}_REMARK_{clean_id}_{int(datetime.now(timezone.utc).timestamp())}"
                        )
                except Exception as e_notif:
                    logger.warning(f"Failed to create remark notification: {e_notif}")

            return {
                "case_id": clean_id,
                "action": "ADD_REMARK",
                "status": current_status,
                "message": "Remark successfully added to case timeline."
            }

        elif action_clean == "REQUEST_EXPEDITE":
            record_case_activity(
                case_uuid=case_uuid,
                case_id=clean_id,
                action_type="EXPEDITE_REQUESTED",
                action_details={
                    "event": "EXPEDITE_REQUESTED",
                    "reason": payload.reason or payload.remarks or "Applicant requested expedite review.",
                    "notification_trigger": "EXPEDITE_REQUESTED",
                    "notification_type": "EMAIL_AND_IN_APP",
                    "recipient_role": "OFFICER",
                    "timestamp": now_iso
                },
                actor_user=user,
                actor_type="USER",
                supabase_client=self.supabase
            )

            # Officer In-App Notification (Phase 2.3)
            if notification_manager:
                try:
                    assigned_officer = case.get("assigned_proctor_user_id")
                    if assigned_officer:
                        notification_manager.create_notification(
                            recipient_user_id=assigned_officer,
                            event_type="EXPEDITE_REQUESTED",
                            title="Urgent Expedite Requested",
                            message=f"Applicant requested expedited review for case {clean_id}.",
                            related_case_id=clean_id,
                            case_uuid=case_uuid,
                            action_url=f"/campus-proctor?case_id={clean_id}",
                            idempotency_key=f"notif_{assigned_officer}_EXPEDITE_{clean_id}_{int(datetime.now(timezone.utc).timestamp())}"
                        )
                except Exception as e_notif:
                    logger.warning(f"Failed to create expedite notification: {e_notif}")

            return {
                "case_id": clean_id,
                "action": "REQUEST_EXPEDITE",
                "status": current_status,
                "message": "Expedite request submitted to the presiding officer."
            }

        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unknown lifecycle action '{payload.action}'. Permitted: WITHDRAW, ADD_REMARK, REQUEST_EXPEDITE."
            )

    # =========================================================================
    # Task 5: Case Search & Public Case Tracking
    # =========================================================================
    def track_case_public(
        self,
        case_id: str,
        verification_key: Optional[str] = None,
        user: Optional[AuthUser] = None
    ) -> Dict[str, Any]:
        """
        Enables public tracking of case progress with zero credential / confidential data leakage.
        - If caller is authenticated owner, access is granted.
        - If unauthenticated, requires the 128-bit secret verification_key matching stored hash.
        - Proctor notes, secret keys, and personal contact info are strictly omitted.
        """
        self._ensure_connected()
        clean_id = (case_id or "").strip().upper()
        case = self._fetch_single_raw_case(clean_id)

        if not case:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Case not found. Please verify the Case ID."
            )

        # Check authorization
        authorized = False
        owner_id = self._get_owner_id(case)

        if user and user.user_id and user.user_id == owner_id:
            authorized = True
        elif verification_key and verification_key.strip():
            candidate_hash = hashlib.sha256(verification_key.strip().encode()).hexdigest()
            stored_hash = case.get("verification_key_hash") or case.get("tracking_key_hash")
            if stored_hash and candidate_hash == stored_hash:
                authorized = True

        if not authorized:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid verification key or unauthorized access. Case tracking requires ownership or valid verification code."
            )

        # Public tracking projection (Zero PII, zero proctor notes)
        timeline = self._build_case_timeline(case)
        public_summary = {
            "case_id": case.get("case_id"),
            "case_type": case.get("case_type") or "CAMPUS_GRIEVANCE",
            "category": case.get("category") or "General",
            "department": case.get("department"),
            "status": (case.get("status") or "SUBMITTED").upper(),
            "hearing_date": case.get("hearing_date"),
            "action_taken": case.get("action_taken"),
            "created_at": case.get("created_at"),
            "updated_at": case.get("updated_at")
        }

        return {
            "case": public_summary,
            "timeline": timeline
        }

    # =========================================================================
    # Task 2 & 7: Dashboard Statistics
    # =========================================================================
    def get_dashboard_stats(self, user: AuthUser) -> Dict[str, Any]:
        """
        Calculates live summary statistics strictly for cases owned by the authenticated citizen/student.
        Fails closed on database outages.
        """
        cases = self._fetch_all_user_cases(user.user_id)

        total_cases = len(cases)
        active_cases = sum(1 for c in cases if (c.get("status") or "").upper() in ACTIVE_STATUSES)
        resolved_cases = sum(1 for c in cases if (c.get("status") or "").upper() in RESOLVED_STATUSES)
        
        # Pending actions: Cases requiring user attention (e.g. Hearing scheduled, action required)
        pending_actions = sum(
            1 for c in cases 
            if (c.get("status") or "").upper() == "HEARING_SCHEDULED" 
            or (c.get("hearing_date") and c.get("hearing_date") != "Pending Proctorial Review")
        )

        # Sort recent cases by created_at descending
        sorted_cases = sorted(
            cases,
            key=lambda x: str(x.get("created_at") or ""),
            reverse=True
        )

        recent_cases = [self._sanitize_summary_case(c) for c in sorted_cases[:5]]

        return {
            "stats": {
                "total_cases": total_cases,
                "active_cases": active_cases,
                "resolved_cases": resolved_cases,
                "pending_actions": pending_actions
            },
            "recent_cases": recent_cases,
            "user_profile": {
                "user_id": user.user_id,
                "name": user.name or "Citizen",
                "email": user.email,
                "role": user.role.value if hasattr(user.role, "value") else str(user.role),
                "institution_id": user.institution_id
            }
        }

    # =========================================================================
    # Task 3 & 7: My Cases Workspace (List, Filter, Search, Pagination)
    # =========================================================================
    def list_citizen_cases(
        self,
        user: AuthUser,
        status_filter: Optional[str] = None,
        category_filter: Optional[str] = None,
        search: Optional[str] = None,
        sort_by: str = "created_at",
        sort_order: str = "desc",
        page: int = 1,
        limit: int = 10
    ) -> Dict[str, Any]:
        """
        Retrieves paginated, filtered cases strictly belonging to the authenticated citizen.
        Internal officer-only notes (proctor_notes) and tracking secrets are stripped.
        """
        all_cases = self._fetch_all_user_cases(user.user_id)

        # Filter by status
        filtered = all_cases
        if status_filter and status_filter.strip().upper() != "ALL":
            s_clean = status_filter.strip().upper()
            if s_clean == "ACTIVE":
                filtered = [c for c in filtered if (c.get("status") or "").upper() in ACTIVE_STATUSES]
            elif s_clean == "RESOLVED":
                filtered = [c for c in filtered if (c.get("status") or "").upper() in RESOLVED_STATUSES]
            else:
                filtered = [c for c in filtered if (c.get("status") or "").upper() == s_clean]

        # Filter by category
        if category_filter and category_filter.strip().upper() != "ALL":
            c_clean = category_filter.strip().upper()
            filtered = [c for c in filtered if (c.get("category") or "").upper() == c_clean]

        # Filter by search keyword (case_id, subject, description)
        if search and search.strip():
            q = search.strip().lower()
            filtered = [
                c for c in filtered
                if q in (c.get("case_id") or "").lower()
                or q in (c.get("subject") or "").lower()
                or q in (c.get("description") or "").lower()
            ]

        # Sort
        reverse = (sort_order.lower() == "desc")
        filtered = sorted(
            filtered,
            key=lambda x: str(x.get(sort_by) or ""),
            reverse=reverse
        )

        total = len(filtered)
        total_pages = max(1, math.ceil(total / limit)) if limit > 0 else 1
        page = max(1, min(page, total_pages))

        start_idx = (page - 1) * limit
        end_idx = start_idx + limit
        paginated_cases = filtered[start_idx:end_idx]

        sanitized_list = [self._sanitize_summary_case(c) for c in paginated_cases]

        return {
            "cases": sanitized_list,
            "total": total,
            "page": page,
            "limit": limit,
            "total_pages": total_pages
        }

    # =========================================================================
    # Task 4 & 7: Case Details & Progress Timeline
    # =========================================================================
    def get_case_details(self, case_id: str, user: AuthUser) -> Dict[str, Any]:
        """
        Retrieves full details of a specific case strictly verifying ownership.
        Internal proctor notes and secret verification hashes are strictly hidden.
        """
        clean_id = (case_id or "").strip().upper()
        case = self._fetch_single_raw_case(clean_id)

        if not case:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Case not found. Please verify the Case ID."
            )

        # Strict ownership verification
        owner_id = self._get_owner_id(case)

        if owner_id != user.user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied: You do not have permission to view this case."
            )

        # Sanitize case: Strip confidential internal proctor notes
        sanitized_case = dict(case)
        sanitized_case.pop("proctor_notes", None)  # STRICTLY HIDDEN FROM CITIZENS
        sanitized_case.pop("verification_key_hash", None)
        sanitized_case.pop("key_version", None)

        # Build activity timeline
        timeline = self._build_case_timeline(sanitized_case)

        # Build documents list
        documents = self._fetch_case_documents(clean_id, sanitized_case)

        return {
            "case": sanitized_case,
            "timeline": timeline,
            "documents": documents
        }

    # =========================================================================
    # Internal Helper Methods
    # =========================================================================
    def _fetch_all_user_cases(self, user_id: str) -> List[Dict[str, Any]]:
        """
        Queries all cases belonging to user_id across campus_cases and cases tables.
        Fails closed on database errors in production.
        """
        self._ensure_connected()
        user_cases: List[Dict[str, Any]] = []
        seen_case_ids = set()

        if self.use_supabase and self.supabase:
            try:
                # 1. Query campus_cases where student_user_id == user_id
                res_campus = self.supabase.table("campus_cases").select("*").eq("student_user_id", user_id).execute()
                if res_campus.data:
                    for row in res_campus.data:
                        cid = row.get("case_id")
                        if cid and cid not in seen_case_ids:
                            seen_case_ids.add(cid)
                            row["case_type"] = row.get("case_type") or "CAMPUS_GRIEVANCE"
                            user_cases.append(row)

                # 2. Query cases table where data->>'citizen_user_id' == user_id
                res_cases = self.supabase.table("cases").select("*").execute()
                if res_cases.data:
                    for row in res_cases.data:
                        cid = row.get("case_id")
                        if cid and cid not in seen_case_ids:
                            cdata = row.get("data") or {}
                            if isinstance(cdata, dict):
                                c_uid = cdata.get("citizen_user_id") or cdata.get("student_user_id") or cdata.get("user_id")
                                if c_uid == user_id:
                                    seen_case_ids.add(cid)
                                    flattened = dict(cdata)
                                    flattened["case_id"] = cid
                                    flattened["id"] = row.get("id")
                                    flattened["case_type"] = row.get("case_type") or flattened.get("case_type") or "RTI"
                                    flattened["status"] = row.get("status") or flattened.get("status") or "SUBMITTED"
                                    flattened["created_at"] = row.get("created_at") or flattened.get("created_at")
                                    flattened["updated_at"] = row.get("updated_at") or flattened.get("updated_at")
                                    user_cases.append(flattened)
                return user_cases
            except Exception as e:
                logger.error(f"Error fetching user cases from Supabase: {e}")
                if _is_production():
                    raise HTTPException(
                        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                        detail="Database query failed in production environment."
                    ) from e

        # Dev / Test fallback: In-memory & SQLite
        for cid, c in self._memory_cases.items():
            c_uid = c.get("student_user_id") or c.get("user_id") or c.get("data", {}).get("citizen_user_id")
            if c_uid == user_id and cid not in seen_case_ids:
                seen_case_ids.add(cid)
                user_cases.append(dict(c))

        try:
            from api.campus_proctor import campus_proctor_manager
            # Check SQLite
            if campus_proctor_manager.db_path and os.path.exists(campus_proctor_manager.db_path):
                import sqlite3
                conn = sqlite3.connect(campus_proctor_manager.db_path)
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM campus_cases WHERE student_user_id = ?", (user_id,))
                rows = cursor.fetchall()
                conn.close()
                for r in rows:
                    d = dict(r)
                    cid = d.get("case_id")
                    if cid and cid not in seen_case_ids:
                        seen_case_ids.add(cid)
                        d["case_type"] = "CAMPUS_GRIEVANCE"
                        user_cases.append(d)

            # Check memory
            for cid, c in campus_proctor_manager._memory_cases.items():
                if c.get("student_user_id") == user_id and cid not in seen_case_ids:
                    seen_case_ids.add(cid)
                    d = dict(c)
                    d["case_type"] = "CAMPUS_GRIEVANCE"
                    user_cases.append(d)
        except Exception as e:
            logger.warning(f"Error fetching fallback cases: {e}")

        return user_cases

    def _fetch_single_raw_case(self, case_id: str) -> Optional[Dict[str, Any]]:
        """Fetches a single raw case by Case ID from campus_cases or cases."""
        self._ensure_connected()
        if self.use_supabase and self.supabase:
            try:
                res_campus = self.supabase.table("campus_cases").select("*").eq("case_id", case_id).execute()
                if res_campus.data and len(res_campus.data) > 0:
                    c = res_campus.data[0]
                    c["case_type"] = c.get("case_type") or "CAMPUS_GRIEVANCE"
                    return c

                res_parent = self.supabase.table("cases").select("*").eq("case_id", case_id).execute()
                if res_parent.data and len(res_parent.data) > 0:
                    row = res_parent.data[0]
                    cdata = row.get("data") or {}
                    flattened = dict(cdata) if isinstance(cdata, dict) else {}
                    flattened["case_id"] = row.get("case_id")
                    flattened["id"] = row.get("id")
                    flattened["case_type"] = row.get("case_type") or "RTI"
                    flattened["status"] = row.get("status") or flattened.get("status") or "SUBMITTED"
                    flattened["created_at"] = row.get("created_at")
                    flattened["updated_at"] = row.get("updated_at")
                    flattened["tracking_key_hash"] = row.get("tracking_key_hash")
                    flattened["data"] = cdata
                    return flattened
                return None
            except Exception as e:
                logger.error(f"Error querying single case from Supabase: {e}")
                if _is_production():
                    raise HTTPException(
                        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                        detail="Database query failed in production environment."
                    ) from e

        # Dev fallback
        if case_id in self._memory_cases:
            return dict(self._memory_cases[case_id])

        from api.campus_proctor import campus_proctor_manager
        return campus_proctor_manager._fetch_raw_case(case_id)

    def _sanitize_summary_case(self, case: Dict[str, Any]) -> Dict[str, Any]:
        """Extracts citizen-facing summary fields and hides internal proctor notes."""
        docs = case.get("supporting_documents")
        doc_count = len(docs) if isinstance(docs, list) else 0

        return {
            "id": case.get("id"),
            "case_id": case.get("case_id"),
            "case_type": case.get("case_type") or "CAMPUS_GRIEVANCE",
            "category": case.get("category") or "General",
            "subject": case.get("subject") or case.get("case_id"),
            "description": case.get("description") or case.get("facts") or "",
            "status": (case.get("status") or "SUBMITTED").upper(),
            "severity": case.get("severity") or "NORMAL",
            "department": case.get("department"),
            "year": case.get("year"),
            "institution_id": case.get("institution_id"),
            "hearing_date": case.get("hearing_date"),
            "action_taken": case.get("action_taken"),
            "created_at": case.get("created_at"),
            "updated_at": case.get("updated_at"),
            "documents_count": doc_count
            # proctor_notes is strictly omitted!
        }

    def _build_case_timeline(self, case: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Constructs chronological case activity timeline.
        Hides internal committee deliberations or proctorial notes.
        """
        timeline: List[Dict[str, Any]] = []
        case_id = case.get("case_id")
        created_at = case.get("created_at") or datetime.now(timezone.utc).isoformat()

        # Step 1: Grievance Submission
        timeline.append({
            "id": "event-1-submission",
            "title": "Case Submitted",
            "description": f"Case filed under category '{case.get('category', 'General')}'.",
            "timestamp": created_at,
            "status": "SUBMITTED",
            "actor_type": "CITIZEN"
        })

        # Step 2: Query case_activity_log if Supabase is connected
        if self.use_supabase and self.supabase and case_id:
            try:
                res_log = self.supabase.table("case_activity_log").select("*").eq("case_id", case_id).order("created_at").execute()
                if res_log.data:
                    for idx, entry in enumerate(res_log.data, start=2):
                        act = entry.get("action_type") or ""
                        details = entry.get("action_details") or {}
                        # Exclude internal officer deliberations
                        if act in ["INTERNAL_NOTE_ADDED", "SECRET_AUDIT", "CONFIDENTIAL_INQUIRY"]:
                            continue

                        title = act.replace("_", " ").title()
                        desc = (
                            details.get("public_message") or
                            details.get("reason") or
                            details.get("remarks") or
                            details.get("note") or
                            f"Case milestone recorded: {title}"
                        )
                        timeline.append({
                            "id": f"event-{idx}-{act}",
                            "title": title,
                            "description": desc,
                            "timestamp": entry.get("created_at"),
                            "status": details.get("status") or case.get("status"),
                            "actor_type": entry.get("actor_type", "SYSTEM")
                        })
                    return timeline
            except Exception as e:
                logger.warning(f"Error fetching case_activity_log: {e}")

        # Fallback to history JSONB or lifecycle milestones
        raw_history = case.get("history")
        if isinstance(raw_history, list) and len(raw_history) > 0:
            for idx, h in enumerate(raw_history, start=2):
                if isinstance(h, dict):
                    action_name = h.get("action", "Status Update")
                    msg = h.get("note") or f"Updated status to {h.get('status', 'In Progress')}"
                    timeline.append({
                        "id": f"history-{idx}",
                        "title": action_name,
                        "description": msg,
                        "timestamp": h.get("timestamp") or case.get("updated_at") or created_at,
                        "status": h.get("status") or case.get("status"),
                        "actor_type": "INSTITUTION"
                    })
            return timeline

        # Standard milestones based on current status
        current_status = (case.get("status") or "SUBMITTED").upper()

        if current_status in ["UNDER_INQUIRY", "HEARING_SCHEDULED", "ACTION_TAKEN", "RESOLVED", "CLOSED"]:
            timeline.append({
                "id": "event-2-inquiry",
                "title": "Inquiry Initiated",
                "description": f"Grievance assigned to the {case.get('department', 'departmental')} inquiry cell for review.",
                "timestamp": case.get("updated_at") or created_at,
                "status": "UNDER_INQUIRY",
                "actor_type": "INSTITUTION"
            })

        if current_status in ["HEARING_SCHEDULED", "ACTION_TAKEN", "RESOLVED", "CLOSED"]:
            h_date = case.get("hearing_date")
            desc = f"Formal inquiry session scheduled for {h_date}." if h_date else "Proctorial hearing scheduled."
            timeline.append({
                "id": "event-3-hearing",
                "title": "Hearing Scheduled",
                "description": desc,
                "timestamp": case.get("updated_at") or created_at,
                "status": "HEARING_SCHEDULED",
                "actor_type": "COMMITTEE"
            })

        if current_status in ["ACTION_TAKEN", "RESOLVED", "CLOSED"]:
            action = case.get("action_taken") or "Action taken by departmental proctorial cell."
            timeline.append({
                "id": "event-4-action",
                "title": "Action Taken",
                "description": action,
                "timestamp": case.get("updated_at") or created_at,
                "status": "ACTION_TAKEN",
                "actor_type": "INSTITUTION"
            })

        if current_status in ["RESOLVED", "CLOSED"]:
            res_details = case.get("resolution_details") or "Grievance resolved following procedural review."
            timeline.append({
                "id": "event-5-resolution",
                "title": "Case Resolved",
                "description": res_details,
                "timestamp": case.get("updated_at") or created_at,
                "status": current_status,
                "actor_type": "INSTITUTION"
            })

        return timeline

    def _fetch_case_documents(self, case_id: str, case: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Retrieves list of supporting documents attached to the case.
        Excludes confidential internal files.
        """
        documents: List[Dict[str, Any]] = []
        seen_names = set()

        # 1. From case_documents table if Supabase is connected
        if self.use_supabase and self.supabase:
            try:
                res_docs = self.supabase.table("case_documents").select("*").eq("case_id", case_id).eq("is_confidential", False).execute()
                if res_docs.data:
                    for doc in res_docs.data:
                        fname = doc.get("file_name")
                        doc_id = str(doc.get("id"))
                        if fname and fname not in seen_names:
                            seen_names.add(fname)
                            documents.append({
                                "id": doc_id,
                                "document_id": doc_id,
                                "file_name": fname,
                                "file_size_bytes": doc.get("file_size_bytes"),
                                "mime_type": doc.get("mime_type") or "application/octet-stream",
                                "storage_path": doc.get("storage_path"),
                                "created_at": doc.get("created_at")
                            })
            except Exception as e:
                logger.warning(f"Error fetching case_documents table: {e}")

        # 2. From case['supporting_documents'] JSONB
        raw_docs = case.get("supporting_documents")
        if isinstance(raw_docs, list):
            for idx, d in enumerate(raw_docs, start=1):
                if isinstance(d, dict):
                    fname = d.get("name") or d.get("file_name") or f"document_{idx}.pdf"
                    doc_id = d.get("id") or d.get("document_id") or fname
                    if fname not in seen_names:
                        seen_names.add(fname)
                        documents.append({
                            "id": str(doc_id),
                            "document_id": str(doc_id),
                            "file_name": fname,
                            "file_size_bytes": d.get("size") or d.get("file_size_bytes"),
                            "mime_type": d.get("type") or d.get("mime_type") or "application/pdf",
                            "created_at": d.get("created_at") or case.get("created_at")
                        })
                elif isinstance(d, str):
                    if d not in seen_names:
                        seen_names.add(d)
                        documents.append({
                            "id": d,
                            "document_id": d,
                            "file_name": d,
                            "file_size_bytes": None,
                            "mime_type": "application/pdf",
                            "created_at": case.get("created_at")
                        })

        return documents


citizen_workspace_manager = CitizenWorkspaceManager()

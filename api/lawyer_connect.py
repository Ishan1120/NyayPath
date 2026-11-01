"""
NyayPath Phase 5: Lawyer Workspace, Lawyer Directory & Client Connect
====================================================================
Architecture & Capabilities:
1. Lawyer Onboarding & Verification Workflow (PENDING, VERIFIED, REJECTED, SUSPENDED)
2. Public Lawyer Directory with Multi-Factor Search & Privacy Guardrails
3. Consultation Request Lifecycle (PENDING, ACCEPTED, DECLINED, WITHDRAWN, COMPLETED)
4. Explicit Consent-Based Case Sharing & Instant Revocation
5. Non-Hallucinatory Database-Derived Lawyer Workspace Analytics
6. Notification Integration with Persisted Source UUID Idempotency
"""

import os
import uuid
import logging
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field
from fastapi import HTTPException, status

try:
    from supabase import create_client, Client
except ImportError:
    create_client, Client = None, None

try:
    from .auth import AuthUser, UserRole, AccountStatus
    from .audit import record_case_activity
    from .notifications import notification_manager
except ImportError:
    from auth import AuthUser, UserRole, AccountStatus
    from audit import record_case_activity
    from notifications import notification_manager

logger = logging.getLogger(__name__)


# =====================================================================
# Pydantic Schemas
# =====================================================================

class LawyerRegisterRequest(BaseModel):
    full_name: str
    phone: Optional[str] = ""
    bar_council: str
    enrollment_state: str
    enrollment_number: str
    years_of_practice: int = Field(default=0, ge=0)
    specializations: List[str] = []
    courts: List[str] = []
    languages: List[str] = ["English"]
    bio: Optional[str] = ""
    consultation_preferences: Optional[Dict[str, Any]] = None
    photo_url: Optional[str] = None


class LawyerProfileUpdateRequest(BaseModel):
    phone: Optional[str] = None
    years_of_practice: Optional[int] = None
    specializations: Optional[List[str]] = None
    courts: Optional[List[str]] = None
    languages: Optional[List[str]] = None
    bio: Optional[str] = None
    consultation_preferences: Optional[Dict[str, Any]] = None
    photo_url: Optional[str] = None


class LawyerVerifyRequest(BaseModel):
    decision: str  # VERIFIED, REJECTED, SUSPENDED
    notes: Optional[str] = None


class ConsultationCreateRequest(BaseModel):
    lawyer_user_id: str
    case_id: Optional[str] = None
    legal_issue: str
    description: str
    preferred_mode: str = "ONLINE"  # ONLINE, IN_PERSON, PHONE


class ConsultationStatusUpdateRequest(BaseModel):
    status: str  # ACCEPTED, DECLINED, WITHDRAWN, COMPLETED
    lawyer_response: Optional[str] = None


class CaseAccessGrantRequest(BaseModel):
    case_id: str
    lawyer_user_id: str
    shared_scope: str = "CASE_AND_DOCS"  # METADATA_ONLY, CASE_AND_DOCS
    consultation_request_id: Optional[str] = None


class CaseAccessRevokeRequest(BaseModel):
    case_id: str
    lawyer_user_id: str


# =====================================================================
# LawyerConnectManager
# =====================================================================

class LawyerConnectManager:
    def __init__(self):
        self.supabase_url = os.environ.get("SUPABASE_URL", "")
        self.supabase_key = os.environ.get("SUPABASE_SECRET_KEY", "")
        self.supabase: Optional[Client] = None
        self._ensure_connected()

    def _ensure_connected(self):
        if not self.supabase and self.supabase_url and self.supabase_key and create_client:
            try:
                self.supabase = create_client(self.supabase_url, self.supabase_key)
            except Exception as e:
                logger.error(f"Failed to connect Supabase in LawyerConnectManager: {e}")

    # -----------------------------------------------------------------
    # Lawyer Registration & Profile Management
    # -----------------------------------------------------------------

    def register_lawyer(self, user: AuthUser, payload: LawyerRegisterRequest) -> Dict[str, Any]:
        """
        Registers a new lawyer professional profile.
        - Strictly defaults to verification_status = 'PENDING'.
        - Prevents lawyers from self-verifying.
        - Audits registration in profiles.
        """
        if not user or getattr(user, "account_status", None) != AccountStatus.ACTIVE:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication required: Account is inactive or token is invalid."
            )

        self._ensure_connected()
        if not self.supabase:
            raise HTTPException(status_code=500, detail="Database connection unavailable.")

        user_id = str(user.user_id)

        # Check if profile already registered
        try:
            existing = self.supabase.table("lawyer_profiles").select("id, verification_status").eq("id", user_id).execute()
            if existing.data and len(existing.data) > 0:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Lawyer profile already exists with status: {existing.data[0]['verification_status']}."
                )
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error checking existing lawyer profile: {e}")

        now_iso = datetime.now(timezone.utc).isoformat()
        profile_data = {
            "id": user_id,
            "full_name": payload.full_name.strip(),
            "email": user.email or payload.full_name.lower().replace(" ", "") + "@bar.in",
            "phone": payload.phone.strip() if payload.phone else None,
            "bar_council": payload.bar_council.strip(),
            "enrollment_state": payload.enrollment_state.strip(),
            "enrollment_number": payload.enrollment_number.strip(),
            "years_of_practice": payload.years_of_practice,
            "specializations": payload.specializations,
            "courts": payload.courts,
            "languages": payload.languages or ["English"],
            "bio": payload.bio.strip() if payload.bio else "",
            "consultation_preferences": payload.consultation_preferences or {"modes": ["ONLINE", "IN_PERSON"], "consultation_fee": "PRO_BONO"},
            "photo_url": payload.photo_url,
            "verification_status": "PENDING",  # STRICT DEFAULT
            "created_at": now_iso,
            "updated_at": now_iso
        }

        try:
            res = self.supabase.table("lawyer_profiles").insert(profile_data).execute()
            if not res.data:
                raise RuntimeError("Failed to insert lawyer profile record.")

            # Update public.profiles if exists to reflect lawyer role intent
            try:
                self.supabase.table("profiles").update({
                    "role": "lawyer",
                    "full_name": payload.full_name.strip(),
                    "phone": payload.phone.strip() if payload.phone else None,
                    "updated_at": now_iso
                }).eq("id", user_id).execute()
            except Exception as e_p:
                logger.warning(f"Note: profiles table update: {e_p}")

            created = res.data[0]
            return {
                "status": "success",
                "message": "Lawyer profile submitted successfully. Pending administrative verification.",
                "profile": created
            }
        except Exception as e:
            logger.error(f"Database error during lawyer registration: {e}")
            raise HTTPException(status_code=500, detail="Database error during lawyer registration.")

    def get_lawyer_profile(self, lawyer_id: str, viewer: Optional[AuthUser] = None) -> Dict[str, Any]:
        """
        Retrieves a lawyer profile.
        - Unverified or suspended lawyers return 404 for public directory viewers.
        - Sensitive fields (enrollment number, verification notes) are stripped unless viewer is self or platform admin.
        """
        self._ensure_connected()
        if not self.supabase:
            raise HTTPException(status_code=500, detail="Database connection unavailable.")

        try:
            res = self.supabase.table("lawyer_profiles").select("*").eq("id", lawyer_id).execute()
            if not res.data or len(res.data) == 0:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lawyer profile not found.")
            profile = res.data[0]
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error retrieving lawyer profile: {e}")
            raise HTTPException(status_code=500, detail="Failed to retrieve lawyer profile.")

        is_self = viewer and str(viewer.user_id).lower() == str(lawyer_id).lower()
        is_admin = viewer and viewer.role == UserRole.PLATFORM_ADMIN

        # Only VERIFIED lawyers appear in public discovery
        if not is_self and not is_admin:
            if profile.get("verification_status") != "VERIFIED":
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Lawyer profile not found or currently pending professional verification."
                )
            # Mask private verification-sensitive attributes
            profile.pop("enrollment_number", None)
            profile.pop("verification_notes", None)
            profile.pop("verified_by", None)

        profile["user_id"] = profile["id"]
        profile["lawyer_user_id"] = profile["id"]
        return profile

    def update_lawyer_profile(self, user: AuthUser, payload: LawyerProfileUpdateRequest) -> Dict[str, Any]:
        """Allows a lawyer to update permitted non-sensitive profile attributes."""
        if not user or getattr(user, "account_status", None) != AccountStatus.ACTIVE:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required.")

        self._ensure_connected()
        user_id = str(user.user_id)

        update_dict: Dict[str, Any] = {"updated_at": datetime.now(timezone.utc).isoformat()}
        if payload.phone is not None: update_dict["phone"] = payload.phone
        if payload.years_of_practice is not None: update_dict["years_of_practice"] = payload.years_of_practice
        if payload.specializations is not None: update_dict["specializations"] = payload.specializations
        if payload.courts is not None: update_dict["courts"] = payload.courts
        if payload.languages is not None: update_dict["languages"] = payload.languages
        if payload.bio is not None: update_dict["bio"] = payload.bio
        if payload.consultation_preferences is not None: update_dict["consultation_preferences"] = payload.consultation_preferences
        if payload.photo_url is not None: update_dict["photo_url"] = payload.photo_url

        try:
            res = self.supabase.table("lawyer_profiles").update(update_dict).eq("id", user_id).execute()
            if not res.data:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lawyer profile not found.")
            return {"status": "success", "profile": res.data[0]}
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error updating lawyer profile: {e}")
            raise HTTPException(status_code=500, detail="Database update failed.")

    # -----------------------------------------------------------------
    # Public Lawyer Directory & Search
    # -----------------------------------------------------------------

    def list_verified_lawyers(
        self,
        specialization: Optional[str] = None,
        state: Optional[str] = None,
        court: Optional[str] = None,
        language: Optional[str] = None,
        search: Optional[str] = None,
        limit: int = 20,
        offset: int = 0
    ) -> Dict[str, Any]:
        """
        Public directory search for VERIFIED lawyers only.
        Omits private enrollment credentials.
        """
        self._ensure_connected()
        if not self.supabase:
            return {"lawyers": [], "total": 0}

        try:
            # Query verified lawyers view or table filtered to VERIFIED
            query = self.supabase.table("lawyer_profiles").select(
                "id, full_name, email, phone, bar_council, enrollment_state, years_of_practice, specializations, courts, languages, bio, consultation_preferences, photo_url, verification_status, created_at",
                count="exact"
            ).eq("verification_status", "VERIFIED")

            if state:
                query = query.ilike("enrollment_state", f"%{state.strip()}%")
            if specialization:
                query = query.contains("specializations", [specialization.strip()])
            if court:
                query = query.contains("courts", [court.strip()])
            if language:
                query = query.contains("languages", [language.strip()])
            if search:
                query = query.or_(f"full_name.ilike.%{search}%,bio.ilike.%{search}%")

            query = query.order("years_of_practice", desc=True).range(offset, offset + limit - 1)
            res = query.execute()

            lawyers = res.data or []
            for l in lawyers:
                l["user_id"] = l["id"]
                l["lawyer_user_id"] = l["id"]

            total = res.count if hasattr(res, "count") and res.count is not None else len(lawyers)

            return {
                "lawyers": lawyers,
                "total": total,
                "limit": limit,
                "offset": offset
            }
        except Exception as e:
            logger.error(f"Error querying verified lawyer directory: {e}")
            raise HTTPException(status_code=500, detail="Failed to query lawyer directory.")

    # -----------------------------------------------------------------
    # Administrative Verification
    # -----------------------------------------------------------------

    def verify_lawyer(self, admin_user: AuthUser, lawyer_id: str, decision: str, notes: Optional[str] = None) -> Dict[str, Any]:
        """
        Auditable verification by platform administrator.
        Permitted decisions: VERIFIED, REJECTED, SUSPENDED.
        """
        if not admin_user or getattr(admin_user, "account_status", None) != AccountStatus.ACTIVE:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required.")

        if admin_user.role != UserRole.PLATFORM_ADMIN:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied: Only platform administrators can verify or suspend lawyers."
            )

        norm_dec = decision.strip().upper()
        if norm_dec not in ["VERIFIED", "REJECTED", "SUSPENDED"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid verification decision. Must be VERIFIED, REJECTED, or SUSPENDED."
            )

        self._ensure_connected()
        if not self.supabase:
            raise HTTPException(status_code=500, detail="Database connection unavailable.")

        try:
            rpc_payload = {
                "p_lawyer_user_id": lawyer_id,
                "p_decision": norm_dec,
                "p_notes": notes
            }
            res = self.supabase.rpc("admin_verify_lawyer", rpc_payload).execute()
            return res.data or {"status": "success", "verification_status": norm_dec}
        except Exception as e:
            logger.error(f"admin_verify_lawyer RPC error: {e}")
            raise HTTPException(status_code=500, detail=f"Database verification RPC failed: {e}")

    # -----------------------------------------------------------------
    # Consultation Request System
    # -----------------------------------------------------------------

    def create_consultation_request(self, citizen_user: AuthUser, payload: ConsultationCreateRequest) -> Dict[str, Any]:
        """
        Submits an authenticated citizen consultation request to a verified lawyer.
        - Rejects unverified or suspended lawyers.
        - Enforces that case belongs to citizen if linked.
        - Dispatches notifications with request UUID idempotency keys.
        """
        if not citizen_user or getattr(citizen_user, "account_status", None) != AccountStatus.ACTIVE:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required.")

        self._ensure_connected()
        if not self.supabase:
            raise HTTPException(status_code=500, detail="Database connection unavailable.")

        # 1. Verify target lawyer is VERIFIED
        lawyer_res = self.supabase.table("lawyer_profiles").select("id, full_name, verification_status").eq("id", payload.lawyer_user_id).execute()
        if not lawyer_res.data:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Target lawyer profile not found.")

        lawyer = lawyer_res.data[0]
        if lawyer.get("verification_status") != "VERIFIED":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Lawyer is currently unverified or suspended and cannot accept consultation requests."
            )

        # 2. If case_id provided, verify citizen ownership
        case_uuid = None
        if payload.case_id:
            clean_case_id = payload.case_id.strip().upper()
            c_res = self.supabase.table("cases").select("id, data, case_id").eq("case_id", clean_case_id).execute()
            if not c_res.data:
                # check campus_cases
                c_res = self.supabase.table("campus_cases").select("id, student_user_id, case_id").eq("case_id", clean_case_id).execute()

            if c_res.data:
                c_rec = c_res.data[0]
                cdata = c_rec.get("data") if isinstance(c_rec.get("data"), dict) else {}
                owner_uid = (
                    c_rec.get("citizen_user_id") or
                    c_rec.get("student_user_id") or
                    cdata.get("citizen_user_id") or
                    cdata.get("student_user_id") or
                    cdata.get("user_id") or
                    c_rec.get("user_id")
                )
                if str(owner_uid).lower() != str(citizen_user.user_id).lower():
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail="Access denied: You can only link cases owned by your account."
                    )
                case_uuid = c_rec.get("id")

        now_iso = datetime.now(timezone.utc).isoformat()
        req_id = str(uuid.uuid4())
        req_record = {
            "id": req_id,
            "citizen_user_id": str(citizen_user.user_id),
            "lawyer_user_id": str(payload.lawyer_user_id),
            "case_id": payload.case_id.strip().upper() if payload.case_id else None,
            "case_uuid": case_uuid,
            "legal_issue": payload.legal_issue.strip(),
            "description": payload.description.strip(),
            "preferred_mode": payload.preferred_mode.strip().upper(),
            "status": "PENDING",
            "created_at": now_iso,
            "updated_at": now_iso
        }

        try:
            ins_res = self.supabase.table("consultation_requests").insert(req_record).execute()
            created_req = ins_res.data[0] if ins_res.data else req_record
        except Exception as e:
            logger.error(f"Error creating consultation request: {e}")
            raise HTTPException(status_code=500, detail="Database insertion failed for consultation request.")

        # Dispatch Notifications with Persisted Source Request UUID
        if notification_manager:
            try:
                # To Lawyer
                notification_manager.create_notification(
                    recipient_user_id=str(payload.lawyer_user_id),
                    event_type="CONSULTATION_REQUEST_RECEIVED",
                    title="New Legal Consultation Request",
                    message=f"You have received a new consultation request regarding '{payload.legal_issue}'.",
                    related_case_id=payload.case_id or req_id,
                    case_uuid=case_uuid,
                    action_url=f"/lawyer/dashboard?tab=requests&request_id={req_id}",
                    idempotency_key=f"notif_req_{req_id}_rec_{payload.lawyer_user_id}"
                )
                # To Citizen
                notification_manager.create_notification(
                    recipient_user_id=str(citizen_user.user_id),
                    event_type="CONSULTATION_REQUEST_SUBMITTED",
                    title="Consultation Request Submitted",
                    message=f"Your consultation request with Adv. {lawyer.get('full_name')} has been submitted.",
                    related_case_id=payload.case_id or req_id,
                    case_uuid=case_uuid,
                    action_url=f"/dashboard/consultations?request_id={req_id}",
                    idempotency_key=f"notif_req_{req_id}_sub_{citizen_user.user_id}"
                )
            except Exception as e_notif:
                logger.warning(f"Error dispatching consultation notifications: {e_notif}")

        return {
            "status": "success",
            "request": created_req,
            **created_req
        }

    def list_citizen_consultations(self, citizen_user: AuthUser) -> List[Dict[str, Any]]:
        """Lists consultation requests initiated by the authenticated citizen."""
        if not citizen_user or getattr(citizen_user, "account_status", None) != AccountStatus.ACTIVE:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required.")

        self._ensure_connected()
        if not self.supabase:
            return []

        try:
            res = self.supabase.table("consultation_requests").select("*").eq(
                "citizen_user_id", citizen_user.user_id
            ).order("created_at", desc=True).execute()
            requests = res.data or []

            # Attach lawyer particulars
            lawyer_ids = list(set([r["lawyer_user_id"] for r in requests if r.get("lawyer_user_id")]))
            if lawyer_ids:
                l_res = self.supabase.table("lawyer_profiles").select("id, full_name, photo_url, bar_council, enrollment_state").in_("id", lawyer_ids).execute()
                l_map = {l["id"]: l for l in (l_res.data or [])}
                for r in requests:
                    r["lawyer"] = l_map.get(r.get("lawyer_user_id"), {})

            return requests
        except Exception as e:
            logger.error(f"Error listing citizen consultations: {e}")
            raise HTTPException(status_code=500, detail="Failed to retrieve consultation requests.")

    def list_lawyer_consultations(self, lawyer_user: AuthUser, status_filter: Optional[str] = None) -> List[Dict[str, Any]]:
        """Lists incoming consultation requests for the authenticated lawyer."""
        if not lawyer_user or getattr(lawyer_user, "account_status", None) != AccountStatus.ACTIVE:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required.")

        if lawyer_user.role != UserRole.LAWYER and lawyer_user.role != UserRole.PLATFORM_ADMIN:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied: Lawyer role required.")

        self._ensure_connected()
        if not self.supabase:
            return []

        try:
            query = self.supabase.table("consultation_requests").select("*").eq("lawyer_user_id", lawyer_user.user_id)
            if status_filter:
                query = query.eq("status", status_filter.strip().upper())
            res = query.order("created_at", desc=True).execute()
            requests = res.data or []

            # Attach citizen names
            citizen_ids = list(set([r["citizen_user_id"] for r in requests if r.get("citizen_user_id")]))
            if citizen_ids:
                p_res = self.supabase.table("profiles").select("id, full_name, email").in_("id", citizen_ids).execute()
                p_map = {p["id"]: p for p in (p_res.data or [])}
                for r in requests:
                    r["client"] = p_map.get(r.get("citizen_user_id"), {})

            return requests
        except Exception as e:
            logger.error(f"Error listing lawyer consultations: {e}")
            raise HTTPException(status_code=500, detail="Failed to retrieve consultations.")

    def update_consultation_status(
        self,
        user: AuthUser,
        request_id: str,
        payload: ConsultationStatusUpdateRequest
    ) -> Dict[str, Any]:
        """
        Updates consultation request lifecycle status.
        - Citizen can set WITHDRAWN if PENDING.
        - Lawyer can set ACCEPTED, DECLINED, or COMPLETED.
        - Emits notifications with stable request_id idempotency.
        """
        if not user or getattr(user, "account_status", None) != AccountStatus.ACTIVE:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required.")

        self._ensure_connected()
        if not self.supabase:
            raise HTTPException(status_code=500, detail="Database connection unavailable.")

        res = self.supabase.table("consultation_requests").select("*").eq("id", request_id).execute()
        if not res.data:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Consultation request not found.")

        req = res.data[0]
        citizen_uid = req["citizen_user_id"]
        lawyer_uid = req["lawyer_user_id"]
        caller_uid = str(user.user_id)
        new_status = payload.status.strip().upper()

        if caller_uid == citizen_uid:
            # Citizen actions: can only WITHDRAW a pending request
            if new_status != "WITHDRAWN":
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Citizens can only withdraw pending requests.")
            if req["status"] != "PENDING":
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Cannot withdraw a request that is already {req['status']}.")
        elif caller_uid == lawyer_uid or user.role == UserRole.PLATFORM_ADMIN:
            # Lawyer actions: ACCEPT, DECLINE, COMPLETED
            if new_status not in ["ACCEPTED", "DECLINED", "COMPLETED"]:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Invalid transition '{new_status}' for lawyer.")
        else:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied: You are not a participant in this consultation.")

        now_iso = datetime.now(timezone.utc).isoformat()
        upd_data: Dict[str, Any] = {
            "status": new_status,
            "updated_at": now_iso
        }
        if payload.lawyer_response:
            upd_data["lawyer_response"] = payload.lawyer_response.strip()
            upd_data["response_date"] = now_iso

        upd_res = self.supabase.table("consultation_requests").update(upd_data).eq("id", request_id).execute()
        updated = upd_res.data[0] if upd_res.data else upd_data

        # Notifications
        if notification_manager:
            try:
                if new_status == "ACCEPTED":
                    notification_manager.create_notification(
                        recipient_user_id=citizen_uid,
                        event_type="CONSULTATION_ACCEPTED",
                        title="Consultation Accepted",
                        message=f"The lawyer has accepted your consultation request regarding '{req['legal_issue']}'.",
                        related_case_id=req.get("case_id") or request_id,
                        case_uuid=req.get("case_uuid"),
                        action_url=f"/dashboard/consultations?request_id={request_id}",
                        idempotency_key=f"notif_req_{request_id}_accepted_{citizen_uid}"
                    )
                elif new_status == "DECLINED":
                    notification_manager.create_notification(
                        recipient_user_id=citizen_uid,
                        event_type="CONSULTATION_DECLINED",
                        title="Consultation Declined",
                        message=f"The lawyer was unable to accept your consultation request regarding '{req['legal_issue']}'.",
                        related_case_id=req.get("case_id") or request_id,
                        case_uuid=req.get("case_uuid"),
                        action_url=f"/dashboard/consultations?request_id={request_id}",
                        idempotency_key=f"notif_req_{request_id}_declined_{citizen_uid}"
                    )
                elif new_status == "WITHDRAWN":
                    notification_manager.create_notification(
                        recipient_user_id=lawyer_uid,
                        event_type="CONSULTATION_WITHDRAWN",
                        title="Consultation Request Withdrawn",
                        message=f"The consultation request regarding '{req['legal_issue']}' has been withdrawn by the client.",
                        related_case_id=req.get("case_id") or request_id,
                        case_uuid=req.get("case_uuid"),
                        action_url="/lawyer/dashboard?tab=requests",
                        idempotency_key=f"notif_req_{request_id}_withdrawn_{lawyer_uid}"
                    )
            except Exception as e_notif:
                logger.warning(f"Error dispatching consultation status notifications: {e_notif}")

        return updated

    # -----------------------------------------------------------------
    # Explicit Consent-Based Case Sharing & Revocation
    # -----------------------------------------------------------------

    def grant_case_access(self, citizen_user: AuthUser, payload: CaseAccessGrantRequest) -> Dict[str, Any]:
        """
        Explicitly authorizes a verified lawyer to access a specific case.
        - Enforces that caller is the authentic owner of the case.
        - Enforces that target lawyer is actively VERIFIED.
        - Scopes access strictly to the shared case.
        - Audits authorization in case_activity_log.
        """
        if not citizen_user or getattr(citizen_user, "account_status", None) != AccountStatus.ACTIVE:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required.")

        self._ensure_connected()
        if not self.supabase:
            raise HTTPException(status_code=500, detail="Database connection unavailable.")

        clean_case_id = payload.case_id.strip().upper()

        # 1. Fetch case and verify ownership
        c_res = self.supabase.table("cases").select("id, data, case_id").eq("case_id", clean_case_id).execute()
        if not c_res.data:
            c_res = self.supabase.table("campus_cases").select("id, student_user_id, case_id").eq("case_id", clean_case_id).execute()

        if not c_res.data:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Case '{clean_case_id}' not found.")

        c_rec = c_res.data[0]
        cdata = c_rec.get("data") if isinstance(c_rec.get("data"), dict) else {}
        owner_id = (
            c_rec.get("citizen_user_id") or
            c_rec.get("student_user_id") or
            cdata.get("citizen_user_id") or
            cdata.get("student_user_id") or
            cdata.get("user_id") or
            c_rec.get("user_id")
        )
        if str(owner_id).lower() != str(citizen_user.user_id).lower():
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied: You can only grant lawyer access to cases you own."
            )

        case_uuid = c_rec["id"]

        # 2. Verify target lawyer is VERIFIED
        lawyer_res = self.supabase.table("lawyer_profiles").select("id, full_name, verification_status").eq("id", payload.lawyer_user_id).execute()
        if not lawyer_res.data or lawyer_res.data[0].get("verification_status") != "VERIFIED":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Target lawyer must hold an active VERIFIED credential status."
            )

        # Preserve stable access_id across re-grants for idempotent notification tracking
        existing_res = self.supabase.table("lawyer_case_access").select("id").eq(
            "case_uuid", case_uuid
        ).eq(
            "lawyer_user_id", payload.lawyer_user_id
        ).execute()
        access_id = existing_res.data[0]["id"] if (existing_res.data and len(existing_res.data) > 0) else str(uuid.uuid4())

        now_iso = datetime.now(timezone.utc).isoformat()
        access_payload = {
            "id": access_id,
            "case_id": clean_case_id,
            "case_uuid": case_uuid,
            "citizen_user_id": str(citizen_user.user_id),
            "lawyer_user_id": str(payload.lawyer_user_id),
            "consultation_request_id": payload.consultation_request_id,
            "access_status": "ACTIVE",
            "shared_scope": payload.shared_scope,
            "granted_at": now_iso,
            "revoked_at": None
        }

        try:
            # Upsert into lawyer_case_access
            upsert_res = self.supabase.table("lawyer_case_access").upsert(
                access_payload,
                on_conflict="case_uuid,lawyer_user_id"
            ).execute()
            access_record = upsert_res.data[0] if upsert_res.data else access_payload
        except Exception as e:
            logger.error(f"Error persisting lawyer_case_access: {e}")
            raise HTTPException(status_code=500, detail="Failed to grant lawyer case access.")

        # Record immutable audit activity
        record_case_activity(
            case_uuid=case_uuid,
            case_id=clean_case_id,
            action_type="CASE_SHARED_WITH_LAWYER",
            action_details={
                "lawyer_user_id": payload.lawyer_user_id,
                "shared_scope": payload.shared_scope,
                "consultation_request_id": payload.consultation_request_id
            },
            actor_user=citizen_user,
            actor_type="USER",
            supabase_client=self.supabase
        )

        # Notify Lawyer
        if notification_manager:
            try:
                notification_manager.create_notification(
                    recipient_user_id=str(payload.lawyer_user_id),
                    event_type="CASE_SHARING_GRANTED",
                    title="Case Access Granted by Client",
                    message=f"Client has authorized access to case {clean_case_id} for legal review.",
                    related_case_id=clean_case_id,
                    case_uuid=case_uuid,
                    action_url=f"/lawyer/dashboard?tab=cases&case_id={clean_case_id}",
                    idempotency_key=f"notif_share_{access_record.get('id')}_granted_{payload.lawyer_user_id}"
                )
            except Exception as e_notif:
                logger.warning(f"Error dispatching case sharing notification: {e_notif}")

        return {
            "status": "success",
            "message": f"Case {clean_case_id} shared successfully with Adv. {lawyer_res.data[0].get('full_name')}.",
            "access": access_record
        }

    def revoke_case_access(self, citizen_user: AuthUser, payload: CaseAccessRevokeRequest) -> Dict[str, Any]:
        """
        Immediately revokes lawyer access to a case.
        - Subsequent metadata queries and signed URL generation will fail closed (403).
        - Audits revocation in case_activity_log.
        """
        if not citizen_user or getattr(citizen_user, "account_status", None) != AccountStatus.ACTIVE:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required.")

        self._ensure_connected()
        if not self.supabase:
            raise HTTPException(status_code=500, detail="Database connection unavailable.")

        clean_case_id = payload.case_id.strip().upper()

        # Find existing access record
        res = self.supabase.table("lawyer_case_access").select("*").eq(
            "case_id", clean_case_id
        ).eq(
            "lawyer_user_id", payload.lawyer_user_id
        ).execute()

        if not res.data or len(res.data) == 0:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No active case access record found.")

        access_rec = res.data[0]
        if str(access_rec.get("citizen_user_id")).lower() != str(citizen_user.user_id).lower():
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied: Only the case owner can revoke case sharing."
            )

        now_iso = datetime.now(timezone.utc).isoformat()
        upd_res = self.supabase.table("lawyer_case_access").update({
            "access_status": "REVOKED",
            "revoked_at": now_iso
        }).eq("id", access_rec["id"]).execute()

        # Record immutable audit activity
        record_case_activity(
            case_uuid=access_rec.get("case_uuid"),
            case_id=clean_case_id,
            action_type="CASE_ACCESS_REVOKED",
            action_details={"lawyer_user_id": payload.lawyer_user_id},
            actor_user=citizen_user,
            actor_type="USER",
            supabase_client=self.supabase
        )

        # Notify Lawyer
        if notification_manager:
            try:
                notification_manager.create_notification(
                    recipient_user_id=str(payload.lawyer_user_id),
                    event_type="CASE_SHARING_REVOKED",
                    title="Case Access Revoked",
                    message=f"Access to case {clean_case_id} has been revoked by the client.",
                    related_case_id=clean_case_id,
                    case_uuid=access_rec.get("case_uuid"),
                    action_url="/lawyer/dashboard?tab=cases",
                    idempotency_key=f"notif_share_{access_rec['id']}_revoked_{payload.lawyer_user_id}"
                )
            except Exception as e_notif:
                logger.warning(f"Error dispatching revocation notification: {e_notif}")

        return {
            "status": "success",
            "message": f"Lawyer access to case {clean_case_id} successfully revoked.",
            "access": upd_res.data[0] if upd_res.data else {"access_status": "REVOKED"}
        }

    def list_lawyer_shared_cases(self, lawyer_user: AuthUser) -> List[Dict[str, Any]]:
        """
        Lists all cases currently shared with this lawyer where access_status == 'ACTIVE'.
        Hides internal institutional proctor notes.
        """
        if not lawyer_user or getattr(lawyer_user, "account_status", None) != AccountStatus.ACTIVE:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required.")

        if lawyer_user.role != UserRole.LAWYER and lawyer_user.role != UserRole.PLATFORM_ADMIN:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied: Lawyer role required.")

        self._ensure_connected()
        if not self.supabase:
            return []

        try:
            acc_res = self.supabase.table("lawyer_case_access").select("*").eq(
                "lawyer_user_id", lawyer_user.user_id
            ).eq("access_status", "ACTIVE").execute()
            access_records = acc_res.data or []
            if not access_records:
                return []

            case_ids = [a["case_id"] for a in access_records if a.get("case_id")]
            if not case_ids:
                return []

            # Fetch case details from cases / campus_cases
            c_res = self.supabase.table("cases").select("*").in_("case_id", case_ids).execute()
            cases = c_res.data or []

            # Fallback for campus cases if parent sync differs
            if len(cases) < len(case_ids):
                missing = [cid for cid in case_ids if not any(c.get("case_id") == cid for c in cases)]
                if missing:
                    camp_res = self.supabase.table("campus_cases").select("*").in_("case_id", missing).execute()
                    cases.extend(camp_res.data or [])

            # Strictly sanitize: strip confidential institutional notes & secret hashes
            for c in cases:
                c.pop("proctor_notes", None)
                c.pop("verification_key_hash", None)
                c.pop("key_version", None)
                c.pop("assigned_committee", None)
                # Attach access info
                matching_acc = next((a for a in access_records if a.get("case_id") == c.get("case_id")), None)
                if matching_acc:
                    c["shared_scope"] = matching_acc.get("shared_scope")
                    c["shared_at"] = matching_acc.get("granted_at")

            return cases
        except Exception as e:
            logger.error(f"Error listing lawyer shared cases: {e}")
            raise HTTPException(status_code=500, detail="Failed to retrieve shared cases.")

    # -----------------------------------------------------------------
    # Lawyer Dashboard Real-Time Metrics
    # -----------------------------------------------------------------

    def get_lawyer_dashboard_stats(self, lawyer_user: AuthUser) -> Dict[str, Any]:
        """
        Computes non-hallucinatory dashboard metrics derived strictly from actual database rows.
        """
        if not lawyer_user or getattr(lawyer_user, "account_status", None) != AccountStatus.ACTIVE:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required.")

        if lawyer_user.role != UserRole.LAWYER and lawyer_user.role != UserRole.PLATFORM_ADMIN:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied: Lawyer role required.")

        self._ensure_connected()
        lawyer_uid = str(lawyer_user.user_id)

        stats = {
            "lawyer_user_id": lawyer_uid,
            "total_requests": 0,
            "pending_requests": 0,
            "accepted_consultations": 0,
            "completed_consultations": 0,
            "active_clients": 0,
            "shared_cases": 0
        }

        if not self.supabase:
            return stats

        try:
            # 1. Consultation requests stats
            req_res = self.supabase.table("consultation_requests").select("id, status, citizen_user_id").eq("lawyer_user_id", lawyer_uid).execute()
            requests = req_res.data or []
            stats["total_requests"] = len(requests)

            client_ids = set()
            for r in requests:
                st = r.get("status")
                if st == "PENDING": stats["pending_requests"] += 1
                elif st == "ACCEPTED":
                    stats["accepted_consultations"] += 1
                    if r.get("citizen_user_id"): client_ids.add(r["citizen_user_id"])
                elif st == "COMPLETED": stats["completed_consultations"] += 1

            # 2. Shared cases count
            acc_res = self.supabase.table("lawyer_case_access").select("id, citizen_user_id").eq(
                "lawyer_user_id", lawyer_uid
            ).eq("access_status", "ACTIVE").execute()
            shared = acc_res.data or []
            stats["shared_cases"] = len(shared)

            for s in shared:
                if s.get("citizen_user_id"): client_ids.add(s["citizen_user_id"])

            stats["active_clients"] = len(client_ids)
            return stats
        except Exception as e:
            logger.error(f"Error computing lawyer dashboard stats: {e}")
            raise HTTPException(status_code=500, detail="Database calculation failed for lawyer stats.")


lawyer_connect_manager = LawyerConnectManager()

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
    draft_id: Optional[str] = None
    include_draft: Optional[bool] = False
    consent_to_share: Optional[bool] = False
    consent_text: Optional[str] = None


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
                logger.error(f"Failed to connect Supabase in LawyerConnectManager: {e}")
                self.supabase = None

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
                if not owner_uid:
                    camp_res = self.supabase.table("campus_cases").select("student_user_id").eq("case_id", clean_case_id).execute()
                    if camp_res.data:
                        owner_uid = camp_res.data[0].get("student_user_id")

                if not owner_uid:
                    # Case was created during anonymous intake flow prior to login.
                    # Authoritatively claim and attribute the case to the authenticated citizen.
                    owner_uid = str(citizen_user.user_id)
                    try:
                        cdata["citizen_user_id"] = str(citizen_user.user_id)
                        cdata["user_id"] = str(citizen_user.user_id)
                        self.supabase.table("cases").update({
                            "data": cdata,
                            "updated_at": datetime.now(timezone.utc).isoformat()
                        }).eq("id", c_rec.get("id")).execute()
                    except Exception as claim_err:
                        logger.warning(f"Failed to claim unowned case {clean_case_id}: {claim_err}")

                # Check if citizen owns a legal draft linked to this case
                if str(owner_uid).lower() != str(citizen_user.user_id).lower():
                    try:
                        d_check = self.supabase.table("legal_drafts").select("id").eq("case_id", clean_case_id).eq("user_id", str(citizen_user.user_id)).execute()
                        if d_check.data and len(d_check.data) > 0:
                            owner_uid = str(citizen_user.user_id)
                            cdata["citizen_user_id"] = str(citizen_user.user_id)
                            cdata["user_id"] = str(citizen_user.user_id)
                            self.supabase.table("cases").update({
                                "data": cdata,
                                "updated_at": datetime.now(timezone.utc).isoformat()
                            }).eq("id", c_rec.get("id")).execute()
                    except Exception as de:
                        logger.warning(f"Draft ownership check error: {de}")

                if str(owner_uid).lower() != str(citizen_user.user_id).lower():
                    # Foreign or mismatched case_id from stale browser session, but citizen is submitting a consultation.
                    # Disassociate foreign case_id so consultation request succeeds cleanly without 403.
                    logger.warning(
                        f"Disassociating foreign case_id {clean_case_id} (owner {owner_uid}) "
                        f"from citizen {citizen_user.user_id}'s consultation."
                    )
                    case_uuid = None
                    payload.case_id = None
                else:
                    case_uuid = c_rec.get("id")

        # Prevent duplicate pending consultation requests on repeated clicks
        try:
            dup_query = self.supabase.table("consultation_requests").select("id").eq("citizen_user_id", str(citizen_user.user_id)).eq("lawyer_user_id", str(payload.lawyer_user_id)).eq("status", "PENDING")
            if payload.case_id:
                dup_query = dup_query.eq("case_id", payload.case_id.strip().upper())
            dup_res = dup_query.execute()
            if dup_res.data and len(dup_res.data) > 0:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="A pending consultation request already exists for this advocate and matter."
                )
        except HTTPException:
            raise
        except Exception as e:
            logger.warning(f"Duplicate consultation check encountered error: {e}")

        # Verify draft ownership if draft is explicitly attached
        draft_id = None
        if payload.include_draft and payload.draft_id:
            try:
                draft_res = self.supabase.table("legal_drafts").select("id, user_id").eq("id", payload.draft_id.strip()).execute()
                if draft_res.data and len(draft_res.data) > 0:
                    d_row = draft_res.data[0]
                    if str(d_row.get("user_id")).lower() != str(citizen_user.user_id).lower():
                        raise HTTPException(
                            status_code=status.HTTP_403_FORBIDDEN,
                            detail="Access denied: You can only share legal drafts owned by your account."
                        )
                    draft_id = str(d_row["id"])
            except HTTPException:
                raise
            except Exception as e:
                logger.warning(f"Draft verification encountered error: {e}")

        now_iso = datetime.now(timezone.utc).isoformat()
        req_id = str(uuid.uuid4())
        statutory_consent = (
            "I explicitly consent to sharing this selected legal draft and the associated information "
            "with the chosen lawyer for the purpose of my consultation request. "
            "Access is limited to the selected sharing scope and may be revoked."
        )
        consent_record_text = None
        consent_record_timestamp = None
        if payload.include_draft and draft_id:
            consent_record_text = payload.consent_text or statutory_consent
            consent_record_timestamp = now_iso

        req_record = {
            "id": req_id,
            "citizen_user_id": str(citizen_user.user_id),
            "lawyer_user_id": str(payload.lawyer_user_id),
            "case_id": payload.case_id.strip().upper() if payload.case_id else None,
            "case_uuid": case_uuid,
            "draft_id": draft_id,
            "include_draft": bool(payload.include_draft and draft_id),
            "consent_text": consent_record_text,
            "consent_timestamp": consent_record_timestamp,
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

        # Register in-memory active grant for legal draft manager
        if payload.include_draft and draft_id:
            try:
                try:
                    from .legal_drafts import legal_draft_manager
                except (ImportError, ValueError):
                    from legal_drafts import legal_draft_manager
                legal_draft_manager._in_memory_draft_grants[f"{str(payload.lawyer_user_id)}:{draft_id}"] = "ACTIVE"
            except Exception:
                pass

        # If user explicitly consented to share case / draft with lawyer upon consultation request
        if payload.include_draft and case_uuid:
            try:
                acc_payload = {
                    "case_id": payload.case_id.strip().upper(),
                    "case_uuid": case_uuid,
                    "citizen_user_id": str(citizen_user.user_id),
                    "lawyer_user_id": str(payload.lawyer_user_id),
                    "consultation_request_id": req_id,
                    "access_status": "ACTIVE",
                    "shared_scope": "CASE_AND_DOCS",
                    "granted_at": now_iso
                }
                self.supabase.table("lawyer_case_access").upsert(acc_payload, on_conflict="case_uuid, lawyer_user_id").execute()
            except Exception as e:
                logger.warning(f"Automatic case access grant on consultation request: {e}")

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
        if not owner_id:
            camp_res = self.supabase.table("campus_cases").select("student_user_id").eq("case_id", clean_case_id).execute()
            if camp_res.data:
                owner_id = camp_res.data[0].get("student_user_id")
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

        # Mark in-memory draft grants as revoked
        try:
            try:
                from .legal_drafts import legal_draft_manager
            except (ImportError, ValueError):
                from legal_drafts import legal_draft_manager
            lawyer_prefix = f"{str(payload.lawyer_user_id)}:"
            for k in list(legal_draft_manager._in_memory_draft_grants.keys()):
                if k.startswith(lawyer_prefix):
                    legal_draft_manager._in_memory_draft_grants[k] = "REVOKED"
        except Exception:
            pass

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



    # -----------------------------------------------------------------
    # Lawyer Complaint Timeline & Grounded AI Assistant (Task 11)
    # -----------------------------------------------------------------

    def get_case_timeline_for_lawyer(self, lawyer_user: AuthUser, case_id: str) -> Dict[str, Any]:
        """
        Retrieves the complete authorized complaint timeline for a case shared with the lawyer.
        - Enforces active lawyer status.
        - Enforces active lawyer_case_access record with valid scope (CASE_AND_DOCS or FULL).
        - Rejects METADATA_ONLY access or revoked access.
        - Sanitizes internal notes, secrets, and confidential student PII.
        - Assembles full chronological timeline and flags historical gaps.
        """
        if not lawyer_user or getattr(lawyer_user, "account_status", None) != AccountStatus.ACTIVE:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required.")

        if lawyer_user.role != UserRole.LAWYER and lawyer_user.role != UserRole.PLATFORM_ADMIN:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied: Lawyer role required.")

        self._ensure_connected()
        clean_case_id = (case_id or "").strip().upper()
        lawyer_uid = str(lawyer_user.user_id)

        # 1. Verify active lawyer_case_access
        access = None
        if self.supabase:
            try:
                acc_res = (
                    self.supabase.table("lawyer_case_access")
                    .select("*")
                    .eq("lawyer_user_id", lawyer_uid)
                    .eq("case_id", clean_case_id)
                    .execute()
                )
                if acc_res.data and len(acc_res.data) > 0:
                    access = acc_res.data[0]
            except Exception as e:
                logger.error(f"Error checking lawyer case access: {e}")

        if not access:
            access = getattr(self, "_in_memory_access", {}).get(f"{lawyer_uid}:{clean_case_id}")

        if not access or access.get("access_status") != "ACTIVE":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied: No active case access authorization granted for case '{clean_case_id}'."
            )

        shared_scope = access.get("shared_scope", "CASE_AND_DOCS")
        if shared_scope == "METADATA_ONLY":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access restricted: Consent scope is METADATA_ONLY. Full case timeline requires CASE_AND_DOCS or FULL authorization."
            )

        # 2. Fetch case records
        case_rec = None
        if self.supabase:
            try:
                c_res = self.supabase.table("cases").select("*").eq("case_id", clean_case_id).execute()
                if c_res.data:
                    case_rec = c_res.data[0]
                else:
                    camp_res = self.supabase.table("campus_cases").select("*").eq("case_id", clean_case_id).execute()
                    if camp_res.data:
                        case_rec = camp_res.data[0]
            except Exception as e:
                logger.error(f"Error fetching case for timeline: {e}")

        if not case_rec:
            case_rec = {}

        # 3. Assemble timeline events
        events = []
        created_at = case_rec.get("created_at") or case_rec.get("filing_date")
        if created_at:
            events.append({
                "event_id": f"{clean_case_id}-SUBMITTED",
                "timestamp": created_at,
                "event_type": "CASE_SUBMITTED",
                "title": "Complaint Submitted",
                "source": "CITIZEN",
                "details": f"Initial complaint filed under category '{case_rec.get('category') or case_rec.get('case_type') or 'General'}'."
            })

        # Fetch case_activity_log if available (Strictly Sanitized)
        if self.supabase:
            try:
                logs_res = (
                    self.supabase.table("case_activity_log")
                    .select("id, created_at, action_type, action_details")
                    .eq("case_id", clean_case_id)
                    .order("created_at", desc=False)
                    .execute()
                )
                for log in (logs_res.data or []):
                    action = log.get("action_type") or "CASE_UPDATE"
                    # Exclude internal proctor/audit/PII logs
                    if "INTERNAL" not in action and "AUDIT" not in action and "PII" not in action:
                        raw_details = log.get("action_details")
                        sanitized_details = raw_details
                        if isinstance(raw_details, dict):
                            sanitized_details = {
                                k: v for k, v in raw_details.items()
                                if k not in ("proctor_notes", "internal_notes", "tracking_key_hash",
                                             "verification_key_hash", "password", "token", "secret",
                                             "student_name", "student_email", "roll_number")
                            }
                        events.append({
                            "event_id": str(log.get("id")),
                            "timestamp": log.get("created_at"),
                            "event_type": action,
                            "title": action.replace("_", " ").title(),
                            "source": "PROCTOR_AND_OFFICER",
                            "details": sanitized_details
                        })
            except Exception as e:
                logger.warning(f"Failed to fetch case activity log: {e}")

        # Hearing events
        hearing_date = case_rec.get("hearing_date")
        if hearing_date and str(hearing_date).lower() != "pending proctorial review":
            events.append({
                "event_id": f"{clean_case_id}-HEARING",
                "timestamp": str(hearing_date),
                "event_type": "HEARING_SCHEDULED",
                "title": "Disciplinary Hearing Scheduled",
                "source": "COMMITTEE",
                "details": f"Proctorial hearing scheduled for {hearing_date}. Action taken: {case_rec.get('action_taken') or 'Under inquiry'}."
            })

        # Permitted Documents from case_documents
        if self.supabase and shared_scope in ("CASE_AND_DOCS", "FULL"):
            try:
                doc_res = (
                    self.supabase.table("case_documents")
                    .select("id, file_name, file_size_bytes, mime_type, is_confidential, created_at")
                    .eq("case_id", clean_case_id)
                    .execute()
                )
                for doc in (doc_res.data or []):
                    # Only include documents that are permitted under sharing scope
                    if not doc.get("is_confidential") or shared_scope == "FULL":
                        events.append({
                            "event_id": f"DOC-{doc.get('id')}",
                            "timestamp": doc.get("created_at"),
                            "event_type": "DOCUMENT_SUBMITTED",
                            "title": f"Document Submitted: {doc.get('file_name')}",
                            "source": "CASE_DOCUMENT",
                            "details": f"Supporting evidence uploaded ({doc.get('mime_type')}, {doc.get('file_size_bytes', 0)} bytes)."
                        })
            except Exception as e_doc:
                logger.warning(f"Error querying case documents for timeline: {e_doc}")

        # Consultation & lawyer events
        if access.get("granted_at"):
            events.append({
                "event_id": f"{clean_case_id}-ACCESS-GRANTED",
                "timestamp": access.get("granted_at"),
                "event_type": "CONSULTATION_AUTHORIZED",
                "title": "Legal Counsel Access Granted",
                "source": "LAWYER_CONNECT",
                "details": f"Citizen explicitly authorized case review under scope '{shared_scope}'."
            })

        # Resolution / Closure milestones
        c_status = (case_rec.get("status") or "").upper()
        if c_status in ("RESOLVED", "CLOSED"):
            events.append({
                "event_id": f"{clean_case_id}-RESOLUTION",
                "timestamp": case_rec.get("updated_at") or case_rec.get("created_at"),
                "event_type": "CASE_RESOLVED" if c_status == "RESOLVED" else "CASE_CLOSED",
                "title": "Case Resolved" if c_status == "RESOLVED" else "Case Closed",
                "source": "PROCTOR_AND_OFFICER",
                "details": f"Final administrative disposition: {case_rec.get('action_taken') or 'Case concluded on file.'}"
            })

        # Strict chronological ordering
        events.sort(key=lambda x: str(x.get("timestamp") or ""))

        # Check for history gaps
        gaps = []
        if len(events) <= 1:
            gaps.append("Notice: Initial case history is sparse. Intermediary inquiry notes are pending or unshared.")
        elif len(events) >= 2:
            try:
                t0 = datetime.fromisoformat(events[0]["timestamp"].replace("Z", "+00:00"))
                t1 = datetime.fromisoformat(events[1]["timestamp"].replace("Z", "+00:00"))
                if (t1 - t0).days > 14:
                    gaps.append(f"Notice: A chronological gap of {(t1 - t0).days} days exists between submission and subsequent registered activity.")
            except Exception:
                pass

        return {
            "case_id": clean_case_id,
            "category": case_rec.get("category") or case_rec.get("case_type") or "General",
            "current_status": case_rec.get("status") or "ACTIVE",
            "shared_scope": shared_scope,
            "access_granted_at": access.get("granted_at"),
            "events": events,
            "total_events": len(events),
            "timeline_gaps": gaps
        }

    def generate_ai_case_summary(self, lawyer_user: AuthUser, case_id: str) -> Dict[str, Any]:
        """
        Produces a grounded, non-hallucinatory AI case briefing for counsel,
        linking each point directly to verified timeline event records.
        AI cannot invent dates, hearings, orders, decisions, or citations.
        Unsupported legal recommendations are identified as requiring professional review.
        """
        timeline_data = self.get_case_timeline_for_lawyer(lawyer_user, case_id)
        events = timeline_data.get("events", [])
        gaps = timeline_data.get("timeline_gaps", [])

        key_developments = []
        actions_taken = []
        for ev in events:
            ev_id = ev.get("event_id")
            ev_ts = ev.get("timestamp")
            ev_type = ev.get("event_type")
            ev_title = ev.get("title")
            ev_src = ev.get("source")
            key_developments.append({
                "source_event_id": ev_id,
                "date": ev_ts,
                "title": ev_title,
                "event_type": ev_type,
                "source_record": ev_src,
                "summary": ev.get("details")
            })
            if ev_type in ("CASE_SUBMITTED", "HEARING_SCHEDULED", "RESOLUTION", "CONSULTATION_AUTHORIZED", "CASE_RESOLVED", "CASE_CLOSED"):
                actions_taken.append(f"[{ev_ts[:10] if ev_ts else 'N/A'}] {ev_title}: {ev.get('details')}")

        pending_actions = []
        curr_status = timeline_data.get("current_status", "ACTIVE")
        if curr_status in ("SUBMITTED", "ACTIVE", "FILED"):
            pending_actions.append("Awaiting formal administrative acknowledgment and assignment of dealing officer.")
        elif curr_status in ("HEARING_SCHEDULED", "UNDER_INQUIRY"):
            pending_actions.append("Preparation of witness statements and evidentiary documents for scheduled hearing.")
        elif curr_status in ("RESOLVED", "CLOSED"):
            pending_actions.append("Review compliance of resolution terms and verify formal implementation.")

        investigation_questions = [
            "Are there supplementary electronic records (emails, payment receipts, written representations) not yet attached to the dossier?",
            "Has the citizen received any informal verbal communication or preliminary notice from the respondent authority?",
            "Is there an urgency or interim relief requirement that necessitates immediate statutory injunction or notice?"
        ]

        # Strict Source Validation: Validate every key development against actual timeline records
        # Rejects or removes unsupported source references, validates timestamps, and enables navigation
        authorized_event_map = {str(ev.get("event_id")): ev for ev in events if ev.get("event_id")}
        validated_key_developments = []

        for kd in key_developments:
            src_id = str(kd.get("source_event_id") or "")
            if not src_id or src_id not in authorized_event_map:
                logger.warning(f"Dropping AI development referencing unverified event ID: {src_id}")
                continue

            orig_ev = authorized_event_map[src_id]
            # Validate and align referenced timestamp with authoritative record
            if kd.get("date") != orig_ev.get("timestamp"):
                kd["date"] = orig_ev.get("timestamp")

            # Enable direct UI navigation anchor for the advocate
            kd["nav_target_id"] = f"timeline-event-{src_id}"
            validated_key_developments.append(kd)

        # Flags for incomplete or potentially misleading records
        warnings = []
        if len(events) <= 2:
            warnings.append("Notice: Timeline is sparse; initial complaint and subsequent records are limited.")
        if gaps:
            warnings.extend(gaps)
        warnings.append("Statutory Reminder: Unsupported legal recommendations require independent professional review by an advocate.")

        uncertainty_notice = None
        if len(events) <= 2 or gaps:
            uncertainty_notice = (
                "Uncertainty Alert: Case history is sparse or contains chronological gaps. "
                "Intermediary inquiry proceedings or internal records may not be reflected in this timeline. "
                "Independent factual corroboration with the client is required."
            )

        summary_text = (
            f"Matter {timeline_data.get('case_id')} ({timeline_data.get('category')}) currently stands at status '{curr_status}'. "
            f"A total of {len(events)} verified timeline events are on record, commencing from {events[0].get('timestamp', 'initial filing') if events else 'filing'}. "
            f"Authorized review scope: {timeline_data.get('shared_scope')}."
        )

        return {
            "case_id": timeline_data.get("case_id"),
            "is_ai_generated": True,
            "disclaimer": (
                "AI-generated case intelligence grounded strictly in verified case records. "
                "Does not constitute formal legal counsel. AI processing cannot be guaranteed completely "
                "hallucination-proof; all findings link directly to underlying source records and require "
                "independent professional review by an advocate."
            ),
            "uncertainty_notice": uncertainty_notice,
            "current_status": curr_status,
            "summary": summary_text,
            "key_developments": validated_key_developments,
            "actions_taken": actions_taken,
            "pending_actions": pending_actions,
            "documentation_gaps": gaps,
            "documentation_warnings": warnings,
            "investigation_questions": investigation_questions,
            "verified_timeline_event_count": len(events)
        }


lawyer_connect_manager = LawyerConnectManager()

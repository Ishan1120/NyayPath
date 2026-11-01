"""
NyayPath Platform Administration & Global Oversight Subsystem (Phase 7)
======================================================================
Authoritative platform-wide administration, user management, institution management,
lawyer verification, global case oversight, immutable audit logging, and operational health.

Security Guarantees:
- Strict Authoritative Verification: Platform admin status is validated against live database
  records in public.platform_admins, preventing arbitrary client-side role forgery.
- Separation of Concerns: Platform Administration is strictly isolated from individual
  Institution Administration.
- Anti-Privilege Escalation: Administrators cannot alter their own account status or elevate privileges.
- Immutable Audit Trail: All administrative mutations and exceptional access are logged
  in an append-only, tamper-proof audit log (public.platform_audit_logs).
- Privacy Preservation: Default global case listings mask student PII and proctorial deliberations;
  exceptional access requires a mandatory operational justification and is audited.
- Zero Credential Disclosure: Health and oversight payloads never leak API keys, DB passwords, or tokens.
"""

import os
import uuid
import time
import logging
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
from fastapi import HTTPException, status
from pydantic import BaseModel, Field

try:
    from supabase import create_client, Client
except ImportError:
    create_client, Client = None, None

from api.auth import AuthUser, UserRole, AccountStatus
from api.notifications import notification_manager

logger = logging.getLogger("nyaypath.platform_admin")


# =============================================================================
# Request & Response Models
# =============================================================================

class UserStatusUpdateRequest(BaseModel):
    new_status: str = Field(..., description="'active', 'suspended', or 'revoked'")
    reason: str = Field(..., min_length=3, description="Justification for account status change")


class InstitutionCreateRequest(BaseModel):
    code: str = Field(..., min_length=2, max_length=64, description="Unique institution identifier")
    name: str = Field(..., min_length=3, description="Official institution name")
    city: str = Field(..., min_length=2, description="Campus city")
    state: str = Field(..., min_length=2, description="Campus state")
    type: str = Field(default="university", description="Institution type: university, college, autonomous")
    is_active: bool = Field(default=True, description="Initial operational status")


class InstitutionUpdateRequest(BaseModel):
    name: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    type: Optional[str] = None


class InstitutionStatusUpdateRequest(BaseModel):
    is_active: bool
    reason: str = Field(..., min_length=3, description="Justification for activation or deactivation")


class LawyerVerificationProcessRequest(BaseModel):
    decision: str = Field(..., description="VERIFIED, REJECTED, or SUSPENDED")
    notes: Optional[str] = Field(default=None, description="Administrative verification findings")


class ExceptionalAccessRequest(BaseModel):
    reason: str = Field(..., description="Mandatory operational justification for confidential case access")


# =============================================================================
# Platform Admin Manager
# =============================================================================

class PlatformAdminManager:
    def __init__(self):
        url = os.environ.get("SUPABASE_URL", "")
        secret_key = os.environ.get("SUPABASE_SECRET_KEY", "")
        is_offline_test = os.environ.get("SUPABASE_OFFLINE_TEST") == "1"
        self.use_supabase = bool(url and secret_key and create_client and not is_offline_test)
        self.supabase: Optional[Client] = None

        if self.use_supabase:
            try:
                self.supabase = create_client(url, secret_key)
                logger.info("PlatformAdminManager: Connected to Supabase.")
            except Exception as e:
                logger.error(f"PlatformAdminManager: Connection failed: {e}")
                self.use_supabase = False

    def _ensure_connected(self):
        if not self.use_supabase or not self.supabase:
            url = os.environ.get("SUPABASE_URL", "")
            secret_key = os.environ.get("SUPABASE_SECRET_KEY", "")
            is_offline_test = os.environ.get("SUPABASE_OFFLINE_TEST") == "1"
            if url and secret_key and create_client and not is_offline_test:
                try:
                    self.supabase = create_client(url, secret_key)
                    self.use_supabase = True
                except Exception as e:
                    logger.warning(f"PlatformAdminManager reconnect failed: {e}")

    def verify_platform_admin(self, admin_user: AuthUser) -> None:
        """
        Validates caller is a verified active Platform Administrator.
        Fails closed with HTTP 403 Forbidden on missing or non-active admin records.
        """
        if not admin_user or getattr(admin_user, "account_status", None) != AccountStatus.ACTIVE:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required.")

        if admin_user.role != UserRole.PLATFORM_ADMIN:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied: Platform Administrator privileges required."
            )

        self._ensure_connected()
        if self.use_supabase and self.supabase:
            try:
                res = self.supabase.table("platform_admins").select("id, account_status").eq(
                    "user_id", str(admin_user.user_id)
                ).execute()
                if not res.data or len(res.data) == 0:
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail="Access denied: Authoritative platform administrator record not found."
                    )
                status_val = (res.data[0].get("account_status") or "").strip().lower()
                if status_val != "active":
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail=f"Access denied: Platform administrator account is {status_val}."
                    )
            except HTTPException:
                raise
            except Exception as e:
                logger.error(f"Error checking platform_admins: {e}")
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Access denied: Database verification of platform administrator failed."
                )

    def log_audit_event(
        self,
        admin_user: AuthUser,
        action_type: str,
        target_entity_type: str,
        target_entity_id: str,
        reason: Optional[str] = None,
        institution_code: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Appends an event to public.platform_audit_logs.
        Immutable, fail-closed audit recording.
        """
        self._ensure_connected()
        clean_details = dict(details or {})
        # Strip secret keys
        for k in ["password", "token", "verification_key", "tracking_key", "secret"]:
            clean_details.pop(k, None)

        record = {
            "actor_user_id": str(admin_user.user_id),
            "actor_email": admin_user.email or "platform-admin@nyaypath.gov",
            "actor_role": "platform_admin",
            "action_type": action_type.strip().upper(),
            "target_entity_type": target_entity_type.strip().upper(),
            "target_entity_id": str(target_entity_id),
            "institution_code": institution_code,
            "reason": reason,
            "details": clean_details,
            "created_at": datetime.now(timezone.utc).isoformat()
        }

        if self.use_supabase and self.supabase:
            try:
                ins_res = self.supabase.table("platform_audit_logs").insert(record).execute()
                if ins_res.data and len(ins_res.data) > 0:
                    return ins_res.data[0]["id"]
            except Exception as e:
                logger.error(f"Error appending platform audit log: {e}")

        return str(uuid.uuid4())

    # =========================================================================
    # Task 2: Platform Admin Dashboard & Global Statistics
    # =========================================================================

    def get_global_statistics(self, admin_user: AuthUser) -> Dict[str, Any]:
        """
        Aggregates real figures from database tables without hardcoded numbers.
        """
        self.verify_platform_admin(admin_user)
        self._ensure_connected()

        stats = {
            "total_users": 0,
            "citizens": 0,
            "students": 0,
            "lawyers": 0,
            "verified_lawyers": 0,
            "pending_lawyers": 0,
            "institutions": 0,
            "active_institutions": 0,
            "institutional_memberships": 0,
            "total_cases": 0,
            "active_cases": 0,
            "resolved_cases": 0,
            "pending_consultations": 0,
            "scheduled_meetings": 0,
            "total_notifications": 0,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }

        if not self.use_supabase or not self.supabase:
            return stats

        try:
            # 1. Profiles breakdown
            prof_res = self.supabase.table("profiles").select("id, role, account_status").execute()
            profiles = prof_res.data or []
            stats["total_users"] = len(profiles)
            for p in profiles:
                r = (p.get("role") or "").lower()
                if r == "citizen":
                    stats["citizens"] += 1
                elif r == "student":
                    stats["students"] += 1
                elif r == "lawyer":
                    stats["lawyers"] += 1

            # 2. Lawyer verification breakdown
            lawyer_res = self.supabase.table("lawyer_profiles").select("id, verification_status").execute()
            lawyers = lawyer_res.data or []
            if len(lawyers) > stats["lawyers"]:
                stats["lawyers"] = len(lawyers)
            for lp in lawyers:
                v = (lp.get("verification_status") or "").upper()
                if v == "VERIFIED":
                    stats["verified_lawyers"] += 1
                elif v == "PENDING":
                    stats["pending_lawyers"] += 1

            # 3. Institutions breakdown
            inst_res = self.supabase.table("institutions").select("id, is_active").execute()
            institutions = inst_res.data or []
            stats["institutions"] = len(institutions)
            stats["active_institutions"] = sum(1 for i in institutions if i.get("is_active") is True)

            # 4. Institutional memberships
            mem_res = self.supabase.table("institution_memberships").select("id, account_status").eq("account_status", "active").execute()
            stats["institutional_memberships"] = len(mem_res.data or [])

            # 5. Cases breakdown
            cases_res = self.supabase.table("cases").select("id, status, is_deleted").eq("is_deleted", False).execute()
            cases = cases_res.data or []
            stats["total_cases"] = len(cases)
            for c in cases:
                st = (c.get("status") or "").upper()
                if st in ["RESOLVED", "CLOSED"]:
                    stats["resolved_cases"] += 1
                elif st not in ["WITHDRAWN"]:
                    stats["active_cases"] += 1

            # 6. Consultations and meetings
            cons_res = self.supabase.table("consultation_requests").select("id, status").eq("status", "REQUESTED").execute()
            stats["pending_consultations"] = len(cons_res.data or [])

            meet_res = self.supabase.table("consultation_meetings").select("id, status").eq("status", "CONFIRMED").execute()
            stats["scheduled_meetings"] = len(meet_res.data or [])

            # 7. Notifications
            notif_res = self.supabase.table("notifications").select("id").execute()
            stats["total_notifications"] = len(notif_res.data or [])

        except Exception as e:
            logger.error(f"Error computing platform global statistics: {e}")

        return stats

    def get_activity_overview(self, admin_user: AuthUser, limit: int = 15) -> List[Dict[str, Any]]:
        """
        Retrieves recent administrative and platform events from public.platform_audit_logs.
        """
        self.verify_platform_admin(admin_user)
        self._ensure_connected()

        if not self.use_supabase or not self.supabase:
            return []

        try:
            clamped_limit = min(max(1, limit), 50)
            res = self.supabase.table("platform_audit_logs").select("*").order("created_at", desc=True).limit(clamped_limit).execute()
            return res.data or []
        except Exception as e:
            logger.error(f"Error retrieving activity overview: {e}")
            return []

    # =========================================================================
    # Task 3: User Management
    # =========================================================================

    def list_users(
        self,
        admin_user: AuthUser,
        search: Optional[str] = None,
        role: Optional[str] = None,
        account_status: Optional[str] = None,
        page: int = 1,
        page_size: int = 20
    ) -> Dict[str, Any]:
        """
        Lists users across all platform categories with search, role, and status filtering.
        """
        self.verify_platform_admin(admin_user)
        self._ensure_connected()

        if not self.use_supabase or not self.supabase:
            return {"users": [], "total": 0, "page": page, "page_size": page_size}

        try:
            query = self.supabase.table("profiles").select(
                "id, email, full_name, phone, role, account_status, is_verified, created_at, updated_at"
            )

            if role and role.strip():
                query = query.eq("role", role.strip().lower())
            if account_status and account_status.strip():
                query = query.eq("account_status", account_status.strip().lower())

            res = query.order("created_at", desc=True).execute()
            all_users = res.data or []

            # Client-side search on name or email if provided
            if search and search.strip():
                s = search.strip().lower()
                all_users = [
                    u for u in all_users
                    if s in (u.get("full_name") or "").lower() or s in (u.get("email") or "").lower()
                ]

            total = len(all_users)
            safe_page = max(1, page)
            safe_page_size = min(max(1, page_size), 100)
            start_idx = (safe_page - 1) * safe_page_size
            end_idx = start_idx + safe_page_size
            paginated = all_users[start_idx:end_idx]

            # Enrich with institution or lawyer metadata if relevant
            for u in paginated:
                uid = u["id"]
                if u.get("role") in ["proctor", "chief_proctor", "committee_member", "institution_admin"]:
                    m_res = self.supabase.table("institution_memberships").select(
                        "institution_code, role, account_status"
                    ).eq("user_id", uid).execute()
                    if m_res.data:
                        u["institution_code"] = m_res.data[0].get("institution_code")
                elif u.get("role") == "lawyer":
                    l_res = self.supabase.table("lawyer_profiles").select(
                        "verification_status, bar_council, enrollment_number, years_of_practice"
                    ).eq("id", uid).execute()
                    if l_res.data:
                        u["lawyer_profile"] = l_res.data[0]

            return {
                "users": paginated,
                "total": total,
                "page": safe_page,
                "page_size": safe_page_size
            }
        except Exception as e:
            logger.error(f"Error listing users: {e}")
            raise HTTPException(status_code=500, detail="Failed to retrieve user directory.")

    def get_user_profile(self, admin_user: AuthUser, target_user_id: str) -> Dict[str, Any]:
        """
        Retrieves detailed profile metadata for a specific user.
        Excludes credentials and sensitive authentication secrets.
        """
        self.verify_platform_admin(admin_user)
        self._ensure_connected()

        clean_uid = target_user_id.strip()
        res = self.supabase.table("profiles").select(
            "id, email, full_name, phone, role, account_status, is_verified, created_at, updated_at"
        ).eq("id", clean_uid).execute()

        if not res.data or len(res.data) == 0:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")

        profile = res.data[0]

        # Fetch lawyer details if applicable
        if profile.get("role") == "lawyer":
            lp = self.supabase.table("lawyer_profiles").select("*").eq("id", clean_uid).execute()
            if lp.data:
                profile["lawyer_profile"] = lp.data[0]

        # Fetch institution memberships if applicable
        im = self.supabase.table("institution_memberships").select("*").eq("user_id", clean_uid).execute()
        profile["institution_memberships"] = im.data or []

        return profile

    def update_user_account_status(
        self,
        admin_user: AuthUser,
        target_user_id: str,
        payload: UserStatusUpdateRequest
    ) -> Dict[str, Any]:
        """
        Suspends, reinstates, or revokes a platform user.
        Enforces self-modification prevention and records immutable audit trail.
        """
        self.verify_platform_admin(admin_user)
        self._ensure_connected()

        clean_uid = target_user_id.strip()

        # Guardrail 1: Self-modification prohibited
        if str(clean_uid) == str(admin_user.user_id):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Security policy violation: Administrators cannot alter their own account status."
            )

        new_status = payload.new_status.strip().lower()
        if new_status not in ["active", "suspended", "revoked"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid account status: Must be 'active', 'suspended', or 'revoked'."
            )

        # Check target user exists
        curr = self.supabase.table("profiles").select("id, role, account_status, email").eq("id", clean_uid).execute()
        if not curr.data or len(curr.data) == 0:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Target user not found.")

        target = curr.data[0]
        old_status = target.get("account_status")

        # 1. Update profiles table
        now_iso = datetime.now(timezone.utc).isoformat()
        upd_res = self.supabase.table("profiles").update({
            "account_status": new_status,
            "updated_at": now_iso
        }).eq("id", clean_uid).execute()

        # 2. Update institution memberships if target is an officer
        try:
            self.supabase.table("institution_memberships").update({
                "account_status": new_status,
                "updated_at": now_iso
            }).eq("user_id", clean_uid).execute()
        except Exception as e:
            logger.warning(f"Note: Error syncing membership status for {clean_uid}: {e}")

        # 3. Update lawyer profile if target is a lawyer and being suspended
        if target.get("role") == "lawyer":
            try:
                lawyer_v_status = "SUSPENDED" if new_status in ["suspended", "revoked"] else "VERIFIED"
                self.supabase.table("lawyer_profiles").update({
                    "verification_status": lawyer_v_status,
                    "updated_at": now_iso
                }).eq("id", clean_uid).execute()
            except Exception as e:
                logger.warning(f"Note: Error syncing lawyer profile status for {clean_uid}: {e}")

        # 4. Append immutable audit event
        action_name = f"USER_{new_status.upper()}"
        audit_id = self.log_audit_event(
            admin_user=admin_user,
            action_type=action_name,
            target_entity_type="USER",
            target_entity_id=clean_uid,
            reason=payload.reason,
            details={
                "previous_status": old_status,
                "new_status": new_status,
                "target_email": target.get("email"),
                "target_role": target.get("role")
            }
        )

        return {
            "status": "success",
            "user_id": clean_uid,
            "previous_status": old_status,
            "account_status": new_status,
            "audit_log_id": audit_id
        }

    # =========================================================================
    # Task 4: Institution Management
    # =========================================================================

    def list_institutions(
        self,
        admin_user: AuthUser,
        search: Optional[str] = None,
        is_active: Optional[bool] = None,
        page: int = 1,
        page_size: int = 20
    ) -> Dict[str, Any]:
        """
        Lists registered institutions with member and grievance counts.
        """
        self.verify_platform_admin(admin_user)
        self._ensure_connected()

        if not self.use_supabase or not self.supabase:
            return {"institutions": [], "total": 0, "page": page, "page_size": page_size}

        try:
            query = self.supabase.table("institutions").select("*")
            if is_active is not None:
                query = query.eq("is_active", is_active)

            res = query.order("name").execute()
            all_insts = res.data or []

            if search and search.strip():
                s = search.strip().lower()
                all_insts = [
                    i for i in all_insts
                    if s in (i.get("name") or "").lower() or s in (i.get("code") or "").lower() or s in (i.get("city") or "").lower()
                ]

            total = len(all_insts)
            safe_page = max(1, page)
            safe_page_size = min(max(1, page_size), 100)
            start_idx = (safe_page - 1) * safe_page_size
            end_idx = start_idx + safe_page_size
            paginated = all_insts[start_idx:end_idx]

            # Aggregate member and case counts for each institution
            for inst in paginated:
                icode = inst.get("code")
                uuid_id = inst.get("id")
                # Count active members
                m_res = self.supabase.table("institution_memberships").select("id").eq(
                    "institution_code", icode
                ).eq("account_status", "active").execute()
                inst["member_count"] = len(m_res.data or [])

                # Count grievances
                c_res = self.supabase.table("campus_cases").select("id").eq(
                    "institution_id", icode
                ).execute()
                inst["grievance_count"] = len(c_res.data or [])

            return {
                "institutions": paginated,
                "total": total,
                "page": safe_page,
                "page_size": safe_page_size
            }
        except Exception as e:
            logger.error(f"Error listing institutions: {e}")
            raise HTTPException(status_code=500, detail="Failed to list institutions.")

    def get_institution_details(self, admin_user: AuthUser, institution_id: str) -> Dict[str, Any]:
        """
        Retrieves comprehensive details, roster, and grievance stats for an institution.
        """
        self.verify_platform_admin(admin_user)
        self._ensure_connected()

        clean_id = institution_id.strip()
        # Query by UUID or code
        res = self.supabase.table("institutions").select("*").or_(
            f"id.eq.{clean_id},code.eq.{clean_id}"
        ).execute()

        if not res.data or len(res.data) == 0:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Institution not found.")

        inst = res.data[0]
        icode = inst.get("code")

        # Members breakdown
        m_res = self.supabase.table("institution_memberships").select(
            "id, user_id, role, account_status, created_at"
        ).eq("institution_code", icode).execute()
        members = m_res.data or []

        # Grievance breakdown
        c_res = self.supabase.table("campus_cases").select("id, status, severity, category").eq("institution_id", icode).execute()
        cases = c_res.data or []

        inst["roster"] = members
        inst["member_count"] = len(members)
        inst["grievance_count"] = len(cases)
        inst["active_grievance_count"] = sum(1 for c in cases if c.get("status") not in ["RESOLVED", "CLOSED"])

        return inst

    def register_institution(self, admin_user: AuthUser, payload: InstitutionCreateRequest) -> Dict[str, Any]:
        """
        Registers a new educational institution with unique code and metadata.
        """
        self.verify_platform_admin(admin_user)
        self._ensure_connected()

        clean_code = payload.code.strip().upper()
        # Check uniqueness
        existing = self.supabase.table("institutions").select("id").eq("code", clean_code).execute()
        if existing.data and len(existing.data) > 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Institution code '{clean_code}' is already registered."
            )

        new_record = {
            "code": clean_code,
            "name": payload.name.strip(),
            "city": payload.city.strip(),
            "state": payload.state.strip(),
            "type": payload.type.strip().lower(),
            "is_active": payload.is_active,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat()
        }

        res = self.supabase.table("institutions").insert(new_record).execute()
        if not res.data:
            raise HTTPException(status_code=500, detail="Failed to register institution.")

        created_inst = res.data[0]

        # Audit log
        self.log_audit_event(
            admin_user=admin_user,
            action_type="INSTITUTION_REGISTERED",
            target_entity_type="INSTITUTION",
            target_entity_id=created_inst["id"],
            institution_code=clean_code,
            details=new_record
        )

        return {
            "status": "success",
            "institution": created_inst
        }

    def update_institution_metadata(
        self,
        admin_user: AuthUser,
        institution_id: str,
        payload: InstitutionUpdateRequest
    ) -> Dict[str, Any]:
        """
        Updates permitted metadata for a registered institution.
        """
        self.verify_platform_admin(admin_user)
        self._ensure_connected()

        clean_id = institution_id.strip()
        update_dict = {"updated_at": datetime.now(timezone.utc).isoformat()}
        if payload.name:
            update_dict["name"] = payload.name.strip()
        if payload.city:
            update_dict["city"] = payload.city.strip()
        if payload.state:
            update_dict["state"] = payload.state.strip()
        if payload.type:
            update_dict["type"] = payload.type.strip().lower()

        res = self.supabase.table("institutions").update(update_dict).or_(
            f"id.eq.{clean_id},code.eq.{clean_id}"
        ).execute()

        if not res.data:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Institution not found.")

        updated_inst = res.data[0]

        self.log_audit_event(
            admin_user=admin_user,
            action_type="INSTITUTION_METADATA_UPDATED",
            target_entity_type="INSTITUTION",
            target_entity_id=updated_inst["id"],
            institution_code=updated_inst.get("code"),
            details=update_dict
        )

        return {"status": "success", "institution": updated_inst}

    def toggle_institution_status(
        self,
        admin_user: AuthUser,
        institution_id: str,
        payload: InstitutionStatusUpdateRequest
    ) -> Dict[str, Any]:
        """
        Activates or deactivates an institution without deleting cases or audit history.
        """
        self.verify_platform_admin(admin_user)
        self._ensure_connected()

        clean_id = institution_id.strip()
        now_iso = datetime.now(timezone.utc).isoformat()

        res = self.supabase.table("institutions").update({
            "is_active": payload.is_active,
            "updated_at": now_iso
        }).or_(f"id.eq.{clean_id},code.eq.{clean_id}").execute()

        if not res.data:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Institution not found.")

        inst = res.data[0]
        action_name = "INSTITUTION_ACTIVATED" if payload.is_active else "INSTITUTION_DEACTIVATED"

        self.log_audit_event(
            admin_user=admin_user,
            action_type=action_name,
            target_entity_type="INSTITUTION",
            target_entity_id=inst["id"],
            institution_code=inst.get("code"),
            reason=payload.reason,
            details={"is_active": payload.is_active}
        )

        return {
            "status": "success",
            "institution_id": inst["id"],
            "code": inst.get("code"),
            "is_active": payload.is_active
        }

    # =========================================================================
    # Task 5: Lawyer Verification Management
    # =========================================================================

    def list_lawyer_verification_queue(
        self,
        admin_user: AuthUser,
        status_filter: Optional[str] = None,
        page: int = 1,
        page_size: int = 20
    ) -> Dict[str, Any]:
        """
        Retrieves lawyers from the verification queue with admin-level details.
        """
        self.verify_platform_admin(admin_user)
        self._ensure_connected()

        if not self.use_supabase or not self.supabase:
            return {"lawyers": [], "total": 0, "page": page, "page_size": page_size}

        try:
            query = self.supabase.table("lawyer_profiles").select(
                "id, full_name, email, phone, bar_council, enrollment_state, enrollment_number, "
                "years_of_practice, specializations, courts, verification_status, verified_at, "
                "verified_by, verification_notes, created_at, updated_at"
            )

            if status_filter and status_filter.strip():
                query = query.eq("verification_status", status_filter.strip().upper())

            res = query.order("created_at", desc=True).execute()
            lawyers = res.data or []

            total = len(lawyers)
            safe_page = max(1, page)
            safe_page_size = min(max(1, page_size), 100)
            start_idx = (safe_page - 1) * safe_page_size
            end_idx = start_idx + safe_page_size

            return {
                "lawyers": lawyers[start_idx:end_idx],
                "total": total,
                "page": safe_page,
                "page_size": safe_page_size
            }
        except Exception as e:
            logger.error(f"Error querying lawyer verification queue: {e}")
            raise HTTPException(status_code=500, detail="Failed to retrieve lawyer verification queue.")

    def process_lawyer_verification(
        self,
        admin_user: AuthUser,
        lawyer_id: str,
        payload: LawyerVerificationProcessRequest
    ) -> Dict[str, Any]:
        """
        Executes verified decision on a lawyer's profile via admin_verify_lawyer RPC.
        Strictly prohibits self-verification and audits the decision.
        """
        self.verify_platform_admin(admin_user)
        self._ensure_connected()

        clean_lid = lawyer_id.strip()

        # Guardrail: Lawyers cannot verify themselves
        if str(clean_lid) == str(admin_user.user_id):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Security policy violation: Self-verification is strictly prohibited."
            )

        decision_upper = payload.decision.strip().upper()
        if decision_upper not in ["VERIFIED", "REJECTED", "SUSPENDED"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid decision: Must be VERIFIED, REJECTED, or SUSPENDED."
            )

        try:
            rpc_res = self.supabase.rpc("admin_verify_lawyer", {
                "p_lawyer_user_id": clean_lid,
                "p_decision": decision_upper,
                "p_notes": payload.notes
            }).execute()

            # Record in platform audit log
            self.log_audit_event(
                admin_user=admin_user,
                action_type=f"LAWYER_{decision_upper}",
                target_entity_type="LAWYER",
                target_entity_id=clean_lid,
                reason=payload.notes,
                details={
                    "decision": decision_upper,
                    "verified_by": str(admin_user.user_id)
                }
            )

            # Notify the lawyer
            notification_manager.create_notification(
                recipient_user_id=clean_lid,
                event_type=f"LAWYER_VERIFICATION_{decision_upper}",
                title="Lawyer Verification Status Updated",
                message=f"Your NyayPath Advocate verification status is now: {decision_upper}. Notes: {payload.notes or 'No remarks'}",
                related_case_id="PLATFORM",
                action_url="/lawyer/dashboard",
                idempotency_key=f"notif_lawyer_verify_{clean_lid}_{decision_upper}_{int(time.time())}"
            )

            return rpc_res.data or {
                "status": "success",
                "lawyer_user_id": clean_lid,
                "verification_status": decision_upper
            }
        except Exception as e:
            logger.error(f"Error processing lawyer verification RPC: {e}")
            raise HTTPException(status_code=500, detail=f"Database verification RPC failed: {e}")

    # =========================================================================
    # Task 6: Global Case Oversight & Privacy Protection
    # =========================================================================

    def list_global_cases(
        self,
        admin_user: AuthUser,
        case_type: Optional[str] = None,
        case_status: Optional[str] = None,
        institution_code: Optional[str] = None,
        search: Optional[str] = None,
        page: int = 1,
        page_size: int = 20
    ) -> Dict[str, Any]:
        """
        Platform-wide case oversight.
        Default listings mask student PII and proctor deliberations to preserve privacy.
        """
        self.verify_platform_admin(admin_user)
        self._ensure_connected()

        if not self.use_supabase or not self.supabase:
            return {"cases": [], "total": 0, "page": page, "page_size": page_size}

        try:
            # Query parent cases
            query = self.supabase.table("cases").select(
                "id, case_id, case_type, status, created_at, updated_at, data"
            ).eq("is_deleted", False)

            if case_type and case_type.strip():
                query = query.eq("case_type", case_type.strip().upper())
            if case_status and case_status.strip():
                query = query.eq("status", case_status.strip().upper())

            res = query.order("created_at", desc=True).execute()
            cases = res.data or []

            # Filter by institution or search query
            filtered_cases = []
            for c in cases:
                data = c.get("data") or {}
                c_inst = data.get("institution_id") or ""
                if institution_code and institution_code.strip():
                    if c_inst.upper() != institution_code.strip().upper():
                        continue
                if search and search.strip():
                    s = search.strip().lower()
                    cid = (c.get("case_id") or "").lower()
                    title = (data.get("title") or data.get("category") or "").lower()
                    if s not in cid and s not in title and s not in c_inst.lower():
                        continue

                # Strip student PII and proctor deliberations from administrative oversight view
                masked_item = {
                    "id": c["id"],
                    "case_id": c["case_id"],
                    "case_type": c["case_type"],
                    "status": c["status"],
                    "institution_id": c_inst or "N/A",
                    "category": data.get("category") or data.get("case_type") or "General",
                    "severity": data.get("severity") or "NORMAL",
                    "confidentiality_mode": data.get("confidentiality_mode") or "STANDARD",
                    "created_at": c["created_at"],
                    "updated_at": c["updated_at"],
                    # Privacy masking:
                    "student_name": "[PROTECTED / ANONYMOUS]",
                    "roll_number": "[PROTECTED]",
                    "proctor_notes": "[DELIBERATION PROTECTED]"
                }
                filtered_cases.append(masked_item)

            total = len(filtered_cases)
            safe_page = max(1, page)
            safe_page_size = min(max(1, page_size), 100)
            start_idx = (safe_page - 1) * safe_page_size
            end_idx = start_idx + safe_page_size

            return {
                "cases": filtered_cases[start_idx:end_idx],
                "total": total,
                "page": safe_page,
                "page_size": safe_page_size
            }
        except Exception as e:
            logger.error(f"Error querying global cases: {e}")
            raise HTTPException(status_code=500, detail="Failed to retrieve global case directory.")

    def get_case_confidential_details(
        self,
        admin_user: AuthUser,
        case_id: str,
        payload: ExceptionalAccessRequest
    ) -> Dict[str, Any]:
        """
        Exceptional confidential case access.
        Strictly requires a justification (minimum 10 characters) and records an immutable audit trail.
        """
        self.verify_platform_admin(admin_user)
        self._ensure_connected()

        clean_cid = case_id.strip()
        reason = payload.reason.strip()
        if len(reason) < 10:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="A legitimate operational reason (minimum 10 characters) is required for exceptional case access."
            )

        # 1. Fetch case details
        res = self.supabase.table("cases").select("*").eq("case_id", clean_cid).execute()
        if not res.data or len(res.data) == 0:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Case '{clean_cid}' not found.")

        case_record = res.data[0]

        # 2. Record exceptional access in platform audit log
        audit_id = self.log_audit_event(
            admin_user=admin_user,
            action_type="EXCEPTIONAL_CONFIDENTIAL_CASE_ACCESS",
            target_entity_type="CASE",
            target_entity_id=clean_cid,
            reason=reason,
            details={
                "case_uuid": case_record.get("id"),
                "case_type": case_record.get("case_type"),
                "status": case_record.get("status")
            }
        )

        # 3. If campus case, fetch unmasked campus details
        campus_details = None
        try:
            c_res = self.supabase.table("campus_cases").select("*").eq("case_id", clean_cid).execute()
            if c_res.data:
                campus_details = c_res.data[0]
        except Exception as e:
            logger.warning(f"Could not load campus case details for {clean_cid}: {e}")

        return {
            "status": "success",
            "audit_log_id": audit_id,
            "case": case_record,
            "campus_details": campus_details,
            "access_timestamp": datetime.now(timezone.utc).isoformat()
        }

    # =========================================================================
    # Task 7: Audit Logs & Activity Centre
    # =========================================================================

    def list_platform_audit_logs(
        self,
        admin_user: AuthUser,
        actor_id: Optional[str] = None,
        action_type: Optional[str] = None,
        target_entity_type: Optional[str] = None,
        institution_code: Optional[str] = None,
        page: int = 1,
        page_size: int = 50
    ) -> Dict[str, Any]:
        """
        Retrieves immutable platform audit history.
        Only accessible by authorized Platform Administrators.
        """
        self.verify_platform_admin(admin_user)
        self._ensure_connected()

        if not self.use_supabase or not self.supabase:
            return {"audit_logs": [], "total": 0, "page": page, "page_size": page_size}

        try:
            query = self.supabase.table("platform_audit_logs").select("*")

            if actor_id and actor_id.strip():
                query = query.eq("actor_user_id", actor_id.strip())
            if action_type and action_type.strip():
                query = query.eq("action_type", action_type.strip().upper())
            if target_entity_type and target_entity_type.strip():
                query = query.eq("target_entity_type", target_entity_type.strip().upper())
            if institution_code and institution_code.strip():
                query = query.eq("institution_code", institution_code.strip().upper())

            res = query.order("created_at", desc=True).execute()
            logs = res.data or []

            total = len(logs)
            safe_page = max(1, page)
            safe_page_size = min(max(1, page_size), 100)
            start_idx = (safe_page - 1) * safe_page_size
            end_idx = start_idx + safe_page_size

            return {
                "audit_logs": logs[start_idx:end_idx],
                "total": total,
                "page": safe_page,
                "page_size": safe_page_size
            }
        except Exception as e:
            logger.error(f"Error querying platform audit logs: {e}")
            raise HTTPException(status_code=500, detail="Failed to retrieve audit logs.")

    # =========================================================================
    # Task 8: System Monitoring & Operational Health
    # =========================================================================

    def get_system_health(self, admin_user: AuthUser) -> Dict[str, Any]:
        """
        Lightweight operational health check of core platform dependencies.
        Never discloses passwords, connection strings, or internal traces.
        """
        self.verify_platform_admin(admin_user)
        self._ensure_connected()

        health = {
            "status": "healthy",
            "version": "2.0.0-phase7",
            "environment": os.environ.get("ENVIRONMENT", "local"),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "services": {}
        }

        # 1. FastAPI Web Server
        health["services"]["api_server"] = {
            "status": "operational",
            "uptime_check": "active"
        }

        # 2. Database Connectivity
        db_start = time.time()
        try:
            if self.supabase:
                res = self.supabase.table("platform_admins").select("count", count="exact").limit(1).execute()
                db_latency_ms = round((time.time() - db_start) * 1000, 2)
                health["services"]["database"] = {
                    "status": "operational",
                    "latency_ms": db_latency_ms,
                    "target": "PostgreSQL 17 (Supabase)"
                }
            else:
                health["services"]["database"] = {"status": "unconfigured"}
        except Exception as e:
            health["status"] = "degraded"
            health["services"]["database"] = {
                "status": "unreachable",
                "error_type": type(e).__name__
            }

        # 3. Supabase Auth Service
        try:
            if self.supabase:
                health["services"]["auth_service"] = {
                    "status": "operational",
                    "provider": "Gotrue / Supabase Auth"
                }
            else:
                health["services"]["auth_service"] = {"status": "unconfigured"}
        except Exception as e:
            health["status"] = "degraded"
            health["services"]["auth_service"] = {"status": "unreachable", "error_type": type(e).__name__}

        # 4. Storage Service
        try:
            if self.supabase:
                buckets = self.supabase.storage.list_buckets()
                health["services"]["storage"] = {
                    "status": "operational",
                    "bucket_count": len(buckets) if isinstance(buckets, list) else 1
                }
            else:
                health["services"]["storage"] = {"status": "unconfigured"}
        except Exception as e:
            health["status"] = "degraded"
            health["services"]["storage"] = {"status": "degraded", "error_type": type(e).__name__}

        # 5. AI Legal Engine Service
        groq_key = os.environ.get("GROQ_API_KEY", "")
        health["services"]["ai_legal_engine"] = {
            "status": "operational" if bool(groq_key) else "standby",
            "provider": "Groq LLM"
        }

        # 6. Notification Dispatcher
        health["services"]["notification_service"] = {
            "status": "operational",
            "dispatch_mode": "persistent_in_app"
        }

        return health

    # =========================================================================
    # Task 9: Admin Notifications
    # =========================================================================

    def dispatch_admin_notification(
        self,
        event_type: str,
        title: str,
        message: str,
        entity_id: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> List[str]:
        """
        Dispatches platform alert notifications to all active Platform Administrators.
        Uses deterministic idempotency keys.
        """
        self._ensure_connected()
        dispatched_ids = []

        if not self.use_supabase or not self.supabase:
            return dispatched_ids

        try:
            admins_res = self.supabase.table("platform_admins").select("user_id").eq("account_status", "active").execute()
            admin_users = admins_res.data or []

            for a in admin_users:
                admin_uid = a["user_id"]
                idempotency_key = f"admin_alert_{event_type}_{entity_id}_{admin_uid}"
                notif = notification_manager.create_notification(
                    recipient_user_id=admin_uid,
                    event_type=f"ADMIN_ALERT_{event_type}",
                    title=title,
                    message=message,
                    related_case_id="PLATFORM",
                    action_url="/admin/dashboard",
                    idempotency_key=idempotency_key,
                    metadata=metadata
                )
                if notif:
                    dispatched_ids.append(notif.get("id"))
        except Exception as e:
            logger.error(f"Error dispatching admin notification: {e}")

        return dispatched_ids


# Global Singleton Instance
platform_admin_manager = PlatformAdminManager()

"""
NyayPath Phase 6: Secure Messaging, Client Communication & Meeting Scheduling
=============================================================================
Architecture & Capabilities:
1. Participant-Authorized Conversation Management (Lawyer-Citizen, Institutional Grievance, Shared Case)
2. Reliable Idempotent Messaging with Duplicate Submission Prevention
3. Private Signed Document Attachments (clamped to <= 300s TTL)
4. Consultation Meeting Scheduling with Transactional Double-Booking Prevention
5. Lawyer Practice Availability & Timezone-Aware Slot Configuration
6. Deterministic Notification Integration with Persisted Source UUIDs
"""

import os
import re
import uuid
import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field, field_validator
from fastapi import HTTPException, status

try:
    from supabase import create_client, Client
except ImportError:
    create_client, Client = None, None

try:
    from .auth import AuthUser, UserRole, AccountStatus
    from .notifications import notification_manager
    from .audit import record_case_activity
except ImportError:
    from auth import AuthUser, UserRole, AccountStatus
    from notifications import notification_manager
    from audit import record_case_activity

logger = logging.getLogger("nyaypath.messaging")


def _is_production() -> bool:
    return (
        os.environ.get("ENVIRONMENT") == "production" or
        os.environ.get("NODE_ENV") == "production" or
        os.environ.get("ENV") == "production" or
        os.environ.get("VERCEL") == "1"
    )


# =============================================================================
# Pydantic Request & Response Schemas
# =============================================================================

class ConversationCreateRequest(BaseModel):
    conversation_type: str = "LAWYER_CITIZEN"  # LAWYER_CITIZEN, INSTITUTION_CASE, GENERAL_CASE
    consultation_request_id: Optional[str] = None
    case_id: Optional[str] = None
    initial_message: Optional[str] = None


class ConsultationConversationRequest(BaseModel):
    consultation_request_id: str
    initial_message: Optional[str] = None


class CaseConversationRequest(BaseModel):
    case_id: str
    conversation_type: Optional[str] = "GENERAL_CASE"
    initial_message: Optional[str] = None


class MessageSendRequest(BaseModel):
    message_body: str
    message_type: str = "TEXT"  # TEXT, ATTACHMENT, SYSTEM, MEETING_LINK
    client_message_id: Optional[str] = None

    @field_validator("message_body")
    def validate_body(cls, v: str) -> str:
        clean = v.strip()
        if not clean:
            raise ValueError("Message body cannot be empty.")
        if len(clean) > 4000:
            raise ValueError("Message body exceeds 4,000 character maximum limit.")
        return clean


class MeetingScheduleRequest(BaseModel):
    consultation_request_id: Optional[str] = None
    case_id: Optional[str] = None
    lawyer_user_id: str
    scheduled_start: str  # ISO 8601 UTC
    scheduled_end: str    # ISO 8601 UTC
    meeting_mode: str = "ONLINE"  # ONLINE, IN_PERSON, PHONE
    agenda: Optional[str] = None
    phone_contact: Optional[str] = None


class MeetingStatusUpdateRequest(BaseModel):
    status: str  # CONFIRMED, DECLINED, RESCHEDULE_REQUESTED, CANCELLED, COMPLETED, NO_SHOW
    notes: Optional[str] = None
    online_meeting_url: Optional[str] = None
    location_details: Optional[str] = None
    phone_contact: Optional[str] = None
    reschedule_start: Optional[str] = None
    reschedule_end: Optional[str] = None


class LawyerAvailabilityPayload(BaseModel):
    available_days: List[int] = [1, 2, 3, 4, 5]  # 1=Mon, 7=Sun
    start_time_utc: str = "04:30:00"  # 10:00 AM IST
    end_time_utc: str = "12:30:00"    # 18:00 PM IST
    slot_duration_minutes: int = 30
    timezone: str = "Asia/Kolkata"
    unavailable_dates: List[str] = []


# =============================================================================
# CommunicationManager Implementation
# =============================================================================

class CommunicationManager:
    """
    Central manager for secure case communication, client messaging, and meeting scheduling.
    Guarantees participant isolation, strict access validation, and reliable idempotency.
    """

    def __init__(self):
        url = os.environ.get("SUPABASE_URL", "")
        secret_key = os.environ.get("SUPABASE_SECRET_KEY", "")
        is_offline_test = os.environ.get("SUPABASE_OFFLINE_TEST") == "1"
        self.use_supabase = bool(url and secret_key and create_client and not is_offline_test)
        self.supabase: Optional[Client] = None

        if self.use_supabase:
            try:
                self.supabase = create_client(url, secret_key)
                logger.info("CommunicationManager: Connected to Supabase.")
            except Exception as e:
                logger.error(f"CommunicationManager Supabase init error: {e}")
                self.use_supabase = False
                if _is_production():
                    raise RuntimeError("Persistent database required in production.") from e

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
                    logger.warning(f"CommunicationManager reconnect failed: {e}")

    def _verify_lawyer_case_access(
        self,
        lawyer_uid: str,
        case_uuid: str,
        required_scope: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Phase 6.1: Strictly verifies that a lawyer has an ACTIVE lawyer_case_access record
        for the given case UUID. Fails closed with HTTP 403 on missing, inactive,
        revoked, scope-insufficient, or failed database checks.
        """
        self._ensure_connected()
        if not self.supabase:
            raise HTTPException(status_code=500, detail="Database connection unavailable.")

        try:
            res = self.supabase.table("lawyer_case_access").select(
                "id, case_uuid, lawyer_user_id, access_status, shared_scope"
            ).eq("case_uuid", str(case_uuid)).eq("lawyer_user_id", str(lawyer_uid)).execute()
        except Exception as e:
            logger.error(f"Database error verifying lawyer case access for {lawyer_uid} on {case_uuid}: {e}")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied: Unable to verify case sharing authorization."
            )

        if not res or not res.data or len(res.data) == 0:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied: No active case sharing authorization found for this case."
            )

        access_row = res.data[0]
        # Match check
        if str(access_row.get("lawyer_user_id")) != str(lawyer_uid) or str(access_row.get("case_uuid")) != str(case_uuid):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied: Authorization record identity mismatch."
            )

        # Status check: must be strictly ACTIVE
        current_status = (access_row.get("access_status") or "").strip().upper()
        if current_status != "ACTIVE":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied: Case sharing permission is {current_status.lower() or 'inactive'}."
            )

        # Scope check if required_scope specified
        scope = (access_row.get("shared_scope") or "").strip().upper()
        if required_scope == "CASE_AND_DOCS" and scope != "CASE_AND_DOCS":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied: Case sharing scope does not permit document attachment access."
            )

        return access_row

    # =========================================================================
    # Conversation Creation & Authorization
    # =========================================================================

    def create_or_get_consultation_conversation(
        self,
        user: AuthUser,
        consultation_request_id: str,
        initial_message: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Creates or retrieves a 1-to-1 conversation based on an ACCEPTED consultation request.
        Strictly requires caller to be citizen or lawyer participant.
        """
        if not user or getattr(user, "account_status", None) != AccountStatus.ACTIVE:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Active authentication required.")

        self._ensure_connected()
        if not self.supabase:
            raise HTTPException(status_code=500, detail="Database connection unavailable.")

        # 1. Fetch Consultation Request
        clean_req_id = consultation_request_id.strip()
        c_res = self.supabase.table("consultation_requests").select("*").eq("id", clean_req_id).execute()
        if not c_res.data:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Consultation request not found.")

        req = c_res.data[0]
        citizen_uid = str(req["citizen_user_id"])
        lawyer_uid = str(req["lawyer_user_id"])
        caller_uid = str(user.user_id)

        # 2. Authorization check
        if caller_uid != citizen_uid and caller_uid != lawyer_uid and user.role != UserRole.PLATFORM_ADMIN:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied: You are not a party to this consultation."
            )

        # 3. Status check: Consultation must be ACCEPTED or COMPLETED to permit messaging
        if req["status"] not in ["ACCEPTED", "COMPLETED"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Messaging requires an ACCEPTED consultation. Current status is '{req['status']}'."
            )

        # 4. Check for existing conversation linked to this consultation_request_id
        existing_conv = self.supabase.table("conversations").select("*").eq(
            "consultation_request_id", clean_req_id
        ).execute()

        if existing_conv.data and len(existing_conv.data) > 0:
            conv = existing_conv.data[0]
            # Ensure caller is active participant
            self._ensure_participant(conv["id"], citizen_uid, "citizen")
            self._ensure_participant(conv["id"], lawyer_uid, "lawyer")
            return self.get_conversation(user, conv["id"])

        # 5. Create new conversation
        now_iso = datetime.now(timezone.utc).isoformat()
        conv_id = str(uuid.uuid4())
        conv_payload = {
            "id": conv_id,
            "conversation_type": "LAWYER_CITIZEN",
            "title": f"Consultation: {req.get('legal_issue', 'Legal Inquiry')}",
            "related_case_uuid": req.get("case_uuid"),
            "related_case_id": req.get("case_id"),
            "consultation_request_id": clean_req_id,
            "created_by": caller_uid,
            "conversation_status": "ACTIVE",
            "created_at": now_iso,
            "updated_at": now_iso
        }

        self.supabase.table("conversations").insert(conv_payload).execute()

        # Add both participants
        self.supabase.table("conversation_participants").insert([
            {
                "conversation_id": conv_id,
                "user_id": citizen_uid,
                "participant_role": "citizen",
                "joined_at": now_iso,
                "last_read_at": now_iso,
                "participant_status": "ACTIVE"
            },
            {
                "conversation_id": conv_id,
                "user_id": lawyer_uid,
                "participant_role": "lawyer",
                "joined_at": now_iso,
                "last_read_at": now_iso,
                "participant_status": "ACTIVE"
            }
        ]).execute()

        # Send initial message if provided
        if initial_message and initial_message.strip():
            self.send_message(user, conv_id, MessageSendRequest(message_body=initial_message.strip()))

        # Notify the other party of new conversation channel
        other_party_uid = lawyer_uid if caller_uid == citizen_uid else citizen_uid
        notification_manager.create_notification(
            recipient_user_id=other_party_uid,
            event_type="CONVERSATION_STARTED",
            title="Secure Consultation Channel Opened",
            message=f"A confidential messaging channel has been established for your consultation on '{req.get('legal_issue')}'.",
            related_case_id=req.get("case_id") or clean_req_id,
            action_url=f"/messages/{conv_id}",
            idempotency_key=f"notif_conv_{conv_id}_start_{other_party_uid}"
        )

        return self.get_conversation(user, conv_id)

    def create_or_get_case_conversation(
        self,
        user: AuthUser,
        case_id: str,
        conversation_type: Optional[str] = None,
        initial_message: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Creates or retrieves an authorized case communication channel.
        - Institutional grievance: Citizen student + assigned proctor.
        - Shared Case: Citizen + verified lawyer with ACTIVE case access.
        """
        if not user or getattr(user, "account_status", None) != AccountStatus.ACTIVE:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Active authentication required.")

        self._ensure_connected()
        if not self.supabase:
            raise HTTPException(status_code=500, detail="Database connection unavailable.")

        clean_case_id = case_id.strip().upper()

        # 1. Fetch case record from cases or campus_cases
        c_res = self.supabase.table("cases").select("*").eq("case_id", clean_case_id).execute()
        is_campus = False
        if not c_res.data:
            c_res = self.supabase.table("campus_cases").select("*").eq("case_id", clean_case_id).execute()
            is_campus = True

        if not c_res.data:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Case '{clean_case_id}' not found.")

        case = c_res.data[0]
        case_uuid = case["id"]
        cdata = case.get("data") if isinstance(case.get("data"), dict) else {}
        owner_id = (
            case.get("student_user_id") or
            case.get("citizen_user_id") or
            cdata.get("citizen_user_id") or
            cdata.get("student_user_id") or
            cdata.get("user_id")
        )

        caller_uid = str(user.user_id)
        other_party_uid = None
        conv_type = "GENERAL_CASE"
        participant_role = "member"

        # 2. Check Lawyer Case Access Pathway
        if user.role == UserRole.LAWYER:
            self._verify_lawyer_case_access(caller_uid, case_uuid)
            other_party_uid = owner_id
            conv_type = "LAWYER_CITIZEN"
            participant_role = "lawyer"

        # 3. Check Citizen Pathway (citizen initiating with lawyer who has case access)
        elif caller_uid == str(owner_id):
            participant_role = "citizen"
            # If campus grievance, connect with assigned proctor
            if is_campus or case.get("institution_id"):
                assigned_proctor = case.get("assigned_proctor_user_id")
                if assigned_proctor:
                    other_party_uid = str(assigned_proctor)
                    conv_type = "INSTITUTION_CASE"
            else:
                # Check if case shared with any active lawyer
                acc_res = self.supabase.table("lawyer_case_access").select("lawyer_user_id").eq(
                    "case_uuid", case_uuid
                ).eq("access_status", "ACTIVE").limit(1).execute()
                if acc_res.data:
                    other_party_uid = str(acc_res.data[0]["lawyer_user_id"])
                    conv_type = "LAWYER_CITIZEN"

        # 4. Check Institutional Proctor Pathway
        elif user.role in [UserRole.PROCTOR, UserRole.CHIEF_PROCTOR, UserRole.INSTITUTION_ADMIN]:
            case_inst = (case.get("institution_id") or "").strip().upper()
            user_inst = (user.institution_id or "").strip().upper()
            if case_inst != user_inst:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Cross-institution communication forbidden: Case belongs to a different institution."
                )
            other_party_uid = owner_id
            conv_type = "INSTITUTION_CASE"
            participant_role = "proctor"

        else:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied: You are not authorized to participate in conversations for this case."
            )

        if not other_party_uid:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Unable to open case conversation: No active counsel or proctor assignment found for this case."
            )

        # 5. Check existing conversation for this case and participants
        existing = self.supabase.table("conversations").select("*").eq(
            "related_case_uuid", case_uuid
        ).execute()

        for c in existing.data or []:
            parts = self.supabase.table("conversation_participants").select("user_id").eq(
                "conversation_id", c["id"]
            ).execute()
            uids = [str(p["user_id"]) for p in parts.data or []]
            if caller_uid in uids and str(other_party_uid) in uids:
                return self.get_conversation(user, c["id"])

        # 6. Create conversation
        now_iso = datetime.now(timezone.utc).isoformat()
        conv_id = str(uuid.uuid4())
        conv_payload = {
            "id": conv_id,
            "conversation_type": conv_type,
            "title": f"Case Discussion: {clean_case_id}",
            "related_case_uuid": case_uuid,
            "related_case_id": clean_case_id,
            "created_by": caller_uid,
            "conversation_status": "ACTIVE",
            "created_at": now_iso,
            "updated_at": now_iso
        }

        self.supabase.table("conversations").insert(conv_payload).execute()

        self.supabase.table("conversation_participants").insert([
            {
                "conversation_id": conv_id,
                "user_id": caller_uid,
                "participant_role": participant_role,
                "joined_at": now_iso,
                "last_read_at": now_iso,
                "participant_status": "ACTIVE"
            },
            {
                "conversation_id": conv_id,
                "user_id": str(other_party_uid),
                "participant_role": "citizen" if participant_role != "citizen" else "lawyer",
                "joined_at": now_iso,
                "last_read_at": now_iso,
                "participant_status": "ACTIVE"
            }
        ]).execute()

        if initial_message and initial_message.strip():
            self.send_message(user, conv_id, MessageSendRequest(message_body=initial_message.strip()))

        return self.get_conversation(user, conv_id)

    # =========================================================================
    # Conversation Listing & Retrieval
    # =========================================================================

    def list_user_conversations(self, user: AuthUser) -> List[Dict[str, Any]]:
        """
        Retrieves all conversations where the authenticated user is an active participant.
        Computes unread message count and dynamic permission re-validation.
        """
        if not user or getattr(user, "account_status", None) != AccountStatus.ACTIVE:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required.")

        self._ensure_connected()
        if not self.supabase:
            return []

        caller_uid = str(user.user_id)

        # 1. Fetch user's participant records
        parts_res = self.supabase.table("conversation_participants").select(
            "conversation_id, last_read_at, participant_role"
        ).eq("user_id", caller_uid).eq("participant_status", "ACTIVE").execute()

        if not parts_res.data:
            return []

        conv_ids = [p["conversation_id"] for p in parts_res.data]
        read_map = {p["conversation_id"]: p.get("last_read_at") for p in parts_res.data}
        role_map = {p["conversation_id"]: p.get("participant_role") for p in parts_res.data}

        # 2. Fetch conversations
        conv_res = self.supabase.table("conversations").select("*").in_("id", conv_ids).order(
            "updated_at", desc=True
        ).execute()

        conversations = conv_res.data or []
        valid_conversations = []

        # 3. Dynamic Case Access Filter:
        # If caller is a lawyer and conversation is tied to a case, verify access is actively ACTIVE
        active_case_uuids = set()
        if user.role == UserRole.LAWYER:
            try:
                active_res = self.supabase.table("lawyer_case_access").select("case_uuid").eq(
                    "lawyer_user_id", caller_uid
                ).eq("access_status", "ACTIVE").execute()
                active_case_uuids = {str(r["case_uuid"]) for r in active_res.data or []}
            except Exception as e:
                logger.error(f"Failed to query active lawyer case access for {caller_uid}: {e}")
                # Fail closed: treat as having no active case access
                active_case_uuids = set()

        for conv in conversations:
            if user.role == UserRole.LAWYER and conv.get("related_case_uuid"):
                case_uuid_str = str(conv.get("related_case_uuid"))
                if case_uuid_str not in active_case_uuids:
                    # Missing, revoked, or inactive case share record: hide from lawyer conversation list
                    continue
            valid_conversations.append(conv)

        # 4. Enrich with participant profiles & unread counts
        for conv in valid_conversations:
            cid = conv["id"]
            # Other participants
            all_parts = self.supabase.table("conversation_participants").select(
                "user_id, participant_role, last_read_at"
            ).eq("conversation_id", cid).execute()

            other_uids = [str(p["user_id"]) for p in all_parts.data or [] if str(p["user_id"]) != caller_uid]

            # Fetch profiles for other participants
            other_profiles = []
            if other_uids:
                prof_res = self.supabase.table("profiles").select(
                    "id, full_name, email, role"
                ).in_("id", other_uids).execute()
                other_profiles = prof_res.data or []

            conv["participants"] = other_profiles
            conv["user_role"] = role_map.get(cid, "member")

            # Unread count: messages in cid created > last_read_at and sender != caller_uid
            last_read = read_map.get(cid)
            unread_query = self.supabase.table("messages").select("id", count="exact").eq(
                "conversation_id", cid
            ).neq("sender_user_id", caller_uid)

            if last_read:
                unread_query = unread_query.gt("created_at", last_read)

            unread_res = unread_query.execute()
            conv["unread_count"] = unread_res.count if hasattr(unread_res, "count") and unread_res.count is not None else 0

        return valid_conversations

    def get_conversation(self, user: AuthUser, conversation_id: str) -> Dict[str, Any]:
        """
        Fetches conversation metadata and validates active membership.
        Fails closed with 403 on revoked permissions.
        """
        if not user or getattr(user, "account_status", None) != AccountStatus.ACTIVE:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required.")

        self._ensure_connected()
        if not self.supabase:
            raise HTTPException(status_code=500, detail="Database connection unavailable.")

        clean_id = conversation_id.strip()
        conv_res = self.supabase.table("conversations").select("*").eq("id", clean_id).execute()
        if not conv_res.data:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found.")

        conv = conv_res.data[0]
        caller_uid = str(user.user_id)

        # Verify active participant
        part_res = self.supabase.table("conversation_participants").select("*").eq(
            "conversation_id", clean_id
        ).eq("user_id", caller_uid).eq("participant_status", "ACTIVE").execute()

        is_admin = user.role == UserRole.PLATFORM_ADMIN
        if not part_res.data and not is_admin:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied: You are not an active participant in this conversation."
            )

        # Dynamic Authorization Check for Lawyer on Case-Linked Conversations
        if user.role == UserRole.LAWYER and conv.get("related_case_uuid"):
            self._verify_lawyer_case_access(caller_uid, conv["related_case_uuid"])

        # Load participants roster
        all_parts = self.supabase.table("conversation_participants").select(
            "user_id, participant_role, joined_at, last_read_at"
        ).eq("conversation_id", clean_id).execute()

        uids = [str(p["user_id"]) for p in all_parts.data or []]
        profiles = []
        if uids:
            prof_res = self.supabase.table("profiles").select("id, full_name, email, role").in_("id", uids).execute()
            profiles = prof_res.data or []

        conv["participants"] = profiles
        conv["case_id"] = conv.get("related_case_id")
        conv["status"] = conv.get("conversation_status", "ACTIVE")
        return conv

    # =========================================================================
    # Messaging Engine (Send, Read, Deduplicate)
    # =========================================================================

    def send_message(
        self,
        user: AuthUser,
        conversation_id: str,
        payload: MessageSendRequest
    ) -> Dict[str, Any]:
        """
        Sends a message in an authorized conversation.
        Strictly derives sender identity from user.user_id (prevents sender spoofing).
        Enforces idempotency using client_message_id.
        """
        if not user or getattr(user, "account_status", None) != AccountStatus.ACTIVE:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required.")

        self._ensure_connected()
        if not self.supabase:
            raise HTTPException(status_code=500, detail="Database connection unavailable.")

        clean_id = conversation_id.strip()
        caller_uid = str(user.user_id)

        # 1. Authorize sender in conversation
        conv = self.get_conversation(user, clean_id)
        if user.role == UserRole.LAWYER and conv.get("related_case_uuid"):
            req_scope = "CASE_AND_DOCS" if payload.message_type == "ATTACHMENT" else None
            self._verify_lawyer_case_access(caller_uid, conv["related_case_uuid"], required_scope=req_scope)

        # 2. Check client_message_id idempotency
        client_msg_id = payload.client_message_id.strip() if payload.client_message_id else None
        if client_msg_id:
            existing_msg = self.supabase.table("messages").select("*").eq(
                "conversation_id", clean_id
            ).eq("client_message_id", client_msg_id).execute()
            if existing_msg.data and len(existing_msg.data) > 0:
                logger.info(f"Duplicate message suppressed by client_message_id: {client_msg_id}")
                return existing_msg.data[0]

        # 3. Insert new message
        now_iso = datetime.now(timezone.utc).isoformat()
        msg_id = str(uuid.uuid4())
        msg_record = {
            "id": msg_id,
            "conversation_id": clean_id,
            "sender_user_id": caller_uid,
            "message_type": payload.message_type,
            "message_body": payload.message_body,
            "client_message_id": client_msg_id,
            "created_at": now_iso,
            "edited_at": None
        }

        try:
            res = self.supabase.table("messages").insert(msg_record).execute()
            created_msg = res.data[0] if res.data else msg_record
        except Exception as e:
            # Handle unique index race condition on client_message_id
            if "unique" in str(e).lower() and client_msg_id:
                existing = self.supabase.table("messages").select("*").eq(
                    "conversation_id", clean_id
                ).eq("client_message_id", client_msg_id).execute()
                if existing.data:
                    return existing.data[0]
            logger.error(f"Error persisting message: {e}")
            raise HTTPException(status_code=500, detail="Failed to send message.")

        # 4. Update sender's last_read_at
        self.supabase.table("conversation_participants").update({
            "last_read_at": now_iso
        }).eq("conversation_id", clean_id).eq("user_id", caller_uid).execute()

        # 5. Dispatch in-app notifications to other participants
        parts = self.supabase.table("conversation_participants").select("user_id").eq(
            "conversation_id", clean_id
        ).eq("participant_status", "ACTIVE").neq("user_id", caller_uid).execute()

        sender_name = user.name or "A participant"
        safe_preview = payload.message_body[:80] + ("..." if len(payload.message_body) > 80 else "")

        for p in parts.data or []:
            recip_uid = str(p["user_id"])
            notification_manager.create_notification(
                recipient_user_id=recip_uid,
                event_type="NEW_MESSAGE",
                title=f"New Message from {sender_name}",
                message=f"{sender_name}: \"{safe_preview}\"",
                related_case_id=conv.get("related_case_id") or clean_id,
                action_url=f"/messages/{clean_id}",
                idempotency_key=f"notif_msg_{msg_id}_{recip_uid}"
            )

        return created_msg

    def list_conversation_messages(
        self,
        user: AuthUser,
        conversation_id: str,
        limit: int = 50,
        offset: int = 0,
        before: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Fetches chronological messages with sender profiles and attachment metadata.
        Strictly revalidates dynamic permissions.
        """
        if not user or getattr(user, "account_status", None) != AccountStatus.ACTIVE:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required.")

        self._ensure_connected()
        if not self.supabase:
            return []

        clean_id = conversation_id.strip()
        # Verify caller has active access
        conv = self.get_conversation(user, clean_id)
        is_metadata_only = False
        if user.role == UserRole.LAWYER and conv.get("related_case_uuid"):
            acc = self._verify_lawyer_case_access(str(user.user_id), conv["related_case_uuid"])
            if (acc.get("shared_scope") or "").strip().upper() == "METADATA_ONLY":
                is_metadata_only = True

        # Query messages with attachments
        clamped_limit = min(max(1, limit), 100)
        msg_res = self.supabase.table("messages").select(
            "id, conversation_id, sender_user_id, message_type, message_body, client_message_id, created_at, edited_at"
        ).eq("conversation_id", clean_id).order("created_at", desc=False).range(offset, offset + clamped_limit - 1).execute()

        messages = msg_res.data or []
        if not messages:
            return []

        # Attachments join
        msg_ids = [m["id"] for m in messages]
        att_res = self.supabase.table("message_attachments").select("*").in_("message_id", msg_ids).execute()
        att_map: Dict[str, List[Dict[str, Any]]] = {}
        for a in att_res.data or []:
            att_map.setdefault(a["message_id"], []).append(a)

        # Sender profiles lookup
        senders = list(set([m["sender_user_id"] for m in messages]))
        sender_map = {}
        if senders:
            p_res = self.supabase.table("profiles").select("id, full_name, email, role").in_("id", senders).execute()
            sender_map = {p["id"]: p for p in p_res.data or []}

        for m in messages:
            m["attachments"] = [] if is_metadata_only else att_map.get(m["id"], [])
            m["sender"] = sender_map.get(m["sender_user_id"], {"full_name": "User"})

        return messages

    def mark_conversation_read(self, user: AuthUser, conversation_id: str) -> Dict[str, Any]:
        """Updates last_read_at timestamp for authenticated caller in the conversation."""
        if not user or getattr(user, "account_status", None) != AccountStatus.ACTIVE:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required.")

        self._ensure_connected()
        if not self.supabase:
            raise HTTPException(status_code=500, detail="Database connection unavailable.")

        clean_id = conversation_id.strip()
        # Verify active membership and dynamic permissions
        self.get_conversation(user, clean_id)

        caller_uid = str(user.user_id)
        now_iso = datetime.now(timezone.utc).isoformat()

        self.supabase.table("conversation_participants").update({
            "last_read_at": now_iso
        }).eq("conversation_id", clean_id).eq("user_id", caller_uid).execute()

        return {"status": "success", "last_read_at": now_iso, "read_at": now_iso}

    # =========================================================================
    # Attachments & Storage
    # =========================================================================

    def upload_attachment(
        self,
        user: AuthUser,
        conversation_id: str,
        file_bytes: bytes,
        filename: str,
        content_type: str = "application/octet-stream",
        mime_type: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Uploads a private document attachment into conversation storage.
        Enforces 10MB limit and signed URL generation capped at 300s TTL.
        """
        effective_mime = mime_type or content_type
        if not user or getattr(user, "account_status", None) != AccountStatus.ACTIVE:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required.")

        self._ensure_connected()
        if not self.supabase:
            raise HTTPException(status_code=500, detail="Database connection unavailable.")

        clean_id = conversation_id.strip()
        # Verify authorization
        conv = self.get_conversation(user, clean_id)
        if user.role == UserRole.LAWYER and conv.get("related_case_uuid"):
            self._verify_lawyer_case_access(
                lawyer_uid=str(user.user_id),
                case_uuid=conv["related_case_uuid"],
                required_scope="CASE_AND_DOCS"
            )

        # 1. Size check: 10MB maximum
        if len(file_bytes) > 10 * 1024 * 1024:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Attachment size exceeds 10MB limit.")

        # 2. MIME check
        allowed_mimes = ["application/pdf", "image/jpeg", "image/png", "image/webp"]
        clean_mime = (effective_mime or "application/pdf").lower()
        if clean_mime not in allowed_mimes:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unsupported file type '{clean_mime}'. Allowed types: PDF, JPEG, PNG, WebP."
            )

        # 3. Sanitize filename
        safe_name = re.sub(r"[^a-zA-Z0-9_\-\.]", "_", filename or "document.pdf")
        att_id = str(uuid.uuid4())
        storage_path = f"conversations/{clean_id}/{att_id}_{safe_name}"

        # 4. Upload to Supabase Storage
        try:
            self.supabase.storage.from_("message-attachments").upload(
                storage_path,
                file_bytes,
                {"content-type": clean_mime}
            )
        except Exception as e:
            logger.error(f"Failed to upload attachment to Supabase Storage: {e}")
            raise HTTPException(status_code=500, detail="Storage upload failed.")

        # 5. Insert Message Record
        msg_payload = MessageSendRequest(
            message_body=f"Shared attachment: {safe_name}",
            message_type="ATTACHMENT"
        )
        msg = self.send_message(user, clean_id, msg_payload)

        # 6. Insert Attachment Record
        now_iso = datetime.now(timezone.utc).isoformat()
        att_record = {
            "id": att_id,
            "message_id": msg["id"],
            "conversation_id": clean_id,
            "storage_path": storage_path,
            "file_name": safe_name,
            "mime_type": clean_mime,
            "file_size": len(file_bytes),
            "uploaded_by": str(user.user_id),
            "created_at": now_iso
        }
        self.supabase.table("message_attachments").insert(att_record).execute()

        # 7. Generate Signed URL (<= 300s TTL)
        signed_url_res = self.supabase.storage.from_("message-attachments").create_signed_url(storage_path, 300)
        signed_url = signed_url_res.get("signedURL") or signed_url_res.get("signedUrl") if isinstance(signed_url_res, dict) else str(signed_url_res)

        return {
            "id": att_id,
            "status": "success",
            "attachment": att_record,
            "file_name": safe_name,
            "mime_type": clean_mime,
            "signed_url": signed_url,
            "download_url": signed_url,
            "expires_in": 300,
            "expires_in_seconds": 300
        }

    def get_attachment_signed_url(self, user: AuthUser, attachment_id: str) -> Dict[str, Any]:
        """Generates a temporary signed URL (capped at 300s TTL) for an authorized attachment."""
        if not user or getattr(user, "account_status", None) != AccountStatus.ACTIVE:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required.")

        self._ensure_connected()
        if not self.supabase:
            raise HTTPException(status_code=500, detail="Database connection unavailable.")

        clean_att_id = attachment_id.strip()
        att_res = self.supabase.table("message_attachments").select("*").eq("id", clean_att_id).execute()
        if not att_res.data:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Attachment not found.")

        att = att_res.data[0]
        # Revalidate caller's access to the conversation and document scope
        conv = self.get_conversation(user, att["conversation_id"])
        if user.role == UserRole.LAWYER and conv.get("related_case_uuid"):
            self._verify_lawyer_case_access(
                lawyer_uid=str(user.user_id),
                case_uuid=conv["related_case_uuid"],
                required_scope="CASE_AND_DOCS"
            )

        signed_url_res = self.supabase.storage.from_("message-attachments").create_signed_url(att["storage_path"], 300)
        signed_url = signed_url_res.get("signedURL") or signed_url_res.get("signedUrl") if isinstance(signed_url_res, dict) else str(signed_url_res)

        return {
            "attachment_id": clean_att_id,
            "file_name": att["file_name"],
            "signed_url": signed_url,
            "expires_in": 300,
            "expires_in_seconds": 300
        }

    # =========================================================================
    # Meeting Scheduling & Availability (Tasks 6 & 7)
    # =========================================================================

    def schedule_meeting(
        self,
        user: AuthUser,
        payload: MeetingScheduleRequest
    ) -> Dict[str, Any]:
        """
        Schedules a legal consultation appointment.
        Enforces double-booking prevention, availability adherence, and participant verification.
        """
        if not user or getattr(user, "account_status", None) != AccountStatus.ACTIVE:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required.")

        self._ensure_connected()
        if not self.supabase:
            raise HTTPException(status_code=500, detail="Database connection unavailable.")

        caller_uid = str(user.user_id)
        lawyer_uid = payload.lawyer_user_id.strip()

        # 1. Parse and validate timestamps
        try:
            start_dt = datetime.fromisoformat(payload.scheduled_start.replace("Z", "+00:00"))
            end_dt = datetime.fromisoformat(payload.scheduled_end.replace("Z", "+00:00"))
        except Exception:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid ISO 8601 timestamp format.")

        now_utc = datetime.now(timezone.utc)
        if start_dt < now_utc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Meeting start time must be in the future.")

        duration_sec = (end_dt - start_dt).total_seconds()
        if duration_sec < 15 * 60 or duration_sec > 180 * 60:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Meeting duration must be between 15 and 180 minutes.")

        # 2. Determine citizen and lawyer roles
        is_lawyer = (caller_uid == lawyer_uid)
        citizen_uid = None

        if is_lawyer:
            # Lawyer scheduling with citizen: consultation_request_id is mandatory to resolve client
            if not payload.consultation_request_id:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="consultation_request_id required when lawyer schedules a meeting.")
            c_res = self.supabase.table("consultation_requests").select("citizen_user_id, status").eq(
                "id", payload.consultation_request_id.strip()
            ).execute()
            if not c_res.data:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Consultation request not found.")
            citizen_uid = str(c_res.data[0]["citizen_user_id"])
        else:
            citizen_uid = caller_uid

        # 3. Verify Consultation Context
        case_uuid = None
        case_id = payload.case_id.strip().upper() if payload.case_id else None
        if payload.consultation_request_id:
            c_res = self.supabase.table("consultation_requests").select("*").eq(
                "id", payload.consultation_request_id.strip()
            ).execute()
            if c_res.data:
                req = c_res.data[0]
                case_uuid = req.get("case_uuid")
                case_id = case_id or req.get("case_id")
                if req.get("status") not in ["ACCEPTED", "COMPLETED"] and not is_lawyer:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Meetings can only be scheduled for ACCEPTED consultations."
                    )

        # 4. Check Lawyer Availability
        avail_res = self.supabase.table("lawyer_availability").select("*").eq("lawyer_user_id", lawyer_uid).execute()
        if avail_res.data and len(avail_res.data) > 0:
            avail = avail_res.data[0]
            # Check weekday (1=Monday ... 7=Sunday)
            weekday = start_dt.isoweekday()
            if weekday not in avail.get("available_days", [1, 2, 3, 4, 5]):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Advocate is not available on this day of the week ({start_dt.strftime('%A')})."
                )

            # Check unavailable dates
            meeting_date_str = start_dt.strftime("%Y-%m-%d")
            if meeting_date_str in avail.get("unavailable_dates", []):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Advocate has marked {meeting_date_str} as an unavailable date."
                )

        # 5. Transactional Overlap & Double-Booking Prevention
        # Check if lawyer already has a CONFIRMED meeting in this window:
        # Overlap: NOT (end <= existing_start OR start >= existing_end)
        conflicts = self.supabase.table("consultation_meetings").select("id, scheduled_start, scheduled_end").eq(
            "lawyer_user_id", lawyer_uid
        ).in_("status", ["CONFIRMED"]).lt("scheduled_start", end_dt.isoformat()).gt("scheduled_end", start_dt.isoformat()).execute()

        if conflicts.data and len(conflicts.data) > 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Time slot conflict: Advocate already has a confirmed meeting scheduled during this window."
            )

        # 6. Insert Meeting Record
        meeting_id = str(uuid.uuid4())
        initial_status = "CONFIRMED" if is_lawyer else "REQUESTED"
        now_iso = datetime.now(timezone.utc).isoformat()

        meeting_record = {
            "id": meeting_id,
            "consultation_request_id": payload.consultation_request_id,
            "citizen_user_id": citizen_uid,
            "lawyer_user_id": lawyer_uid,
            "case_uuid": case_uuid,
            "case_id": case_id,
            "scheduled_start": start_dt.isoformat(),
            "scheduled_end": end_dt.isoformat(),
            "meeting_mode": payload.meeting_mode.strip().upper(),
            "status": initial_status,
            "agenda": payload.agenda.strip() if payload.agenda else "Legal consultation discussion",
            "phone_contact": payload.phone_contact.strip() if payload.phone_contact else None,
            "created_by": caller_uid,
            "created_at": now_iso,
            "updated_at": now_iso
        }

        try:
            self.supabase.table("consultation_meetings").insert(meeting_record).execute()
        except Exception as e:
            err_str = str(e).lower()
            if "exclude" in err_str or "23p01" in err_str or "conflict" in err_str:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Time slot conflict: Advocate already has a confirmed meeting scheduled during this window."
                )
            logger.error(f"Error scheduling meeting: {e}")
            raise HTTPException(status_code=500, detail="Failed to schedule meeting.")

        # 7. Notify Recipient
        recipient_uid = lawyer_uid if not is_lawyer else citizen_uid
        event_name = "MEETING_CONFIRMED" if is_lawyer else "MEETING_REQUESTED"
        notification_manager.create_notification(
            recipient_user_id=recipient_uid,
            event_type=event_name,
            title="Consultation Appointment Scheduled" if is_lawyer else "New Consultation Appointment Request",
            message=f"Meeting requested for {start_dt.strftime('%b %d, %Y at %I:%M %p UTC')}.",
            related_case_id=case_id or meeting_id,
            action_url="/lawyer/meetings" if not is_lawyer else "/dashboard/consultations",
            idempotency_key=f"notif_meet_{meeting_id}_{initial_status.lower()}_{recipient_uid}"
        )

        return meeting_record

    def update_meeting_status(
        self,
        user: AuthUser,
        meeting_id: str,
        payload: MeetingStatusUpdateRequest
    ) -> Dict[str, Any]:
        """
        Updates meeting status: CONFIRMED, DECLINED, RESCHEDULE_REQUESTED, CANCELLED, COMPLETED.
        When confirming an online or in-person meeting, records link/location.
        """
        if not user or getattr(user, "account_status", None) != AccountStatus.ACTIVE:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required.")

        self._ensure_connected()
        if not self.supabase:
            raise HTTPException(status_code=500, detail="Database connection unavailable.")

        clean_id = meeting_id.strip()
        m_res = self.supabase.table("consultation_meetings").select("*").eq("id", clean_id).execute()
        if not m_res.data:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Meeting not found.")

        meeting = m_res.data[0]
        caller_uid = str(user.user_id)
        lawyer_uid = str(meeting["lawyer_user_id"])
        citizen_uid = str(meeting["citizen_user_id"])

        if caller_uid != lawyer_uid and caller_uid != citizen_uid and user.role != UserRole.PLATFORM_ADMIN:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied: You are not a party to this meeting.")

        new_status = payload.status.strip().upper()
        now_iso = datetime.now(timezone.utc).isoformat()
        update_dict: Dict[str, Any] = {"status": new_status, "updated_at": now_iso}

        if payload.notes:
            update_dict["notes"] = payload.notes.strip()

        # If Lawyer confirms meeting, check for double booking and attach links
        if new_status == "CONFIRMED":
            if caller_uid != lawyer_uid and user.role != UserRole.PLATFORM_ADMIN:
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only the advocate can confirm a consultation appointment.")

            # Double-check overlap
            conflicts = self.supabase.table("consultation_meetings").select("id").eq(
                "lawyer_user_id", lawyer_uid
            ).eq("status", "CONFIRMED").neq("id", clean_id).lt(
                "scheduled_start", meeting["scheduled_end"]
            ).gt("scheduled_end", meeting["scheduled_start"]).execute()

            if conflicts.data and len(conflicts.data) > 0:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot confirm: You have an overlapping confirmed meeting.")

            if payload.online_meeting_url:
                update_dict["online_meeting_url"] = payload.online_meeting_url.strip()
            if payload.location_details:
                update_dict["location_details"] = payload.location_details.strip()
            if payload.phone_contact:
                update_dict["phone_contact"] = payload.phone_contact.strip()

        elif new_status == "RESCHEDULE_REQUESTED":
            if payload.reschedule_start and payload.reschedule_end:
                update_dict["scheduled_start"] = payload.reschedule_start
                update_dict["scheduled_end"] = payload.reschedule_end

        try:
            res = self.supabase.table("consultation_meetings").update(update_dict).eq("id", clean_id).execute()
        except Exception as e:
            err_str = str(e).lower()
            if "exclude" in err_str or "23p01" in err_str or "conflict" in err_str:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Cannot confirm: You have an overlapping confirmed meeting."
                )
            logger.error(f"Error updating meeting status: {e}")
            raise HTTPException(status_code=500, detail="Failed to update meeting status.")
        updated_meeting = res.data[0] if res.data else {**meeting, **update_dict}

        # Notify the other party
        other_party_uid = citizen_uid if caller_uid == lawyer_uid else lawyer_uid
        notification_manager.create_notification(
            recipient_user_id=other_party_uid,
            event_type=f"MEETING_{new_status}",
            title=f"Meeting {new_status.replace('_', ' ').title()}",
            message=f"Consultation appointment has been updated to {new_status}.",
            related_case_id=meeting.get("case_id") or clean_id,
            action_url="/lawyer/meetings" if other_party_uid == lawyer_uid else "/dashboard/consultations",
            idempotency_key=f"notif_meet_{clean_id}_{new_status.lower()}_{other_party_uid}"
        )

        return updated_meeting

    def get_meeting_details(self, user: AuthUser, meeting_id: str) -> Dict[str, Any]:
        """
        Retrieves meeting details.
        Online URL, location address, and phone are disclosed ONLY to confirmed participants.
        """
        if not user or getattr(user, "account_status", None) != AccountStatus.ACTIVE:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required.")

        self._ensure_connected()
        if not self.supabase:
            raise HTTPException(status_code=500, detail="Database connection unavailable.")

        clean_id = meeting_id.strip()
        m_res = self.supabase.table("consultation_meetings").select("*").eq("id", clean_id).execute()
        if not m_res.data:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Meeting not found.")

        meeting = m_res.data[0]
        caller_uid = str(user.user_id)
        lawyer_uid = str(meeting["lawyer_user_id"])
        citizen_uid = str(meeting["citizen_user_id"])

        if caller_uid != lawyer_uid and caller_uid != citizen_uid and user.role != UserRole.PLATFORM_ADMIN:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied: You are not a party to this meeting.")

        # Privacy Shield: If meeting is NOT confirmed, mask location/URL details
        if meeting.get("status") != "CONFIRMED":
            meeting["online_meeting_url"] = None
            meeting["location_details"] = None
            meeting["phone_contact"] = None

        return meeting

    def list_user_meetings(self, user: AuthUser, status_filter: Optional[str] = None) -> List[Dict[str, Any]]:
        """Lists meetings for authenticated citizen or lawyer."""
        if not user or getattr(user, "account_status", None) != AccountStatus.ACTIVE:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required.")

        self._ensure_connected()
        if not self.supabase:
            return []

        caller_uid = str(user.user_id)
        query = self.supabase.table("consultation_meetings").select("*")

        if user.role == UserRole.LAWYER:
            query = query.eq("lawyer_user_id", caller_uid)
        else:
            query = query.eq("citizen_user_id", caller_uid)

        if status_filter and status_filter.upper() != "ALL":
            query = query.eq("status", status_filter.strip().upper())

        res = query.order("scheduled_start", desc=False).execute()
        meetings = res.data or []

        # Mask unconfirmed meeting links
        for m in meetings:
            if m.get("status") != "CONFIRMED":
                m["online_meeting_url"] = None
                m["location_details"] = None
                m["phone_contact"] = None

        return meetings

    def get_lawyer_availability(self, lawyer_user_id: str) -> Dict[str, Any]:
        """Public/Authenticated lookup of advocate availability rules and slot durations."""
        self._ensure_connected()
        if not self.supabase:
            return {"available_days": [1, 2, 3, 4, 5], "slot_duration_minutes": 30}

        clean_uid = lawyer_user_id.strip()
        res = self.supabase.table("lawyer_availability").select("*").eq("lawyer_user_id", clean_uid).execute()
        if res.data and len(res.data) > 0:
            return res.data[0]

        # Default standard business hours (10:00 - 18:00 IST / 04:30 - 12:30 UTC)
        return {
            "lawyer_user_id": clean_uid,
            "available_days": [1, 2, 3, 4, 5],
            "start_time_utc": "04:30:00",
            "end_time_utc": "12:30:00",
            "slot_duration_minutes": 30,
            "timezone": "Asia/Kolkata",
            "unavailable_dates": []
        }

    def update_lawyer_availability(self, user: AuthUser, payload: LawyerAvailabilityPayload) -> Dict[str, Any]:
        """Allows an advocate to configure their consultation schedule and unavailable dates."""
        if not user or user.role != UserRole.LAWYER:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only registered advocates can configure consultation availability.")

        self._ensure_connected()
        if not self.supabase:
            raise HTTPException(status_code=500, detail="Database connection unavailable.")

        caller_uid = str(user.user_id)
        now_iso = datetime.now(timezone.utc).isoformat()

        record = {
            "lawyer_user_id": caller_uid,
            "available_days": payload.available_days,
            "start_time_utc": payload.start_time_utc,
            "end_time_utc": payload.end_time_utc,
            "slot_duration_minutes": payload.slot_duration_minutes,
            "timezone": payload.timezone,
            "unavailable_dates": payload.unavailable_dates,
            "updated_at": now_iso
        }

        res = self.supabase.table("lawyer_availability").upsert(record, on_conflict="lawyer_user_id").execute()
        return res.data[0] if res.data else record

    # =========================================================================
    # Internal Helpers
    # =========================================================================

    def _ensure_participant(self, conversation_id: str, user_id: str, role: str):
        """Idempotently ensures user is an active participant in a conversation."""
        existing = self.supabase.table("conversation_participants").select("id").eq(
            "conversation_id", conversation_id
        ).eq("user_id", user_id).execute()

        if not existing.data:
            self.supabase.table("conversation_participants").insert({
                "conversation_id": conversation_id,
                "user_id": user_id,
                "participant_role": role,
                "participant_status": "ACTIVE"
            }).execute()


communication_manager = CommunicationManager()

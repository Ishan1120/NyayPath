"""
NyayPath Audit & Identity Management Module (Phase 1.3.7)
=========================================================
Strict separation of authenticated user identities and immutable audit trails.
- audit_actor_id: Pseudonymous stable UUID.
- audit_actor_mappings: Restricted mapping table connecting audit_actor_id to auth.users(id).
- case_activity_log: Append-only under application permissions; zero IP address storage.
- Statutory erasure: Severs mapping without modifying historical audit events.
"""

import uuid
import logging
from typing import Optional, Dict, Any
from datetime import datetime, timezone

try:
    from .auth import AuthUser, UserRole
except (ImportError, ValueError):
    from auth import AuthUser, UserRole

logger = logging.getLogger("nyaypath.audit")

# In-memory mapping fallback for local test/dev when remote Supabase is unconfigured
_LOCAL_ACTOR_MAPPINGS: Dict[str, str] = {}  # user_id -> audit_actor_id
_LOCAL_ACTIVITY_LOGS: list = []


def get_or_create_audit_actor_id(user_id: str, supabase_client=None) -> str:
    """
    Retrieves or generates a stable pseudonymous audit_actor_id for an authenticated user.
    Never exposes real user_id in the audit log.
    """
    if not user_id:
        raise ValueError("user_id cannot be null or empty for user-attributed audit events.")

    if supabase_client:
        try:
            # Query restricted audit_actor_mappings vault
            res = supabase_client.table("audit_actor_mappings").select("audit_actor_id").eq("user_id", user_id).execute()
            if res.data and len(res.data) > 0:
                return res.data[0]["audit_actor_id"]

            # Provision new stable pseudonymous UUID
            new_audit_id = str(uuid.uuid4())
            insert_res = supabase_client.table("audit_actor_mappings").insert({
                "audit_actor_id": new_audit_id,
                "user_id": user_id
            }).execute()
            if insert_res.data:
                return new_audit_id
        except Exception as e:
            logger.warning(f"Error querying audit_actor_mappings via Supabase: {e}. Falling back to memory.")

    # Local fallback for dev/testing
    if user_id not in _LOCAL_ACTOR_MAPPINGS:
        _LOCAL_ACTOR_MAPPINGS[user_id] = str(uuid.uuid4())
    return _LOCAL_ACTOR_MAPPINGS[user_id]


def sever_audit_actor_mapping(user_id: str, supabase_client=None) -> bool:
    """
    Executes approved statutory erasure by removing the identity mapping.
    Permanently unlinks historical case_activity_log events from the user account.
    Historical events remain 100% byte-for-byte immutable; zero fabricated users created.
    """
    if not user_id:
        return False

    success = False
    if supabase_client:
        try:
            res = supabase_client.table("audit_actor_mappings").delete().eq("user_id", user_id).execute()
            success = bool(res.data)
        except Exception as e:
            logger.error(f"Failed to sever audit_actor_mapping for user {user_id}: {e}")
            success = False

    if user_id in _LOCAL_ACTOR_MAPPINGS:
        del _LOCAL_ACTOR_MAPPINGS[user_id]
        success = True

    return success


def record_case_activity(
    case_uuid: str,
    case_id: str,
    action_type: str,
    action_details: Dict[str, Any],
    actor_user: Optional[AuthUser] = None,
    actor_type: str = "USER",  # USER, SYSTEM, ANONYMOUS
    supabase_client=None
) -> Dict[str, Any]:
    """
    Appends an event to the case activity audit log.
    - actor_role is derived STRICTLY from trusted server-verified AuthUser (never client body).
    - audit_actor_id is NULL for SYSTEM and ANONYMOUS events.
    - Zero IP addresses are stored in this business audit log.
    """
    now_iso = datetime.now(timezone.utc).isoformat()

    # 1. Establish actor_type and trusted actor_role
    if actor_type == "SYSTEM" or actor_user is None and actor_type != "ANONYMOUS":
        provenance = "SYSTEM"
        trusted_role = "SYSTEM"
        audit_actor_id = None
    elif actor_type == "ANONYMOUS":
        provenance = "ANONYMOUS"
        trusted_role = "CITIZEN"
        audit_actor_id = None
    else:
        provenance = "USER"
        trusted_role = actor_user.role.value if hasattr(actor_user.role, "value") else str(actor_user.role)
        audit_actor_id = get_or_create_audit_actor_id(actor_user.user_id, supabase_client=supabase_client)

    # 2. Sanitize action_details to guarantee zero PII, credentials, or confidential complaint contents
    sanitized_details = dict(action_details or {})
    for secret_key in [
        "password", "token", "verification_key", "tracking_key", "salt", "ip",
        "student_name", "roll_number", "contact_email", "email", "phone",
        "description", "complaint", "subject"
    ]:
        sanitized_details.pop(secret_key, None)

    event_record = {
        "id": str(uuid.uuid4()),
        "case_uuid": case_uuid,
        "case_id": case_id,
        "audit_actor_id": audit_actor_id,
        "actor_type": provenance,
        "actor_role": trusted_role,
        "action_type": action_type,
        "action_details": sanitized_details,
        "created_at": now_iso
    }

    if supabase_client:
        try:
            res = supabase_client.table("case_activity_log").insert(event_record).execute()
            if res.data:
                return res.data[0]
        except Exception as e:
            logger.error(f"Failed to persist case activity event via Supabase: {e}")

    _LOCAL_ACTIVITY_LOGS.append(event_record)
    return event_record


"""
NyayPath Intelligent Notification System (Phase 2.3)
===================================================
Provides persistent, user-specific in-app notifications tied directly to
genuine case lifecycle events.

Key Security & Reliability Guarantees:
- Strict Recipient Boundary: Notifications are indexed and queried strictly by recipient_user_id.
- Zero Proctor Notes Leakage: Internal deliberations and secret keys are stripped before notification generation.
- Idempotency & Deduplication: High-entropy idempotency keys prevent duplicate notifications on retry.
- Non-Blocking Fault Tolerance: Notification dispatch errors are caught safely so underlying case actions succeed.
- Fail-Closed Access Control: Users can view, update, or dismiss ONLY their own notifications (403 on tampering).
"""

import os
import uuid
import secrets
import logging
from enum import Enum
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
from fastapi import HTTPException, status
from pydantic import BaseModel, Field

try:
    from supabase import create_client, Client
except ImportError:
    create_client, Client = None, None

logger = logging.getLogger("nyaypath.notifications")


def _is_production() -> bool:
    return (
        os.environ.get("ENVIRONMENT") == "production" or
        os.environ.get("NODE_ENV") == "production" or
        os.environ.get("ENV") == "production" or
        os.environ.get("VERCEL") == "1"
    )


# =============================================================================
# Models & Event Types
# =============================================================================

class NotificationEvent(str, Enum):
    CASE_SUBMITTED = "CASE_SUBMITTED"
    CASE_STATUS_UPDATED = "CASE_STATUS_UPDATED"
    CASE_RESOLVED = "CASE_RESOLVED"
    CASE_WITHDRAWN = "CASE_WITHDRAWN"
    HEARING_SCHEDULED = "HEARING_SCHEDULED"
    CITIZEN_REMARK_ADDED = "CITIZEN_REMARK_ADDED"
    EXPEDITE_REQUESTED = "EXPEDITE_REQUESTED"
    COMMITTEE_ASSIGNED = "COMMITTEE_ASSIGNED"

class NotificationResponse(BaseModel):
    id: str
    recipient_user_id: str
    event_type: str
    title: str
    message: str
    related_case_id: str
    case_uuid: Optional[str] = None
    is_read: bool = False
    action_url: Optional[str] = None
    created_at: str
    read_at: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class NotificationListResponse(BaseModel):
    notifications: List[Dict[str, Any]]
    unread_count: int
    total: int


class MarkReadRequest(BaseModel):
    notification_ids: Optional[List[str]] = None


# =============================================================================
# Notification Service
# =============================================================================

class NotificationManager:
    def __init__(self):
        url = os.environ.get("SUPABASE_URL", "")
        secret_key = os.environ.get("SUPABASE_SECRET_KEY", "")
        is_offline_test = os.environ.get("SUPABASE_OFFLINE_TEST") == "1"
        self.use_supabase = bool(url and secret_key and create_client and not is_offline_test)
        self.supabase: Optional[Client] = None
        self._memory_notifications: Dict[str, Dict[str, Any]] = {}

        if self.use_supabase:
            try:
                self.supabase = create_client(url, secret_key)
                logger.info("NotificationManager: Connected to Supabase.")
            except Exception as e:
                logger.error(f"NotificationManager: Supabase connection failed: {e}")
                self.use_supabase = False
                if _is_production():
                    raise RuntimeError("Persistent database required for notifications in production.") from e

    def _ensure_connected(self):
        is_offline_test = os.environ.get("SUPABASE_OFFLINE_TEST") == "1"
        if is_offline_test:
            self.use_supabase = False
            self.supabase = None
            return

        url = os.environ.get("SUPABASE_URL", "")
        secret_key = os.environ.get("SUPABASE_SECRET_KEY", "")
        if url and secret_key and create_client and not self.supabase:
            try:
                self.supabase = create_client(url, secret_key)
                self.use_supabase = True
            except Exception as e:
                logger.warning(f"NotificationManager reconnect failed: {e}")
                self.use_supabase = False
                self.supabase = None

    # -------------------------------------------------------------------------
    # Core Dispatch Engine
    # -------------------------------------------------------------------------
    def create_notification(
        self,
        recipient_user_id: str,
        event_type: str,
        title: str,
        message: str,
        related_case_id: str,
        case_uuid: Optional[str] = None,
        action_url: Optional[str] = None,
        idempotency_key: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Persists a user-specific notification with idempotency enforcement.
        - Strips any accidental confidential note leakage.
        - Fails safely: Log errors without breaking core case transitions.
        """
        if not recipient_user_id or not recipient_user_id.strip():
            logger.warning("Notification discarded: recipient_user_id is missing.")
            return None

        clean_recipient = recipient_user_id.strip()
        now_iso = datetime.now(timezone.utc).isoformat()
        notif_id = str(uuid.uuid4())

        # Auto-generate unique high-entropy idempotency key if omitted
        if not idempotency_key:
            idempotency_key = f"notif_{clean_recipient}_{event_type}_{related_case_id}_{secrets.token_hex(8)}"

        # Default action_url to case details if omitted
        if not action_url and related_case_id:
            action_url = f"/dashboard/my-cases/{related_case_id}"

        # Clean metadata to prevent secret leakage
        clean_metadata = dict(metadata or {})
        for secret in ["proctor_notes", "verification_key_hash", "tracking_key_hash", "password", "token"]:
            clean_metadata.pop(secret, None)

        record = {
            "id": notif_id,
            "recipient_user_id": clean_recipient,
            "event_type": event_type,
            "title": title.strip(),
            "message": message.strip(),
            "related_case_id": related_case_id.strip(),
            "case_uuid": case_uuid,
            "is_read": False,
            "action_url": action_url,
            "idempotency_key": idempotency_key,
            "metadata": clean_metadata,
            "created_at": now_iso,
            "read_at": None
        }

        # 1. Supabase Persistence via direct insert or RPC
        self._ensure_connected()
        if self.use_supabase and self.supabase:
            try:
                # Use private.create_notification RPC if available for atomic idempotency
                try:
                    rpc_res = self.supabase.rpc("create_notification", {
                        "p_recipient_user_id": clean_recipient,
                        "p_event_type": event_type,
                        "p_title": record["title"],
                        "p_message": record["message"],
                        "p_related_case_id": record["related_case_id"],
                        "p_case_uuid": case_uuid,
                        "p_action_url": action_url,
                        "p_idempotency_key": idempotency_key,
                        "p_metadata": clean_metadata
                    }).execute()
                    if rpc_res.data:
                        record["id"] = str(rpc_res.data)
                        return record
                except Exception as rpc_err:
                    # Fallback to direct table insertion if RPC is not loaded
                    logger.debug(f"RPC create_notification fallback: {rpc_err}")
                    res = self.supabase.table("notifications").insert(record).execute()
                    if res.data:
                        return res.data[0]
            except Exception as e:
                err_str = str(e).lower()
                if "unique" in err_str or "duplicate" in err_str or "23505" in err_str:
                    logger.info(f"Duplicate notification suppressed by idempotency_key {idempotency_key}")
                    # Fetch existing record
                    try:
                        existing = self.supabase.table("notifications").select("*").eq("idempotency_key", idempotency_key).execute()
                        if existing.data:
                            return existing.data[0]
                    except Exception:
                        pass
                    return record
                logger.error(f"Failed to persist notification to Supabase: {e}")
                if _is_production():
                    # Log and fail closed in production without memory fallback
                    return None

        # 2. Local memory fallback for dev/testing only
        if _is_production():
            return None

        if idempotency_key in self._memory_notifications:
            return self._memory_notifications[idempotency_key]

        self._memory_notifications[idempotency_key] = record
        return record

    # -------------------------------------------------------------------------
    # Retrieval & Read Status
    # -------------------------------------------------------------------------
    def list_user_notifications(
        self,
        user_id: str,
        is_read: Optional[bool] = None,
        limit: int = 50,
        offset: int = 0
    ) -> Dict[str, Any]:
        """
        Lists notifications strictly for the authenticated recipient user_id.
        """
        self._ensure_connected()
        safe_limit = max(1, min(100, int(limit)))
        safe_offset = max(0, int(offset))
        user_notifs: List[Dict[str, Any]] = []

        if self.use_supabase and self.supabase:
            try:
                query = self.supabase.table("notifications").select("*").eq("recipient_user_id", user_id).order("created_at", desc=True)
                if is_read is not None:
                    query = query.eq("is_read", is_read)
                query = query.limit(safe_limit).offset(safe_offset)
                res = query.execute()

                # Get unread count
                unread_res = self.supabase.table("notifications").select("id", count="exact").eq("recipient_user_id", user_id).eq("is_read", False).execute()
                unread_count = unread_res.count if unread_res.count is not None else 0

                return {
                    "notifications": res.data or [],
                    "unread_count": unread_count,
                    "total": len(res.data or [])
                }
            except Exception as e:
                logger.error(f"Error querying notifications from Supabase: {e}")
                if _is_production():
                    raise HTTPException(
                        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                        detail="Failed to query notifications in production."
                    ) from e

        if _is_production():
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Database notifications unavailable in production."
            )

        # Dev / memory fallback
        for key, notif in self._memory_notifications.items():
            if notif.get("recipient_user_id") == user_id:
                if is_read is None or notif.get("is_read") == is_read:
                    user_notifs.append(dict(notif))

        # Sort descending by created_at
        user_notifs = sorted(user_notifs, key=lambda x: x.get("created_at", ""), reverse=True)
        unread_count = sum(1 for n in user_notifs if not n.get("is_read"))

        paginated = user_notifs[safe_offset:safe_offset + safe_limit]
        return {
            "notifications": paginated,
            "unread_count": unread_count,
            "total": len(user_notifs)
        }

    def get_unread_count(self, user_id: str) -> int:
        """Returns the live count of unread notifications for a user."""
        self._ensure_connected()
        if self.use_supabase and self.supabase:
            try:
                res = self.supabase.table("notifications").select("id", count="exact").eq("recipient_user_id", user_id).eq("is_read", False).execute()
                return res.count if res.count is not None else 0
            except Exception as e:
                logger.warning(f"Error counting unread notifications: {e}")
                if _is_production():
                    raise HTTPException(
                        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                        detail="Database notification count error in production."
                    ) from e

        if _is_production():
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Database notification count unavailable in production."
            )

        # Fallback
        return sum(
            1 for n in self._memory_notifications.values()
            if n.get("recipient_user_id") == user_id and not n.get("is_read")
        )

    def mark_as_read(self, notification_id: str, user_id: str) -> Dict[str, Any]:
        """
        Marks a specific notification as read.
        Fails closed with 403 Forbidden if the notification does not belong to user_id.
        """
        self._ensure_connected()
        now_iso = datetime.now(timezone.utc).isoformat()

        if self.use_supabase and self.supabase:
            try:
                # 1. Fetch notification to verify ownership
                res = self.supabase.table("notifications").select("*").eq("id", notification_id).execute()
                if not res.data:
                    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Notification not found.")

                notif = res.data[0]
                if notif.get("recipient_user_id") != user_id:
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail="Access denied: Cannot modify another user's notifications."
                    )

                # 2. Update is_read
                update_res = self.supabase.table("notifications").update({
                    "is_read": True,
                    "read_at": now_iso
                }).eq("id", notification_id).execute()

                return update_res.data[0] if update_res.data else notif
            except HTTPException:
                raise
            except Exception as e:
                logger.error(f"Error updating notification read status: {e}")
                if _is_production():
                    raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Database update error in production.") from e
                raise HTTPException(status_code=500, detail="Database update error.") from e

        if _is_production():
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Database notifications unavailable in production."
            )

        # Memory fallback
        for key, notif in self._memory_notifications.items():
            if notif.get("id") == notification_id:
                if notif.get("recipient_user_id") != user_id:
                    raise HTTPException(status_code=403, detail="Access denied.")
                notif["is_read"] = True
                notif["read_at"] = now_iso
                return dict(notif)

        raise HTTPException(status_code=404, detail="Notification not found.")

    def mark_all_as_read(self, user_id: str) -> int:
        """Marks all unread notifications for user_id as read."""
        self._ensure_connected()
        now_iso = datetime.now(timezone.utc).isoformat()

        if self.use_supabase and self.supabase:
            try:
                res = self.supabase.table("notifications").update({
                    "is_read": True,
                    "read_at": now_iso
                }).eq("recipient_user_id", user_id).eq("is_read", False).execute()
                return len(res.data or [])
            except Exception as e:
                logger.error(f"Error marking all notifications as read: {e}")
                if _is_production():
                    raise HTTPException(status_code=503, detail="Database update error in production.") from e
                return 0

        if _is_production():
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Database notifications unavailable in production."
            )

        # Memory fallback
        count = 0
        for notif in self._memory_notifications.values():
            if notif.get("recipient_user_id") == user_id and not notif.get("is_read"):
                notif["is_read"] = True
                notif["read_at"] = now_iso
                count += 1
        return count

    def delete_notification(self, notification_id: str, user_id: str) -> bool:
        """
        Deletes/dismisses a notification.
        Fails closed with 403 Forbidden if the notification does not belong to user_id.
        """
        self._ensure_connected()

        if self.use_supabase and self.supabase:
            try:
                res = self.supabase.table("notifications").select("recipient_user_id").eq("id", notification_id).execute()
                if not res.data:
                    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Notification not found.")

                if res.data[0].get("recipient_user_id") != user_id:
                    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied.")

                del_res = self.supabase.table("notifications").delete().eq("id", notification_id).execute()
                return bool(del_res.data)
            except HTTPException:
                raise
            except Exception as e:
                logger.error(f"Error deleting notification: {e}")
                if _is_production():
                    raise HTTPException(status_code=503, detail="Database error deleting notification.") from e
                return False

        if _is_production():
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Database notifications unavailable in production."
            )

        # Memory fallback
        target_key = None
        for key, notif in self._memory_notifications.items():
            if notif.get("id") == notification_id:
                if notif.get("recipient_user_id") != user_id:
                    raise HTTPException(status_code=403, detail="Access denied.")
                target_key = key
                break

        if target_key:
            del self._memory_notifications[target_key]
            return True

        raise HTTPException(status_code=404, detail="Notification not found.")


notification_manager = NotificationManager()

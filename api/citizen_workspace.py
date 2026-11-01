"""
NyayPath Citizen Dashboard & My Cases Workspace Module
Phase 2.1 Implementation

Provides dedicated citizen-facing endpoints and logic for:
- Citizen Dashboard Statistics (Total, Active, Resolved, Pending Actions)
- My Cases Workspace (Strict Ownership Filtering, Search, Category/Status Filters, Sorting, Pagination)
- Case Details & Timeline Tracking (Milestone Events, Hidden Internal Proctor Notes, Document Inventory)
- Fail-Closed Security & Ownership Validation
"""

import os
import math
import logging
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
from fastapi import HTTPException, status
from pydantic import BaseModel

try:
    from .auth import AuthUser, UserRole, AccountStatus
except ImportError:
    from auth import AuthUser, UserRole, AccountStatus

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
    "DISPOSED"
}


def _is_production() -> bool:
    return (
        os.environ.get("ENVIRONMENT") == "production" or
        os.environ.get("NODE_ENV") == "production" or
        os.environ.get("ENV") == "production" or
        os.environ.get("VERCEL") == "1"
    )


class CitizenWorkspaceManager:
    def __init__(self):
        url: str = os.environ.get("SUPABASE_URL", "")
        secret_key: str = os.environ.get("SUPABASE_SECRET_KEY", "")
        is_offline_test = os.environ.get("SUPABASE_OFFLINE_TEST") == "1"
        self.use_supabase = bool(url and secret_key and create_client and not is_offline_test)
        self.supabase: Optional[Client] = None

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
                "role": user.role.value,
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

        # Sorting
        reverse = (sort_order.lower() == "desc")
        if sort_by in ["created_at", "updated_at"]:
            filtered = sorted(filtered, key=lambda x: str(x.get(sort_by) or ""), reverse=reverse)
        elif sort_by == "status":
            filtered = sorted(filtered, key=lambda x: str(x.get("status") or ""), reverse=reverse)
        elif sort_by == "category":
            filtered = sorted(filtered, key=lambda x: str(x.get("category") or ""), reverse=reverse)
        else:
            filtered = sorted(filtered, key=lambda x: str(x.get("created_at") or ""), reverse=True)

        total = len(filtered)
        limit = max(1, min(limit, 100))
        page = max(1, page)
        total_pages = max(1, math.ceil(total / limit)) if total > 0 else 1
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
        owner_id = (
            case.get("student_user_id") or
            case.get("data", {}).get("citizen_user_id") or
            case.get("user_id")
        )

        if owner_id != user.user_id:
            # Rejection with 403 Forbidden
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

                # 2. Query cases table where data->>'citizen_user_id' == user_id or data->>'student_user_id' == user_id
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
                                    flattened["status"] = row.get("status") or flattened.get("status") or "FILED"
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

        # Dev / Test fallback: SQLite & In-memory
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
                    flattened["status"] = row.get("status") or flattened.get("status") or "FILED"
                    flattened["created_at"] = row.get("created_at")
                    flattened["updated_at"] = row.get("updated_at")
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
            "description": case.get("description") or "",
            "status": (case.get("status") or "SUBMITTED").upper(),
            "severity": case.get("severity") or "NORMAL",
            "department": case.get("department"),
            "year": case.get("year"),
            "institution_id": case.get("institution_id"),
            "hearing_date": case.get("hearing_date"),
            "action_taken": case.get("action_taken"),
            "resolution_details": case.get("resolution_details"),
            "incident_date": case.get("incident_date"),
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
            "title": "Grievance Submitted",
            "description": f"Grievance registered under category '{case.get('category', 'General')}'.",
            "timestamp": created_at,
            "status": "SUBMITTED",
            "actor_type": "STUDENT"
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
                        desc = details.get("public_message") or details.get("note") or f"Case milestone recorded: {title}"
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
                    # Clean out internal proctor notes
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
                "title": "Grievance Resolved",
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

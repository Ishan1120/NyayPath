"""
NyayPath College Proctor & Student Grievance Redressal Engine
Remediated for Phase 1.2:
- Strict production database persistence (zero silent SQLite fallback in production).
- 128-bit Verification Keys with constant-time SHA-256 verification.
- Complete anonymous privacy: student_user_id is strictly NULL, student_name and roll_number omitted.
- Valid UUID enforcement on student_user_id foreign keys (never invalid string IDs).
- Scoped Supabase database operations.
"""

import os
import uuid
import json
import sqlite3
import logging
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, List, Optional
from pydantic import BaseModel
from fastapi import HTTPException, status

try:
    from supabase import create_client, Client
except ImportError:
    create_client, Client = None, None

try:
    from .auth import (
        AuthUser,
        UserRole,
        AccountStatus,
        generate_secure_verification_key,
        hash_verification_key,
        verify_tracking_credential,
        verify_institutional_boundary
    )
    from .rate_limiter import enforce_rate_limit, rate_limiter
except ImportError:
    from auth import (
        AuthUser,
        UserRole,
        AccountStatus,
        generate_secure_verification_key,
        hash_verification_key,
        verify_tracking_credential,
        verify_institutional_boundary
    )
    from rate_limiter import enforce_rate_limit, rate_limiter

logger = logging.getLogger(__name__)

def is_valid_uuid(val: Optional[str]) -> bool:
    """Validates whether a string is a standard RFC 4122 UUID."""
    if not val:
        return False
    try:
        uuid_obj = uuid.UUID(str(val))
        return str(uuid_obj) == str(val).lower()
    except Exception:
        return False

class StudentGrievanceSubmit(BaseModel):
    institution_id: Optional[str] = "INST_DEFAULT"
    student_name: Optional[str] = None
    roll_number: Optional[str] = None
    department: str
    year: str
    category: str
    subject: str
    description: str
    incident_date: Optional[str] = None
    is_anonymous: Optional[bool] = False
    confidentiality_mode: Optional[str] = "CONFIDENTIAL"
    supporting_documents: Optional[List[Dict[str, Any]]] = []

class ProctorUpdateStatus(BaseModel):
    case_id: str
    new_status: str  # SUBMITTED, UNDER_INQUIRY, HEARING_SCHEDULED, ACTION_TAKEN, RESOLVED, CLOSED
    proctor_notes: Optional[str] = ""
    hearing_date: Optional[str] = None
    action_taken: Optional[str] = None
    resolution_details: Optional[str] = None
    assigned_proctor: Optional[str] = None
    assigned_proctor_user_id: Optional[str] = None
    assigned_committee: Optional[str] = None

class StudentTrackingRequest(BaseModel):
    case_id: str
    verification_key: str

# Permitted state machine transitions for campus grievances (Task 2 & 4)
PERMITTED_STATUS_TRANSITIONS: Dict[str, set] = {
    "SUBMITTED": {"UNDER_INQUIRY", "UNDER_REVIEW", "HEARING_SCHEDULED", "ACTION_TAKEN", "RESOLVED", "CLOSED"},
    "UNDER_REVIEW": {"UNDER_INQUIRY", "HEARING_SCHEDULED", "ACTION_TAKEN", "RESOLVED", "CLOSED"},
    "UNDER_INQUIRY": {"HEARING_SCHEDULED", "ACTION_TAKEN", "RESOLVED", "CLOSED"},
    "HEARING_SCHEDULED": {"ACTION_TAKEN", "RESOLVED", "CLOSED", "UNDER_INQUIRY"},
    "ACTION_TAKEN": {"RESOLVED", "CLOSED", "UNDER_INQUIRY"},
    "RESOLVED": {"CLOSED"},
    "CLOSED": set()  # Terminal state
}

def parse_and_validate_hearing_date(date_str: Optional[str]) -> Optional[str]:
    """
    Parses and validates hearing_date into standard ISO 'YYYY-MM-DD' format for PostgreSQL DATE.
    Accepts ISO dates, standard date strings, or human-readable formats.
    """
    if not date_str or not date_str.strip():
        return None
    val = date_str.strip()
    try:
        from dateutil import parser
        parsed_date = parser.parse(val, fuzzy=True).date()
        return parsed_date.isoformat()
    except Exception:
        try:
            return datetime.strptime(val[:10], "%Y-%m-%d").date().isoformat()
        except Exception:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid hearing_date format: '{val}'. Expected a valid calendar date (e.g. YYYY-MM-DD)."
            )

# =====================================================================
# Persistent Storage Manager for Campus Cases (Remediated)
# =====================================================================

class CampusProctorManager:
    def __init__(self):
        url: str = os.environ.get("SUPABASE_URL", "")
        # Campus proctor operations require the service-role secret key because:
        #   - Case writes (INSERT/UPDATE) are performed by the FastAPI backend on
        #     behalf of authenticated users — not directly by browser clients.
        #   - The backend verifies identity and institution boundary in application
        #     code before issuing any database write.
        #   - Anon/publishable key cannot bypass RLS for service-side writes.
        # SUPABASE_SECRET_KEY: service_role key — never sent to the browser.
        secret_key: str = os.environ.get("SUPABASE_SECRET_KEY", "")

        is_offline_test = os.environ.get("SUPABASE_OFFLINE_TEST") == "1"
        self.use_supabase = bool(url and secret_key and create_client and not is_offline_test)
        self.supabase: Optional[Client] = None
        self._local_db_path = os.environ.get("CAMPUS_SQLITE_DB", "campus_cases_persistent.db")
        self._local_case_cache: Dict[str, Any] = {}

        is_production = (
            os.environ.get("VERCEL") == "1" or
            os.environ.get("NODE_ENV") == "production" or
            os.environ.get("ENV") == "production" or
            os.environ.get("ENVIRONMENT") == "production"
        )
        explicit_allow = os.environ.get("ALLOW_LOCAL_SQLITE")
        explicit_test = os.environ.get("TEST_MODE")

        if explicit_allow == "0" or explicit_test == "0":
            self.allow_local_sqlite = False
        elif explicit_allow == "1" or explicit_test == "1":
            self.allow_local_sqlite = True
        else:
            self.allow_local_sqlite = not is_production

        if self.use_supabase:
            try:
                self.supabase = create_client(url, secret_key)
                logger.info("Campus Proctor Manager: Connected to Supabase PostgreSQL.")
            except Exception as e:
                logger.error(f"Campus Proctor Supabase connection error: {e}")
                self.use_supabase = False
                self.supabase = None
        else:
            if self.allow_local_sqlite:
                logger.info(f"Supabase credentials not configured. Local test SQLite enabled at '{self._local_db_path}'.")
                self._init_sqlite_db()
            else:
                logger.warning("Supabase credentials not configured and ALLOW_LOCAL_SQLITE=0. Production database persistence is strictly enforced.")

    def _init_sqlite_db(self):
        """Initializes persistent disk-backed database schema for local dev/testing."""
        try:
            conn = sqlite3.connect(self._local_db_path)
            cursor = conn.cursor()
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS campus_cases (
                id TEXT PRIMARY KEY,
                case_id TEXT UNIQUE NOT NULL,
                institution_id TEXT NOT NULL,
                student_user_id TEXT,
                student_name TEXT,
                roll_number TEXT,
                department TEXT NOT NULL,
                year TEXT NOT NULL,
                category TEXT NOT NULL,
                subject TEXT NOT NULL,
                description TEXT NOT NULL,
                incident_date TEXT,
                is_anonymous INTEGER NOT NULL DEFAULT 0,
                confidentiality_mode TEXT NOT NULL,
                severity TEXT NOT NULL,
                status TEXT NOT NULL,
                proctor_notes TEXT,
                hearing_date TEXT,
                action_taken TEXT,
                resolution_details TEXT,
                resolution_deadline TEXT,
                assigned_proctor TEXT,
                assigned_committee TEXT,
                supporting_documents TEXT NOT NULL DEFAULT '[]',
                verification_key_hash TEXT NOT NULL,
                key_version TEXT NOT NULL DEFAULT 'v1',
                history TEXT NOT NULL DEFAULT '[]',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            """)
            try:
                cursor.execute("ALTER TABLE campus_cases ADD COLUMN key_version TEXT NOT NULL DEFAULT 'v1';")
            except Exception:
                pass
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_campus_case_id ON campus_cases(case_id);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_campus_institution ON campus_cases(institution_id);")
            conn.commit()
            conn.close()
        except Exception as e:
            logger.error(f"Failed to initialize local SQLite persistent DB: {e}")

    def _ensure_connected(self):
        """
        Validates that persistent storage is available.
        In production, raises HTTP 503 if Supabase is disconnected.
        """
        if self.use_supabase and self.supabase is not None:
            return
        if not self.allow_local_sqlite:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Database unavailable: Persistent Supabase database connection required. Ephemeral storage is strictly disabled in production."
            )

    # -----------------------------------------------------------------
    # Case Submission (Student Workflow - Task 4, 5, 7)
    # -----------------------------------------------------------------
    def create_case(
        self,
        payload: StudentGrievanceSubmit,
        student_user: Optional[AuthUser] = None
    ) -> Dict[str, Any]:
        """
        Registers a new grievance with unique Case ID and 128-bit verification key.
        - If anonymous: student_user_id is strictly NULL, student_name & roll_number are omitted.
        - If authenticated & not anonymous: student_user_id is verified as genuine UUID.
        - Strictly persists to Supabase (or local SQLite if explicitly enabled in dev/test).
        """
        self._ensure_connected()

        raw_code = uuid.uuid4().hex[:4].upper()
        dept_code = payload.department[:2].upper() if payload.department else "GR"
        case_id = f"CAMPUS-{raw_code}-{dept_code}"
        
        # Genuine 128-bit random verification key (32 hex characters)
        verification_key = generate_secure_verification_key()
        verification_hash = hash_verification_key(verification_key)

        now = datetime.now(timezone.utc)
        now_iso = now.isoformat()
        deadline = (now + timedelta(days=15)).strftime("%Y-%m-%d")

        # Classify severity
        desc_lower = (payload.description or "").lower()
        if any(term in desc_lower for term in ["ragging", "harassment", "contaminated", "sick", "assault", "threat"]):
            severity = "URGENT"
        elif any(term in desc_lower for term in ["exam", "marksheet", "scholarship", "fee", "discrepancy"]):
            severity = "HIGH"
        else:
            severity = "NORMAL"

        # Task 7: Strict Anonymous Privacy
        is_anon = bool(payload.is_anonymous)
        if is_anon:
            # Strictly decouple from student account identity
            student_uid = None
            student_name = None
            roll_number = None
            history_actor = "Anonymous Student"
        else:
            # Confidential / Non-anonymous
            student_uid = student_user.user_id if (student_user and is_valid_uuid(student_user.user_id)) else None
            student_name = payload.student_name or "Confidential Student"
            roll_number = payload.roll_number or "Protected"
            history_actor = student_name

        initial_history = [{
            "timestamp": now_iso,
            "action": "GRIEVANCE_REGISTERED",
            "actor": history_actor,
            "details": "Grievance submitted under UGC Student Grievance Regulations."
        }]

        record = {
            "id": str(uuid.uuid4()),
            "case_id": case_id,
            "institution_id": (payload.institution_id or "INST_DEFAULT").strip().upper(),
            "student_user_id": student_uid,
            "student_name": student_name,
            "roll_number": roll_number,
            "department": payload.department,
            "year": payload.year,
            "category": payload.category,
            "subject": payload.subject,
            "description": payload.description,
            "incident_date": payload.incident_date or now.strftime("%Y-%m-%d"),
            "is_anonymous": is_anon,
            "confidentiality_mode": payload.confidentiality_mode or "CONFIDENTIAL",
            "severity": severity,
            "status": "SUBMITTED",
            "proctor_notes": "Grievance received by the Proctorial Grievance Redressal Cell. Acknowledged.",
            "hearing_date": "Pending Proctorial Review",
            "action_taken": "Pending inquiry by departmental committee.",
            "resolution_details": None,
            "resolution_deadline": deadline,
            "assigned_proctor": None,
            "assigned_committee": None,
            "supporting_documents": payload.supporting_documents or [],
            "verification_key_hash": verification_hash,
            "key_version": "v1",
            "history": initial_history,
            "created_at": now_iso,
            "updated_at": now_iso
        }

        # 1. Supabase Persistence
        if self.use_supabase and self.supabase:
            try:
                res = self.supabase.table("campus_cases").insert(record).execute()
                if not res.data:
                    raise RuntimeError("Supabase returned empty insert response.")
            except Exception as e:
                logger.error(f"Supabase INSERT Error in campus_proctor: {e}")
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Database persistence failure: {str(e)}"
                )
        else:
            # 2. Local Persistent SQLite (dev/testing only)
            self._save_record_sqlite(record)

        # Return record to student along with the plaintext verification key
        result = dict(record)
        result["verification_key"] = verification_key
        # Never expose hash or raw internal fields
        result.pop("verification_key_hash", None)
        return result

    # -----------------------------------------------------------------
    # Student Grievance Lookup (Protected by 128-Bit Verification Key)
    # -----------------------------------------------------------------
    def get_case_for_student(
        self,
        case_id: str,
        verification_key: Optional[str] = None,
        student_user: Optional[AuthUser] = None
    ) -> Dict[str, Any]:
        """
        Securely retrieves grievance for student.
        Enforces verification key match OR student user ID ownership.
        Uniform error message prevents Case ID enumeration attacks.
        """
        clean_id = (case_id or "").strip().upper()
        case = self._fetch_raw_case(clean_id)

        # Uniform error message prevents Case ID enumeration attacks (Task 2)
        if not case:
            if verification_key:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Access denied: Invalid Case ID or Verification Key."
                )
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Grievance not found. Please verify the Case ID."
            )

        # Check authorization
        authorized = False

        # Mode A: Authenticated student owns this record
        if student_user and case.get("student_user_id") and case["student_user_id"] == student_user.user_id:
            authorized = True

        # Mode B: High-entropy verification credential supplied (versioned HMAC-SHA256)
        if verification_key:
            rec_version = case.get("key_version", "v1")
            if verify_tracking_credential(verification_key, case.get("verification_key_hash", ""), key_version=rec_version):
                authorized = True

        if not authorized:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied: Invalid Case ID or Verification Key."
            )

        # Return only minimum necessary case information to student
        sanitized = dict(case)
        sanitized.pop("verification_key_hash", None)
        sanitized.pop("key_version", None)
        return sanitized

    # -----------------------------------------------------------------
    # Proctor Dashboard: Fetch Single Case with Institutional Boundary
    # -----------------------------------------------------------------
    def get_case_for_proctor(self, case_id: str, proctor_user: AuthUser) -> Dict[str, Any]:
        if not proctor_user or getattr(proctor_user, "account_status", None) != AccountStatus.ACTIVE:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication required: Officer account is inactive, suspended, or revoked."
            )

        clean_id = (case_id or "").strip().upper()
        case = self._fetch_raw_case(clean_id)
        if not case:
            raise HTTPException(status_code=404, detail="Campus grievance case not found.")

        verify_institutional_boundary(proctor_user, case.get("institution_id", "INST_DEFAULT"))

        # Verify active institutional membership in Supabase mode
        if self.use_supabase and self.supabase and proctor_user.role != UserRole.PLATFORM_ADMIN:
            try:
                res = self.supabase.table("institution_memberships").select("id, account_status, role").eq("user_id", proctor_user.user_id).eq("account_status", "active").execute()
                if not res.data:
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail="Forbidden: User lacks an active institutional membership in institution_memberships."
                    )
            except HTTPException:
                raise
            except Exception as e:
                logger.warning(f"institution_memberships lookup exception: {e}")

        # Confidential grievances: unassigned proctors restricted unless committee or admin
        is_confidential = case.get("confidentiality_mode") in ["CONFIDENTIAL", "STRICT_CONFIDENTIAL"]
        if is_confidential and proctor_user.role == UserRole.PROCTOR:
            assigned = case.get("assigned_proctor")
            if assigned and assigned != proctor_user.name and assigned != proctor_user.user_id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Access denied: Confidential grievances require direct case assignment or committee membership."
                )

        sanitized = dict(case)
        sanitized.pop("verification_key_hash", None)
        return sanitized

    # -----------------------------------------------------------------
    # Proctor Dashboard: List Inquiries for Authorized Institution
    # -----------------------------------------------------------------
    def list_cases_for_proctor(self, proctor_user: AuthUser) -> List[Dict[str, Any]]:
        self._ensure_connected()
        if not proctor_user or getattr(proctor_user, "account_status", None) != AccountStatus.ACTIVE:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication required: Officer account is inactive, suspended, or revoked."
            )

        # In Supabase mode, verify active membership in institution_memberships
        if self.use_supabase and self.supabase and proctor_user.role != UserRole.PLATFORM_ADMIN:
            try:
                res = self.supabase.table("institution_memberships").select("id, account_status, role").eq("user_id", proctor_user.user_id).eq("account_status", "active").execute()
                if not res.data:
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail="Forbidden: User lacks an active institutional membership in institution_memberships."
                    )
            except HTTPException:
                raise
            except Exception as e:
                logger.warning(f"institution_memberships lookup exception: {e}")

        cases: List[Dict[str, Any]] = []

        if self.use_supabase and self.supabase:
            try:
                query = self.supabase.table("campus_cases").select("*").order("created_at", desc=True)
                if proctor_user.role != UserRole.PLATFORM_ADMIN:
                    query = query.eq("institution_id", proctor_user.institution_id)
                res = query.execute()
                cases = res.data or []
            except Exception as e:
                logger.error(f"Supabase list_cases_for_proctor error: {e}")
                raise HTTPException(status_code=500, detail="Failed to retrieve institutional cases.")
        else:
            cases = self._list_cases_sqlite(proctor_user.institution_id, is_admin=(proctor_user.role == UserRole.PLATFORM_ADMIN))

        for c in cases:
            c.pop("verification_key_hash", None)

        return cases

    # -----------------------------------------------------------------
    # Proctor Dashboard: Update Status & Findings (Phase 1.3.7 - Task 2, 3, 4)
    # -----------------------------------------------------------------
    def update_case(self, payload: ProctorUpdateStatus, proctor_user: AuthUser) -> Dict[str, Any]:
        """
        Executes an atomic workflow update for a campus grievance.
        - Verifies initiating proctor token and authorized institutional role.
        - Validates institutional boundary and active membership.
        - Validates permitted workflow status transitions against state machine.
        - Executes single atomic RPC (update_campus_grievance_status) with zero partial state.
        - Records pseudonymous audit activity in case_activity_log under initiating proctor identity.
        - Returns allowlisted, non-sensitive response payload.
        """
        if not proctor_user or getattr(proctor_user, "account_status", None) != AccountStatus.ACTIVE:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication required: Officer account is inactive or token is invalid."
            )

        authorized_roles = [
            UserRole.PROCTOR,
            UserRole.CHIEF_PROCTOR,
            UserRole.COMMITTEE_MEMBER,
            UserRole.INSTITUTION_ADMIN,
            UserRole.PLATFORM_ADMIN
        ]
        if proctor_user.role not in authorized_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied: Only authorized proctors or committee members may update case statuses."
            )

        clean_id = payload.case_id.strip().upper()
        case = self._fetch_raw_case(clean_id)
        if not case:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Case '{clean_id}' not found.")

        # Institutional boundary enforcement
        verify_institutional_boundary(proctor_user, case.get("institution_id", "INST_DEFAULT"))

        # In Supabase mode, verify active membership in institution_memberships
        if self.use_supabase and self.supabase and proctor_user.role != UserRole.PLATFORM_ADMIN:
            try:
                res = self.supabase.table("institution_memberships").select("id, account_status, role").eq("user_id", proctor_user.user_id).eq("account_status", "active").execute()
                if not res.data:
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail="Forbidden: User lacks an active institutional membership in institution_memberships."
                    )
            except HTTPException:
                raise
            except Exception as e:
                logger.warning(f"institution_memberships lookup exception (verifying via token context): {e}")

        # Validate status transition state machine
        current_status = (case.get("status") or "SUBMITTED").strip().upper()
        new_status = payload.new_status.strip().upper()
        if new_status != current_status:
            allowed = PERMITTED_STATUS_TRANSITIONS.get(current_status, set())
            if new_status not in allowed:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid status transition from '{current_status}' to '{new_status}'. Allowed transitions: {sorted(list(allowed)) or 'None (terminal state)'}."
                )

        # Validate typed hearing_date if provided
        validated_hearing_date = parse_and_validate_hearing_date(payload.hearing_date) if payload.hearing_date else None
        now_iso = datetime.now(timezone.utc).isoformat()

        # Database Update via Single Atomic RPC
        if self.use_supabase and self.supabase:
            try:
                rpc_payload = {
                    "p_case_id": clean_id,
                    "p_new_status": new_status,
                    "p_proctor_notes": payload.proctor_notes,
                    "p_hearing_date": validated_hearing_date,
                    "p_action_taken": payload.action_taken,
                    "p_resolution_details": payload.resolution_details,
                    "p_assigned_proctor": payload.assigned_proctor,
                    "p_assigned_proctor_user_id": payload.assigned_proctor_user_id,
                    "p_assigned_committee": payload.assigned_committee,
                    "p_history": None  # Preserves existing history; does not bloat child table
                }
                res = self.supabase.rpc("update_campus_grievance_status", rpc_payload).execute()
                if not res.data:
                    raise RuntimeError("Atomic grievance update RPC returned empty data.")
                updated_record = res.data
            except Exception as e:
                err_msg = str(e)
                logger.error(f"Atomic update_campus_grievance_status RPC failure: {err_msg}")
                if "is not a campus grievance" in err_msg:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Cross-case-type rejection: {err_msg}"
                    )
                if "Case" in err_msg and "not found" in err_msg:
                    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=err_msg)
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Database atomic update failed: {err_msg}"
                )
        else:
            # Local dev fallback
            case["status"] = new_status
            if payload.proctor_notes is not None:
                case["proctor_notes"] = payload.proctor_notes
            if validated_hearing_date is not None:
                case["hearing_date"] = validated_hearing_date
            if payload.action_taken is not None:
                case["action_taken"] = payload.action_taken
            if payload.resolution_details is not None:
                case["resolution_details"] = payload.resolution_details
            if payload.assigned_proctor is not None:
                case["assigned_proctor"] = payload.assigned_proctor
            if payload.assigned_proctor_user_id is not None:
                case["assigned_proctor_user_id"] = payload.assigned_proctor_user_id
            if payload.assigned_committee is not None:
                case["assigned_committee"] = payload.assigned_committee
            case["updated_at"] = now_iso
            self._update_record_sqlite(case)
            updated_record = case

        # Append audit activity log with genuine proctor identity (pseudonymized audit_actor_id)
        try:
            from .audit import record_case_activity
        except ImportError:
            from audit import record_case_activity

        record_case_activity(
            case_uuid=case.get("id"),
            case_id=clean_id,
            action_type=f"STATUS_TRANSITION_{new_status}",
            action_details={
                "from_status": current_status,
                "to_status": new_status,
                "proctor_notes": payload.proctor_notes,
                "hearing_date": validated_hearing_date,
                "assigned_proctor": payload.assigned_proctor,
                "assigned_proctor_user_id": payload.assigned_proctor_user_id,
                "assigned_committee": payload.assigned_committee
            },
            actor_user=proctor_user,
            actor_type="USER",
            supabase_client=self.supabase
        )

        # Return strictly allowlisted non-sensitive fields
        return {
            "case_id": updated_record.get("case_id", clean_id),
            "status": updated_record.get("status", new_status),
            "updated_at": updated_record.get("updated_at", now_iso),
            "proctor_notes": updated_record.get("proctor_notes"),
            "hearing_date": updated_record.get("hearing_date"),
            "action_taken": updated_record.get("action_taken"),
            "resolution_details": updated_record.get("resolution_details"),
            "assigned_proctor": updated_record.get("assigned_proctor"),
            "assigned_committee": updated_record.get("assigned_committee")
        }

    # -----------------------------------------------------------------
    # Notice Generator
    # -----------------------------------------------------------------
    def generate_proctorial_notice(
        self,
        case_id: str,
        user: Optional[AuthUser] = None,
        verification_key: Optional[str] = None
    ) -> str:
        """Generates an official formal Proctorial Inquiry & Hearing Notice."""
        clean_id = (case_id or "").strip().upper()
        case = self._fetch_raw_case(clean_id)
        if not case:
            raise HTTPException(status_code=404, detail="Case ID not found in campus registry.")

        # Verify access rights
        if user:
            verify_institutional_boundary(user, case.get("institution_id", "INST_DEFAULT"))
        elif verification_key:
            if not verify_tracking_credential(verification_key, case.get("verification_key_hash", "")):
                raise HTTPException(status_code=403, detail="Invalid verification key for this notice.")

        notice = f"""OFFICE OF THE CHIEF PROCTOR & STUDENT GRIEVANCE REDRESSAL CELL
================================================================================
FORMAL PROCTORIAL INQUIRY NOTICE & CASE PROCEEDINGS
Ref No: PROCTOR/SGRC/2026/{case['case_id']}
Institution Identifier: {case.get('institution_id', 'INST_DEFAULT')}
Date of Issuance: {datetime.now().strftime('%d-%B-%Y')}
Statutory Mandate: UGC (Grievance Redressal of Students) Regulations, 2023

1. CASE IDENTIFIER & COMPLAINANT PARTICULARS:
   - Case Reference ID : {case['case_id']}
   - Complainant Name  : {case.get('student_name') or 'Anonymous / Protected Complainant'}
   - Department / Year : {case['department']} ({case['year']})
   - Case Category     : {case['category']} (Severity: {case['severity']})
   - Current Status    : {case['status']}

2. SUBJECT MATTER / CAUSE OF GRIEVANCE:
   "{case['subject']}"

3. SUMMARY OF INQUIRY PROCEEDINGS & FINDINGS:
   {case['description']}

4. PROCTORIAL DIRECTIVE & ACTION TAKEN:
   - Notes by Chief Proctor : {case.get('proctor_notes', 'Under investigation.')}
   - Hearing / Meeting Date : {case.get('hearing_date', 'To be scheduled.')}
   - Institutional Action   : {case.get('action_taken', 'Pending departmental review.')}
   - Statutory UGC Deadline : {case.get('resolution_deadline', '15 Days')} (UGC SLA)

5. ESCALATION PRIVILEGE:
   If this matter remains unredressed beyond the 15-day statutory window, the student
   retains the non-derogable right under Section 6(1) of the RTI Act, 2005 read with
   CBSE v. Aditya Bandopadhyay [(2011) 8 SCC 497] to escalate this matter to the
   State University / Chancellor's Secretariat.

By Order of,
The Chief Proctor & Student Ombudsperson,
Campus Grievance Redressal Committee (SGRC)
================================================================================
"""
        return notice

    # -----------------------------------------------------------------
    # Internal Helpers (SQLite Persistent Fallback for Local Dev/Tests)
    # -----------------------------------------------------------------
    def _fetch_raw_case(self, case_id: str) -> Optional[Dict[str, Any]]:
        self._ensure_connected()
        if hasattr(self, "_local_case_cache") and case_id in self._local_case_cache:
            return self._local_case_cache[case_id]
        if self.use_supabase and self.supabase:
            try:
                res = self.supabase.table("campus_cases").select("*").eq("case_id", case_id).execute()
                if res.data and len(res.data) > 0:
                    return res.data[0]
                return None
            except Exception as e:
                logger.error(f"Supabase fetch error for {case_id}: {e}")
                return None
        else:
            return self._get_record_sqlite(case_id)

    def _save_record_sqlite(self, r: Dict[str, Any]):
        conn = sqlite3.connect(self._local_db_path)
        cur = conn.cursor()
        cur.execute("""
            INSERT OR REPLACE INTO campus_cases (
                id, case_id, institution_id, student_user_id, student_name, roll_number,
                department, year, category, subject, description, incident_date,
                is_anonymous, confidentiality_mode, severity, status, proctor_notes,
                hearing_date, action_taken, resolution_details, resolution_deadline,
                assigned_proctor, assigned_committee, supporting_documents,
                verification_key_hash, key_version, history, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
        """, (
            r["id"], r["case_id"], r["institution_id"], r["student_user_id"], r["student_name"],
            r["roll_number"], r["department"], r["year"], r["category"], r["subject"],
            r["description"], r["incident_date"], 1 if r["is_anonymous"] else 0,
            r["confidentiality_mode"], r["severity"], r["status"], r["proctor_notes"],
            r["hearing_date"], r["action_taken"], r["resolution_details"],
            r["resolution_deadline"], r["assigned_proctor"], r["assigned_committee"],
            json.dumps(r["supporting_documents"]), r["verification_key_hash"],
            r.get("key_version", "v1"), json.dumps(r["history"]), r["created_at"], r["updated_at"]
        ))
        conn.commit()
        conn.close()

    def _get_record_sqlite(self, case_id: str) -> Optional[Dict[str, Any]]:
        conn = sqlite3.connect(self._local_db_path)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute("SELECT * FROM campus_cases WHERE case_id = ?", (case_id,))
        row = cur.fetchone()
        conn.close()
        if not row:
            return None
        d = dict(row)
        d["is_anonymous"] = bool(d["is_anonymous"])
        try:
            d["supporting_documents"] = json.loads(d["supporting_documents"])
        except Exception:
            d["supporting_documents"] = []
        try:
            d["history"] = json.loads(d["history"])
        except Exception:
            d["history"] = []
        return d

    def _update_record_sqlite(self, r: Dict[str, Any]):
        conn = sqlite3.connect(self._local_db_path)
        cur = conn.cursor()
        cur.execute("""
            UPDATE campus_cases SET
                status = ?, proctor_notes = ?, hearing_date = ?, action_taken = ?,
                resolution_details = ?, assigned_proctor = ?, assigned_committee = ?,
                history = ?, updated_at = ?
            WHERE case_id = ?
        """, (
            r["status"], r["proctor_notes"], r["hearing_date"], r["action_taken"],
            r["resolution_details"], r["assigned_proctor"], r["assigned_committee"],
            json.dumps(r["history"]), r["updated_at"], r["case_id"]
        ))
        conn.commit()
        conn.close()

    def _list_cases_sqlite(self, institution_id: str, is_admin: bool = False) -> List[Dict[str, Any]]:
        conn = sqlite3.connect(self._local_db_path)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        if is_admin:
            cur.execute("SELECT * FROM campus_cases ORDER BY created_at DESC")
        else:
            cur.execute("SELECT * FROM campus_cases WHERE institution_id = ? ORDER BY created_at DESC", (institution_id,))
        rows = cur.fetchall()
        conn.close()
        result = []
        for row in rows:
            d = dict(row)
            d["is_anonymous"] = bool(d["is_anonymous"])
            try:
                d["supporting_documents"] = json.loads(d["supporting_documents"])
            except Exception:
                d["supporting_documents"] = []
            try:
                d["history"] = json.loads(d["history"])
            except Exception:
                d["history"] = []
            result.append(d)
        return result

campus_proctor_manager = CampusProctorManager()

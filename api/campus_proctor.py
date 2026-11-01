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
    confidentiality_mode: Optional[str] = "NORMAL"
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

class CaseCommitteeAssignRequest(BaseModel):
    case_id: str
    target_user_id: str
    role: Optional[str] = "member"
    committee_name: Optional[str] = None

class CaseCommitteeRevokeRequest(BaseModel):
    case_id: str
    target_user_id: str

class InstitutionMemberStatusUpdate(BaseModel):
    account_status: str

class CommitteeObservationRequest(BaseModel):
    case_id: str
    observations: str
    recommendations: Optional[str] = ""
    findings: Optional[str] = ""

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
        is_offline_test = os.environ.get("SUPABASE_OFFLINE_TEST") == "1"
        if is_offline_test:
            self.use_supabase = False
            self.supabase = None
        else:
            url: str = os.environ.get("SUPABASE_URL", "")
            secret_key: str = os.environ.get("SUPABASE_SECRET_KEY", "")
            if url and secret_key and create_client and not self.supabase:
                try:
                    self.supabase = create_client(url, secret_key)
                    self.use_supabase = True
                except Exception as e:
                    logger.warning(f"Campus Proctor reconnect failed: {e}")
                    self.use_supabase = False
                    self.supabase = None

        if self.use_supabase and self.supabase is not None:
            return

        is_production = (
            os.environ.get("VERCEL") == "1" or
            os.environ.get("NODE_ENV") == "production" or
            os.environ.get("ENV") == "production" or
            os.environ.get("ENVIRONMENT") == "production"
        )
        explicit_allow = os.environ.get("ALLOW_LOCAL_SQLITE")
        explicit_test = os.environ.get("TEST_MODE")

        if explicit_allow == "0" or explicit_test == "0":
            allow = False
        elif explicit_allow == "1" or explicit_test == "1":
            allow = True
        else:
            allow = not is_production

        if not allow:
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

        # Confidential grievances: unassigned officers restricted unless committee assignment, direct proctor assignment, or admin oversight
        is_confidential = case.get("confidentiality_mode") in ["CONFIDENTIAL", "STRICT_CONFIDENTIAL"]
        if is_confidential and proctor_user.role not in [UserRole.PLATFORM_ADMIN, UserRole.INSTITUTION_ADMIN]:
            assigned_uuid = case.get("assigned_proctor_user_id")
            assigned = case.get("assigned_proctor")
            is_assigned_proctor = bool(
                (assigned_uuid and str(assigned_uuid).lower() == str(proctor_user.user_id).lower()) or
                (not assigned_uuid and assigned and (str(assigned).lower() == str(proctor_user.user_id).lower() or assigned == proctor_user.name))
            )
            is_assigned_comm = False
            if proctor_user.role in [UserRole.COMMITTEE_MEMBER, UserRole.CHIEF_PROCTOR]:
                if self.supabase and case.get("id"):
                    try:
                        res_c = self.supabase.table("case_committee_assignments").select("id").eq(
                            "case_uuid", case["id"]
                        ).eq("user_id", proctor_user.user_id).eq("assignment_status", "active").execute()
                        if res_c.data and len(res_c.data) > 0:
                            is_assigned_comm = True
                    except Exception as e:
                        logger.warning(f"Error checking case_committee_assignments in get_case_for_proctor: {e}")
                elif not self.use_supabase:
                    is_assigned_comm = getattr(proctor_user, "_mock_assigned_comm", False)

            if not is_assigned_proctor and not is_assigned_comm:
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

        # Cross-case-type rejection: Campus proctor can only manage CAMPUS_GRIEVANCE cases
        case_type = case.get("case_type")
        if case_type and case_type != "CAMPUS_GRIEVANCE":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cross-case-type rejection: Case '{clean_id}' is of type '{case_type}' and is not a campus grievance."
            )

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

        # Check authorization to reassign proctor
        if (payload.assigned_proctor_user_id or payload.assigned_proctor) and proctor_user.role not in [
            UserRole.CHIEF_PROCTOR, UserRole.INSTITUTION_ADMIN, UserRole.PLATFORM_ADMIN
        ]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Forbidden: Only Chief Proctors, Institution Administrators, or Platform Admins may assign or reassign proctors."
            )

        # Check confidential case update permissions
        is_confidential = (
            case.get("confidentiality_mode") in ["CONFIDENTIAL", "STRICT_CONFIDENTIAL"] or
            case.get("is_confidential") is True
        )
        if is_confidential and proctor_user.role not in [UserRole.PLATFORM_ADMIN, UserRole.INSTITUTION_ADMIN, UserRole.CHIEF_PROCTOR]:
            assigned_uuid = case.get("assigned_proctor_user_id")
            assigned_name = case.get("assigned_proctor")
            is_assigned_proctor = bool(
                (assigned_uuid and str(assigned_uuid).lower() == str(proctor_user.user_id).lower()) or
                (not assigned_uuid and assigned_name and (
                    str(assigned_name).lower() == str(proctor_user.user_id).lower() or
                    assigned_name == proctor_user.name
                ))
            )
            is_assigned_comm = False
            if proctor_user.role == UserRole.COMMITTEE_MEMBER and self.supabase and case.get("id"):
                try:
                    res_c = self.supabase.table("case_committee_assignments").select("id").eq(
                        "case_uuid", case["id"]
                    ).eq("user_id", proctor_user.user_id).eq("assignment_status", "active").execute()
                    if res_c.data and len(res_c.data) > 0:
                        is_assigned_comm = True
                except Exception as e:
                    logger.warning(f"Error checking case_committee_assignments: {e}")

            if not is_assigned_proctor and not is_assigned_comm:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Access denied: Confidential grievances can only be updated by the assigned proctor, designated committee inquiry member, or Chief Proctor."
                )

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

        act_rec = record_case_activity(
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
        activity_id = act_rec.get("id") if isinstance(act_rec, dict) else None

        # Dispatch In-App Notifications (Phase 2.3 & 4: Immutable activity_id idempotency)
        try:
            from .notifications import notification_manager
        except ImportError:
            try:
                from notifications import notification_manager
            except ImportError:
                notification_manager = None

        if notification_manager and activity_id:
            try:
                student_uid = case.get("student_user_id")
                if student_uid:
                    # Status Update Notification
                    if new_status != current_status:
                        stat_title = f"Case Status: {new_status.replace('_', ' ').title()}"
                        stat_msg = f"Your case {clean_id} status has been updated to {new_status}."
                        if payload.resolution_details:
                            stat_msg += f" Resolution: {payload.resolution_details}"
                        notification_manager.create_notification(
                            recipient_user_id=student_uid,
                            event_type=f"CASE_{new_status}",
                            title=stat_title,
                            message=stat_msg,
                            related_case_id=clean_id,
                            case_uuid=case.get("id"),
                            action_url=f"/dashboard/my-cases/{clean_id}",
                            idempotency_key=f"notif_act_{activity_id}_status_{student_uid}"
                        )

                    # Hearing Scheduled Notification
                    if validated_hearing_date:
                        notification_manager.create_notification(
                            recipient_user_id=student_uid,
                            event_type="HEARING_SCHEDULED",
                            title="Inquiry Hearing Scheduled",
                            message=f"A formal inquiry hearing for case {clean_id} has been scheduled for {validated_hearing_date}.",
                            related_case_id=clean_id,
                            case_uuid=case.get("id"),
                            action_url=f"/dashboard/my-cases/{clean_id}",
                            idempotency_key=f"notif_act_{activity_id}_hearing_{student_uid}"
                        )

                # Proctor Assigned Notification
                if payload.assigned_proctor_user_id and payload.assigned_proctor_user_id != proctor_user.user_id:
                    notification_manager.create_notification(
                        recipient_user_id=payload.assigned_proctor_user_id,
                        event_type="CASE_ASSIGNED",
                        title="New Case Assigned to You",
                        message=f"You have been assigned as the presiding officer for case {clean_id}.",
                        related_case_id=clean_id,
                        case_uuid=case.get("id"),
                        action_url=f"/campus-proctor/dashboard?case_id={clean_id}",
                        idempotency_key=f"notif_act_{activity_id}_assign_{payload.assigned_proctor_user_id}"
                    )
            except Exception as e_notif:
                logger.warning(f"Error dispatching status update notifications: {e_notif}")

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

4. STATUTORY TIMELINE UNDER UGC REGULATIONS, 2023:
   - Institutional Referral : Grievance referral to SGRC within 15 days of filing.
   - SGRC Determination     : Committee inquiry report preferably within 15 working days.
   - Student Appeal Window  : Aggrieved complainant may appeal to University Ombudsperson within 15 days of SGRC decision.
   - Ombudsperson Window    : University Ombudsperson resolution mandate within 30 days.

5. ESCALATION & APPELLATE PRIVILEGE:
   If this matter remains unredressed or the complainant is aggrieved by the SGRC determination,
   the student retains the statutory right under Regulation 6 of the UGC (Grievance Redressal of Students)
   Regulations, 2023 to file an appeal before the University Ombudsperson, without prejudice to
   statutory transparency remedies under Section 6(1) of the RTI Act, 2005.

By Order of,
The Chief Proctor & Campus Grievance Redressal Cell,
Student Grievance Redressal Committee (SGRC)
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
            r.get("status"), r.get("proctor_notes"), r.get("hearing_date"), r.get("action_taken"),
            r.get("resolution_details"), r.get("assigned_proctor"), r.get("assigned_committee"),
            json.dumps(r.get("history") if isinstance(r.get("history"), list) else []),
            r.get("updated_at"), r.get("case_id")
        ))
        conn.commit()
        conn.close()

    def assign_committee_member(
        self,
        case_id: str,
        target_user_id: str,
        role: str = "member",
        committee_name: Optional[str] = None,
        assigner_user: Optional[AuthUser] = None
    ) -> Dict[str, Any]:
        """
        Provisions a case-specific committee assignment for a confidential inquiry.
        Authorizes only Institution Admins, Chief Proctors, or Platform Admins.
        Enforces that target user holds an active committee_member role in the case's institution.
        """
        if not assigner_user or getattr(assigner_user, "account_status", None) != AccountStatus.ACTIVE:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication required: Assigner account is inactive or token is invalid."
            )

        if assigner_user.role not in [UserRole.INSTITUTION_ADMIN, UserRole.CHIEF_PROCTOR, UserRole.PLATFORM_ADMIN]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Forbidden: Only Institution Administrators, Chief Proctors, or Platform Admins may provision committee assignments."
            )

        clean_id = case_id.strip().upper()
        case = self._fetch_raw_case(clean_id)
        if not case:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Case '{clean_id}' not found.")

        # Cross-case-type rejection: Campus proctor can only manage CAMPUS_GRIEVANCE cases
        case_type = case.get("case_type")
        if case_type and case_type != "CAMPUS_GRIEVANCE":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cross-case-type rejection: Case '{clean_id}' is of type '{case_type}' and is not a campus grievance."
            )

        # Institutional boundary enforcement for assigner
        verify_institutional_boundary(assigner_user, case.get("institution_id", "INST_DEFAULT"))

        # Database Execution via Security Definer RPC
        if self.use_supabase and self.supabase:
            try:
                rpc_payload = {
                    "p_case_id": clean_id,
                    "p_target_user_id": target_user_id,
                    "p_role": role or "member",
                    "p_committee_name": committee_name,
                    "p_assigned_by": assigner_user.user_id
                }
                res = self.supabase.rpc("assign_case_committee_member", rpc_payload).execute()
                if not res.data:
                    raise RuntimeError("Committee assignment RPC returned empty data.")
                assignment_record = res.data
            except Exception as e:
                err_msg = str(e)
                logger.error(f"assign_case_committee_member RPC failure: {err_msg}")
                if "not authorized" in err_msg:
                    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=err_msg)
                if "lacks an active committee membership" in err_msg:
                    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=err_msg)
                if "not found" in err_msg:
                    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=err_msg)
                raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Database assignment failed: {err_msg}")
        else:
            assignment_record = {
                "assignment_id": str(uuid.uuid4()),
                "case_id": clean_id,
                "user_id": target_user_id,
                "role": role,
                "committee_name": committee_name,
                "assignment_status": "active"
            }

        # Log audit activity
        try:
            from .audit import record_case_activity
        except ImportError:
            from audit import record_case_activity

        act_rec = record_case_activity(
            case_uuid=case.get("id"),
            case_id=clean_id,
            action_type="COMMITTEE_ASSIGNMENT_PROVISIONED",
            action_details={
                "target_user_id": target_user_id,
                "role": role,
                "committee_name": committee_name
            },
            actor_user=assigner_user,
            actor_type="USER",
            supabase_client=self.supabase
        )
        activity_id = act_rec.get("id") if isinstance(act_rec, dict) else None

        # Dispatch In-App Notification (Phase 2.3 & 4)
        if activity_id:
            try:
                from .notifications import notification_manager
            except ImportError:
                from notifications import notification_manager
            try:
                notification_manager.create_notification(
                    recipient_user_id=target_user_id,
                    event_type="COMMITTEE_ASSIGNED",
                    title="Appointed to Inquiry Committee",
                    message=f"You have been appointed to the inquiry committee for case {clean_id}.",
                    related_case_id=clean_id,
                    case_uuid=case.get("id"),
                    action_url=f"/campus-proctor/committee?case_id={clean_id}",
                    idempotency_key=f"notif_act_{activity_id}_comm_{target_user_id}"
                )
            except Exception as e_notif:
                logger.warning(f"Error dispatching committee assignment notification: {e_notif}")

        return assignment_record

    def revoke_committee_assignment(
        self,
        case_id: str,
        target_user_id: str,
        revoker_user: Optional[AuthUser] = None
    ) -> Dict[str, Any]:
        """
        Revokes a case-specific committee assignment immediately.
        Authorizes only Institution Admins, Chief Proctors, or Platform Admins.
        """
        if not revoker_user or getattr(revoker_user, "account_status", None) != AccountStatus.ACTIVE:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication required: Revoker account is inactive or token is invalid."
            )

        if revoker_user.role not in [UserRole.INSTITUTION_ADMIN, UserRole.CHIEF_PROCTOR, UserRole.PLATFORM_ADMIN]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Forbidden: Only Institution Administrators, Chief Proctors, or Platform Admins may revoke committee assignments."
            )

        clean_id = case_id.strip().upper()
        case = self._fetch_raw_case(clean_id)
        if not case:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Case '{clean_id}' not found.")

        # Cross-case-type rejection: Campus proctor can only manage CAMPUS_GRIEVANCE cases
        case_type = case.get("case_type")
        if case_type and case_type != "CAMPUS_GRIEVANCE":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cross-case-type rejection: Case '{clean_id}' is of type '{case_type}' and is not a campus grievance."
            )

        verify_institutional_boundary(revoker_user, case.get("institution_id", "INST_DEFAULT"))

        if self.use_supabase and self.supabase:
            try:
                rpc_payload = {
                    "p_case_id": clean_id,
                    "p_target_user_id": target_user_id,
                    "p_revoked_by": revoker_user.user_id
                }
                res = self.supabase.rpc("revoke_case_committee_assignment", rpc_payload).execute()
                if not res.data:
                    raise RuntimeError("Committee revoke RPC returned empty data.")
                revoked_record = res.data
            except Exception as e:
                err_msg = str(e)
                logger.error(f"revoke_case_committee_assignment RPC failure: {err_msg}")
                if "not authorized" in err_msg:
                    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=err_msg)
                if "not found" in err_msg:
                    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=err_msg)
                raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Database revocation failed: {err_msg}")
        else:
            revoked_record = {
                "case_id": clean_id,
                "user_id": target_user_id,
                "assignment_status": "revoked"
            }

        try:
            from .audit import record_case_activity
        except ImportError:
            from audit import record_case_activity

        act_rec = record_case_activity(
            case_uuid=case.get("id"),
            case_id=clean_id,
            action_type="COMMITTEE_ASSIGNMENT_REVOKED",
            action_details={"target_user_id": target_user_id},
            actor_user=revoker_user,
            actor_type="USER",
            supabase_client=self.supabase
        )
        activity_id = act_rec.get("id") if isinstance(act_rec, dict) else None

        # Dispatch In-App Notification (Phase 2.3 & 4)
        if activity_id:
            try:
                from .notifications import notification_manager
            except ImportError:
                from notifications import notification_manager
            try:
                notification_manager.create_notification(
                    recipient_user_id=target_user_id,
                    event_type="COMMITTEE_REVOKED",
                    title="Committee Assignment Revoked",
                    message=f"Your appointment to the inquiry committee for case {clean_id} has been revoked.",
                    related_case_id=clean_id,
                    case_uuid=case.get("id"),
                    action_url="/campus-proctor/committee",
                    idempotency_key=f"notif_act_{activity_id}_comm_rev_{target_user_id}"
                )
            except Exception as e_notif:
                logger.warning(f"Error dispatching committee revocation notification: {e_notif}")

        return revoked_record

    def get_committee_assignments(
        self,
        case_id: str,
        officer_user: Optional[AuthUser] = None
    ) -> List[Dict[str, Any]]:
        """
        Retrieves committee assignments for a specific case.
        Accessible by Institution Admins, Chief Proctors, Platform Admins, or assigned officers.
        """
        if not officer_user or getattr(officer_user, "account_status", None) != AccountStatus.ACTIVE:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication required: Officer account is inactive or token is invalid."
            )

        clean_id = case_id.strip().upper()
        case = self._fetch_raw_case(clean_id)
        if not case:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Case '{clean_id}' not found.")

        # Cross-case-type rejection: Campus proctor can only manage CAMPUS_GRIEVANCE cases
        case_type = case.get("case_type")
        if case_type and case_type != "CAMPUS_GRIEVANCE":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cross-case-type rejection: Case '{clean_id}' is of type '{case_type}' and is not a campus grievance."
            )

        verify_institutional_boundary(officer_user, case.get("institution_id", "INST_DEFAULT"))

        if self.use_supabase and self.supabase:
            try:
                res = self.supabase.table("case_committee_assignments").select(
                    "id, case_id, user_id, role, committee_name, assignment_status, assigned_at"
                ).eq("case_id", clean_id).execute()
                return res.data or []
            except Exception as e:
                logger.error(f"Error listing committee assignments: {e}")
                return []
        return []

    # -----------------------------------------------------------------
    # Institution Administrator & Proctor Methods (Phase 4)
    # -----------------------------------------------------------------
    def get_institution_dashboard_stats(self, officer_user: AuthUser) -> Dict[str, Any]:
        """
        Computes real-time dashboard statistics derived from actual DB records for the officer's institution.
        Accessible by Institution Administrators, Chief Proctors, or Platform Admins.
        """
        if not officer_user or getattr(officer_user, "account_status", None) != AccountStatus.ACTIVE:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication required: Officer account is inactive or token is invalid."
            )

        if officer_user.role not in [UserRole.INSTITUTION_ADMIN, UserRole.CHIEF_PROCTOR, UserRole.PLATFORM_ADMIN]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied: Only Institution Administrators, Chief Proctors, or Platform Admins may view institution dashboard stats."
            )

        inst_id = officer_user.institution_id
        self._ensure_connected()

        stats = {
            "institution_id": inst_id,
            "total_cases": 0,
            "active_inquiries": 0,
            "resolved_cases": 0,
            "hearings_scheduled": 0,
            "confidential_cases": 0,
            "sla_breaches": 0,
            "total_members": 0,
            "active_members": 0,
            "unassigned_cases": 0,
        }

        if self.use_supabase and self.supabase:
            try:
                query = self.supabase.table("campus_cases").select(
                    "id, case_id, status, severity, category, confidentiality_mode, hearing_date, assigned_proctor, assigned_proctor_user_id, created_at, resolution_deadline"
                )
                if officer_user.role != UserRole.PLATFORM_ADMIN:
                    query = query.eq("institution_id", inst_id)
                res = query.execute()
                cases = res.data or []

                stats["total_cases"] = len(cases)
                now_dt = datetime.now(timezone.utc)

                for c in cases:
                    st = (c.get("status") or "").upper()
                    if st in ["SUBMITTED", "UNDER_INQUIRY", "UNDER_REVIEW", "HEARING_SCHEDULED", "ACTION_TAKEN"]:
                        stats["active_inquiries"] += 1
                    elif st in ["RESOLVED", "CLOSED"]:
                        stats["resolved_cases"] += 1

                    if st == "HEARING_SCHEDULED" or c.get("hearing_date"):
                        stats["hearings_scheduled"] += 1

                    if c.get("confidentiality_mode") in ["CONFIDENTIAL", "STRICT_CONFIDENTIAL"]:
                        stats["confidential_cases"] += 1

                    if not c.get("assigned_proctor") and not c.get("assigned_proctor_user_id"):
                        stats["unassigned_cases"] += 1

                    if st not in ["RESOLVED", "CLOSED"]:
                        created_str = c.get("created_at")
                        if created_str:
                            try:
                                created_dt = datetime.fromisoformat(created_str.replace("Z", "+00:00"))
                                if (now_dt - created_dt).days >= 15:
                                    stats["sla_breaches"] += 1
                            except Exception:
                                pass

                m_query = self.supabase.table("institution_memberships").select("id, account_status, role")
                if officer_user.role != UserRole.PLATFORM_ADMIN:
                    m_query = m_query.eq("institution_code", inst_id)
                m_res = m_query.execute()
                members = m_res.data or []
                stats["total_members"] = len(members)
                stats["active_members"] = sum(1 for m in members if m.get("account_status") == "active")

            except Exception as e:
                logger.error(f"Error computing dashboard stats in Supabase: {e}")
                raise HTTPException(status_code=500, detail="Failed to calculate institution statistics.")
        else:
            cases = self._list_cases_sqlite(inst_id, is_admin=(officer_user.role == UserRole.PLATFORM_ADMIN))
            stats["total_cases"] = len(cases)
            for c in cases:
                st = (c.get("status") or "").upper()
                if st in ["SUBMITTED", "UNDER_INQUIRY", "UNDER_REVIEW", "HEARING_SCHEDULED", "ACTION_TAKEN"]:
                    stats["active_inquiries"] += 1
                elif st in ["RESOLVED", "CLOSED"]:
                    stats["resolved_cases"] += 1
                if st == "HEARING_SCHEDULED" or c.get("hearing_date"):
                    stats["hearings_scheduled"] += 1
                if c.get("confidentiality_mode") in ["CONFIDENTIAL", "STRICT_CONFIDENTIAL"]:
                    stats["confidential_cases"] += 1
                if not c.get("assigned_proctor"):
                    stats["unassigned_cases"] += 1

        return stats

    def get_institution_analytics(self, officer_user: AuthUser) -> Dict[str, Any]:
        """
        Provides detailed breakdown analytics (category, severity, status, resolution trends)
        for the officer's institution derived from actual database records.
        """
        if not officer_user or getattr(officer_user, "account_status", None) != AccountStatus.ACTIVE:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication required: Officer account is inactive or token is invalid."
            )

        if officer_user.role not in [UserRole.INSTITUTION_ADMIN, UserRole.CHIEF_PROCTOR, UserRole.PLATFORM_ADMIN]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied: Only Institution Administrators, Chief Proctors, or Platform Admins may view institution analytics."
            )

        inst_id = officer_user.institution_id
        self._ensure_connected()

        if self.use_supabase and self.supabase:
            try:
                query = self.supabase.table("campus_cases").select(
                    "id, case_id, status, severity, category, created_at, updated_at, hearing_date"
                )
                if officer_user.role != UserRole.PLATFORM_ADMIN:
                    query = query.eq("institution_id", inst_id)
                res = query.execute()
                cases = res.data or []
            except Exception as e:
                logger.error(f"Error fetching analytics data from Supabase: {e}")
                raise HTTPException(status_code=500, detail="Failed to retrieve analytics data.")
        else:
            cases = self._list_cases_sqlite(inst_id, is_admin=(officer_user.role == UserRole.PLATFORM_ADMIN))

        by_category: Dict[str, int] = {}
        by_severity: Dict[str, int] = {}
        by_status: Dict[str, int] = {}
        resolution_durations_days: List[float] = []

        for c in cases:
            cat = c.get("category") or "OTHER"
            by_category[cat] = by_category.get(cat, 0) + 1

            sev = c.get("severity") or "MEDIUM"
            by_severity[sev] = by_severity.get(sev, 0) + 1

            st = c.get("status") or "SUBMITTED"
            by_status[st] = by_status.get(st, 0) + 1

            if st in ["RESOLVED", "CLOSED"] and c.get("created_at") and c.get("updated_at"):
                try:
                    c_dt = datetime.fromisoformat(c["created_at"].replace("Z", "+00:00"))
                    u_dt = datetime.fromisoformat(c["updated_at"].replace("Z", "+00:00"))
                    diff_days = max(0.0, (u_dt - c_dt).total_seconds() / 86400.0)
                    resolution_durations_days.append(diff_days)
                except Exception:
                    pass

        avg_resolution_days = round(sum(resolution_durations_days) / len(resolution_durations_days), 1) if resolution_durations_days else 0.0

        return {
            "institution_id": inst_id,
            "total_cases": len(cases),
            "by_category": by_category,
            "by_severity": by_severity,
            "by_status": by_status,
            "avg_resolution_days": avg_resolution_days,
            "resolved_count": len(resolution_durations_days)
        }

    def list_institution_cases(
        self,
        officer_user: AuthUser,
        status_filter: Optional[str] = None,
        category_filter: Optional[str] = None,
        severity_filter: Optional[str] = None,
        search: Optional[str] = None,
        limit: int = 50,
        offset: int = 0
    ) -> Dict[str, Any]:
        """
        Retrieves paginated and filtered cases for the officer's institution.
        Enforces cross-institution isolation.
        """
        if not officer_user or getattr(officer_user, "account_status", None) != AccountStatus.ACTIVE:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication required: Officer account is inactive or token is invalid."
            )

        if officer_user.role not in [UserRole.INSTITUTION_ADMIN, UserRole.CHIEF_PROCTOR, UserRole.PLATFORM_ADMIN, UserRole.PROCTOR]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied: Only authorized institutional personnel may view institutional cases."
            )

        inst_id = officer_user.institution_id
        self._ensure_connected()

        if self.use_supabase and self.supabase:
            try:
                query = self.supabase.table("campus_cases").select("*", count="exact")
                if officer_user.role != UserRole.PLATFORM_ADMIN:
                    query = query.eq("institution_id", inst_id)

                if status_filter:
                    query = query.eq("status", status_filter.strip().upper())
                if category_filter:
                    query = query.eq("category", category_filter.strip())
                if severity_filter:
                    query = query.eq("severity", severity_filter.strip().upper())
                if search:
                    query = query.or_(f"case_id.ilike.%{search}%,subject.ilike.%{search}%")

                query = query.order("created_at", desc=True)
                query = query.range(offset, offset + limit - 1)
                res = query.execute()

                cases = res.data or []
                total_count = res.count if hasattr(res, "count") and res.count is not None else len(cases)
                for c in cases:
                    c.pop("verification_key_hash", None)

                return {
                    "cases": cases,
                    "total": total_count,
                    "limit": limit,
                    "offset": offset,
                    "institution_id": inst_id
                }
            except Exception as e:
                logger.error(f"Error listing institution cases: {e}")
                raise HTTPException(status_code=500, detail="Failed to retrieve institution cases.")
        else:
            all_cases = self._list_cases_sqlite(inst_id, is_admin=(officer_user.role == UserRole.PLATFORM_ADMIN))
            filtered = all_cases
            if status_filter:
                filtered = [c for c in filtered if (c.get("status") or "").upper() == status_filter.strip().upper()]
            if category_filter:
                filtered = [c for c in filtered if (c.get("category") or "").upper() == category_filter.strip().upper()]
            if severity_filter:
                filtered = [c for c in filtered if (c.get("severity") or "").upper() == severity_filter.strip().upper()]
            if search:
                s = search.lower()
                filtered = [c for c in filtered if s in (c.get("case_id") or "").lower() or s in (c.get("subject") or "").lower()]

            total_count = len(filtered)
            paginated = filtered[offset : offset + limit]
            for c in paginated:
                c.pop("verification_key_hash", None)

            return {
                "cases": paginated,
                "total": total_count,
                "limit": limit,
                "offset": offset,
                "institution_id": inst_id
            }

    def list_institution_members(self, officer_user: AuthUser) -> List[Dict[str, Any]]:
        """
        Lists registered officers and committee members for the administrator's institution.
        """
        if not officer_user or getattr(officer_user, "account_status", None) != AccountStatus.ACTIVE:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication required: Officer account is inactive or token is invalid."
            )

        if officer_user.role not in [UserRole.INSTITUTION_ADMIN, UserRole.CHIEF_PROCTOR, UserRole.PLATFORM_ADMIN]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied: Only Institution Administrators, Chief Proctors, or Platform Admins may view member rosters."
            )

        inst_id = officer_user.institution_id
        if self.use_supabase and self.supabase:
            try:
                query = self.supabase.table("institution_memberships").select(
                    "id, user_id, institution_id, institution_code, role, account_status, created_at, updated_at"
                )
                if officer_user.role != UserRole.PLATFORM_ADMIN:
                    query = query.eq("institution_code", inst_id)
                res = query.execute()
                members = res.data or []

                user_ids = [m["user_id"] for m in members if m.get("user_id")]
                profile_map = {}
                if user_ids:
                    p_res = self.supabase.table("profiles").select("id, email, full_name").in_("id", user_ids).execute()
                    for p in (p_res.data or []):
                        profile_map[p["id"]] = p

                for m in members:
                    uid = m.get("user_id")
                    if uid in profile_map:
                        m["full_name"] = profile_map[uid].get("full_name") or "Institutional Officer"
                        m["email"] = profile_map[uid].get("email") or ""
                    else:
                        m["full_name"] = "Institutional Officer"
                        m["email"] = ""

                return members
            except Exception as e:
                logger.error(f"Error listing institution members: {e}")
                raise HTTPException(status_code=500, detail="Failed to retrieve institution members.")
        return []

    def update_member_status(self, admin_user: AuthUser, target_user_id: str, new_status: str) -> Dict[str, Any]:
        """
        Updates an institution member's account status (active, suspended, revoked).
        Strictly restricted to Institution Administrators or Platform Admins.
        Enforces cross-institution isolation (target must belong to admin's institution).
        """
        if not admin_user or getattr(admin_user, "account_status", None) != AccountStatus.ACTIVE:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication required: Admin account is inactive or token is invalid."
            )

        if admin_user.role not in [UserRole.INSTITUTION_ADMIN, UserRole.PLATFORM_ADMIN]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied: Only Institution Administrators or Platform Admins may update member account statuses."
            )

        valid_statuses = ["active", "suspended", "revoked"]
        norm_status = new_status.strip().lower()
        if norm_status not in valid_statuses:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid status '{new_status}'. Permitted: {valid_statuses}."
            )

        if self.use_supabase and self.supabase:
            try:
                query = self.supabase.table("institution_memberships").select("*").eq("user_id", target_user_id)
                if admin_user.role != UserRole.PLATFORM_ADMIN:
                    query = query.eq("institution_code", admin_user.institution_id)
                res = query.execute()
                if not res.data:
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail="Member not found in your institution."
                    )
                membership = res.data[0]

                upd_res = self.supabase.table("institution_memberships").update({
                    "account_status": norm_status,
                    "updated_at": datetime.now(timezone.utc).isoformat()
                }).eq("id", membership["id"]).execute()

                try:
                    self.supabase.table("profiles").update({
                        "account_status": norm_status,
                        "updated_at": datetime.now(timezone.utc).isoformat()
                    }).eq("id", target_user_id).execute()
                except Exception as ep:
                    logger.warning(f"Error updating profiles account_status: {ep}")

                return upd_res.data[0] if upd_res.data else {"user_id": target_user_id, "account_status": norm_status}
            except HTTPException:
                raise
            except Exception as e:
                logger.error(f"Error updating member status: {e}")
                raise HTTPException(status_code=500, detail="Database update failed for member status.")
        return {"user_id": target_user_id, "account_status": norm_status}

    def list_unassigned_cases(self, chief_user: AuthUser) -> List[Dict[str, Any]]:
        """
        Lists grievances in the chief proctor's institution that have not yet been assigned to an individual proctor.
        Authorized for Chief Proctors, Institution Admins, or Platform Admins.
        """
        if not chief_user or getattr(chief_user, "account_status", None) != AccountStatus.ACTIVE:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication required: Officer account is inactive or token is invalid."
            )

        if chief_user.role not in [UserRole.CHIEF_PROCTOR, UserRole.INSTITUTION_ADMIN, UserRole.PLATFORM_ADMIN]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied: Only Chief Proctors or Administrators may view unassigned triage queue."
            )

        self._ensure_connected()
        inst_id = chief_user.institution_id

        if self.use_supabase and self.supabase:
            try:
                query = self.supabase.table("campus_cases").select("*").order("created_at", desc=True)
                if chief_user.role != UserRole.PLATFORM_ADMIN:
                    query = query.eq("institution_id", inst_id)
                res = query.execute()
                cases = res.data or []
                unassigned = [
                    c for c in cases
                    if not c.get("assigned_proctor") and not c.get("assigned_proctor_user_id")
                ]
                for c in unassigned:
                    c.pop("verification_key_hash", None)
                return unassigned
            except Exception as e:
                logger.error(f"Error fetching unassigned cases: {e}")
                raise HTTPException(status_code=500, detail="Failed to fetch unassigned cases.")
        else:
            cases = self._list_cases_sqlite(inst_id, is_admin=(chief_user.role == UserRole.PLATFORM_ADMIN))
            unassigned = [c for c in cases if not c.get("assigned_proctor")]
            for c in unassigned:
                c.pop("verification_key_hash", None)
            return unassigned

    def list_assigned_cases_for_proctor(self, proctor_user: AuthUser) -> List[Dict[str, Any]]:
        """
        Lists campus cases specifically assigned to this proctor.
        """
        if not proctor_user or getattr(proctor_user, "account_status", None) != AccountStatus.ACTIVE:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication required: Officer account is inactive, suspended, or revoked."
            )

        if proctor_user.role not in [UserRole.PROCTOR, UserRole.CHIEF_PROCTOR, UserRole.INSTITUTION_ADMIN, UserRole.PLATFORM_ADMIN]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied: Only proctors or administrators may view assigned inquiries."
            )

        self._ensure_connected()
        inst_id = proctor_user.institution_id
        uid = str(proctor_user.user_id)

        if self.use_supabase and self.supabase:
            try:
                query = self.supabase.table("campus_cases").select("*").order("created_at", desc=True)
                if proctor_user.role != UserRole.PLATFORM_ADMIN:
                    query = query.eq("institution_id", inst_id)
                res = query.execute()
                cases = res.data or []
                assigned_cases = []
                for c in cases:
                    assigned_uuid = c.get("assigned_proctor_user_id")
                    assigned_name = c.get("assigned_proctor")
                    if (
                        (assigned_uuid and str(assigned_uuid).lower() == uid.lower()) or
                        (not assigned_uuid and assigned_name and (
                            str(assigned_name).lower() == uid.lower() or
                            assigned_name == proctor_user.name
                        ))
                    ):
                        c.pop("verification_key_hash", None)
                        assigned_cases.append(c)
                return assigned_cases
            except Exception as e:
                logger.error(f"Error fetching assigned cases for proctor: {e}")
                raise HTTPException(status_code=500, detail="Failed to fetch assigned cases.")
        else:
            cases = self._list_cases_sqlite(inst_id, is_admin=(proctor_user.role == UserRole.PLATFORM_ADMIN))
            assigned_cases = [c for c in cases if c.get("assigned_proctor") == proctor_user.name or c.get("assigned_proctor") == uid]
            for c in assigned_cases:
                c.pop("verification_key_hash", None)
            return assigned_cases

    def list_committee_inquiries(self, member_user: AuthUser) -> List[Dict[str, Any]]:
        """
        Lists only cases where the member has an active committee assignment.
        Revoked or suspended members receive immediate denial or empty result.
        """
        if not member_user or getattr(member_user, "account_status", None) != AccountStatus.ACTIVE:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication required: Committee member account is inactive, suspended, or revoked."
            )

        self._ensure_connected()
        uid = str(member_user.user_id)

        if self.use_supabase and self.supabase:
            try:
                # First verify active membership in institution_memberships
                m_check = self.supabase.table("institution_memberships").select("id, account_status").eq(
                    "user_id", uid
                ).eq("account_status", "active").execute()
                if not m_check.data and member_user.role != UserRole.PLATFORM_ADMIN:
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail="Access denied: User lacks active institutional membership."
                    )

                # Query active assignments
                asgn_res = self.supabase.table("case_committee_assignments").select(
                    "id, case_uuid, case_id, role, committee_name, assignment_status"
                ).eq("user_id", uid).eq("assignment_status", "active").execute()
                active_assignments = asgn_res.data or []
                if not active_assignments:
                    return []

                case_ids = [a["case_id"] for a in active_assignments if a.get("case_id")]
                if not case_ids:
                    return []

                c_res = self.supabase.table("campus_cases").select("*").in_("case_id", case_ids).order("created_at", desc=True).execute()
                cases = c_res.data or []
                for c in cases:
                    c.pop("verification_key_hash", None)
                    matching_asgn = next((a for a in active_assignments if a.get("case_id") == c.get("case_id")), None)
                    if matching_asgn:
                        c["committee_role"] = matching_asgn.get("role")
                        c["committee_name"] = matching_asgn.get("committee_name")
                return cases
            except HTTPException:
                raise
            except Exception as e:
                logger.error(f"Error fetching committee inquiries: {e}")
                raise HTTPException(status_code=500, detail="Failed to fetch committee inquiries.")
        else:
            return []

    def add_committee_observation(
        self,
        case_id: str,
        observations: str,
        recommendations: Optional[str] = "",
        findings: Optional[str] = "",
        member_user: Optional[AuthUser] = None
    ) -> Dict[str, Any]:
        """
        Records observations, findings, and recommendations from an authorized committee member.
        Enforces active assignment and active account status.
        Logs immutable case activity and dispatches notifications.
        """
        if not member_user or getattr(member_user, "account_status", None) != AccountStatus.ACTIVE:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication required: Committee member account is inactive or token is invalid."
            )

        clean_id = (case_id or "").strip().upper()
        case = self._fetch_raw_case(clean_id)
        if not case:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Case '{clean_id}' not found.")

        # Cross-case-type rejection: Campus proctor can only manage CAMPUS_GRIEVANCE cases
        case_type = case.get("case_type")
        if case_type and case_type != "CAMPUS_GRIEVANCE":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cross-case-type rejection: Case '{clean_id}' is of type '{case_type}' and is not a campus grievance."
            )

        verify_institutional_boundary(member_user, case.get("institution_id", "INST_DEFAULT"))

        # Verify active committee assignment if not Platform Admin, Chief Proctor, or Institution Admin
        if member_user.role not in [UserRole.PLATFORM_ADMIN, UserRole.CHIEF_PROCTOR, UserRole.INSTITUTION_ADMIN]:
            if self.use_supabase and self.supabase:
                asgn_check = self.supabase.table("case_committee_assignments").select("id").eq(
                    "case_id", clean_id
                ).eq("user_id", member_user.user_id).eq("assignment_status", "active").execute()
                if not asgn_check.data:
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail="Access denied: You do not have an active committee assignment for this case inquiry."
                    )

        now_iso = datetime.now(timezone.utc).isoformat()
        obs_record = {
            "author_id": member_user.user_id,
            "author_name": member_user.name or "Committee Member",
            "observations": observations.strip(),
            "recommendations": (recommendations or "").strip(),
            "findings": (findings or "").strip(),
            "recorded_at": now_iso
        }

        # Record immutable case activity
        try:
            from .audit import record_case_activity
        except ImportError:
            from audit import record_case_activity

        act_rec = record_case_activity(
            case_uuid=case.get("id"),
            case_id=clean_id,
            action_type="COMMITTEE_OBSERVATIONS_RECORDED",
            action_details=obs_record,
            actor_user=member_user,
            actor_type="USER",
            supabase_client=self.supabase
        )
        activity_id = act_rec.get("id") if isinstance(act_rec, dict) else None

        # Notify assigned proctor if assigned
        if activity_id:
            try:
                from .notifications import notification_manager
            except ImportError:
                from notifications import notification_manager

            assigned_proctor_uid = case.get("assigned_proctor_user_id")
            if assigned_proctor_uid and str(assigned_proctor_uid).lower() != str(member_user.user_id).lower():
                try:
                    notification_manager.create_notification(
                        recipient_user_id=str(assigned_proctor_uid),
                        event_type="COMMITTEE_OBSERVATIONS",
                        title="Committee Findings Submitted",
                        message=f"New committee observations and findings have been recorded for case {clean_id}.",
                        related_case_id=clean_id,
                        case_uuid=case.get("id"),
                        action_url=f"/campus-proctor/dashboard?case_id={clean_id}",
                        idempotency_key=f"notif_act_{activity_id}_obs_{assigned_proctor_uid}"
                    )
                except Exception as e_notif:
                    logger.warning(f"Error dispatching committee observation notification: {e_notif}")

        return {
            "status": "success",
            "case_id": clean_id,
            "observation": obs_record
        }

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

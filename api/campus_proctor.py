"""
NyayPath College Proctor & Student Grievance Redressal Engine
Dual-interface system for college students and the Proctorial / Grievance Redressal Committee.
Tracks campus issues, enforces UGC 15-day resolution SLA, and generates Proctorial Notices / Action Taken Reports.
Persistently backed by Supabase PostgreSQL (with on-disk persistent fallback for local testing).
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

from .auth import (
    AuthUser,
    UserRole,
    generate_secure_verification_key,
    hash_verification_key,
    verify_tracking_credential,
    verify_institutional_boundary
)

logger = logging.getLogger(__name__)

class StudentGrievanceSubmit(BaseModel):
    institution_id: Optional[str] = "INST_DEFAULT"
    student_name: Optional[str] = "Anonymous Student"
    roll_number: Optional[str] = "Confidential"
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
    assigned_committee: Optional[str] = None

class StudentTrackingRequest(BaseModel):
    case_id: str
    verification_key: str

# =====================================================================
# Persistent Storage Manager for Campus Cases
# =====================================================================

class CampusProctorManager:
    def __init__(self):
        url: str = os.environ.get("SUPABASE_URL", "")
        key: str = os.environ.get("SUPABASE_KEY", "")

        self.use_supabase = bool(url and key and create_client)
        self.supabase: Optional[Client] = None
        self._local_db_path = os.environ.get("CAMPUS_SQLITE_DB", "campus_cases_persistent.db")

        if self.use_supabase:
            try:
                self.supabase = create_client(url, key)
                logger.info("Campus Proctor Manager: Connected to Supabase PostgreSQL.")
            except Exception as e:
                logger.error(f"Campus Proctor Supabase connection error: {e}")
                self.use_supabase = False
                self.supabase = None
        else:
            logger.info(f"Supabase credentials not configured. Using local persistent disk storage at '{self._local_db_path}'.")
            self._init_sqlite_db()

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
                history TEXT NOT NULL DEFAULT '[]',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            """)
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_campus_case_id ON campus_cases(case_id);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_campus_institution ON campus_cases(institution_id);")
            conn.commit()
            conn.close()
        except Exception as e:
            logger.error(f"Failed to initialize local SQLite persistent DB: {e}")

    def _ensure_connected(self):
        """Validates that a persistent database is ready. Raises 503 if unavailable."""
        if self.use_supabase and self.supabase is not None:
            return
        if os.environ.get("STRICT_SUPABASE_ONLY") == "1":
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Database unavailable: Supabase credentials required for permanent grievance persistence."
            )

    # -----------------------------------------------------------------
    # Case Submission (Student Workflow)
    # -----------------------------------------------------------------
    def create_case(
        self,
        payload: StudentGrievanceSubmit,
        student_user: Optional[AuthUser] = None
    ) -> Dict[str, Any]:
        """
        Registers a new grievance with unique Case ID and high-entropy verification key.
        Persists directly to database (Supabase or disk-backed store).
        """
        self._ensure_connected()

        raw_code = uuid.uuid4().hex[:4].upper()
        dept_code = payload.department[:2].upper() if payload.department else "GR"
        case_id = f"CAMPUS-{raw_code}-{dept_code}"
        
        # High-entropy secret for anonymous verification
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

        initial_history = [{
            "timestamp": now_iso,
            "action": "GRIEVANCE_REGISTERED",
            "actor": "Complainant (Student)",
            "details": "Grievance submitted under UGC Student Grievance Regulations."
        }]

        record = {
            "id": str(uuid.uuid4()),
            "case_id": case_id,
            "institution_id": (payload.institution_id or "INST_DEFAULT").strip().upper(),
            "student_user_id": student_user.user_id if student_user else None,
            "student_name": "Confidential Student" if payload.is_anonymous else payload.student_name,
            "roll_number": "Protected" if payload.is_anonymous else payload.roll_number,
            "department": payload.department,
            "year": payload.year,
            "category": payload.category,
            "subject": payload.subject,
            "description": payload.description,
            "incident_date": payload.incident_date or now.strftime("%Y-%m-%d"),
            "is_anonymous": bool(payload.is_anonymous),
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
            # 2. Local Persistent Disk Storage
            self._save_record_sqlite(record)

        # Return record to student along with the plaintext verification key
        result = dict(record)
        result["verification_key"] = verification_key
        # Omit internal hash from student response
        result.pop("verification_key_hash", None)
        return result

    # -----------------------------------------------------------------
    # Student Grievance Lookup (Protected by Verification Key)
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
        """
        clean_id = (case_id or "").strip().upper()
        case = self._fetch_raw_case(clean_id)
        if not case:
            raise HTTPException(status_code=404, detail="Campus grievance case not found.")

        # Check authorization
        authorized = False

        # Mode A: Authenticated student owns this record
        if student_user and case.get("student_user_id") and case["student_user_id"] == student_user.user_id:
            authorized = True

        # Mode B: High-entropy verification credential supplied
        if verification_key and verify_tracking_credential(verification_key, case.get("verification_key_hash", "")):
            authorized = True

        if not authorized:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied: Case ID alone is insufficient to view private grievance details. Please provide your secret Verification Key."
            )

        sanitized = dict(case)
        sanitized.pop("verification_key_hash", None)
        return sanitized

    # -----------------------------------------------------------------
    # Proctor Dashboard: Fetch Single Case with Institutional Boundary
    # -----------------------------------------------------------------
    def get_case_for_proctor(self, case_id: str, proctor_user: AuthUser) -> Dict[str, Any]:
        clean_id = (case_id or "").strip().upper()
        case = self._fetch_raw_case(clean_id)
        if not case:
            raise HTTPException(status_code=404, detail="Campus grievance case not found.")

        verify_institutional_boundary(proctor_user, case.get("institution_id", "INST_DEFAULT"))
        sanitized = dict(case)
        sanitized.pop("verification_key_hash", None)
        return sanitized

    # -----------------------------------------------------------------
    # Proctor Dashboard: List Inquiries for Authorized Institution
    # -----------------------------------------------------------------
    def list_cases_for_proctor(self, proctor_user: AuthUser) -> List[Dict[str, Any]]:
        self._ensure_connected()
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

        # Sanitize sensitive hashes from list output
        for c in cases:
            c.pop("verification_key_hash", None)

        return cases

    # -----------------------------------------------------------------
    # Proctor Dashboard: Update Status & Findings
    # -----------------------------------------------------------------
    def update_case(self, payload: ProctorUpdateStatus, proctor_user: AuthUser) -> Dict[str, Any]:
        clean_id = payload.case_id.strip().upper()
        case = self._fetch_raw_case(clean_id)
        if not case:
            raise HTTPException(status_code=404, detail="Case not found.")

        verify_institutional_boundary(proctor_user, case.get("institution_id", "INST_DEFAULT"))

        now_iso = datetime.now(timezone.utc).isoformat()
        history = list(case.get("history") or [])
        history.append({
            "timestamp": now_iso,
            "action": f"STATUS_UPDATED_TO_{payload.new_status}",
            "actor": f"{proctor_user.name} ({proctor_user.role.value})",
            "details": payload.proctor_notes or "Status updated by proctorial authority."
        })

        updates = {
            "status": payload.new_status,
            "proctor_notes": payload.proctor_notes if payload.proctor_notes is not None else case.get("proctor_notes"),
            "hearing_date": payload.hearing_date if payload.hearing_date is not None else case.get("hearing_date"),
            "action_taken": payload.action_taken if payload.action_taken is not None else case.get("action_taken"),
            "resolution_details": payload.resolution_details if payload.resolution_details is not None else case.get("resolution_details"),
            "assigned_proctor": payload.assigned_proctor if payload.assigned_proctor is not None else case.get("assigned_proctor"),
            "assigned_committee": payload.assigned_committee if payload.assigned_committee is not None else case.get("assigned_committee"),
            "history": history,
            "updated_at": now_iso
        }

        if self.use_supabase and self.supabase:
            try:
                res = self.supabase.table("campus_cases").update(updates).eq("case_id", clean_id).execute()
                if not res.data:
                    raise RuntimeError("Supabase update returned empty.")
                case = res.data[0]
            except Exception as e:
                logger.error(f"Supabase UPDATE Error in campus_proctor: {e}")
                raise HTTPException(status_code=500, detail="Database update failed.")
        else:
            case.update(updates)
            self._update_record_sqlite(case)

        sanitized = dict(case)
        sanitized.pop("verification_key_hash", None)
        return sanitized

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
        else:
            # If called without credentials, sanitize complainant identity
            pass

        notice = f"""OFFICE OF THE CHIEF PROCTOR & STUDENT GRIEVANCE REDRESSAL CELL
================================================================================
FORMAL PROCTORIAL INQUIRY NOTICE & CASE PROCEEDINGS
Ref No: PROCTOR/SGRC/2026/{case['case_id']}
Institution Identifier: {case.get('institution_id', 'INST_DEFAULT')}
Date of Issuance: {datetime.now().strftime('%d-%B-%Y')}
Statutory Mandate: UGC (Grievance Redressal of Students) Regulations, 2023

1. CASE IDENTIFIER & COMPLAINANT PARTICULARS:
   - Case Reference ID : {case['case_id']}
   - Complainant Name  : {case.get('student_name', 'Protected Complainant')}
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
                verification_key_hash, history, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
        """, (
            r["id"], r["case_id"], r["institution_id"], r["student_user_id"], r["student_name"],
            r["roll_number"], r["department"], r["year"], r["category"], r["subject"],
            r["description"], r["incident_date"], 1 if r["is_anonymous"] else 0,
            r["confidentiality_mode"], r["severity"], r["status"], r["proctor_notes"],
            r["hearing_date"], r["action_taken"], r["resolution_details"],
            r["resolution_deadline"], r["assigned_proctor"], r["assigned_committee"],
            json.dumps(r["supporting_documents"]), r["verification_key_hash"],
            json.dumps(r["history"]), r["created_at"], r["updated_at"]
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

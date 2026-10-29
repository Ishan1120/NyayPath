"""
JanAdhikar College Proctor & Student Grievance Redressal Engine
Dual-interface system for college students and the Proctorial / Grievance Redressal Committee.
Tracks campus issues, enforces UGC 15-day resolution SLA, and generates Proctorial Notices / Action Taken Reports.
"""

import time
import uuid
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, List, Optional
from pydantic import BaseModel

# In-memory storage for campus proctorial cases
CAMPUS_CASES: Dict[str, Dict[str, Any]] = {
    "CAMPUS-7821-UP": {
        "case_id": "CAMPUS-7821-UP",
        "student_name": "Aarav Gupta",
        "roll_number": "22CS104",
        "department": "Computer Science & Engineering",
        "year": "3rd Year",
        "category": "Hostel & Facilities",
        "subject": "Contaminated drinking water in Boys Hostel Block B",
        "description": "The water cooler on the 2nd floor of Hostel B has not been cleaned for 4 months. Multiple students have fallen sick with jaundice symptoms. Warden has ignored 3 written requests.",
        "incident_date": "2024-10-15",
        "submitted_at": "2024-10-18T10:30:00Z",
        "status": "HEARING_SCHEDULED",
        "severity": "URGENT",
        "proctor_notes": "Estate officer summoned. Sample sent for laboratory bacteriological testing. Hearing scheduled with hostel representatives.",
        "hearing_date": "2024-11-02 at 11:30 AM (Proctor's Office, Room 102)",
        "resolution_deadline": "2024-11-05",
        "is_anonymous": False,
        "action_taken": "Maintenance agency served show-cause notice. Water filter cartridge replaced on 24-Oct."
    },
    "CAMPUS-9034-EX": {
        "case_id": "CAMPUS-9034-EX",
        "student_name": "Riya Verma",
        "roll_number": "22IT058",
        "department": "Information Technology",
        "year": "3rd Year",
        "category": "Examination & Evaluation",
        "subject": "Discrepancy in Semester 5 Database Management Systems evaluation",
        "description": "My total marks in DBMS theory were miscalculated on the marksheet (awarded 42 instead of 64). Examination cell refuses to accept re-evaluation form citing expired 7-day window.",
        "incident_date": "2024-10-20",
        "submitted_at": "2024-10-22T14:15:00Z",
        "status": "UNDER_INQUIRY",
        "severity": "HIGH",
        "proctor_notes": "Controller of Examinations requested to verify original tabulation ledger as per Supreme Court Aditya Bandopadhyay precedent.",
        "hearing_date": "TBD",
        "resolution_deadline": "2024-11-06",
        "is_anonymous": False,
        "action_taken": "Tabulation ledger requisitioned from Central Evaluation Center."
    }
}

class StudentGrievanceSubmit(BaseModel):
    student_name: Optional[str] = "Anonymous Student"
    roll_number: Optional[str] = "Confidential"
    department: str
    year: str
    category: str  # Hostel, Examination, Fee/Scholarship, Ragging/Harassment, Lab/Infrastructure
    subject: str
    description: str
    incident_date: Optional[str] = None
    is_anonymous: Optional[bool] = False

class ProctorUpdateStatus(BaseModel):
    case_id: str
    new_status: str  # SUBMITTED, UNDER_INQUIRY, HEARING_SCHEDULED, ACTION_TAKEN, RESOLVED
    proctor_notes: Optional[str] = ""
    hearing_date: Optional[str] = None
    action_taken: Optional[str] = None

class CampusProctorManager:
    def create_case(self, payload: StudentGrievanceSubmit) -> Dict[str, Any]:
        """Generates a unique Campus Case Passkey and registers student grievance."""
        raw_code = uuid.uuid4().hex[:4].upper()
        case_id = f"CAMPUS-{raw_code}-{payload.department[:2].upper()}"
        
        now = datetime.now(timezone.utc)
        deadline = (now + timedelta(days=15)).strftime("%Y-%m-%d")

        # Determine severity based on category keywords
        desc_lower = payload.description.lower()
        if "ragging" in desc_lower or "harassment" in desc_lower or "contaminated" in desc_lower or "sick" in desc_lower:
            severity = "URGENT"
        elif "exam" in desc_lower or "marksheet" in desc_lower or "scholarship" in desc_lower or "fee" in desc_lower:
            severity = "HIGH"
        else:
            severity = "NORMAL"

        case_record = {
            "case_id": case_id,
            "student_name": "Confidential Student" if payload.is_anonymous else payload.student_name,
            "roll_number": "Protected" if payload.is_anonymous else payload.roll_number,
            "department": payload.department,
            "year": payload.year,
            "category": payload.category,
            "subject": payload.subject,
            "description": payload.description,
            "incident_date": payload.incident_date or now.strftime("%Y-%m-%d"),
            "submitted_at": now.isoformat(),
            "status": "SUBMITTED",
            "severity": severity,
            "proctor_notes": "Grievance received by the Proctorial Grievance Redressal Cell. Acknowledged.",
            "hearing_date": "Pending Proctorial Review",
            "resolution_deadline": deadline,
            "is_anonymous": payload.is_anonymous or False,
            "action_taken": "Pending inquiry by departmental committee."
        }
        
        CAMPUS_CASES[case_id] = case_record
        return case_record

    def get_case(self, case_id: str) -> Optional[Dict[str, Any]]:
        return CAMPUS_CASES.get(case_id.strip().upper())

    def list_all_cases(self) -> List[Dict[str, Any]]:
        return list(CAMPUS_CASES.values())

    def update_case(self, payload: ProctorUpdateStatus) -> Optional[Dict[str, Any]]:
        case = CAMPUS_CASES.get(payload.case_id)
        if not case:
            return None
            
        case["status"] = payload.new_status
        if payload.proctor_notes:
            case["proctor_notes"] = payload.proctor_notes
        if payload.hearing_date:
            case["hearing_date"] = payload.hearing_date
        if payload.action_taken:
            case["action_taken"] = payload.action_taken
            
        CAMPUS_CASES[payload.case_id] = case
        return case

    def generate_proctorial_notice(self, case_id: str) -> str:
        """Generates an official formal Proctorial Inquiry & Hearing Notice."""
        case = self.get_case(case_id)
        if not case:
            return "Case ID not found in campus registry."

        notice = f"""OFFICE OF THE CHIEF PROCTOR & STUDENT GRIEVANCE REDRESSAL CELL
================================================================================
FORMAL PROCTORIAL INQUIRY NOTICE & CASE PROCEEDINGS
Ref No: PROCTOR/SGRC/2025-26/{case['case_id']}
Date of Issuance: {datetime.now().strftime('%d-%B-%Y')}
Statutory Mandate: UGC (Grievance Redressal of Students) Regulations, 2023

1. CASE IDENTIFIER & COMPLAINANT PARTICULARS:
   - Case Reference ID : {case['case_id']}
   - Department / Year : {case['department']} ({case['year']})
   - Case Category     : {case['category']} (Severity: {case['severity']})
   - Status of Case    : {case['status']}

2. SUBJECT MATTER / CAUSE OF GRIEVANCE:
   "{case['subject']}"

3. SUMMARY OF INQUIRY PROCEEDINGS & FINDINGS:
   {case['description']}

4. PROCTORIAL DIRECTIVE & ACTION TAKEN:
   - Notes by Chief Proctor : {case['proctor_notes']}
   - Hearing / Meeting Date : {case['hearing_date']}
   - Institutional Action   : {case['action_taken']}
   - Statutory UGC Deadline : {case['resolution_deadline']} (15-Day Resolution Limit)

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

campus_proctor_manager = CampusProctorManager()


from dotenv import load_dotenv
load_dotenv()
import os
import json
import re
import logging
from typing import Dict, Any, List, Optional
from groq import Groq

logger = logging.getLogger(__name__)

# =====================================================================
# DOMAIN KNOWLEDGE BASE FOR TARGETED CLARIFYING QUESTIONS
# Covers all 12 major Indian civic, legal, administrative & consumer domains
# =====================================================================

CLARIFYING_DOMAIN_TEMPLATES: Dict[str, Dict[str, Any]] = {
    "campus_ragging": {
        "domain_name": "Campus Anti-Ragging, Student Safety & Proctorial Discipline",
        "likely_route": "Rights/Grievance",
        "target_authority": "Chief Proctor / Head of Institution & Anti-Ragging Committee",
        "statutory_act": "UGC Regulations on Curbing Ragging (2009) & Supreme Court Mandate (SLP No. 24295/2004) read with BNS/IPC Sec. 351/115",
        "questions": [
            {
                "id": "q_campus",
                "field_key": "target_department",
                "title": "College/University & Hostel Details",
                "question": "What is the name of your College/University, Campus location, and Hostel block/room number?",
                "placeholder": "e.g., National Institute of Technology, Boys Hostel Block-C, Room 204",
                "suggestions": ["Campus Hostel Resident", "Day Scholar / College Campus", "Off-Campus Approved Housing", "First-Year Hostel Wing"]
            },
            {
                "id": "q_accused",
                "field_key": "applicant_address",
                "title": "Senior Students / Accused Details (Confidential)",
                "question": "Who are the accused senior students/groups involved? (You may also choose 'Keep My Identity Strictly Confidential')",
                "placeholder": "e.g., 2nd-year seniors (Names / Room / Branch) or specify Confidential",
                "suggestions": [
                    "Keep Complainant Identity Strictly Confidential",
                    "Senior batch students in hostel wing",
                    "Names and room numbers available",
                    "Multiple senior hostel inmates"
                ]
            },
            {
                "id": "q_incident",
                "field_key": "incident_date",
                "title": "Incident Timeline & Specific Acts",
                "question": "When did the ragging occur, and what specific acts took place (e.g. physical assault, verbal abuse, forced tasks, threats)?",
                "placeholder": "e.g., Ongoing for 3 days; physical intimidation and verbal abuse last night at 11 PM",
                "suggestions": [
                    "Physical intimidation & verbal harassment at night in hostel",
                    "Forced late-night menial tasks & sleep deprivation",
                    "Verbal abuse and threats of academic boycott",
                    "Cyber-bullying & group intimidation on messaging apps"
                ]
            },
            {
                "id": "q_relief",
                "field_key": "desired_relief",
                "title": "Emergency Protective Relief Demanded",
                "question": "What immediate statutory action do you demand from the Head of Institution and Proctor under UGC rules?",
                "placeholder": "e.g., Immediate police FIR, provisional suspension of culprits, and 24/7 hostel security protection",
                "suggestions": [
                    "Immediate lodging of FIR with local police under mandatory UGC 24-hr rule",
                    "Immediate provisional suspension of accused seniors pending inquiry",
                    "Confidential Anti-Ragging Committee emergency hearing within 24 hours",
                    "Immediate hostel room relocation and physical security protection"
                ]
            }
        ]
    },

    "pwd_roads": {
        "domain_name": "Public Works & Municipal Infrastructure (Roads/Potholes/Tender)",
        "likely_route": "RTI",
        "target_authority": "Municipal Corporation / Public Works Department (PWD)",
        "statutory_act": "Right to Information Act, 2005 (Sec. 6(1) read with Sec. 2(j)(i))",
        "questions": [
            {
                "id": "q_location",
                "field_key": "applicant_city",
                "title": "Exact Locality & Road Stretch",
                "question": "What is the exact locality, street/ward number, and city where the road work is located?",
                "placeholder": "e.g., Ward 12 Main Market Road, Gomti Nagar, Lucknow",
                "suggestions": ["Ward 12 Main Road", "Colony Connecting Road", "Sector-B Main Boulevard", "State Highway Link"]
            },
            {
                "id": "q_timeline",
                "field_key": "incident_date",
                "title": "Work Execution Timeline",
                "question": "Approximately when was the road carpeting/repair completed, and when did the potholes/breakdown appear?",
                "placeholder": "e.g., Completed 3 months ago; potholes developed within 45 days",
                "suggestions": ["Completed 3 months ago", "Repaired last month", "Work stopped halfway 6 months ago", "Ongoing delay"]
            },
            {
                "id": "q_authority",
                "field_key": "target_department",
                "title": "Concerned Public Authority / Division",
                "question": "Do you know which agency sanctioned or contracted the road work?",
                "placeholder": "e.g., Municipal Corporation Engineering Division or State PWD",
                "suggestions": ["Municipal Corporation (Nagar Nigam)", "State Public Works Department (PWD)", "Development Authority (e.g. LDA/DDA)", "Gram Panchayat"]
            },
            {
                "id": "q_records",
                "field_key": "specific_records",
                "title": "Specific Certified Records Demanded",
                "question": "What certified technical records do you want to inspect or demand under RTI?",
                "placeholder": "e.g., Measurement Book (MB) entries, Bitumen test logs, Contractor penalty ledger",
                "suggestions": [
                    "Tender agreement & milestone schedule",
                    "Measurement Book (MB) entries & bituminous test logs",
                    "Total funds disbursed & delay penalty ledger",
                    "Third-party quality audit inspection report"
                ]
            }
        ]
    },
    "tenancy_deposit": {
        "domain_name": "Tenancy Rights & Security Deposit Refund Refusal",
        "likely_route": "Rights/Grievance",
        "target_authority": "Rent Authority / District Consumer Disputes Redressal Commission",
        "statutory_act": "Consumer Protection Act, 2019 (Sec. 35) & State Model Tenancy Act",
        "questions": [
            {
                "id": "q_amount",
                "field_key": "financial_loss",
                "title": "Withheld Security Deposit Amount",
                "question": "What is the exact security deposit amount withheld by the landlord?",
                "placeholder": "e.g., ₹45,000",
                "suggestions": ["₹25,000", "₹45,000", "₹60,000", "₹1,00,000"]
            },
            {
                "id": "q_address",
                "field_key": "applicant_city",
                "title": "Rented Premises Address & City",
                "question": "What was the complete address of the rented premises and city/district?",
                "placeholder": "e.g., Flat 402, Green Park Apartments, Bengaluru",
                "suggestions": ["Bengaluru, Karnataka", "Noida / Greater Noida", "Pune, Maharashtra", "Gurugram, Haryana"]
            },
            {
                "id": "q_notice",
                "field_key": "incident_date",
                "title": "Date of Vacating & Notice Period",
                "question": "On what date did you vacate the property, and did you give prior written notice (e.g. 1 month)?",
                "placeholder": "e.g., Vacated on 1st of last month after giving 30 days WhatsApp/email notice",
                "suggestions": ["Vacated with 30-day prior written notice", "Vacated at end of lease agreement", "Vacated 15 days ago", "Mutual verbal agreement"]
            },
            {
                "id": "q_excuse",
                "field_key": "desired_relief",
                "title": "Landlord's Excuse & Relief Claimed",
                "question": "What justification did the landlord claim (e.g. repainting, wear-and-tear), and what relief do you demand?",
                "placeholder": "e.g., Claimed bogus repainting charges without bills. Demand 100% refund with 18% p.a. interest.",
                "suggestions": [
                    "Full deposit refund + 18% p.a. interest (no bills provided)",
                    "Deducted bogus painting/cleaning fees despite clean handover",
                    "Refused to reply or answer calls after vacating",
                    "Return of unencumbered deposit plus compensation for harassment"
                ]
            }
        ]
    },
    "consumer_ecommerce": {
        "domain_name": "Consumer Rights & E-Commerce Defective Product/Refund",
        "likely_route": "Rights/Grievance",
        "target_authority": "National Consumer Helpline (NCH) / District Consumer Commission",
        "statutory_act": "Consumer Protection Act, 2019 (Sec. 2(11) Deficiency of Service & Sec. 35)",
        "questions": [
            {
                "id": "q_order_id",
                "field_key": "file_or_work_no",
                "title": "Order / Invoice Reference Number",
                "question": "What is your Order ID, Invoice number, or customer support ticket number?",
                "placeholder": "e.g., OD394819284192 / Support Ticket #88412",
                "suggestions": ["Online Order Reference Available", "Invoice / Bill Available", "Customer Care Ticket Closed Unresolved"]
            },
            {
                "id": "q_price",
                "field_key": "financial_loss",
                "title": "Total Transaction Amount Paid",
                "question": "What was the total purchase amount paid for the product or service?",
                "placeholder": "e.g., ₹24,999",
                "suggestions": ["₹5,499", "₹18,500", "₹42,000", "₹75,000"]
            },
            {
                "id": "q_issue",
                "field_key": "incident_date",
                "title": "Nature of Defect & Delivery Date",
                "question": "What exact defect occurred (e.g. wrong product, damaged in transit, counterfeit) and when was it delivered?",
                "placeholder": "e.g., Delivered damaged/different item on 12th of this month; unboxing video recorded",
                "suggestions": [
                    "Different/damaged item delivered; return rejected",
                    "Item malfunctioned within return window; warranty refused",
                    "Product never delivered despite payment debited",
                    "Cancelled order but refund not credited after 14 days"
                ]
            },
            {
                "id": "q_relief",
                "field_key": "desired_relief",
                "title": "Remedy & Compensation Demanded",
                "question": "What specific remedy do you seek from the seller and marketplace platform?",
                "placeholder": "e.g., Full refund of purchase price + ₹10,000 compensation for mental harassment",
                "suggestions": [
                    "Immediate 100% refund to original payment source with 18% p.a. interest",
                    "Free replacement with certified brand-new unit",
                    "Refund plus ₹15,000 compensation for unfair trade practice",
                    "Formal rectification and warranty honor"
                ]
            }
        ]
    },
    "epfo_pension": {
        "domain_name": "Social Security & EPFO Pension / Provident Fund Hold",
        "likely_route": "RTI",
        "target_authority": "Central Public Information Officer, Regional EPFO Office",
        "statutory_act": "Right to Information Act, 2005 read with Employees' Pension Scheme 1995",
        "questions": [
            {
                "id": "q_uan",
                "field_key": "file_or_work_no",
                "title": "UAN / Member ID / PPO Number",
                "question": "What is your UAN (Universal Account Number) or Pension Payment Order (PPO) number?",
                "placeholder": "e.g., UAN 100928491822 / Claim ID #DLCPM294819",
                "suggestions": ["UAN Number on record", "PPO / EPS-95 Claim ID", "Member ID available"]
            },
            {
                "id": "q_office",
                "field_key": "applicant_city",
                "title": "Regional EPFO Office Location",
                "question": "Which regional EPFO office has jurisdiction over your establishment (city/state)?",
                "placeholder": "e.g., EPFO Regional Office, Bandra (Mumbai) or Delhi South",
                "suggestions": ["EPFO Regional Office Delhi", "EPFO Regional Office Mumbai", "EPFO Regional Office Bengaluru", "EPFO Regional Office Kolkata"]
            },
            {
                "id": "q_delay",
                "field_key": "incident_date",
                "title": "Date of Claim Submission & Rejection",
                "question": "When did you submit the Form 10D/19/31 claim, and what reason (if any) was shown on the portal?",
                "placeholder": "e.g., Submitted 4 months ago; rejected without formal deficiency memo",
                "suggestions": ["Rejected without reason", "Pending beyond 20-day citizen charter limit", "Name/DOB mismatch excuse", "Member signature mismatch claim"]
            },
            {
                "id": "q_notings",
                "field_key": "specific_records",
                "title": "Certified Information Demanded under RTI",
                "question": "What official records do you demand under Section 6(1) to compel processing?",
                "placeholder": "e.g., Daily file movement sheet, Accounts Officer objection memo, Name of dealing official",
                "suggestions": [
                    "Daily file movement notings from submission date to present",
                    "Certified copy of deficiency memo recorded by dealing Accounts Officer",
                    "Name and designation of officer holding file beyond statutory charter",
                    "Grounds of rejection under EPF & MP Act 1952"
                ]
            }
        ]
    },
    "healthcare_ayushman": {
        "domain_name": "Public Healthcare & Ayushman Bharat (PM-JAY) Cashless Denial",
        "likely_route": "Rights/Grievance",
        "target_authority": "National Health Authority (NHA) / State Health Agency (SHA)",
        "statutory_act": "National Health Protection Scheme Directives & Consumer Protection Act, 2019",
        "questions": [
            {
                "id": "q_hospital",
                "field_key": "target_department",
                "title": "Hospital Name & Location",
                "question": "What is the name of the hospital and the city/district where treatment occurred?",
                "placeholder": "e.g., MedLife Multispeciality Hospital, Jaipur",
                "suggestions": ["Private Empanelled Hospital", "District Hospital", "Multi-Speciality Nursing Home"]
            },
            {
                "id": "q_card",
                "field_key": "file_or_work_no",
                "title": "PM-JAY Ayushman Card / Beneficiary ID",
                "question": "What is your Ayushman Bharat Beneficiary ID or Ration Card number linked to the scheme?",
                "placeholder": "e.g., PM-JAY Card #AB-9928-1928-11",
                "suggestions": ["PM-JAY Golden Card Holder", "State Health Card Holder", "BPL/SECC Beneficiary"]
            },
            {
                "id": "q_amount",
                "field_key": "financial_loss",
                "title": "Out-of-Pocket Payment Forced",
                "question": "What was the medical treatment/procedure, and how much were you forced to pay out-of-pocket?",
                "placeholder": "e.g., Emergency gall bladder surgery; forced to pay ₹75,000 in cash",
                "suggestions": ["₹35,000", "₹75,000", "₹1,20,000", "₹2,50,000"]
            },
            {
                "id": "q_relief",
                "field_key": "desired_relief",
                "title": "Relief & Disciplinary Action Demanded",
                "question": "What relief do you demand from the State Health Agency and Hospital Management?",
                "placeholder": "e.g., 100% refund of out-of-pocket charges + de-empanelment penalty against hospital",
                "suggestions": [
                    "100% refund of cash charges paid under duress with 18% interest",
                    "De-empanelment and penalty notice to hospital under PM-JAY guidelines",
                    "Compensation of ₹1,00,000 for mental trauma during emergency admission",
                    "Formal investigation by District Grievance Redressal Committee"
                ]
            }
        ]
    },
    "police_inaction": {
        "domain_name": "Police Inaction, FIR Non-Registration & Civic Harassment",
        "likely_route": "Rights/Grievance",
        "target_authority": "Superintendent of Police (SP) / Police Complaints Authority (PCA)",
        "statutory_act": "Code of Criminal Procedure / Bharatiya Nagarik Suraksha Sanhita (Lalita Kumari Mandate)",
        "questions": [
            {
                "id": "q_station",
                "field_key": "target_department",
                "title": "Police Station & Officer In-Charge",
                "question": "What is the name of the Police Station and city/district where the complaint was submitted?",
                "placeholder": "e.g., Sector 20 Police Station, Noida, Gautam Buddha Nagar",
                "suggestions": ["Local Police Station", "Cyber Crime Cell", "Women Police Station", "Traffic Division"]
            },
            {
                "id": "q_date",
                "field_key": "incident_date",
                "title": "Complaint Submission Date & GD Entry",
                "question": "When did you submit the written complaint, and did you receive a General Diary (GD) number or receiving stamp?",
                "placeholder": "e.g., Submitted written complaint on 10th of last month; stamped receiving available",
                "suggestions": ["Stamped receiving copy available", "Sent via registered speed post", "Refused to give receiving stamp", "Online portal reference number"]
            },
            {
                "id": "q_offence",
                "field_key": "user_problem",
                "title": "Nature of Cognizable Offence",
                "question": "What is the cognizable offence involved (e.g. theft, physical threat, cheating, stalking)?",
                "placeholder": "e.g., Cheating and fraud of ₹1.5 lakhs with forged signatures",
                "suggestions": ["Cheating / Fraud / Breach of Trust", "Physical threat / Criminal intimidation", "Theft / Burglary", "Cyber harassment / Identity fraud"]
            },
            {
                "id": "q_relief",
                "field_key": "desired_relief",
                "title": "Statutory Action Demanded",
                "question": "What action do you seek under Supreme Court ruling Lalita Kumari v. Govt of UP?",
                "placeholder": "e.g., Immediate registration of FIR under relevant sections and transfer to independent investigating officer",
                "suggestions": [
                    "Immediate FIR registration under Lalita Kumari SC mandatory guidelines",
                    "Inquiry by Police Complaints Authority against delinquent SHO",
                    "Preservation of CCTV footage and digital evidence",
                    "Transfer of investigation to Senior Division Officer"
                ]
            }
        ]
    },
    "university_student": {
        "domain_name": "Higher Education, Marksheet Discrepancy & University Fee Grievance",
        "likely_route": "RTI",
        "target_authority": "Public Information Officer / Registrar, University",
        "statutory_act": "RTI Act, 2005 (CBSE v. Aditya Bandopadhyay) & UGC Grievance Redressal Regulations",
        "questions": [
            {
                "id": "q_univ",
                "field_key": "target_department",
                "title": "University / College Name & Department",
                "question": "What is the name of the University / Institution and Department/Faculty?",
                "placeholder": "e.g., State Technical University, Faculty of Engineering",
                "suggestions": ["Central University", "State Technical University", "Deemed University", "Affiliated Engineering College"]
            },
            {
                "id": "q_roll",
                "field_key": "file_or_work_no",
                "title": "Roll Number & Enrollment ID",
                "question": "What is your Student Enrollment Number, Roll Number, and Course/Branch?",
                "placeholder": "e.g., Roll No. 22001928, B.Tech 6th Semester",
                "suggestions": ["Roll Number on Admit Card", "Enrollment ID on ID card", "Registration Number available"]
            },
            {
                "id": "q_issue",
                "field_key": "incident_date",
                "title": "Academic Discrepancy / Evaluation Issue",
                "question": "What exact issue occurred (e.g. marked absent despite attending, re-evaluation delay, fee refund denied)?",
                "placeholder": "e.g., Marked absent in Math-IV exam despite signing attendance sheet on 14th May",
                "suggestions": [
                    "Marked absent despite signing exam attendance sheet",
                    "Certified copy of evaluated answer booklet denied",
                    "Caution money / seat cancellation refund withheld",
                    "Degree / provisional certificate issuance delayed"
                ]
            },
            {
                "id": "q_records",
                "field_key": "specific_records",
                "title": "Certified Academic Records Demanded under RTI",
                "question": "What specific records do you demand pursuant to Supreme Court ruling in Aditya Bandopadhyay?",
                "placeholder": "e.g., Certified photocopy of answer script and invigilator signature attendance roll",
                "suggestions": [
                    "Certified photocopy of evaluated answer booklet (CBSE v. Aditya Bandopadhyay ratio)",
                    "Exam hall attendance register signed by student and invigilator",
                    "Tabulation sheet and examiner moderation marks log",
                    "File notings approving retention of caution deposit/fee"
                ]
            }
        ]
    },
    "general_civic": {
        "domain_name": "Public Administration & Citizen Grievance",
        "likely_route": "RTI",
        "target_authority": "Concerned Public Authority / Public Information Officer",
        "statutory_act": "Right to Information Act, 2005 / Citizen Charter",
        "questions": [
            {
                "id": "q_city",
                "field_key": "applicant_city",
                "title": "City, District & State",
                "question": "What is your City, District, and State of jurisdiction?",
                "placeholder": "e.g., Lucknow, Uttar Pradesh",
                "suggestions": ["New Delhi", "Lucknow, UP", "Bengaluru, Karnataka", "Jaipur, Rajasthan"]
            },
            {
                "id": "q_date",
                "field_key": "incident_date",
                "title": "Timeline of Grievance",
                "question": "When did this issue begin or when was your original application/complaint filed?",
                "placeholder": "e.g., Ongoing for the past 6 months; last representation submitted on 15th",
                "suggestions": ["Within the last 30 days", "Past 3 to 6 months", "Over 1 year ago", "Fresh occurrence"]
            },
            {
                "id": "q_authority",
                "field_key": "target_department",
                "title": "Name of Authority or Organization",
                "question": "Which specific government department, company, or authority is responsible?",
                "placeholder": "e.g., Municipal Corporation, Electricity Board, or Private Vendor",
                "suggestions": ["Municipal Corporation (ULB)", "State Department", "Central Public Authority", "Private Company"]
            },
            {
                "id": "q_relief",
                "field_key": "desired_relief",
                "title": "Specific Relief or Certified Records Sought",
                "question": "What specific certified records or statutory remedy are you seeking?",
                "placeholder": "e.g., Certified copies of file notings, inspection records, or compensation for delay",
                "suggestions": [
                    "Certified true copies of file movement notings and orders",
                    "Immediate resolution under citizen charter service standards",
                    "Financial refund / compensation for administrative deficiency",
                    "Formal written explanation and action taken report"
                ]
            }
        ]
    }
}

def detect_domain_key(text: str) -> str:
    """Classifies user complaint text to the closest domain key with full bilingual (English/Hindi) support."""
    lower = text.lower()
    
    # Campus Anti-Ragging & Student Safety (Top Priority)
    if any(k in lower for k in [
        "ragging", "ragged", "seniors", "hostel", "warden", "proctor", "anti-ragging",
        "रैगिंग", "हॉस्टल", "सीनियर्स", "मारपीट", "धमकी", "परेशान", "उत्पीड़न", "प्रताड़ना",
        "bullying", "marpeet", "ragging ho rahi", "senior student"
    ]):
        return "campus_ragging"

    # Roads & PWD (English + Hindi)
    if any(k in lower for k in [
        "road", "pothole", "potholes", "pwd", "carpeting", "tender", "bitumen", "measurement book",
        "ward 12", "contractor delay", "सड़क", "गड्ढे", "पीडब्ल्यूडी", "नगर निगम", "ठेकेदार", "टेंडर", "टूटी सड़क"
    ]):
        return "pwd_roads"

    # Tenancy / Rent / Deposit (English + Hindi)
    if any(k in lower for k in [
        "landlord", "tenant", "rent", "security deposit", "deposit", "flat", "lease", "vacate", "vacating",
        "मकान मालिक", "किराया", "अमानत राशि", "सिक्योरिटी डिपॉजिट", "फ्लैट"
    ]):
        return "tenancy_deposit"

    # E-Commerce / Consumer (English + Hindi)
    if any(k in lower for k in [
        "flipkart", "amazon", "ecommerce", "e-commerce", "laptop", "refund", "delivered", "defective",
        "warranty", "order", "delivery", "soap", "खराब सामान", "दुकानदार", "रिफंड", "वारंटी", "धोखाधड़ी"
    ]):
        return "consumer_ecommerce"

    # EPFO / Pension (English + Hindi)
    if any(k in lower for k in [
        "epfo", "pension", "eps-95", "pf claim", "provident fund", "uan", "ppo", "gratuity",
        "पेंशन", "पीएफ", "भविष्य निधि"
    ]):
        return "epfo_pension"

    # Healthcare / Ayushman (English + Hindi)
    if any(k in lower for k in [
        "ayushman", "hospital", "cashless", "surgery", "pm-jay", "doctor", "medical bill", "empanelled",
        "अस्पताल", "आयुष्मान", "इलाज", "डॉक्टर", "कैशलेस"
    ]):
        return "healthcare_ayushman"

    # Police (English + Hindi)
    if any(k in lower for k in [
        "police", "fir", "police station", "sho", "harassment", "gd entry", "crime", "threat",
        "पुलिस", "थाना", "एफआईआर", "रिश्वत", "धमकी"
    ]):
        return "police_inaction"

    # University / Student (English + Hindi)
    if any(k in lower for k in [
        "marksheet", "exam", "university", "college", "professor", "semester", "admit card", "roll no", "evaluation",
        "अंकतालिका", "परीक्षा", "विश्वविद्यालय", "कॉलेज", "रिजल्ट"
    ]):
        return "university_student"
        
    return "general_civic"


def recognize_and_generate_questions(user_problem: str, language: str = "English") -> Dict[str, Any]:
    """
    Analyzes user complaint and generates 3-4 targeted clarifying questions
    to construct a court-ready, structured systematic legal draft.
    """
    domain_key = detect_domain_key(user_problem)
    template = CLARIFYING_DOMAIN_TEMPLATES.get(domain_key, CLARIFYING_DOMAIN_TEMPLATES["general_civic"])
    
    api_key = os.environ.get("GROQ_API_KEY")
    if api_key and api_key.startswith("gsk_"):
        try:
            client = Groq(api_key=api_key)
            system_prompt = f"""You are an Expert Indian Legal Draftsman & Senior Advocate.
The citizen provided this raw complaint: "{user_problem}"
Language requested: {language}.

Generate exactly 4 targeted clarifying questions to make the citizen's petition / legal notice watertight, factual, and ready for an advocate.
Questions MUST cover:
1. Exact Location / Address / Organization identification
2. Incident date & timeline
3. Financial quantum, specific deficiency, or reference number
4. Specific certified records (under RTI) or legal relief (under Consumer Act) demanded.

Respond ONLY with valid JSON:
{{
  "recognized_issue": "Brief 3-6 word legal classification",
  "category": "{template['domain_name']}",
  "likely_route": "{template['likely_route']}",
  "target_authority": "Name of primary authority / respondent",
  "statutory_act": "{template['statutory_act']}",
  "questions": [
    {{
      "id": "q1",
      "field_key": "applicant_city",
      "title": "Short Question Title",
      "question": "Clear, friendly question asking for missing facts",
      "placeholder": "Example answer hint",
      "suggestions": ["Option 1", "Option 2", "Option 3"]
    }}
  ]
}}
"""
            completion = client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": f"Complaint: {user_problem}"}
                ],
                temperature=0.2,
                response_format={"type": "json_object"}
            )
            raw = completion.choices[0].message.content.strip()
            res = json.loads(raw)
            if res.get("questions") and len(res["questions"]) >= 3:
                return res
        except Exception as e:
            logger.warning(f"AI question generation fallback to domain templates: {e}")

    # High-quality Knowledge Base Fallback
    return {
        "recognized_issue": template["domain_name"],
        "category": template["domain_name"],
        "likely_route": template["likely_route"],
        "target_authority": template["target_authority"],
        "statutory_act": template["statutory_act"],
        "questions": template["questions"]
    }


def synthesize_systematic_draft(
    problem_text: str,
    answers: Dict[str, str],
    language: str = "English",
    route: str = "RTI",
    applicant_name: str = "The Citizen / Complainant"
) -> Dict[str, Any]:
    """
    Synthesizes the initial complaint + answered clarifying facts into a systematic,
    lawyer-ready legal draft complete with an Advocate Briefing Sheet.
    """
    domain_key = detect_domain_key(problem_text)
    template = CLARIFYING_DOMAIN_TEMPLATES.get(domain_key, CLARIFYING_DOMAIN_TEMPLATES["general_civic"])
    
    # Extract answered facts with intelligent fallbacks
    city = answers.get("applicant_city") or answers.get("q_location") or answers.get("q_address") or answers.get("q_city") or "Local Jurisdiction"
    timeline = answers.get("incident_date") or answers.get("q_timeline") or answers.get("q_notice") or answers.get("q_delay") or "Recent Period"
    authority = answers.get("target_department") or answers.get("q_authority") or answers.get("q_office") or answers.get("q_station") or answers.get("q_univ") or template["target_authority"]
    records_or_relief = answers.get("specific_records") or answers.get("desired_relief") or answers.get("q_records") or answers.get("q_relief") or "Certified inspection of records and immediate statutory relief"
    financial_loss = answers.get("financial_loss") or answers.get("q_amount") or answers.get("q_price") or ""
    ref_no = answers.get("file_or_work_no") or answers.get("q_order_id") or answers.get("q_uan") or answers.get("q_card") or answers.get("q_roll") or "[Official Reference on Record]"

    statutory_act = template["statutory_act"]

    # 1. Systematic Chronological Statement of Facts
    facts_list = [
        f"1. That the Applicant / Complainant is a bonafide citizen residing within {city} and has suffered significant legal injury / deficiency of service as detailed herein.",
        f"2. That the present dispute pertains to {template['domain_name']} involving {authority}.",
        f"3. Timeline & Occurrence: On or about {timeline}, the subject incident / statutory default occurred. Specifically: {problem_text.strip()}.",
        f"4. Official Reference & Identification: The transaction / matter is identified by reference ID / work details: {ref_no}.",
    ]
    if financial_loss:
        facts_list.append(f"5. Financial Quantum: The aggrieved party suffered a wrongful monetary withholding / direct loss quantified at Rs. {financial_loss}.")

    facts_block = "\n\n".join(facts_list)

    # 2. Specific Numbered Queries / Demands
    if route == "RTI" or template["likely_route"] == "RTI":
        title_header = f"FORM 'A' — STATUTORY APPLICATION UNDER SECTION 6(1) OF THE RTI ACT, 2005"
        prayers = [
            f"1. Certified true copy of all official files, notings, administrative sanction orders, and milestone approvals concerning {template['domain_name']} in {city}.",
            f"2. Under Section 2(j)(i) read with Section 2(f), certified copies of all inspection records, measurement books, and third-party audit reports pertaining to {ref_no}.",
            f"3. Details of all public funds sanctioned, disbursed, and delay penalty notices issued to date under contract terms.",
            f"4. Name, designation, and official contact details of the dealing officer(s) responsible for the file movement within the Citizen Charter timeline."
        ]
        statutory_warning = "MANDATORY TIME LIMIT: Under Section 7(1) of the RTI Act, 2005, the CPIO/SPIO is legally bound to provide the requested information within thirty (30) days. In the event of deliberate delay or refusal, personal penalty of Rs. 250 per day up to Rs. 25,000 shall be pursued under Section 20(1)."
    else:
        title_header = f"FORMAL LEGAL NOTICE & STATUTORY GRIEVANCE PETITION UNDER CONSUMER PROTECTION ACT, 2019"
        prayers = [
            f"1. Immediate and unconditional provision of the demanded relief: {records_or_relief}.",
            f"2. Full refund of Rs. {financial_loss or '[Specified Amount]'} along with 18% per annum commercial interest from the date of accrual of the default till actual payment.",
            f"3. Compensation of Rs. 50,000/- on account of mental agony, severe harassment, and unfair trade practice / administrative negligence.",
            f"4. Litigation costs of Rs. 10,000/- incurred in serving this formal notice and preparing documentation."
        ]
        statutory_warning = "STATUTORY ESCALATION WARNING: You are hereby called upon to comply with the above demands within fifteen (15) calendar days from receipt of this notice, failing which appropriate proceedings under Section 35 of the Consumer Protection Act, 2019 shall be instituted before the competent Commission entirely at your risk as to costs and consequences."

    prayers_block = "\n".join(prayers)

    # 3. Assemble Full Systematic Draft
    draft_body = f"""{title_header}

TO:
The Public Information Officer / Competent Authority,
{authority},
{city}

SUBJECT: Formal Petition regarding {template['domain_name']} — Seeking {records_or_relief}.
STATUTORY BASIS: {statutory_act}

I. PARTICULARS OF THE APPLICANT / COMPLAINANT:
Name: {applicant_name}
Address / Locality: {city}
Contact: On Record / Cryptographic Token
Citizenship: Citizen of India (Art. 19(1)(a) & Sec. 3 RTI Act 2005)

II. SYSTEMATIC CHRONOLOGICAL STATEMENT OF FACTS:
{facts_block}

III. STATUTORY GROUNDS & VIOLATIONS:
(a) Violation of statutory service charter and administrative transparency obligations;
(b) Arbitrary withholding of rights and records without authority of law (Article 14 & Article 21, Constitution of India);
(c) Actionable under {statutory_act}.

IV. SPECIFIC DEMANDS & RELIEF PRAYED FOR:
The Applicant / Complainant hereby formally demands:
{prayers_block}

V. STATUTORY NOTICE & COMPLIANCE MANDATE:
{statutory_warning}

VI. VERIFICATION:
I hereby verify that the facts stated hereinabove are true and correct to the best of my knowledge and belief, and no material fact has been concealed.

Place: {city}
Date: {timeline}
Signature of the Applicant / Complainant"""

    # 4. Generate Lawyer-Ready Brief (Brief for Legal Counsel)
    lawyer_brief = f"""-------------------------------------------------------------------------
  CASE SUMMARY BRIEF - PREPARED FOR ADVOCATE / LEGAL COUNSEL REVIEW
-------------------------------------------------------------------------
1. CLIENT / COMPLAINANT    : {applicant_name}
2. OPPOSITE PARTY / DEPT   : {authority} ({city})
3. LEGAL NATURE OF CLAIM   : {template['domain_name']}
4. APPLICABLE STATUTES     : {statutory_act}
5. CAUSE OF ACTION ACCRUED : {timeline}
6. DISPUTE IDENTIFIER      : {ref_no}
7. FINANCIAL QUANTUM / LOSS: {('Rs. ' + financial_loss) if financial_loss else 'Substantive Non-Monetary / Rights Violation'}
8. RELIEF SOUGHT           : {records_or_relief}
9. KEY EVIDENCE REQUIRED   : Certified records, receipts, written communications, GD/ticket logs.
10. RECOMMENDED NEXT STEPS : If respondent fails to reply within statutory window, file Section 19(1) RTI Appeal or Section 35 Consumer Complaint before District Commission.
-------------------------------------------------------------------------"""

    return {
        "domain_name": template["domain_name"],
        "category": template["domain_name"],
        "likely_route": template["likely_route"],
        "target_authority": authority,
        "city": city,
        "statutory_act": statutory_act,
        "systematic_draft": draft_body,
        "lawyer_brief": lawyer_brief,
        "facts_block": facts_block,
        "answered_facts": answers
    }

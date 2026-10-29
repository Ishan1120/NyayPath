from dotenv import load_dotenv
load_dotenv()
import os
import json
import re
import logging
from typing import Dict, Any, Optional
from groq import Groq
try:
    from .prompts import CLASSIFIER_SYSTEM_PROMPT, DYNAMIC_FORM_SCHEMAS
    from .facts_engine import facts_triage
except ImportError:
    from prompts import CLASSIFIER_SYSTEM_PROMPT, DYNAMIC_FORM_SCHEMAS
    from facts_engine import facts_triage

logger = logging.getLogger(__name__)

# =====================================================================
# STEP 2: CIC PRECEDENT KNOWLEDGE BASE & PIO RESPONSE ANALYZER
# =====================================================================

CIC_PRECEDENT_KNOWLEDGE: Dict[str, Dict[str, str]] = {
    "8(1)(j)": {
        "title": "Personal Information Exemption Overturned",
        "precedent": "CIC Landmark Precedent (Paramveer Singh v. CPIO): Blanket reliance on 8(1)(j) fails if public interest is demonstrated. Crucially, the Section 8(1) proviso mandates: 'Information which cannot be denied to the Parliament or a State Legislature shall not be denied to any person.'",
        "grounds": "Request details on public fund utilization, official duties, or administrative actions—these are explicitly non-personal."
    },
    "8(1)(h)": {
        "title": "Obstruction of Investigation / Prosecution",
        "precedent": "Delhi High Court (Bhagat Singh v. CIC): Mere existence of an ongoing investigation is insufficient to deny information under 8(1)(h). The PIO must explicitly demonstrate HOW disclosure would physically impede or obstruct the investigation.",
        "grounds": "Demand specific proof showing how releasing documents causes actual prejudice to the ongoing inquiry."
    },
    "8(1)(e)": {
        "title": "Fiduciary Relationship Claim",
        "precedent": "Supreme Court (CBSE v. Aditya Bandopadhyay): Public authorities holding official records do not automatically stand in a fiduciary capacity toward public servants or contractors.",
        "grounds": "Commercial contracts and government project disbursements fall under public scrutiny, negating private fiduciary privilege."
    },
    "8(1)(a)": {
        "title": "Sovereignty & Security Exemption",
        "precedent": "CIC Ruling (R.K. Jain v. MEA): Exemption 8(1)(a) cannot be invoked routinely for general administrative or policy files that do not expose state defense secrets.",
        "grounds": "Request severance under Section 10 to extract non-sensitive administrative data while redacting sensitive security logs."
    },
    "6(3)": {
        "title": "Transfer of Application",
        "precedent": "Section 6(3) Mandate: The PIO MUST transfer the application within 5 days of receipt and inform the applicant immediately in writing.",
        "grounds": "If transferred after 5 days, the delay period counts toward Section 20 financial penalties against the transferring PIO."
    }
}

PIO_ANALYZER_SYSTEM_PROMPT = """
You are an expert legal parser for Indian Right to Information (RTI) Act Public Information Officer (PIO) replies.
Analyze the PIO response text provided by the user and extract key structured outcomes.

You MUST respond strictly with a single valid JSON object containing these keys:
{
  "classification": "FULL_DISCLOSURE" | "PARTIAL_DISCLOSURE" | "DENIED" | "TRANSFERRED",
  "exemption_cited": "8(1)(j)" | "8(1)(h)" | "8(1)(e)" | "8(1)(a)" | "6(3)" | "NONE" | "OTHER",
  "summary": "Concise 1-2 sentence summary of PIO response."
}
Do NOT include markdown code fences or conversational prose.
"""

def extract_json_from_text(text: str) -> dict:
    """Safely extracts JSON from a string even if it's wrapped in markdown or conversational text."""
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', text, re.DOTALL)
        if json_match:
            try: return json.loads(json_match.group(1))
            except json.JSONDecodeError: pass
        json_match = re.search(r'(\{.*\})', text, re.DOTALL)
        if json_match:
            try: return json.loads(json_match.group(1))
            except json.JSONDecodeError: pass
        return {}

def analyze_pio_response(pio_text: str) -> Dict[str, Any]:
    """
    Parses unstructured PIO reply text into structured status, extracts cited Section 8 clauses,
    and maps them to CIC precedent counter-arguments.
    """
    if not pio_text or not pio_text.strip():
        return {
            "classification": "DENIED",
            "exemption_cited": "DEEMED_REFUSAL",
            "summary": "No response received within statutory 30-day timeline (Deemed Refusal under Section 7(2)).",
            "legal_counter": "Under Section 7(2), failure to issue a decision within 30 days is deemed refusal. Section 19(1) First Appeal is immediately maintainable with zero fee.",
            "precedent_title": "Deemed Refusal Under Section 7(2)",
            "appeal_grounds": "The PIO failed to respond within the statutory 30-day period mandated under Section 7(1)."
        }

    api_key = os.environ.get("GROQ_API_KEY")
    parsed_json = {}

    if api_key:
        try:
            client = Groq(api_key=api_key)
            chat_completion = client.chat.completions.create(
                messages=[
                    {"role": "system", "content": PIO_ANALYZER_SYSTEM_PROMPT},
                    {"role": "user", "content": f"PIO Response Text:\n{pio_text}"}
                ],
                model="llama-3.3-70b-versatile",
                temperature=0.1,
            )
            raw_content = chat_completion.choices[0].message.content.strip()
            parsed_json = extract_json_from_text(raw_content)
        except Exception as e:
            logger.error(f"[PIO Analyzer] Groq execution failed: {e}")

    if not parsed_json:
        parsed_json = _fallback_pio_parser(pio_text)

    raw_exemption = parsed_json.get("exemption_cited", "NONE")
    
    # Clean up the exemption string if the LLM hallucinated words like "Section"
    clean_exemption = raw_exemption.replace("Section ", "").replace("Sec ", "").replace(" ", "").strip()
    
    precedent_info = CIC_PRECEDENT_KNOWLEDGE.get(clean_exemption)
    
    if not precedent_info:
        # Try substring matching if exact match fails
        for key, val in CIC_PRECEDENT_KNOWLEDGE.items():
            if key in clean_exemption:
                precedent_info = val
                clean_exemption = key
                break
        
        # Ultimate fallback if no clause is matched but it was denied
        if not precedent_info:
            precedent_info = {
                "title": "General Deficiency / Evasive Reply", 
                "precedent": "As per Section 7(9) and CIC guidelines, exemptions must be strictly justified. General denial without specifying a Section 8/9 clause is unlawful.", 
                "grounds": "The PIO provided an evasive and incomplete reply without citing a valid statutory exemption."
            }

    return {
        "classification": parsed_json.get("classification", "PARTIAL_DISCLOSURE"),
        "exemption_cited": clean_exemption,
        "summary": parsed_json.get("summary", "PIO response analyzed."),
        "legal_counter": precedent_info.get("precedent", ""),
        "precedent_title": precedent_info.get("title", ""),
        "appeal_grounds": precedent_info.get("grounds", "")
    }

def _fallback_pio_parser(text: str) -> Dict[str, str]:
    lower = text.lower()
    exemption = "NONE"
    classification = "PARTIAL_DISCLOSURE"

    if "8(1)(j)" in lower or "personal" in lower or "third party" in lower:
        exemption = "8(1)(j)"
        classification = "DENIED"
    elif "8(1)(h)" in lower or "investigation" in lower or "prosecution" in lower:
        exemption = "8(1)(h)"
        classification = "DENIED"
    elif "8(1)(e)" in lower or "fiduciary" in lower:
        exemption = "8(1)(e)"
        classification = "DENIED"
    elif "transferred" in lower or "section 6(3)" in lower:
        exemption = "6(3)"
        classification = "TRANSFERRED"
    elif "denied" in lower or "rejected" in lower:
        classification = "DENIED"
    elif "attached" in lower or "provided herewith" in lower:
        classification = "FULL_DISCLOSURE"

    return {
        "classification": classification,
        "exemption_cited": exemption,
        "summary": f"Automated scan detected response status: {classification} (Clause: {exemption})."
    }


# =====================================================================
# INTAKE ROUTE CLASSIFIER
# =====================================================================

class RouteClassifier:
    def __init__(self):
        api_key = os.environ.get("GROQ_API_KEY")
        if api_key and api_key.startswith("gsk_"):
            try:
                self.client = Groq(api_key=api_key)
            except Exception as e:
                logger.error(f"[RouteClassifier] Failed to initialize Groq client: {e}")
                self.client = None
        else:
            self.client = None

    def _rule_based_fallback(self, text: str) -> Dict[str, Any]:
        lower = text.strip().lower()
        
        if len(lower) < 4 or not any(char.isalnum() for char in lower):
            return {
                "route": "Other",
                "sub_category": "Irrelevant",
                "confidence": 0.95,
                "reasoning": "The provided input is too short or unstructured to accurately classify legally.",
                "specific_advice": "Please describe your civic issue, public records request, or campus complaint in more detail.",
                "form_schema": [],
                "extracted_data": {}
            }

        # Explicit non-civic / general knowledge / casual prompts
        other_terms = [
            "poem", "movie", "plot", "interstellar", "tourist", "places to visit",
            "python", "function", "sort", "algorithm", "code", "workout", "muscle",
            "cricket", "world cup", "database", "sql", "nosql", "music", "quantum",
            "cookies", "cookie", "recipe", "bake", "baking", "joke", "funny joke"
        ]
        other_pattern = r"(?<!\w)(" + "|".join(re.escape(t) for t in other_terms) + r")(?!\w)"
        if re.search(other_pattern, lower):
            return {
                "route": "Other",
                "sub_category": "Out of Scope",
                "confidence": 0.95,
                "reasoning": "The query is an educational, technical, or general knowledge request rather than a civic or legal grievance.",
                "specific_advice": "NyayPath is designed for filing RTI applications, citizen grievances, consumer notices, and campus proctorial complaints.",
                "form_schema": [],
                "extracted_data": {}
            }

        # ─── BILINGUAL & MULTI-DOMAIN RECOGNITION (English, Hindi, Hinglish) ───

        # 1. Campus Ragging & Student Safety (UGC 2009 Anti-Ragging Regulations)
        campus_ragging_terms = [
            "ragging", "ragged", "seniors", "hostel", "warden", "proctor", "anti-ragging",
            "bullying", "intimidation", "physical abuse", "campus discipline", "senior student",
            "रैगिंग", "रैगिंग की शिकायत", "हॉस्टल", "सीनियर्स", "कॉलेज", "विश्वविद्यालय", "छात्र", "छात्रा",
            "वार्डन", "प्रॉक्टर", "प्राचार्य", "मारपीट", "धमकी", "परेशान", "गाली", "उत्पीड़न", "प्रताड़ना",
            "marpeet", "dhamki", "pareshan kar rahe", "hostel me ragging", "anti ragging", "senior tang"
        ]

        # 2. RTI / Public Records & Statutory Transparency (RTI Act 2005)
        rti_terms = [
            "rti", "tender", "inspection", "records", "sanction order", "copy of", "copies of", "budget",
            "expenditure", "sanctioned", "funds", "file notations", "file notings", "muster roll", "logbook",
            "beneficiaries", "vacancies", "recruitment exams", "building plan", "contractor", "public authority",
            "measurement book", "certified copy", "certified copies",
            "आरटीआई", "सूचना का अधिकार", "टेंडर", "टैण्डर", "ठेकेदार", "सरकारी काम", "रिकॉर्ड", "दस्तावेज",
            "दस्तावेज़", "प्रमाणित प्रति", "निरीक्षण", "बजट", "खर्च", "फंड", "मंजूरी आदेश", "फाइल नोटिंग",
            "सूचना", "पीडब्ल्यूडी", "नगर निगम", "सड़क निर्माण", "अंकतालिका की प्रति", "उत्तर पुस्तिका",
            "suchna ka adhikar", "sarkari kam", "tender copy", "records maangna", "certified copy", "file noting"
        ]

        # 3. General Grievance / Consumer Disputes / Service Deficiency
        grievance_terms = [
            "pension", "delayed", "withheld", "refund", "deposit", "tenant", "landlord", "defective",
            "salary", "complaint", "fraud", "consumer", "electricity", "bill", "meter", "hospital",
            "doctor", "police", "harassment", "fir", "bank", "service", "insurance", "claim", "damage",
            "flipkart", "laptop", "brick", "return", "customer support", "fired", "gratuity", "notice period",
            "builder", "possession", "rera", "airline", "airlines", "flight", "overcharged", "cghs",
            "helpline", "potholes", "gearbox", "service center", "telecom", "value-added service",
            "water supply", "drainage", "sewage", "ayushman", "pm-jay", "ration", "pds",
            "शिकायत", "परेशान", "रिफंड", "पेंशन", "पीएफ", "मकान मालिक", "किराया", "अमानत राशि", "सिक्योरिटी डिपॉजिट",
            "खराब सामान", "दुकानदार", "धोखाधड़ी", "बिजली", "मीटर", "पानी", "सीवर", "अस्पताल", "आयुष्मान",
            "डॉक्टर", "इलाज", "पुलिस", "थाना", "एफआईआर", "रिश्वत", "घूस", "वेतन", "सैलरी", "नौकरी", "गड्ढे",
            "टूटी सड़क", "जमीन", "दाखिल खारिज", "अवैध कब्जा",
            "shikayat", "pareshan", "refund", "pension", "makan malik", "kiraya", "kharab saman", "bijli bill",
            "paani", "police thana", "fir darj", "hospital", "ayushman card", "gaddhe", "sadak"
        ]

        def count_hits(terms):
            total = 0
            for t in terms:
                if " " in t or any(ord(c) > 127 for c in t):
                    if t in lower:
                        total += 1
                else:
                    pattern = r"(?<!\w)" + re.escape(t) + r"(?!\w)"
                    if re.search(pattern, lower):
                        total += 1
            return total

        ragging_score = count_hits(campus_ragging_terms)
        rti_score = count_hits(rti_terms)
        grievance_score = count_hits(grievance_terms)

        # Immediate Campus Anti-Ragging Priority Route
        if ragging_score > 0:
            return {
                "route": "Rights/Grievance",
                "sub_category": "Campus Anti-Ragging & Proctorial Redressal (UGC Regulations 2009)",
                "confidence": 0.96,
                "reasoning": "Identified serious campus safety / ragging complaint governed by UGC Anti-Ragging Regulations 2009 and Supreme Court directives. Warrants immediate proctorial intervention, confidential inquiry, and FIR escalation.",
                "specific_advice": "Under UGC 2009 Regulations, the Head of Institution is legally mandated to initiate disciplinary action and file a police FIR within 24 hours.",
                "form_schema": DYNAMIC_FORM_SCHEMAS.get("Rights/Grievance", []),
                "extracted_data": {
                    "user_problem": text,
                    "target_department": "Chief Proctor / Head of Institution & Anti-Ragging Committee",
                    "desired_relief": "Immediate institutional inquiry under UGC Anti-Ragging Regulations 2009, physical security protection, and filing of police FIR under BNS/IPC"
                }
            }

        # RTI Priority Route
        if rti_score > 0 and rti_score >= grievance_score:
            return {
                "route": "RTI",
                "sub_category": "Public Records & Statutory Transparency (RTI Act 2005)",
                "confidence": 0.90,
                "reasoning": "User is seeking official records, tender documents, inspection logs, or administrative transparency from a public authority.",
                "specific_advice": "",
                "form_schema": DYNAMIC_FORM_SCHEMAS.get("RTI", []),
                "extracted_data": {"user_problem": text}
            }

        # Grievance / Consumer / Service Deficiency Route
        if grievance_score > 0:
            return {
                "route": "Rights/Grievance",
                "sub_category": "Citizen Grievance & Statutory Redressal",
                "confidence": 0.88,
                "reasoning": "User is seeking dispute resolution, refund, compensation, or administrative remedy for deficiency of service or rights violation.",
                "specific_advice": "",
                "form_schema": DYNAMIC_FORM_SCHEMAS.get("Rights/Grievance", []),
                "extracted_data": {"user_problem": text}
            }

        # Intelligent Default for any genuine civic / legal statement
        # (NEVER falsely label genuine citizen distress as 'Out of Scope'!)
        return {
            "route": "Rights/Grievance",
            "sub_category": "Public Administration & Citizen Redressal",
            "confidence": 0.85,
            "reasoning": "The citizen statement indicates civic or administrative distress requiring formal representation under citizen grievance redressal mechanisms.",
            "specific_advice": "",
            "form_schema": DYNAMIC_FORM_SCHEMAS.get("Rights/Grievance", []),
            "extracted_data": {
                "user_problem": text,
                "target_department": "Concerned Administrative Authority",
                "desired_relief": "Formal investigation, administrative remedy, and compliance with statutory service charter"
            }
        }

    def classify(self, user_text: str, language: str = "English") -> Dict[str, Any]:
        if not user_text or not user_text.strip():
            return {
                "route": "Other", "sub_category": "Empty", "confidence": 1.0,
                "reasoning": "No text provided.", "specific_advice": "Please provide a valid problem statement.",
                "form_schema": [], "extracted_data": {}, "facts_analysis": None
            }

        result: Optional[Dict[str, Any]] = None

        if self.client:
            try:
                system_msg = (
                    f"{CLASSIFIER_SYSTEM_PROMPT}\n\n"
                    f"CRITICAL LANGUAGE INSTRUCTION:\n"
                    f"The user has selected '{language}'. ALL text values in your JSON MUST be written in {language}.\n"
                    f"If '{language}' is 'Hinglish', write conversational Hindi using the English alphabet. "
                )
                
                response = self.client.chat.completions.create(
                    model="llama-3.3-70b-versatile",
                    messages=[
                        {"role": "system", "content": system_msg},
                        {"role": "user", "content": user_text}
                    ],
                    temperature=0.0,
                    response_format={"type": "json_object"}
                )

                content = response.choices[0].message.content.strip()
                result = json.loads(content)

                route = result.get("route", "Other")
                if route not in ["RTI", "Rights/Grievance", "Other"]: route = "Other"
                result["route"] = route
                result["form_schema"] = DYNAMIC_FORM_SCHEMAS.get(route, [])
                result["extracted_data"] = result.get("extracted_data", {})
            except Exception as e:
                print(f"[Classifier Fallback] API failed ({e}).")
                result = None

        if result is None:
            result = self._rule_based_fallback(user_text)

        # F.A.C.T.S. Legal Triage Engine — attached to every classification path
        try:
            result["facts_analysis"] = facts_triage(
                route=result.get("route", "Other"),
                user_problem=user_text,
                form_data={},
                extracted_facts=result.get("extracted_data", {}),
            )
        except Exception as e:
            print(f"[FACTS Triage] failed ({e}).")
            result["facts_analysis"] = None

        return result

classifier = RouteClassifier()
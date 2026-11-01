from dotenv import load_dotenv
load_dotenv()
import os
import io
import json
import email
import logging
from datetime import datetime, timedelta, timezone
from fastapi import FastAPI, HTTPException, File, UploadFile, Form, status
from starlette.requests import Request
from starlette.responses import Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional

import sys
from pathlib import Path

_api_dir = Path(__file__).resolve().parent
_root_dir = _api_dir.parent
for p in [str(_api_dir), str(_root_dir)]:
    if p not in sys.path:
        sys.path.insert(0, p)

try:
    from .precedent_pdf_generator import generate_precedent_case_brief_pdf
    from .precedent_library import LANDMARK_PRECEDENTS
    from .case_manager import case_manager
    from .clarifying_engine import recognize_and_generate_questions, synthesize_systematic_draft
    from .classifier import classifier, analyze_pio_response
    from .outcome_predictor import outcome_engine
    from .department_resolver import department_resolver
    from .rti_pdf_generator import generate_rti_pdf, generate_generic_pdf
    from .appeal_pdf_generator import generate_first_appeal_pdf
    from .grievance_resolver import grievance_resolver
    from .intake_chat import router as intake_router
    from .facts_engine import calculate_readiness_score, facts_triage
    from .social_complaint_generator import social_complaint_generator
    from .watchdog_engine import (
        evaluate_watchdog_state,
        run_scheduled_watchdog,
        calculate_deadlines,
        calculate_section_20_penalty
    )
    from .precedent_library import precedent_engine
    from .court_news import get_court_news
    from .campus_proctor import (
        campus_proctor_manager,
        StudentGrievanceSubmit,
        ProctorUpdateStatus,
        StudentTrackingRequest,
        CaseCommitteeAssignRequest,
        CaseCommitteeRevokeRequest
    )
    from .document_access import DocumentAccessManager
    from .citizen_workspace import (
        citizen_workspace_manager,
        CaseFilingRequest,
        CaseLifecycleActionRequest,
        PublicCaseTrackingRequest
    )
    from .notifications import notification_manager, MarkReadRequest
    from .citations import resolve_citations_for_query
    from .rate_limiter import enforce_rate_limit, record_rate_limit_failure, reset_rate_limit
    from .auth import (
        AuthUser,
        UserRole,
        LoginRequest,
        authenticate_officer,
        authenticate_institutional_user,
        authenticate_citizen,
        create_access_token,
        get_current_user_optional,
        get_current_authenticated_user
    )
except ImportError:
    from precedent_pdf_generator import generate_precedent_case_brief_pdf
    from precedent_library import LANDMARK_PRECEDENTS
    from case_manager import case_manager
    from clarifying_engine import recognize_and_generate_questions, synthesize_systematic_draft
    from classifier import classifier, analyze_pio_response
    from outcome_predictor import outcome_engine
    from department_resolver import department_resolver
    from rti_pdf_generator import generate_rti_pdf, generate_generic_pdf
    from appeal_pdf_generator import generate_first_appeal_pdf
    from grievance_resolver import grievance_resolver
    from intake_chat import router as intake_router
    from facts_engine import calculate_readiness_score, facts_triage
    from social_complaint_generator import social_complaint_generator
    from watchdog_engine import (
        evaluate_watchdog_state,
        run_scheduled_watchdog,
        calculate_deadlines,
        calculate_section_20_penalty
    )
    from precedent_library import precedent_engine
    from court_news import get_court_news
    from campus_proctor import (
        campus_proctor_manager,
        StudentGrievanceSubmit,
        ProctorUpdateStatus,
        StudentTrackingRequest,
        CaseCommitteeAssignRequest,
        CaseCommitteeRevokeRequest
    )
    from document_access import DocumentAccessManager
    from citizen_workspace import (
        citizen_workspace_manager,
        CaseFilingRequest,
        CaseLifecycleActionRequest,
        PublicCaseTrackingRequest
    )
    from notifications import notification_manager, MarkReadRequest
    from citations import resolve_citations_for_query
    from rate_limiter import enforce_rate_limit, record_rate_limit_failure, reset_rate_limit
    from auth import (
        AuthUser,
        UserRole,
        LoginRequest,
        authenticate_officer,
        authenticate_institutional_user,
        authenticate_citizen,
        create_access_token,
        get_current_user_optional,
        get_current_authenticated_user
    )

logger = logging.getLogger(__name__)

app = FastAPI(title="NyayPath AI API", version="2.6")
document_access_manager = DocumentAccessManager()

# =====================================================================
# CORS Configuration (Phase 1.3.4 & Phase 3 — restricted from wildcard)
# Origins: Next.js local dev + explicitly configured frontend origins.
# No wildcard allowed in any environment.
# allow_credentials=False: tokens are sent in Authorization headers,
#   not as cookies, so SameSite credential flow is not required.
# =====================================================================
_CORS_ORIGINS = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
]
_env_origins = [o.strip() for o in os.environ.get("ALLOWED_ORIGINS", "").split(",") if o.strip()]
_frontend_env = os.environ.get("FRONTEND_URL", "").strip()
if _frontend_env and _frontend_env not in _CORS_ORIGINS and _frontend_env != "*":
    _CORS_ORIGINS.append(_frontend_env)
for _o in _env_origins:
    if _o != "*" and _o not in _CORS_ORIGINS:
        _CORS_ORIGINS.append(_o)

def _is_production() -> bool:
    env = os.environ.get("ENVIRONMENT", "").lower()
    node_env = os.environ.get("NODE_ENV", "").lower()
    return env in ("production", "prod") or node_env in ("production", "prod")

app.add_middleware(
    CORSMiddleware,
    allow_origins=_CORS_ORIGINS,
    allow_credentials=False,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Requested-With", "x-proctor-token"],
)

app.include_router(intake_router)


class ClarifyingQuestionsRequest(BaseModel):
    problem_text: str = Field(..., max_length=10000)
    language: Optional[str] = "English"

class SynthesizeDraftRequest(BaseModel):
    case_id: Optional[str] = None
    problem_text: str = Field(..., max_length=10000)
    answers: Dict[str, str] = {}
    language: Optional[str] = "English"
    route: Optional[str] = "RTI"
    applicant_name: Optional[str] = "The Citizen / Complainant"

class GeneratePDFRequest(BaseModel):
    title: Optional[str] = "Document"
    content: Optional[str] = ""

class CaseInitResponse(BaseModel):
    case_id: str
    message: str

class ClassifyRequest(BaseModel):
    case_id: Optional[str] = None
    problem_text: Optional[str] = ""
    language: Optional[str] = "English"

class FormSubmitRequest(BaseModel):
    case_id: Optional[str] = None
    form_data: Optional[Dict[str, Any]] = None

class RTIPredictRequest(BaseModel):
    case_id: Optional[str] = None
    draft_text: Optional[str] = None

class RTIImproveRequest(BaseModel):
    case_id: Optional[str] = None

class DepartmentResolveRequest(BaseModel):
    case_id: Optional[str] = None
    location: Optional[str] = None

class GrievanceGenerateRequest(BaseModel):
    case_id: Optional[str] = None
    form_data: Optional[Any] = None
    user_problem: Optional[str] = ""
    language: Optional[str] = "English"
    files: Optional[List[Dict[str, Any]]] = None

class PIOAnalysisRequest(BaseModel):
    case_id: str
    pio_text: Optional[str] = ""

class FirstAppealRequest(BaseModel):
    appellant_name: str
    appellant_address: str
    first_appellate_authority: str
    pio_address: str
    rti_registration_no: str
    rti_filing_date: str
    pio_reply_date: Optional[str] = None
    grounds_of_appeal: str
    legal_precedent: str

class ReadinessRequest(BaseModel):
    case_id: Optional[str] = None
    route: Optional[str] = None
    form_data: Optional[Dict[str, Any]] = None

class TranslateRequest(BaseModel):
    text: str
    target_language: str

class SocialGenerateRequest(BaseModel):
    case_id: Optional[str] = None
    user_problem: Optional[str] = ""
    language: Optional[str] = "English"
    form_data: Optional[Dict[str, Any]] = None

class WatchdogStartRequest(BaseModel):
    case_id: str
    life_liberty: Optional[bool] = False

class WatchdogResponseRequest(BaseModel):
    case_id: str
    pio_text: Optional[str] = ""
    response_received_at: Optional[str] = None

class WatchdogSimulateRequest(BaseModel):
    case_id: str
    scenario: str  # "today", "7_days", "3_days", "due_today", "overdue_10", "overdue_100", "response_ontime", "response_late", "custom", "reset"
    simulated_days_ago: Optional[int] = None

@app.get("/")
def health_check():
    return {
        "status": "ok", 
        "system": "NyayPath Backend Active",
        "database_connected": getattr(case_manager, "is_connected", True)
    }

@app.post("/api/case/init", response_model=CaseInitResponse)
def init_case():
    new_case_id = case_manager.create_case()
    return CaseInitResponse(case_id=new_case_id, message="Save this ID safely.")

@app.post("/api/translate")
def translate_text(payload: TranslateRequest):
    translated = outcome_engine.translate_document(payload.text, payload.target_language)
    return {"translated_text": translated}

@app.post("/api/transcribe")
async def transcribe_audio(
    audio_file: UploadFile = File(...), 
    language: str = Form("English")
):
    try:
        file_bytes = await audio_file.read()
        filename = audio_file.filename or "recording.webm"
        
        if not file_bytes:
            return {"text": "", "transcription": ""}
            
        client = classifier.client
        if not client:
            return {"text": "Voice input received. Please review your text.", "transcription": "Voice input received."}
            
        if language == "English":
            text = client.audio.transcriptions.create(
                file=(filename, file_bytes),
                model="whisper-large-v3",
                response_format="json",
                language="en"
            ).text
        else:
            raw_text = client.audio.transcriptions.create(
                file=(filename, file_bytes),
                model="whisper-large-v3",
                prompt="The user is speaking Hinglish or an Indian language. Transcribe accurately.",
                response_format="json"
            ).text
            
            resp = client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[
                    {"role": "system", "content": "You are a translator. Translate the following text into 'Hinglish' (conversational Hindi written using ONLY the English alphabet). Under NO circumstances should you use Devanagari script. Do not add commentary."},
                    {"role": "user", "content": raw_text}
                ],
                temperature=0.0
            )
            text = resp.choices[0].message.content.strip()

        return {"text": text, "transcription": text}
    except Exception as e:
        print(f"Transcription error: {e}")
        return {"text": "failed", "transcription": "failed"}

@app.post("/api/case/classify")
def classify_problem(payload: ClassifyRequest):
    case_id = payload.case_id or case_manager.create_case()
    case = case_manager.get_case(case_id) or {}

    problem_text = payload.problem_text or case.get("user_problem", "")
    language = payload.language or case.get("language", "English")

    result = classifier.classify(problem_text, language)
    
    case_manager.update_case(case_id, {
        "status": "classified",
        "route": result["route"],
        "sub_category": result["sub_category"],
        "user_problem": problem_text,
        "form_schema": result["form_schema"],
        "extracted_facts": result.get("extracted_data", {}),
        "facts_analysis": result.get("facts_analysis"),
        "language": language
    })

    return {**result, "case_id": case_id}

@app.post("/api/case/readiness")
def compute_readiness(payload: ReadinessRequest):
    case = case_manager.get_case(payload.case_id) if payload.case_id else None
    route = payload.route or (case.get("route") if case else None) or "RTI"
    form_data = payload.form_data or (case.get("form_data") if case else {}) or {}
    return calculate_readiness_score(form_data, route)

@app.post("/api/rti/generate")
def generate_rti(payload: FormSubmitRequest):
    case_id = payload.case_id or case_manager.create_case()
    case = case_manager.get_case(case_id) or {}

    user_problem = case.get("user_problem", "Public Records & Inspection Inquiry")
    language = case.get("language", "English")
    form_data = payload.form_data or case.get("form_data", {})
    
    draft = outcome_engine.generate_initial_rti(form_data, user_problem, language)

    case_manager.update_case(case_id, {
        "status": "rti_drafted",
        "form_data": form_data,
        "initial_draft": draft
    })
    return {"case_id": case_id, "initial_draft": draft}

@app.post("/api/rti/predict")
def predict_rti(payload: RTIPredictRequest):
    case_id = payload.case_id or case_manager.create_case()
    case = case_manager.get_case(case_id) or {}

    draft_text = payload.draft_text or case.get("initial_draft") or case.get("improved_draft") or "Application under Section 6(1) of RTI Act 2005"
    language = case.get("language", "English")
    
    prediction_result = outcome_engine.predict_rti_outcome(draft_text, language)
    case_manager.update_case(case_id, {
        "status": "rti_predicted",
        "prediction_result": prediction_result
    })
    return {"case_id": case_id, **prediction_result}

@app.post("/api/rti/improve")
def improve_rti(payload: RTIImproveRequest):
    case_id = payload.case_id or case_manager.create_case()
    case = case_manager.get_case(case_id) or {}

    initial_draft = case.get("initial_draft") or case.get("improved_draft", "Application under Section 6(1) of RTI Act 2005")
    pred = case.get("prediction_result", {})
    risks = pred.get("detected_risks", [])
    suggestions = pred.get("improvement_suggestions", [])
    language = case.get("language", "English")

    improved_result = outcome_engine.generate_improved_rti(initial_draft, risks, suggestions, language)
    case_manager.update_case(case_id, {
        "status": "rti_completed",
        "improved_draft": improved_result.get("improved_draft"),
        "filing_instructions": improved_result.get("filing_instructions")
    })
    return {"case_id": case_id, **improved_result}

@app.post("/api/rti/resolve-department")
def resolve_department(payload: DepartmentResolveRequest):
    case_id = payload.case_id or case_manager.create_case()
    case = case_manager.get_case(case_id) or {}

    user_problem = case.get("user_problem", "Public Authority Records Request")
    extracted_facts = {**case.get("form_data", {}), **case.get("extracted_facts", {})}
    location = payload.location or extracted_facts.get("applicant_city") or extracted_facts.get("applicant_state", "")
    language = case.get("language", "English")

    dept_info = department_resolver.resolve("RTI", user_problem, location, extracted_facts, language)
    case_manager.update_case(case_id, {"department_info": dept_info})
    return {"case_id": case_id, **dept_info}

@app.get("/api/rti/pdf/{case_id}")
def download_rti_pdf(case_id: str):
    case = case_manager.get_case(case_id)
    if not case:
        raise HTTPException(status_code=404, detail="Case ID not found.")

    draft_text = (
        case.get("improved_draft") or 
        case.get("initial_draft") or 
        case.get("grievance_pack", {}).get("demand_notice_draft") or
        case.get("user_problem", "")
    )
    dept_info = case.get("department_info") or {}
    form_data = case.get("form_data", {})
    applicant_details = {
        "name": form_data.get("applicant_name", "[Applicant Name]"),
        "address": form_data.get("applicant_address", ""),
        "contact": form_data.get("applicant_contact", ""),
        "place": form_data.get("applicant_city", ""),
        "date": "",
    }

    pdf_bytes = generate_rti_pdf(applicant_details, dept_info, draft_text)
    return StreamingResponse(
        io.BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename={case_id}_Document.pdf"}
    )

@app.post("/api/analyze_pio_backend")
def analyze_pio_backend_endpoint(payload: PIOAnalysisRequest):
    try:
        clean_id = payload.case_id.strip().upper()
        analysis = analyze_pio_response(payload.pio_text or "")
        analysis["case_id"] = clean_id

        case = case_manager.get_case(clean_id)
        if case:
            case["pio_response_text"] = payload.pio_text
            if not case.get("response_received_at"):
                case["response_received_at"] = datetime.now(timezone.utc).isoformat()
            case["pio_response_date"] = case["response_received_at"]

            language = case.get("language", "English")
            draft = outcome_engine.generate_first_appeal(case, analysis, language)

            case["exemption_cited"] = analysis.get("exemption_cited")
            case["legal_counter"] = analysis.get("legal_counter")
            case["precedent_title"] = analysis.get("precedent_title")
            case["status"] = "pio_analyzed"
            case["first_appeal_draft"] = draft

            # Run deterministic watchdog evaluation
            evaluated = evaluate_watchdog_state(case)
            case_manager.update_case(clean_id, evaluated)

        return analysis
    except Exception as e:
        logger.error(f"Error in /analyze_pio_backend: {e}")
        raise HTTPException(status_code=500, detail="Failed to analyze PIO response")

@app.post("/generate_appeal_pdf")
@app.post("/api/generate_appeal_pdf")
def generate_appeal_pdf_endpoint(payload: FirstAppealRequest):
    try:
        pdf_bytes = generate_first_appeal_pdf(
            appellant_name=payload.appellant_name,
            appellant_address=payload.appellant_address,
            first_appellate_authority=payload.first_appellate_authority,
            pio_address=payload.pio_address,
            rti_registration_no=payload.rti_registration_no,
            rti_filing_date=payload.rti_filing_date,
            pio_reply_date=payload.pio_reply_date,
            grounds_of_appeal=payload.grounds_of_appeal,
            legal_precedent=payload.legal_precedent
        )

        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={
                "Content-Disposition": f'attachment; filename="First_Appeal_{payload.rti_registration_no}.pdf"'
            }
        )
    except Exception as e:
        logger.error(f"Error generating appeal PDF: {e}")
        raise HTTPException(status_code=500, detail="Failed to generate First Appeal PDF")

@app.post("/api/grievance/generate")
def generate_grievance(payload: GrievanceGenerateRequest):
    case_id = payload.case_id or case_manager.create_case()
    case = case_manager.get_case(case_id) or {}

    form_data = payload.form_data or case.get("form_data", {})
    if isinstance(form_data, str):
        try:
            parsed_form_data = json.loads(form_data)
        except Exception:
            parsed_form_data = {}
    else:
        parsed_form_data = form_data or {}

    user_problem = payload.user_problem or case.get("user_problem", "Citizen Grievance & Deficiency of Service")
    language = payload.language or case.get("language", "English")
    location = parsed_form_data.get("applicant_city", "")
    files_data = payload.files or []

    try:
        pack = grievance_resolver.analyze_proof_and_rights(
            user_problem=user_problem,
            location=location,
            form_data=parsed_form_data,
            files_data=files_data,
            language=language
        )
    except Exception as e:
        print(f"Grievance resolution fallback: {e}")
        pack = grievance_resolver._fallback()

    case_manager.update_case(case_id, {
        "status": "grievance_completed",
        "form_data": parsed_form_data,
        "grievance_pack": pack
    })

    return {"case_id": case_id, **pack}

@app.post("/api/generate-pdf")
def generate_generic_pdf_endpoint(payload: GeneratePDFRequest):
    pdf_bytes = generate_generic_pdf(payload.title, payload.content)
    return StreamingResponse(
        io.BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename=Document.pdf"}
    )

@app.post("/api/social/generate")
def generate_social_campaign(payload: SocialGenerateRequest):
    """
    GraphRAG-powered social media complaint generator.
    Produces Twitter thread, LinkedIn post, and WhatsApp broadcast
    tagged with verified ministry/authority handles.
    """
    case_id = payload.case_id or ""
    case = case_manager.get_case(case_id.strip().upper()) if case_id else {}

    user_problem = payload.user_problem or case.get("user_problem", "Civic grievance")
    language = payload.language or case.get("language", "English")
    form_data = payload.form_data or case.get("form_data", {})
    dept_info = case.get("department_info", {})

    result = social_complaint_generator.generate(
        user_problem=user_problem,
        form_data=form_data,
        department_info=dept_info,
        case_id=case_id,
        language=language
    )
    return {"case_id": case_id, **result}

# ----------------- WATCHDOG & SLA ENGINE ENDPOINTS -----------------

@app.post("/api/watchdog/start")
def start_watchdog(payload: WatchdogStartRequest):
    clean_id = payload.case_id.strip().upper()
    case = case_manager.get_case(clean_id)
    if not case:
        raise HTTPException(status_code=404, detail="Case ID not found.")
    
    case["watchdog_enabled"] = True
    if payload.life_liberty:
        case["life_liberty_flag"] = True
        
    evaluated_case = evaluate_watchdog_state(case)
    case_manager.update_case(clean_id, evaluated_case)
    
    return {
        "status": "success",
        "message": "NyayPath SLA Watchdog is now monitoring this case.",
        "case_id": clean_id,
        "watchdog_status": evaluated_case.get("watchdog_status"),
        "filing_date": evaluated_case.get("filing_date"),
        "response_due_date": evaluated_case.get("response_due_date"),
        "first_appeal_due_date": evaluated_case.get("first_appeal_due_date"),
        "days_remaining": evaluated_case.get("days_remaining"),
        "days_overdue": evaluated_case.get("days_overdue"),
        "section_20_penalty_inr": evaluated_case.get("section_20_penalty_inr")
    }

@app.get("/api/watchdog/{case_id}")
def get_watchdog_case(case_id: str):
    clean_id = case_id.strip().upper()
    case_data = case_manager.get_case(clean_id)
    if not case_data:
        raise HTTPException(status_code=404, detail="Case ID not found.")
    
    evaluated = evaluate_watchdog_state(case_data)
    case_manager.update_case(clean_id, evaluated)
    
    return {
        "case_id": clean_id,
        "watchdog_enabled": evaluated.get("watchdog_enabled", True),
        "watchdog_status": evaluated.get("watchdog_status", "ACTIVE"),
        "computed_status": evaluated.get("computed_status", "ACTIVE"),
        "filing_date": evaluated.get("filing_date"),
        "response_due_date": evaluated.get("response_due_date"),
        "first_appeal_due_date": evaluated.get("first_appeal_due_date"),
        "response_received_at": evaluated.get("response_received_at") or evaluated.get("pio_response_date"),
        "is_overdue": evaluated.get("is_overdue", False),
        "days_remaining": evaluated.get("days_remaining", 0),
        "days_overdue": evaluated.get("days_overdue", 0),
        "time_remaining_seconds": evaluated.get("time_remaining_seconds", 0),
        "section_20_penalty_inr": evaluated.get("section_20_penalty_inr", 0),
        "appeal_eligible": evaluated.get("appeal_eligible", False),
        "last_watchdog_check_at": evaluated.get("last_watchdog_check_at"),
        "last_watchdog_event": evaluated.get("last_watchdog_event"),
        "watchdog_events": evaluated.get("watchdog_events", []),
        "notification_state": evaluated.get("notification_state", {}),
        "pio_response_text": evaluated.get("pio_response_text", ""),
        "exemption_cited": evaluated.get("exemption_cited", ""),
        "legal_counter": evaluated.get("legal_counter", ""),
        "precedent_title": evaluated.get("precedent_title", ""),
        "first_appeal_draft": evaluated.get("first_appeal_draft", ""),
        "department_info": evaluated.get("department_info", {}),
        "form_data": evaluated.get("form_data", {}),
        "user_problem": evaluated.get("user_problem", ""),
        "data": evaluated
    }

@app.api_route("/api/watchdog/run", methods=["GET", "POST"])
def run_watchdog_cron(request: Request):
    cron_secret = os.environ.get("CRON_SECRET")
    if cron_secret:
        auth_header = request.headers.get("Authorization", "")
        custom_header = request.headers.get("x-vercel-cron-secret", "")
        if auth_header != f"Bearer {cron_secret}" and custom_header != cron_secret:
            raise HTTPException(status_code=401, detail="Unauthorized: Invalid Cron Secret")
            
    result = run_scheduled_watchdog(case_manager)
    return result

@app.post("/api/watchdog/response")
def record_watchdog_response_endpoint(payload: WatchdogResponseRequest):
    clean_id = payload.case_id.strip().upper()
    case = case_manager.get_case(clean_id)
    if not case:
        raise HTTPException(status_code=404, detail="Case ID not found.")
        
    received_dt = payload.response_received_at or datetime.now(timezone.utc).isoformat()
    case["response_received_at"] = received_dt
    case["pio_response_date"] = received_dt
    case["pio_response_text"] = payload.pio_text or ""
    
    # Analyze PIO response
    analysis = analyze_pio_response(payload.pio_text or "")
    case["exemption_cited"] = analysis.get("exemption_cited")
    case["legal_counter"] = analysis.get("legal_counter")
    case["precedent_title"] = analysis.get("precedent_title")
    case["status"] = "pio_analyzed"
    
    # Generate first appeal draft
    language = case.get("language", "English")
    first_appeal_draft = outcome_engine.generate_first_appeal(case, analysis, language)
    case["first_appeal_draft"] = first_appeal_draft
    
    # Re-evaluate watchdog state with response recorded
    evaluated = evaluate_watchdog_state(case)
    case_manager.update_case(clean_id, evaluated)
    
    return {
        "status": "success",
        "case_id": clean_id,
        "analysis": analysis,
        "watchdog_state": evaluated,
        "first_appeal_draft": first_appeal_draft
    }

@app.post("/api/watchdog/simulate")
def simulate_watchdog_scenario(payload: WatchdogSimulateRequest):
    clean_id = payload.case_id.strip().upper()
    case = case_manager.get_case(clean_id)
    if not case:
        raise HTTPException(status_code=404, detail="Case ID not found.")
        
    now = datetime.now(timezone.utc)
    scenario = payload.scenario.lower()
    
    if scenario == "today":
        # Filed today (30 days remaining)
        filing_dt = now
        case["filing_date"] = filing_dt.isoformat()
        case["response_due_date"] = (filing_dt + timedelta(days=30)).isoformat()
        case["first_appeal_due_date"] = (filing_dt + timedelta(days=60)).isoformat()
        case["response_received_at"] = None
        case["pio_response_date"] = None
        case["pio_response_text"] = None
        case["status"] = "FILED"
    elif scenario == "7_days":
        # 23 days ago -> 7 days remaining
        filing_dt = now - timedelta(days=23)
        case["filing_date"] = filing_dt.isoformat()
        case["response_due_date"] = (filing_dt + timedelta(days=30)).isoformat()
        case["first_appeal_due_date"] = (filing_dt + timedelta(days=60)).isoformat()
        case["response_received_at"] = None
        case["pio_response_date"] = None
        case["pio_response_text"] = None
        case["status"] = "FILED"
    elif scenario == "3_days":
        # 27 days ago -> 3 days remaining
        filing_dt = now - timedelta(days=27)
        case["filing_date"] = filing_dt.isoformat()
        case["response_due_date"] = (filing_dt + timedelta(days=30)).isoformat()
        case["first_appeal_due_date"] = (filing_dt + timedelta(days=60)).isoformat()
        case["response_received_at"] = None
        case["pio_response_date"] = None
        case["pio_response_text"] = None
        case["status"] = "FILED"
    elif scenario == "due_today":
        # 30 days ago -> due today
        filing_dt = now - timedelta(days=30)
        case["filing_date"] = filing_dt.isoformat()
        case["response_due_date"] = (filing_dt + timedelta(days=30)).isoformat()
        case["first_appeal_due_date"] = (filing_dt + timedelta(days=60)).isoformat()
        case["response_received_at"] = None
        case["pio_response_date"] = None
        case["pio_response_text"] = None
        case["status"] = "FILED"
    elif scenario == "overdue_10":
        # 40 days ago -> 10 days overdue (₹2500 penalty)
        filing_dt = now - timedelta(days=40)
        case["filing_date"] = filing_dt.isoformat()
        case["response_due_date"] = (filing_dt + timedelta(days=30)).isoformat()
        case["first_appeal_due_date"] = (filing_dt + timedelta(days=60)).isoformat()
        case["response_received_at"] = None
        case["pio_response_date"] = None
        case["pio_response_text"] = None
        case["status"] = "FILED"
    elif scenario == "overdue_100":
        # 130 days ago -> 100 days overdue (₹25,000 max penalty)
        filing_dt = now - timedelta(days=130)
        case["filing_date"] = filing_dt.isoformat()
        case["response_due_date"] = (filing_dt + timedelta(days=30)).isoformat()
        case["first_appeal_due_date"] = (filing_dt + timedelta(days=60)).isoformat()
        case["response_received_at"] = None
        case["pio_response_date"] = None
        case["pio_response_text"] = None
        case["status"] = "FILED"
    elif scenario == "response_ontime":
        # Filed 20 days ago, response received yesterday (0 penalty)
        filing_dt = now - timedelta(days=20)
        case["filing_date"] = filing_dt.isoformat()
        case["response_due_date"] = (filing_dt + timedelta(days=30)).isoformat()
        case["first_appeal_due_date"] = (filing_dt + timedelta(days=60)).isoformat()
        case["response_received_at"] = (now - timedelta(days=1)).isoformat()
        case["pio_response_date"] = case["response_received_at"]
        case["pio_response_text"] = "Information provided under Section 7(1)."
        case["status"] = "RESPONSE_RECEIVED"
    elif scenario == "response_late":
        # Filed 45 days ago, response received 5 days ago (10 days overdue -> ₹2500 penalty)
        filing_dt = now - timedelta(days=45)
        case["filing_date"] = filing_dt.isoformat()
        case["response_due_date"] = (filing_dt + timedelta(days=30)).isoformat()
        case["first_appeal_due_date"] = (filing_dt + timedelta(days=60)).isoformat()
        case["response_received_at"] = (now - timedelta(days=5)).isoformat()
        case["pio_response_date"] = case["response_received_at"]
        case["pio_response_text"] = "Belated response received from PIO."
        case["status"] = "RESPONSE_RECEIVED"
    elif scenario == "custom" and payload.simulated_days_ago is not None:
        filing_dt = now - timedelta(days=payload.simulated_days_ago)
        case["filing_date"] = filing_dt.isoformat()
        case["response_due_date"] = (filing_dt + timedelta(days=30)).isoformat()
        case["first_appeal_due_date"] = (filing_dt + timedelta(days=60)).isoformat()
        case["response_received_at"] = None
        case["pio_response_date"] = None
        case["pio_response_text"] = None
        case["status"] = "FILED"

    # Reset notification flags so clean transition events populate for simulation
    case["notification_state"] = {}
    case["watchdog_events"] = []
    
    evaluated = evaluate_watchdog_state(case, now=now)
    case_manager.update_case(clean_id, evaluated)
    
    return {
        "status": "success",
        "scenario": scenario,
        "case_id": clean_id,
        "evaluated_state": evaluated
    }

@app.get("/api/case/{case_id}")
def get_case_state(case_id: str):
    clean_id = case_id.strip().upper()
    case_data = case_manager.get_case(clean_id)
    if not case_data:
        raise HTTPException(status_code=404, detail="Case ID not found.")
        
    evaluated = evaluate_watchdog_state(case_data)
    case_manager.update_case(clean_id, evaluated)

    response_payload = {
        "case_id": clean_id,
        "watchdog_enabled": evaluated.get("watchdog_enabled", True),
        "watchdog_status": evaluated.get("watchdog_status", "ACTIVE"),
        "computed_status": evaluated.get("computed_status", "ACTIVE"),
        "is_overdue": evaluated.get("is_overdue", False),
        "days_overdue": evaluated.get("days_overdue", 0),
        "days_remaining": evaluated.get("days_remaining", 0),
        "section_20_penalty_inr": evaluated.get("section_20_penalty_inr", 0),
        "filing_date": evaluated.get("filing_date"),
        "response_due_date": evaluated.get("response_due_date"),
        "first_appeal_due_date": evaluated.get("first_appeal_due_date"),
        "time_remaining_seconds": evaluated.get("time_remaining_seconds", 0),
        "appeal_eligible": evaluated.get("appeal_eligible", False),
        "last_watchdog_check_at": evaluated.get("last_watchdog_check_at"),
        "last_watchdog_event": evaluated.get("last_watchdog_event"),
        "watchdog_events": evaluated.get("watchdog_events", []),
        "notification_state": evaluated.get("notification_state", {}),
        "pio_response_text": evaluated.get("pio_response_text", ""),
        "exemption_cited": evaluated.get("exemption_cited", ""),
        "legal_counter": evaluated.get("legal_counter", ""),
        "precedent_title": evaluated.get("precedent_title", ""),
        "first_appeal_draft": evaluated.get("first_appeal_draft", ""),
        "department_info": evaluated.get("department_info", {}),
        "form_data": evaluated.get("form_data", {}),
        "user_problem": evaluated.get("user_problem", ""),
        "data": evaluated 
    }

    return response_payload

@app.get("/api/debug/supabase")
def debug_supabase(request: Request):
    """
    Restricted diagnostic endpoint.
    Disabled entirely in production (returns 404).
    In non-production: Only accessible by authorized platform administrators or valid CRON_SECRET.
    Never exposes database URLs, credentials, or internal configuration.
    """
    if _is_production():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Endpoint not found."
        )

    cron_secret = os.environ.get("CRON_SECRET")
    auth_header = request.headers.get("Authorization", "")
    is_cron_authorized = bool(cron_secret and auth_header == f"Bearer {cron_secret}")
    
    user = get_current_user_optional(request)
    is_admin_authorized = bool(user and user.role == UserRole.PLATFORM_ADMIN)

    if not (is_cron_authorized or is_admin_authorized):
        raise HTTPException(
            status_code=401,
            detail="Unauthorized: Diagnostic access restricted to authorized administrators."
        )

    from .case_manager import case_manager
    return {
        "status": "active",
        "service": "NyayPath Case Management Engine",
        "database_connected": bool(getattr(case_manager, "use_supabase", False)),
        "timestamp": datetime.now(timezone.utc).isoformat()
    }


# =====================================================================
# LIVE COURT NEWS & PRECEDENT INTELLIGENCE
# =====================================================================

@app.get("/api/court-news")
def fetch_court_news(category: str = "All", refresh: bool = False):
    return get_court_news(category, force_refresh=refresh)

class PrecedentSearchRequest(BaseModel):
    query: Optional[str] = Field("", max_length=1000)
    category: Optional[str] = "All"

class PrecedentSummarizeRequest(BaseModel):
    case_id: Optional[str] = None
    custom_text: Optional[str] = None
    user_problem: Optional[str] = None
    language: Optional[str] = "English"

@app.get("/api/precedents")
def list_precedents(category: str = "All"):
    res = precedent_engine.search("", category)
    return res if isinstance(res, dict) else {"precedents": res}

@app.post("/api/precedents/search")
def search_precedents(payload: PrecedentSearchRequest):
    res = precedent_engine.search(payload.query or "", payload.category or "All")
    return res if isinstance(res, dict) else {"precedents": res}

@app.post("/api/precedents/summarize")
def summarize_precedent(payload: PrecedentSummarizeRequest):
    summary = precedent_engine.summarize_case(
        case_id=payload.case_id,
        custom_text=payload.custom_text,
        language=payload.language or "English",
        user_problem=payload.user_problem
    )
    return summary

@app.get("/api/precedents/{case_id}/pdf")
def download_case_brief_pdf(case_id: str):
    target_case = None
    for p in LANDMARK_PRECEDENTS:
        if p["id"] == case_id:
            target_case = p
            break
    if not target_case:
        raise HTTPException(status_code=404, detail="Case precedent not found")
    
    pdf_bytes = generate_precedent_case_brief_pdf(target_case)
    filename = f"Case_Brief_{case_id}.pdf"
    return StreamingResponse(
        io.BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )

# =====================================================================
# COLLEGE PROCTORIAL & STUDENT GRIEVANCE REDRESSAL SYSTEM
# =====================================================================

@app.post("/api/campus-proctor/auth/login")
def proctor_login(payload: LoginRequest, request: Request):
    """
    Authenticates institutional officers (Proctor, Committee Member, Institution Admin).
    Verifies individual credentials and issues an authorized JWT token.
    Enforces persistent rate limiting on failed attempts.
    """
    email_key = (payload.email or "").strip().lower()
    if payload.access_key and not (payload.email and payload.password):
        record_rate_limit_failure(request, action="login", target_id="legacy_passkey", max_attempts=5, window_seconds=900, cooldown_seconds=900)
        raise HTTPException(
            status_code=401,
            detail="Shared passkeys have been permanently decommissioned. Please authenticate using your individual institutional email and password."
        )

    enforce_rate_limit(request, action="login", target_id=email_key, max_attempts=5, window_seconds=900, cooldown_seconds=900)

    user = authenticate_officer(payload)
    if not user:
        record_rate_limit_failure(request, action="login", target_id=email_key, max_attempts=5, window_seconds=900, cooldown_seconds=900)
        raise HTTPException(
            status_code=401,
            detail="Invalid institutional credentials or unauthorized role requested."
        )
    reset_rate_limit(request, action="login", target_id=email_key)
    token = create_access_token(user)
    return {
        "status": "success",
        "token": token,
        "user": {
            "user_id": user.user_id,
            "role": user.role.value,
            "institution_id": user.institution_id,
            "name": user.name,
            "email": user.email
        }
    }

@app.post("/api/campus-proctor/submit")
def submit_student_grievance(payload: StudentGrievanceSubmit, request: Request):
    """
    Submits a student grievance. Open to students and anonymous submitters.
    Returns case details along with a high-entropy secret verification_key.
    """
    student_user = get_current_user_optional(request)
    created = campus_proctor_manager.create_case(payload, student_user=student_user)
    return {"status": "success", "case": created}

@app.post("/api/campus-proctor/track")
def track_student_grievance(payload: StudentTrackingRequest, request: Request):
    """
    Verifies high-entropy verification key against stored hash.
    Case ID alone is insufficient to view private grievance details.
    Enforces rate limiting to prevent key brute-forcing.
    """
    case_key = (payload.case_id or "").strip().upper()
    enforce_rate_limit(request, action="track", target_id=case_key, max_attempts=5, window_seconds=900, cooldown_seconds=900)

    try:
        case = campus_proctor_manager.get_case_for_student(
            case_id=payload.case_id,
            verification_key=payload.verification_key
        )
        reset_rate_limit(request, action="track", target_id=case_key)
        return {"status": "success", "case": case}
    except HTTPException as e:
        if e.status_code in (401, 403, 404):
            record_rate_limit_failure(request, action="track", target_id=case_key, max_attempts=5, window_seconds=900, cooldown_seconds=900)
        raise e

@app.get("/api/campus-proctor/case/{case_id}")
def get_campus_case(
    case_id: str,
    request: Request,
    verification_key: Optional[str] = None
):
    """
    Retrieves grievance details. Requires either:
    1) Student secret verification_key (query param or x-verification-key header)
    2) Authorized Proctor/Admin token belonging to the case's institution.
    Rejects unauthorized access and rate-limits verification key attempts.
    """
    key = verification_key or request.headers.get("x-verification-key")
    user = get_current_user_optional(request)

    # 1. Proctor or administrative officer
    if user and user.role in [UserRole.PROCTOR, UserRole.CHIEF_PROCTOR, UserRole.COMMITTEE_MEMBER, UserRole.INSTITUTION_ADMIN, UserRole.PLATFORM_ADMIN]:
        case = campus_proctor_manager.get_case_for_proctor(case_id, user)
        return {"case": case}

    norm_case_id = (case_id or "").strip().upper()
    enforce_rate_limit(request, action="case", target_id=norm_case_id, max_attempts=5, window_seconds=900, cooldown_seconds=900)

    # 2. Student with verification key
    if key:
        try:
            case = campus_proctor_manager.get_case_for_student(case_id, verification_key=key, student_user=user)
            reset_rate_limit(request, action="case", target_id=norm_case_id)
            return {"case": case}
        except HTTPException as e:
            if e.status_code in (401, 403, 404):
                record_rate_limit_failure(request, action="case", target_id=norm_case_id, max_attempts=5, window_seconds=900, cooldown_seconds=900)
            raise e

    # 3. Authenticated student or citizen matching student_user_id
    if user and user.role in [UserRole.STUDENT, UserRole.CITIZEN]:
        case = campus_proctor_manager.get_case_for_student(case_id, student_user=user)
        return {"case": case}

    record_rate_limit_failure(request, action="case", target_id=norm_case_id, max_attempts=5, window_seconds=900, cooldown_seconds=900)
    raise HTTPException(
        status_code=401,
        detail="Unauthorized: Private grievance access requires your student Verification Key or an authorized Proctor session."
    )

@app.get("/api/campus-proctor/cases")
def list_campus_cases(request: Request):
    """
    Protected endpoint: Lists grievances strictly within the proctor's authorized institution.
    Rejects unauthenticated users (401) and students (403).
    """
    user = get_current_authenticated_user(request)
    if user.role not in [UserRole.PROCTOR, UserRole.CHIEF_PROCTOR, UserRole.COMMITTEE_MEMBER, UserRole.INSTITUTION_ADMIN, UserRole.PLATFORM_ADMIN]:
        raise HTTPException(
            status_code=403,
            detail="Access denied: Students are not permitted to access the proctorial inquiries queue."
        )
    cases = campus_proctor_manager.list_cases_for_proctor(user)
    return {"cases": cases, "institution_id": user.institution_id}

@app.post("/api/campus-proctor/update")
def update_campus_case(payload: ProctorUpdateStatus, request: Request):
    """
    Protected endpoint: Updates grievance status and directive.
    Enforces that proctors can only modify cases belonging to their own institution.
    """
    user = get_current_authenticated_user(request)
    if user.role not in [UserRole.PROCTOR, UserRole.CHIEF_PROCTOR, UserRole.COMMITTEE_MEMBER, UserRole.INSTITUTION_ADMIN, UserRole.PLATFORM_ADMIN]:
        raise HTTPException(
            status_code=403,
            detail="Access denied: Only authorized proctors or committee members may update case statuses."
        )
    updated = campus_proctor_manager.update_case(payload, user)
    return {"status": "success", "case": updated}

@app.get("/api/campus-proctor/notice/{case_id}")
def generate_proctor_notice(
    case_id: str,
    request: Request,
    verification_key: Optional[str] = None
):
    """
    Generates formal UGC inquiry notice for the case.
    Authorized for proctor or student with verification key.
    """
    user = get_current_user_optional(request)
    key = verification_key or request.headers.get("x-verification-key")
    notice_text = campus_proctor_manager.generate_proctorial_notice(case_id, user=user, verification_key=key)
    return {"case_id": case_id, "notice_text": notice_text}


@app.post("/api/campus-proctor/committee/assign")
def assign_committee_member_endpoint(payload: CaseCommitteeAssignRequest, request: Request):
    """
    Assigns an institutional committee member to a case inquiry.
    Authorized strictly for Institution Admins, Chief Proctors, or Platform Admins.
    Target member must belong to the same institution with active account status.
    """
    user = get_current_authenticated_user(request)
    if user.role not in [UserRole.CHIEF_PROCTOR, UserRole.INSTITUTION_ADMIN, UserRole.PLATFORM_ADMIN]:
        raise HTTPException(
            status_code=403,
            detail="Access denied: Only Chief Proctors, Institution Admins, or Platform Admins may assign committee members."
        )
    assignment = campus_proctor_manager.assign_committee_member(
        case_id=payload.case_id,
        target_user_id=payload.target_user_id,
        role=payload.role,
        committee_name=payload.committee_name,
        assigner_user=user
    )
    return {"status": "success", "assignment": assignment}


@app.post("/api/campus-proctor/committee/revoke")
def revoke_committee_member_endpoint(payload: CaseCommitteeRevokeRequest, request: Request):
    """
    Revokes an institutional committee member's assignment from a case inquiry.
    Authorized strictly for Institution Admins, Chief Proctors, or Platform Admins.
    """
    user = get_current_authenticated_user(request)
    if user.role not in [UserRole.CHIEF_PROCTOR, UserRole.INSTITUTION_ADMIN, UserRole.PLATFORM_ADMIN]:
        raise HTTPException(
            status_code=403,
            detail="Access denied: Only Chief Proctors, Institution Admins, or Platform Admins may revoke committee assignments."
        )
    assignment = campus_proctor_manager.revoke_committee_assignment(
        case_id=payload.case_id,
        target_user_id=payload.target_user_id,
        revoker_user=user
    )
    return {"status": "success", "assignment": assignment}


@app.get("/api/campus-proctor/committee/assignments/{case_id}")
def get_committee_assignments_endpoint(case_id: str, request: Request):
    """
    Lists active committee assignments for a case inquiry.
    Authorized for institutional officers belonging to the case's institution.
    """
    user = get_current_authenticated_user(request)
    assignments = campus_proctor_manager.get_committee_assignments(case_id, user)
    return {"case_id": case_id, "assignments": assignments}


@app.get("/api/campus-proctor/document-url")
def get_case_document_url(
    case_id: str,
    document_id: str,
    request: Request,
    verification_key: Optional[str] = None,
    ttl: Optional[int] = None
):
    """
    Generates a secure short-lived signed URL for accessing a case document.
    Enforces dual-pathway authentication and server-side TTL cap (strictly <= 300 seconds).
    """
    auth_header = request.headers.get("Authorization")
    key = verification_key or request.headers.get("x-verification-key")
    client_ip = request.client.host if request.client else "127.0.0.1"

    # Enforce TTL clamping if provided: under no circumstances can client override beyond 300s
    effective_ttl = min(ttl, 300) if (ttl is not None and ttl > 0) else 300

    result = document_access_manager.generate_document_signed_url(
        case_id=case_id,
        document_id=document_id,
        auth_header=auth_header,
        tracking_key=key,
        client_ip=client_ip,
        ttl=effective_ttl
    )
    return result


@app.post("/api/intake/clarifying-questions")
def get_clarifying_questions(payload: ClarifyingQuestionsRequest):
    return recognize_and_generate_questions(payload.problem_text, payload.language)

@app.post("/api/intake/synthesize-draft")
def synthesize_draft_endpoint(payload: SynthesizeDraftRequest):
    case_id = payload.case_id or case_manager.create_case()
    case = case_manager.get_case(case_id) or {}
    
    applicant_name = payload.applicant_name
    if not applicant_name or applicant_name == "The Citizen / Complainant":
        applicant_name = case.get("form_data", {}).get("applicant_name") or "The Citizen / Complainant"
        
    res = synthesize_systematic_draft(
        problem_text=payload.problem_text,
        answers=payload.answers,
        language=payload.language or "English",
        route=payload.route or case.get("route") or "RTI",
        applicant_name=applicant_name
    )
    
    # Update case manager
    case_manager.update_case(case_id, {
        "status": "rti_drafted" if (payload.route == "RTI" or res.get("likely_route") == "RTI") else "grievance_completed",
        "initial_draft": res["systematic_draft"],
        "improved_draft": res["systematic_draft"],
        "lawyer_brief": res["lawyer_brief"],
        "clarifying_answers": payload.answers,
        "form_data": {**case.get("form_data", {}), **payload.answers}
    })
    
    return {"case_id": case_id, **res}


# =====================================================================
# Phase 2.1: Citizen Dashboard & My Cases Workspace Endpoints (Task 7)
# =====================================================================

@app.post("/api/citizen/auth/login")
def citizen_login(payload: LoginRequest, request: Request):
    """
    Authenticates a citizen or student user and returns a signed JWT access token.
    Enforces brute-force rate-limiting.
    """
    email_key = (payload.email or "").strip().lower()
    if not email_key:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing required email address."
        )

    enforce_rate_limit(request, action="citizen_login", target_id=email_key, max_attempts=5, window_seconds=900, cooldown_seconds=900)

    user = authenticate_citizen(payload)
    if not user:
        record_rate_limit_failure(request, action="citizen_login", target_id=email_key, max_attempts=5, window_seconds=900, cooldown_seconds=900)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid citizen/student credentials."
        )

    reset_rate_limit(request, action="citizen_login", target_id=email_key)
    token = create_access_token(user, expires_delta=timedelta(hours=24))

    return {
        "status": "success",
        "token": token,
        "user": {
            "user_id": user.user_id,
            "name": user.name,
            "email": user.email,
            "role": user.role.value,
            "institution_id": user.institution_id,
            "account_status": user.account_status.value
        }
    }


@app.get("/api/citizen/dashboard-stats")
def get_citizen_dashboard_stats(request: Request):
    """
    Protected endpoint: Returns live legal case statistics for the authenticated citizen.
    Strictly derives identity from verified JWT Bearer token (auth.uid()).
    Fails closed if unauthenticated (401) or on database failure (503).
    """
    user = get_current_authenticated_user(request)
    return citizen_workspace_manager.get_dashboard_stats(user)


@app.get("/api/citizen/cases")
def list_citizen_cases(
    request: Request,
    status: Optional[str] = None,
    category: Optional[str] = None,
    search: Optional[str] = None,
    sort_by: str = "created_at",
    sort_order: str = "desc",
    page: int = 1,
    limit: int = 10
):
    """
    Protected endpoint: Returns paginated list of cases owned by the authenticated citizen.
    Internal officer notes and tracking key hashes are strictly omitted.
    Strictly derives identity from verified JWT Bearer token (auth.uid()).
    """
    user = get_current_authenticated_user(request)
    return citizen_workspace_manager.list_citizen_cases(
        user=user,
        status_filter=status,
        category_filter=category,
        search=search,
        sort_by=sort_by,
        sort_order=sort_order,
        page=page,
        limit=limit
    )


@app.get("/api/citizen/cases/{case_id}")
def get_citizen_case_details(case_id: str, request: Request):
    """
    Protected endpoint: Returns full case details, activity timeline, and supporting documents.
    Strictly verifies ownership: rejects non-owners with 403 Forbidden.
    Internal proctorial notes are strictly hidden from citizens.
    """
    user = get_current_authenticated_user(request)
    return citizen_workspace_manager.get_case_details(case_id, user)


@app.post("/api/citizen/cases/file")
def file_citizen_case(payload: CaseFilingRequest, request: Request):
    """
    Protected endpoint: Files a new case in the Central Case Management System.
    Strictly derives identity from verified JWT Bearer token (auth.uid()).
    Fails closed if unauthenticated (401) or if declaration not accepted (400).
    """
    user = get_current_authenticated_user(request)
    return citizen_workspace_manager.file_case(user=user, payload=payload)


@app.post("/api/citizen/cases/upload-document")
async def upload_case_document(
    file: UploadFile = File(...),
    case_id: Optional[str] = Form(None),
    request: Request = None
):
    """
    Protected endpoint: Uploads and sanitizes a supporting case document.
    - Strips PDF metadata & XMP streams; strips image EXIF.
    - Max size 10MB; allowed types: PDF, JPEG, PNG, WebP.
    - If case_id is provided, verifies ownership before associating.
    """
    user = get_current_authenticated_user(request)
    file_bytes = await file.read()
    return citizen_workspace_manager.upload_document(
        user=user,
        file_bytes=file_bytes,
        filename=file.filename or "document.pdf",
        content_type=file.content_type or "application/pdf",
        case_id=case_id
    )


@app.post("/api/citizen/cases/{case_id}/lifecycle")
def execute_case_lifecycle_action(
    case_id: str,
    payload: CaseLifecycleActionRequest,
    request: Request
):
    """
    Protected endpoint: Executes citizen lifecycle actions on their case:
    - WITHDRAW: Permits withdrawal of active cases; sets status to CLOSED.
    - ADD_REMARK: Adds citizen commentary to case audit log.
    - REQUEST_EXPEDITE: Registers formal urgent expedite notification for officers.
    Strictly verifies ownership (403 if unauthorized).
    """
    user = get_current_authenticated_user(request)
    return citizen_workspace_manager.perform_lifecycle_action(
        case_id=case_id,
        user=user,
        payload=payload
    )


@app.post("/api/citizen/track")
def track_citizen_case_post(payload: PublicCaseTrackingRequest, request: Request):
    """
    Public endpoint: Tracks case progress without leaking confidential data or proctor notes.
    Accepts Case ID + optional 128-bit verification key, or authenticated user session.
    """
    case_key = (payload.case_id or "").strip().upper()
    enforce_rate_limit(request, action="track", target_id=case_key, max_attempts=10, window_seconds=900, cooldown_seconds=900)

    user = get_current_user_optional(request)
    try:
        res = citizen_workspace_manager.track_case_public(
            case_id=payload.case_id,
            verification_key=payload.verification_key,
            user=user
        )
        reset_rate_limit(request, action="track", target_id=case_key)
        return res
    except HTTPException as e:
        if e.status_code in (401, 403, 404):
            record_rate_limit_failure(request, action="track", target_id=case_key, max_attempts=10, window_seconds=900, cooldown_seconds=900)
        raise e


@app.get("/api/citizen/track/{case_id}")
def track_citizen_case_get(case_id: str, request: Request, verification_key: Optional[str] = None):
    """
    Public GET endpoint: Quick case progress status lookup.
    """
    case_key = (case_id or "").strip().upper()
    enforce_rate_limit(request, action="track", target_id=case_key, max_attempts=10, window_seconds=900, cooldown_seconds=900)

    user = get_current_user_optional(request)
    try:
        res = citizen_workspace_manager.track_case_public(
            case_id=case_id,
            verification_key=verification_key,
            user=user
        )
        reset_rate_limit(request, action="track", target_id=case_key)
        return res
    except HTTPException as e:
        if e.status_code in (401, 403, 404):
            record_rate_limit_failure(request, action="track", target_id=case_key, max_attempts=10, window_seconds=900, cooldown_seconds=900)
        raise e


# =====================================================================
# Intelligent In-App Notification System Endpoints (Phase 2.3)
# =====================================================================

@app.get("/api/notifications")
def get_user_notifications(
    request: Request,
    is_read: Optional[bool] = None,
    limit: int = 50,
    offset: int = 0
):
    """
    Protected endpoint: Lists notifications strictly for the authenticated caller.
    Returns notification items along with live unread count.
    """
    user = get_current_authenticated_user(request)
    return notification_manager.list_user_notifications(
        user_id=user.user_id,
        is_read=is_read,
        limit=limit,
        offset=offset
    )


@app.get("/api/notifications/unread-count")
def get_user_unread_notification_count(request: Request):
    """
    Protected endpoint: Lightweight unread notification counter for Navbar badge.
    """
    user = get_current_authenticated_user(request)
    count = notification_manager.get_unread_count(user_id=user.user_id)
    return {"unread_count": count}


@app.post("/api/notifications/{notification_id}/read")
def mark_notification_read(notification_id: str, request: Request):
    """
    Protected endpoint: Marks a single notification as read.
    Strictly verifies ownership: Rejects modification of another user's notification with 403.
    """
    user = get_current_authenticated_user(request)
    return notification_manager.mark_as_read(
        notification_id=notification_id,
        user_id=user.user_id
    )


@app.post("/api/notifications/mark-all-read")
def mark_all_notifications_read(request: Request):
    """
    Protected endpoint: Marks all notifications as read for the authenticated caller.
    """
    user = get_current_authenticated_user(request)
    updated_count = notification_manager.mark_all_as_read(user_id=user.user_id)
    return {"status": "success", "marked_read_count": updated_count}


@app.delete("/api/notifications/{notification_id}")
def delete_user_notification(notification_id: str, request: Request):
    """
    Protected endpoint: Dismisses/deletes a single notification.
    Strictly verifies ownership: Rejects deletion of another user's notification with 403.
    """
    user = get_current_authenticated_user(request)
    success = notification_manager.delete_notification(
        notification_id=notification_id,
        user_id=user.user_id
    )
    return {"status": "success" if success else "failed"}


# =====================================================================
# Legal Citations Resolution Endpoint (Phase 2.3)
# =====================================================================

class CitationResolveRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=1000)
    max_results: Optional[int] = Field(3, ge=1, le=20)

@app.post("/api/citations/resolve")
def resolve_legal_citations(payload: CitationResolveRequest, request: Request):
    """
    Public/Authenticated endpoint: Resolves verified legal citations for a claim or legal issue.
    - Matches landmark Supreme Court, High Court, and statutory provisions.
    - Zero hallucination: Indicates clearly when no verified authority exists.
    - Rate limited to prevent scraping/DoS.
    """
    client_ip = request.client.host if request.client else "unknown"
    enforce_rate_limit(request, action="citations", target_id=client_ip, max_attempts=30, window_seconds=60, cooldown_seconds=60)

    if not payload.query or not payload.query.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Query string cannot be empty."
        )
    return resolve_citations_for_query(
        query=payload.query.strip(),
        max_results=payload.max_results or 3
    )




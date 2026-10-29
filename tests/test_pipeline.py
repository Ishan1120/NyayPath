import os
import sys

# Ensure workspace root is in python path
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from fastapi.testclient import TestClient
from api.index import app

client = TestClient(app)

print("==================================================")
print("  NyayPath Full End-to-End Pipeline Verification")
print("==================================================")

print("\n--- Step 1: Initialize Case (Passkey Generation) ---")
r_init = client.post("/api/case/init")
assert r_init.status_code == 200, f"Init failed: {r_init.text}"
case_id = r_init.json()["case_id"]
print(f"[SUCCESS] Passkey Generated: {case_id}")

print("\n--- Step 2: Legal Route Classification ---")
user_query = "The main road in our sector was constructed 3 months ago and already developed huge potholes. Municipal corporation is not repairing it. I want copies of the tender, contractor agreement, and quality inspection reports."
r_class = client.post("/api/case/classify", json={"case_id": case_id, "problem_text": user_query})
assert r_class.status_code == 200, f"Classify failed: {r_class.text}"
route_data = r_class.json()
print(f"[SUCCESS] Route: {route_data['route']} | Confidence: {route_data['confidence']:.2f}")
print(f"          Sub-category: {route_data.get('sub_category')}")

print("\n--- Step 3: Auto-Jurisdiction / Department Resolution ---")
r_dept = client.post("/api/rti/resolve-department", json={"case_id": case_id, "location": "Lucknow, Uttar Pradesh"})
assert r_dept.status_code == 200, f"Dept resolution failed: {r_dept.text}"
dept_data = r_dept.json()
print(f"[SUCCESS] Authority: {dept_data.get('public_authority_name')}")
print(f"          Designation: {dept_data.get('pio_designation')}")

print("\n--- Step 4: RTI Form 'A' Statutory Drafting ---")
form_payload = {
    "case_id": case_id,
    "form_data": {
        "applicant_name": "Ishan Sharma",
        "applicant_address": "Flat 402, Gomti Nagar, Lucknow, UP",
        "applicant_contact": "ishan@example.com",
        "applicant_city": "Lucknow",
        "applicant_state": "Uttar Pradesh",
        "time_period": "Past 6 Months"
    }
}
r_draft = client.post("/api/rti/generate", json=form_payload)
assert r_draft.status_code == 200, f"Drafting failed: {r_draft.text}"
draft_text = r_draft.json().get("initial_draft", "")
print(f"[SUCCESS] Form 'A' Draft Generated ({len(draft_text)} characters)")
assert "SECTION 6(1)" in draft_text.upper()
assert "SECTION 10" in draft_text.upper()

print("\n--- Step 5: PDF Export (ReportLab Form 'A') ---")
r_pdf = client.get(f"/api/rti/pdf/{case_id}")
assert r_pdf.status_code == 200, f"PDF generation failed: {r_pdf.text}"
assert r_pdf.headers.get("content-type") == "application/pdf"
print(f"[SUCCESS] PDF Generated ({len(r_pdf.content)} bytes)")

print("\n--- Step 6: Watchdog SLA & Statutory Section 20(1) Penalty Engine ---")
r_watch = client.post("/api/watchdog/simulate", json={"case_id": case_id, "scenario": "overdue_10"})
assert r_watch.status_code == 200, f"Watchdog failed: {r_watch.text}"
watch_state = r_watch.json().get("evaluated_state", {})
print(f"[SUCCESS] Overdue Days: {watch_state.get('days_overdue')} days")
print(f"          Section 20(1) Penalty Accrued: INR {watch_state.get('section_20_penalty_inr')}")
assert watch_state.get("section_20_penalty_inr") == 2500

print("\n--- Step 7: PIO Response Analysis & CIC Landmark Precedents ---")
r_pio = client.post("/api/analyze_pio_backend", json={
    "case_id": case_id,
    "pio_text": "The information sought regarding contractor payments and third-party inspection is denied under Section 8(1)(j) as it relates to private commercial entities."
})
assert r_pio.status_code == 200, f"PIO analysis failed: {r_pio.text}"
pio_data = r_pio.json()
print(f"[SUCCESS] Exemption Detected: {pio_data.get('exemption_cited')}")
print(f"          Precedent Title: {pio_data.get('precedent_title')}")
print(f"          Counter Grounds: {pio_data.get('appeal_grounds')}")
assert pio_data.get("exemption_cited") == "8(1)(j)"

print("\n--- Step 8: Live Court News Feed ---")
r_news = client.get("/api/court-news")
assert r_news.status_code == 200
news_list = r_news.json().get("news", [])
print(f"[SUCCESS] Court News Items Loaded: {len(news_list)}")
assert len(news_list) > 0

print("\n--- Step 9: Case Precedent Search & AI Case Summarizer ---")
r_prec = client.post("/api/precedents/search", json={"query": "answer sheet", "category": "All"})
assert r_prec.status_code == 200
precedents = r_prec.json().get("precedents", [])
print(f"[SUCCESS] Precedents Matched: {len(precedents)} ({precedents[0]['title']})")
r_summ = client.post("/api/precedents/summarize", json={"case_id": precedents[0]["id"]})
assert r_summ.status_code == 200
print(f"[SUCCESS] AI Case Summary Generated: {r_summ.json().get('case_title')}")

print("\n--- Step 10: College Proctor & Student Grievance Engine ---")
r_proctor_submit = client.post("/api/campus-proctor/submit", json={
    "student_name": "Ishan Sharma",
    "roll_number": "22CS104",
    "department": "Computer Science & Engineering",
    "year": "3rd Year",
    "category": "Examination & Evaluation",
    "subject": "Semester 5 Re-evaluation mark calculation discrepancy",
    "description": "Marks in theoretical DBMS exam were omitted from final tabulation register. Seeking inspection."
})
assert r_proctor_submit.status_code == 200
campus_case = r_proctor_submit.json().get("case", {})
campus_case_id = campus_case.get("case_id")
print(f"[SUCCESS] Student Grievance Registered: {campus_case_id}")
r_notice = client.get(f"/api/campus-proctor/notice/{campus_case_id}")
assert r_notice.status_code == 200
print(f"[SUCCESS] Formal Proctorial Notice Generated ({len(r_notice.json().get('notice_text', ''))} bytes)")

print("\n--- Step 11: AI Clarifying Questions & Systematic Legal Draft Synthesis ---")
r_questions = client.post("/api/intake/clarifying-questions", json={
    "problem_text": "Ward 12 road carpeting was left half done and broken with severe potholes"
})
assert r_questions.status_code == 200
q_data = r_questions.json()
print(f"[SUCCESS] Recognized Issue: {q_data.get('recognized_issue')}")
print(f"          Target Authority: {q_data.get('target_authority')}")
print(f"          Clarifying Questions Generated: {len(q_data.get('questions', []))}")
assert len(q_data.get("questions", [])) >= 3

r_synth = client.post("/api/intake/synthesize-draft", json={
    "case_id": case_id,
    "problem_text": "Ward 12 road carpeting was left half done and broken with severe potholes",
    "answers": {
        "applicant_city": "Lucknow, Uttar Pradesh",
        "incident_date": "Completed 3 months ago",
        "target_department": "Municipal Corporation / PWD",
        "specific_records": "Certified Measurement Book entries and delay penalty ledger",
        "file_or_work_no": "TENDER-PWD-2025-W12"
    },
    "route": "RTI"
})
assert r_synth.status_code == 200
synth_data = r_synth.json()
print(f"[SUCCESS] Systematic Draft Generated ({len(synth_data.get('systematic_draft', ''))} chars)")
print(f"          Advocate Case Brief Generated ({len(synth_data.get('lawyer_brief', ''))} chars)")
assert "SYSTEMATIC CHRONOLOGICAL STATEMENT OF FACTS" in synth_data.get("systematic_draft", "")
assert "CASE SUMMARY BRIEF" in synth_data.get("lawyer_brief", "")

print("\n==================================================")
print("  ALL 11 CORE ENGINEERING MODULES PASSED 100%!")
print("==================================================")

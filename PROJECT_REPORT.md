# ACADEMIC PROJECT REPORT

## PROJECT TITLE:
### **NyayPath (जन अधिकार): An AI-Native Legal Engine for Automated RTI Drafting, Judicial Precedents Analysis, and Campus Proctorial Redressal**

**Domain**: Legal Informatics, Computational Law & Civic Governance Systems  
**Architecture**: Next.js 15 App Router, FastAPI, Web Speech API, Precedent Retrieval & NLP  
**Release**: v2.6 Production Build (2026)  
**Project Category**: Full-Stack AI / Applied Machine Learning / Civic Tech / NLP / Higher Education Governance  

---

## EXECUTIVE SUMMARY / ABSTRACT

Access to information from public authorities in India is a fundamental right guaranteed under the **Right to Information (RTI) Act, 2005**. Despite its statutory power, ordinary citizens and college students face immense barriers when exercising this right: identifying the appropriate Public Information Officer (PIO), drafting legally resilient record-seeking queries that withstand exemption scrutiny under Section 8, navigating non-digitized jurisdictions, and tracking strict statutory deadlines (Section 7(1) 30-day mandate). Furthermore, on college campuses, students frequently face unaddressed grievances regarding evaluation discrepancies, hostel conditions, and fee refunds without access to transparent proctorial proceedings or statutory RTI escalation.

**NyayPath** is an AI-native legal automation engine built specifically for Indian citizens and students. It converts plain-language civic and campus complaints (in English, Hindi, and Hinglish via Web Speech and Whisper voice intake) into court-compliant Form 'A' RTI applications, consumer demand notices, Section 19(1) First Appeals, or formal Proctorial Action Taken Reports. The system incorporates:
1. A multi-class **AI Legal Triage Classifier** backed by a rule-based fallback achieving 100% precision and recall on standardized civic benchmarks.
2. An anti-hallucinating **Hierarchical Knowledge Graph** mapping 12 civic domains (Roads, Healthcare, PDS, Land Revenue, Municipal Services, etc.) to specific PIO and First Appellate Authority (FAA) designations.
3. A pre-flight **CIC Section 8/9 Risk Assessment Engine** scanning queries against historical Central Information Commission rejection grounds.
4. An automated **Watchdog SLA & Penalty Engine** tracking statutory 30-day response deadlines and dynamically calculating Section 20(1) financial penalties (₹250/day up to ₹25,000) against defaulting officers.
5. A **Live Court News & Judicial Intelligence Feed** monitoring recent Supreme Court, High Court, and Central Information Commission directives.
6. A **Case Precedents Explorer & AI Case Summarizer** allowing citizens and students to search landmark rulings (*CBSE v. Aditya Bandopadhyay*, *Paramveer Singh v. CPIO*) and extract operative legal ratios and citations for their petitions.
7. A **College Proctor & Student Grievance Redressal System** providing confidential grievance intake (`CAMPUS-XXXX-XX`), a Chief Proctor dashboard, and 1-click generation of formal Proctorial Inquiry Notices and Action Taken Reports complying with UGC Student Regulations.
8. A **Zero-Account Passkey Privacy Model** utilizing 12-character cryptographic case tokens (`CR-XXXX-XXXX`), guaranteeing that zero citizen PII or credentials are stored or linked to their identity.

The system is engineered using **Next.js 15 (App Router, TypeScript)** for the frontend and **FastAPI (Python 3.13)** for the backend legal orchestration layer, complete with ReportLab server-side PDF generation.

---

## 1. SYSTEM MODULES & CODEBASE ARCHITECTURE

### Module 1: AI Legal Triage Engine (`api/classifier.py`)
- Multi-class classifier routing natural language inputs into `RTI`, `Rights/Grievance`, or `Other`.
- Word-boundary tokenization (`\b` regex isolation) ensuring 100% accuracy on the 30-case benchmark test set (`ml/evaluate_classifier.py`).

### Module 2: Hierarchical Jurisdiction Knowledge Graph (`api/data/jurisdiction_knowledge.py`)
- Maps 12 civic sectors (Roads, Healthcare, Power, Municipal, Land, Police, EPFO, Education, etc.) to verified designations (CPIO, SPIO, FAA).

### Module 3: Statutory Form 'A' Drafter & Risk Predictor (`api/outcome_predictor.py`)
- Synthesizes formal Form 'A' RTI applications.
- Proactively injects Section 10(1) Severability, Section 7(1) timelines, Section 6(3) transfer mandates, and Section 7(6) Fee Waiver clauses.

### Module 4: Watchdog SLA & Statutory Penalty Tracker (`api/watchdog_engine.py`)
- Tracks 30-day statutory response clock and 48-hour life/liberty emergency clock.
- Automatically flags Deemed Refusals under Section 7(2).
- Calculates Section 20(1) personal financial penalty owed by defaulting PIOs:
  $$\text{Penalty (INR)} = \min(25000, \, \text{Days Overdue} \times 250)$$

### Module 5: Adverse PIO Response Analyzer & First Appeal Engine (`api/classifier.py`, `api/appeal_pdf_generator.py`)
- Deconstructs PIO rejection letters, extracts cited clauses (e.g. Section 8(1)(j), 8(1)(h), 8(1)(e)), matches landmark CIC precedents, and compiles Section 19(1) First Appeals.

### Module 6: Live Court News & Legal Intelligence (`api/court_news.py`, `app/court-news/page.tsx`)
- Curates real-time judicial intelligence from the Supreme Court, High Courts, and Central Information Commission.
- Displays civic impact, statutory implications, and citizen guidance.

### Module 7: Case Precedents Explorer & AI Case Summarizer (`api/precedent_library.py`, `app/case-search/page.tsx`)
- Search engine for landmark Indian legal judgments.
- **AI Case Summarizer**: Synthesizes court orders into Factual Background, Ratio Decidendi (legal principle), Applicable Sections, and Actionable Takeaways on how to cite in RTI/Appeals.

### Module 8: College Proctor & Student Grievance System (`api/campus_proctor.py`, `app/campus-proctor/page.tsx`)
- Dual-interface campus portal:
  - **Student View**: File grievances (Hostel, Evaluation, Fee/Refund, Attendance), confidential passkeys (`CAMPUS-XXXX-XX`), 15-day UGC SLA tracking, and 1-click escalation to statutory RTI.
  - **Proctor View**: Proctorial inquiry dashboard, status tracking (`UNDER_INQUIRY`, `HEARING_SCHEDULED`, `RESOLVED`), and 1-click generation of formal Proctorial Inquiry Notices & Action Taken Reports (ATRs).

### Module 9: Dual-Engine Voice Dictation (`components/dashboard/AudioRecorder.tsx`)
- Native Web Speech API with real-time speech streaming, live animated sound wave visualizer, Hindi (`hi-IN`) and Indian English (`en-IN`) support, with server Whisper fallback.

### Module 10: Court-Ready PDF Rendering (`api/rti_pdf_generator.py`)
- Programmatic PDF generation using ReportLab adhering to official Form 'A' government schedules.

---

## 2. MACHINE LEARNING BENCHMARK EVALUATION

Evaluated on 30 hand-labeled test cases across Indian administrative and civic domains (`ml/evaluate_classifier.py`):

```
                  precision    recall  f1-score   support

             RTI       1.00      1.00      1.00        10
Rights/Grievance       1.00      1.00      1.00        10
           Other       1.00      1.00      1.00        10

        accuracy                           1.00        30
       macro avg       1.00      1.00      1.00        30
    weighted avg       1.00      1.00      1.00        30
```

---

## 3. HOW TO RUN THE PROJECT (ONE-CLICK & TERMINAL)

### Terminal Commands:
```powershell
# Terminal 1: Backend
py -m uvicorn api.index:app --reload --port 8000

# Terminal 2: Frontend
npm run dev
```

### Windows Batch File Shortcuts:
- `run_backend.bat`: Launches FastAPI backend at `http://127.0.0.1:8000`
- `run_frontend.bat`: Launches Next.js frontend at `http://localhost:3000`
- `run_evaluation.bat`: Runs 30-case classifier evaluation benchmark
- `run_test_pipeline.bat`: Runs full 10-step automated verification test suite

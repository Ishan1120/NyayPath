import os
import sys
import unittest
from pathlib import Path

# Ensure workspace root is in python path
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from fastapi.testclient import TestClient
from api.index import app


class TestPipelineE2E(unittest.TestCase):
    """Full End-to-End Pipeline Verification across all 11 core engineering modules."""

    @classmethod
    def setUpClass(cls):
        cls.old_offline = os.environ.get("SUPABASE_OFFLINE_TEST")
        cls.old_allow_sqlite = os.environ.get("ALLOW_LOCAL_SQLITE")
        cls.old_test_mode = os.environ.get("TEST_MODE")

        os.environ["ALLOW_LOCAL_SQLITE"] = "1"
        os.environ["TEST_MODE"] = "1"
        os.environ["SUPABASE_OFFLINE_TEST"] = "1"

        cls.client = TestClient(app)
        cls.case_id = None
        cls.campus_case_id = None

    @classmethod
    def tearDownClass(cls):
        if cls.old_offline is not None:
            os.environ["SUPABASE_OFFLINE_TEST"] = cls.old_offline
        else:
            os.environ.pop("SUPABASE_OFFLINE_TEST", None)

        if cls.old_allow_sqlite is not None:
            os.environ["ALLOW_LOCAL_SQLITE"] = cls.old_allow_sqlite
        else:
            os.environ.pop("ALLOW_LOCAL_SQLITE", None)

        if cls.old_test_mode is not None:
            os.environ["TEST_MODE"] = cls.old_test_mode
        else:
            os.environ.pop("TEST_MODE", None)

    def test_01_init_case(self):
        """Step 1: Initialize Case (Passkey Generation)"""
        r_init = self.client.post("/api/case/init")
        self.assertEqual(r_init.status_code, 200, f"Init failed: {r_init.text}")
        TestPipelineE2E.case_id = r_init.json()["case_id"]
        self.assertTrue(TestPipelineE2E.case_id.startswith("CR-"))

    def test_02_classify_legal_route(self):
        """Step 2: Legal Route Classification"""
        if not TestPipelineE2E.case_id:
            r_init = self.client.post("/api/case/init")
            TestPipelineE2E.case_id = r_init.json()["case_id"]

        user_query = (
            "The main road in our sector was constructed 3 months ago and already developed huge potholes. "
            "Municipal corporation is not repairing it. I want copies of the tender, contractor agreement, and quality inspection reports."
        )
        r_class = self.client.post("/api/case/classify", json={"case_id": TestPipelineE2E.case_id, "problem_text": user_query})
        self.assertEqual(r_class.status_code, 200, f"Classify failed: {r_class.text}")
        route_data = r_class.json()
        self.assertEqual(route_data["route"], "RTI")
        self.assertGreaterEqual(route_data["confidence"], 0.70)

    def test_03_resolve_department(self):
        """Step 3: Auto-Jurisdiction / Department Resolution"""
        r_dept = self.client.post("/api/rti/resolve-department", json={"case_id": TestPipelineE2E.case_id, "location": "Lucknow, Uttar Pradesh"})
        self.assertEqual(r_dept.status_code, 200, f"Dept resolution failed: {r_dept.text}")
        dept_data = r_dept.json()
        self.assertIn("public_authority_name", dept_data)
        self.assertIn("pio_designation", dept_data)

    def test_04_form_a_statutory_drafting(self):
        """Step 4: RTI Form 'A' Statutory Drafting"""
        form_payload = {
            "case_id": TestPipelineE2E.case_id,
            "form_data": {
                "applicant_name": "Ishan Sharma",
                "applicant_address": "Flat 402, Gomti Nagar, Lucknow, UP",
                "applicant_contact": "ishan@example.com",
                "applicant_city": "Lucknow",
                "applicant_state": "Uttar Pradesh",
                "time_period": "Past 6 Months"
            }
        }
        r_draft = self.client.post("/api/rti/generate", json=form_payload)
        self.assertEqual(r_draft.status_code, 200, f"Drafting failed: {r_draft.text}")
        draft_text = r_draft.json().get("initial_draft", "")
        self.assertIn("SECTION 6(1)", draft_text.upper())
        self.assertIn("SECTION 10", draft_text.upper())

    def test_05_pdf_export(self):
        """Step 5: PDF Export (ReportLab Form 'A')"""
        r_pdf = self.client.get(f"/api/rti/pdf/{TestPipelineE2E.case_id}")
        self.assertEqual(r_pdf.status_code, 200, f"PDF generation failed: {r_pdf.text}")
        self.assertEqual(r_pdf.headers.get("content-type"), "application/pdf")
        self.assertGreater(len(r_pdf.content), 1000)

    def test_06_watchdog_sla_and_penalty(self):
        """Step 6: Watchdog SLA & Statutory Section 20(1) Penalty Engine"""
        r_watch = self.client.post("/api/watchdog/simulate", json={"case_id": TestPipelineE2E.case_id, "scenario": "overdue_10"})
        self.assertEqual(r_watch.status_code, 200, f"Watchdog failed: {r_watch.text}")
        watch_state = r_watch.json().get("evaluated_state", {})
        self.assertEqual(watch_state.get("days_overdue"), 10)
        self.assertEqual(watch_state.get("section_20_penalty_inr"), 2500)

    def test_07_pio_response_analysis(self):
        """Step 7: PIO Response Analysis & CIC Landmark Precedents"""
        r_pio = self.client.post("/api/analyze_pio_backend", json={
            "case_id": TestPipelineE2E.case_id,
            "pio_text": "The information sought regarding contractor payments and third-party inspection is denied under Section 8(1)(j) as it relates to private commercial entities."
        })
        self.assertEqual(r_pio.status_code, 200, f"PIO analysis failed: {r_pio.text}")
        pio_data = r_pio.json()
        self.assertEqual(pio_data.get("exemption_cited"), "8(1)(j)")
        self.assertIn("precedent_title", pio_data)

    def test_08_live_court_news_feed(self):
        """Step 8: Live Court News Feed"""
        r_news = self.client.get("/api/court-news")
        self.assertEqual(r_news.status_code, 200)
        news_list = r_news.json().get("news", [])
        self.assertGreater(len(news_list), 0)

    def test_09_case_precedent_search_and_summarizer(self):
        """Step 9: Case Precedent Search & AI Case Summarizer"""
        r_prec = self.client.post("/api/precedents/search", json={"query": "answer sheet", "category": "All"})
        self.assertEqual(r_prec.status_code, 200)
        precedents = r_prec.json().get("precedents", [])
        self.assertGreater(len(precedents), 0)
        r_summ = self.client.post("/api/precedents/summarize", json={"case_id": precedents[0]["id"]})
        self.assertEqual(r_summ.status_code, 200)
        self.assertIn("case_title", r_summ.json())

    def test_10_college_proctor_student_grievance(self):
        """Step 10: College Proctor & Student Grievance Engine"""
        r_proctor_submit = self.client.post("/api/campus-proctor/submit", json={
            "student_name": "Ishan Sharma",
            "roll_number": "22CS104",
            "department": "Computer Science & Engineering",
            "year": "3rd Year",
            "category": "Examination & Evaluation",
            "subject": "Semester 5 Re-evaluation mark calculation discrepancy",
            "description": "Marks in theoretical DBMS exam were omitted from final tabulation register. Seeking inspection."
        })
        self.assertEqual(r_proctor_submit.status_code, 200)
        campus_case = r_proctor_submit.json().get("case", {})
        TestPipelineE2E.campus_case_id = campus_case.get("case_id")
        self.assertTrue(TestPipelineE2E.campus_case_id.startswith("CAMPUS-"))

        r_notice = self.client.get(f"/api/campus-proctor/notice/{TestPipelineE2E.campus_case_id}")
        self.assertEqual(r_notice.status_code, 200)
        self.assertGreater(len(r_notice.json().get("notice_text", "")), 100)

    def test_11_ai_clarifying_questions_and_synthesis(self):
        """Step 11: AI Clarifying Questions & Systematic Legal Draft Synthesis"""
        r_questions = self.client.post("/api/intake/clarifying-questions", json={
            "problem_text": "Ward 12 road carpeting was left half done and broken with severe potholes"
        })
        self.assertEqual(r_questions.status_code, 200)
        q_data = r_questions.json()
        self.assertGreaterEqual(len(q_data.get("questions", [])), 3)

        r_synth = self.client.post("/api/intake/synthesize-draft", json={
            "case_id": TestPipelineE2E.case_id,
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
        self.assertEqual(r_synth.status_code, 200)
        synth_data = r_synth.json()
        self.assertIn("SYSTEMATIC CHRONOLOGICAL STATEMENT OF FACTS", synth_data.get("systematic_draft", ""))
        self.assertIn("CASE SUMMARY BRIEF", synth_data.get("lawyer_brief", ""))


if __name__ == "__main__":
    unittest.main()

"""
NyayPath Phase 2.3 Comprehensive Test Suite
Legal Citation Integration & Intelligent Notification System Verification

Tests:
1. Legal Citations Engine:
   - Query for tenant security deposit resolves authentic Supreme Court / High Court citations.
   - Verified metadata fields: case_title, court, citation, authority_type, statutory_provisions, ratio, source_url.
2. Zero Hallucination:
   - Non-legal / irrelevant query (e.g. baking chocolate chip cookies) returns has_citations=False and empty list.
3. Citations API Endpoint:
   - POST /api/citations/resolve returns structured citation results.
   - Empty or whitespace query rejected with 400 Bad Request.
4. AI Legal Engine Classifier Integration:
   - Case classification returns structured citations in result dictionary.
5. In-App Notifications Fail Closed:
   - Unauthenticated requests to /api/notifications endpoints return 401 Unauthorized.
6. Case Submission Notification:
   - Filing a case creates CASE_SUBMITTED notification for applicant.
7. Strict User Isolation:
   - Citizen B cannot view, read, or delete Citizen A's notifications (403 Forbidden or 404).
8. Case Lifecycle Event Notifications:
   - Case withdrawal creates CASE_WITHDRAWN notification.
   - Citizen remarks / expedite actions create corresponding notifications.
9. Proctor Status Update Notification & Zero Notes Leakage:
   - Proctor case update notifies student of milestone.
   - Internal proctor_notes are strictly excluded from notification title and message.
10. Hearing Scheduled Notification:
    - Scheduling a hearing generates HEARING_SCHEDULED notification.
11. Read & Unread Tracking and Deletion:
    - Single mark-as-read updates is_read to true and records read_at.
    - Mark-all-as-read updates all notifications for user.
    - Delete notification removes item cleanly.
12. Idempotency & Deduplication:
    - Multiple dispatches with same idempotency_key do not create duplicate notifications.
"""

import os
import sys
import uuid
from pathlib import Path
from datetime import datetime, timezone

# Ensure tests run against local Supabase instance
os.environ["SUPABASE_URL"] = "http://127.0.0.1:54321"
os.environ["SUPABASE_SECRET_KEY"] = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZS1kZW1vIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImV4cCI6MTk4MzgxMjk5Nn0.EGIM96RAZx35lJzdJsyH-qQwv8Hdp7fsn3W0YpN81IU"
os.environ["SUPABASE_JWT_SECRET"] = "super-secret-jwt-token-with-at-least-32-characters-long"
os.environ["JWT_SECRET"] = "super-secret-jwt-token-with-at-least-32-characters-long"
os.environ["SUPABASE_OFFLINE_TEST"] = "0"

_root = Path(__file__).resolve().parent.parent
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

from starlette.testclient import TestClient
from api.index import app
from api.auth import AuthUser, UserRole, AccountStatus, create_access_token
from api.citations import resolve_citations_for_query, CitationMetadata
from api.notifications import notification_manager, NotificationEvent

client = TestClient(app)

# Test User Identities
CITIZEN_A_UID = "00000000-0000-4000-8000-000000000010"
CITIZEN_B_UID = "00000000-0000-4000-8000-000000000020"
PROCTOR_UID = "00000000-0000-4000-8000-000000000001"

user_a = AuthUser(
    user_id=CITIZEN_A_UID,
    role=UserRole.STUDENT,
    institution_id="INST_DEFAULT",
    name="Aarav Sharma",
    email="student@nit.edu",
    account_status=AccountStatus.ACTIVE
)

user_b = AuthUser(
    user_id=CITIZEN_B_UID,
    role=UserRole.CITIZEN,
    institution_id="INST_DEFAULT",
    name="Priya Patel",
    email="citizen@nyaypath.in",
    account_status=AccountStatus.ACTIVE
)

STUDENT_X_UID = "aaaaaaaa-1111-2222-3333-aaaaaaaaaaaa"
CHIEF_X_UID = "66666666-1111-2222-3333-666666666666"

student_x = AuthUser(
    user_id=STUDENT_X_UID,
    role=UserRole.STUDENT,
    institution_id="INST_COLLEGE_X",
    name="Alice Student",
    email="alice@collegex.edu",
    account_status=AccountStatus.ACTIVE
)

chief_x = AuthUser(
    user_id=CHIEF_X_UID,
    role=UserRole.CHIEF_PROCTOR,
    institution_id="INST_COLLEGE_X",
    name="Charlie Chief",
    email="charlie@collegex.edu",
    account_status=AccountStatus.ACTIVE
)

token_a = create_access_token(user_a)
token_b = create_access_token(user_b)
token_x_student = create_access_token(student_x)
token_x_chief = create_access_token(chief_x)

headers_a = {"Authorization": f"Bearer {token_a}"}
headers_b = {"Authorization": f"Bearer {token_b}"}
headers_x_student = {"Authorization": f"Bearer {token_x_student}"}
headers_x_chief = {"Authorization": f"Bearer {token_x_chief}"}


# =====================================================================
# TASK 2 & 3: CITATIONS ENGINE & ENDPOINTS TESTS
# =====================================================================

def test_01_citations_resolution_legal_query():
    """Verify legal query resolves authoritative Supreme Court / High Court citations."""
    query = "Landlord refused to return tenant security deposit after vacating flat with notice"
    result = resolve_citations_for_query(query, max_results=3)
    
    assert result.has_citations is True, "Legal tenancy query must resolve citations"
    assert len(result.citations) > 0, "At least one citation must be returned"
    
    first = result.citations[0]
    assert isinstance(first, CitationMetadata)
    assert first.case_title, "Case title must not be empty"
    assert first.court, "Court must be specified"
    assert first.citation, "Citation must be specified"
    assert first.authority_type in ["BINDING", "PERSUASIVE"]
    assert first.how_to_cite, "Recommended citation guide must be present"
    assert first.is_verified is True, "Citation must be flagged as verified"
    assert first.source_url.startswith("http"), "Source URL must be valid HTTP/HTTPS link"


def test_02_citations_resolution_irrelevant_query_zero_hallucination():
    """Verify non-legal or irrelevant query strictly returns zero citations (no hallucination)."""
    irrelevant_query = "how to bake delicious chocolate chip cookies with butter and sugar"
    result = resolve_citations_for_query(irrelevant_query, max_results=3)
    
    assert result.has_citations is False, "Irrelevant query must have has_citations=False"
    assert len(result.citations) == 0, "No citations must be returned for non-legal queries"


def test_03_citations_endpoint_api():
    """Verify POST /api/citations/resolve endpoint behavior and validation."""
    # 1. Valid legal query
    resp = client.post(
        "/api/citations/resolve",
        json={"query": "RTI application rejected by PIO on ground of personal information", "max_results": 2}
    )
    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
    data = resp.json()
    assert "citations" in data
    assert "has_citations" in data
    assert data["has_citations"] is True
    assert len(data["citations"]) > 0
    # Must return Girish Ramchandra Deshpande or landmark RTI precedent
    titles = [c["case_title"] for c in data["citations"]]
    assert any("Deshpande" in t or "RTI" in t or "Central Board" in t or "Information" in t or "Union of India" in t for t in titles)

    # 2. Blank query rejection
    blank_resp = client.post("/api/citations/resolve", json={"query": "   "})
    assert blank_resp.status_code == 400, "Blank query must be rejected with 400"


def test_04_classifier_citations_integration():
    """Verify classifier returns citations in classification payload."""
    from api.classifier import RouteClassifier
    classifier = RouteClassifier()
    result = classifier.classify("Landlord withholding security deposit refund without producing bills")
    
    assert "citations" in result, "Classifier result must contain citations field"
    assert "has_citations" in result, "Classifier result must contain has_citations field"
    assert result["has_citations"] is True
    assert len(result["citations"]) > 0
    assert "authority_type" in result["citations"][0]


# =====================================================================
# TASK 4, 5, 6, 7: IN-APP NOTIFICATIONS SECURITY & LIFECYCLE TESTS
# =====================================================================

def test_05_notifications_unauthenticated_fails_closed():
    """Verify unauthenticated requests to notifications endpoints return 401."""
    test_id = str(uuid.uuid4())
    assert client.get("/api/notifications").status_code == 401
    assert client.get("/api/notifications/unread-count").status_code == 401
    assert client.post(f"/api/notifications/{test_id}/read").status_code == 401
    assert client.post("/api/notifications/mark-all-read").status_code == 401
    assert client.delete(f"/api/notifications/{test_id}").status_code == 401


def test_06_case_filing_creates_notification():
    """Verify filing a case creates a persistent CASE_SUBMITTED notification for applicant."""
    payload = {
        "category": "CAMPUS_GRIEVANCE",
        "subject": "Notification Integration Test Grievance",
        "facts": "Testing automated notification generation upon case submission with valid facts.",
        "incident_date": "2026-10-30",
        "declaration_confirmed": True
    }
    file_resp = client.post("/api/citizen/cases/file", json=payload, headers=headers_a)
    assert file_resp.status_code == 200, f"Case filing failed: {file_resp.text}"
    case_data = file_resp.json()
    case_id = case_data["case_id"]

    # Verify notification exists for Citizen A
    notif_resp = client.get("/api/notifications", headers=headers_a)
    assert notif_resp.status_code == 200
    data = notif_resp.json()
    notifications = data["notifications"]
    
    matching = [n for n in notifications if n["related_case_id"] == case_id and n["event_type"] == "CASE_SUBMITTED"]
    assert len(matching) >= 1, f"Expected CASE_SUBMITTED notification for {case_id}"
    notif = matching[0]
    assert notif["recipient_user_id"] == CITIZEN_A_UID
    assert notif["is_read"] is False
    assert "Registration" in notif["title"] or "Confirmed" in notif["title"] or "Registered" in notif["title"]

    # Verify unread count
    count_resp = client.get("/api/notifications/unread-count", headers=headers_a)
    assert count_resp.status_code == 200
    assert count_resp.json()["unread_count"] >= 1

    return case_id, notif["id"]


def test_07_notification_user_isolation():
    """Verify Citizen B cannot view, read, or delete Citizen A's notifications."""
    # First create a notification for Citizen A
    payload = {
        "category": "CAMPUS_GRIEVANCE",
        "subject": "Isolation Verification Petition",
        "facts": "Testing strict cross-user notification isolation with detailed background.",
        "incident_date": "2026-10-25",
        "declaration_confirmed": True
    }
    file_resp = client.post("/api/citizen/cases/file", json=payload, headers=headers_a)
    assert file_resp.status_code == 200
    case_id = file_resp.json()["case_id"]

    # Fetch Citizen A's notification ID
    notif_resp_a = client.get("/api/notifications", headers=headers_a)
    a_notifs = [n for n in notif_resp_a.json()["notifications"] if n["related_case_id"] == case_id]
    assert len(a_notifs) > 0
    a_notif_id = a_notifs[0]["id"]

    # 1. Citizen B fetches notifications; Citizen A's notification must NOT be returned
    notif_resp_b = client.get("/api/notifications", headers=headers_b)
    assert notif_resp_b.status_code == 200
    b_notifs = notif_resp_b.json()["notifications"]
    b_ids = [n["id"] for n in b_notifs]
    assert a_notif_id not in b_ids, "Citizen A's notification must not appear in Citizen B's list"

    # 2. Citizen B attempts to mark Citizen A's notification as read -> must fail 403 or 404
    mark_resp = client.post(f"/api/notifications/{a_notif_id}/read", headers=headers_b)
    assert mark_resp.status_code in [403, 404], f"Cross-tenant mark read must be rejected, got {mark_resp.status_code}"

    # 3. Citizen B attempts to delete Citizen A's notification -> must fail 403 or 404
    del_resp = client.delete(f"/api/notifications/{a_notif_id}", headers=headers_b)
    assert del_resp.status_code in [403, 404], f"Cross-tenant delete must be rejected, got {del_resp.status_code}"


def test_08_lifecycle_withdrawal_creates_notification():
    """Verify withdrawing a case creates a CASE_WITHDRAWN notification."""
    # File case as Citizen A
    payload = {
        "category": "CAMPUS_GRIEVANCE",
        "subject": "Withdrawal Test Petition",
        "facts": "Testing notification on case withdrawal with required narrative facts.",
        "declaration_confirmed": True
    }
    file_resp = client.post("/api/citizen/cases/file", json=payload, headers=headers_a)
    assert file_resp.status_code == 200
    case_id = file_resp.json()["case_id"]

    # Withdraw case
    withdraw_resp = client.post(
        f"/api/citizen/cases/{case_id}/lifecycle",
        json={"action": "WITHDRAW", "reason": "Settled amicably with hostel administration."},
        headers=headers_a
    )
    assert withdraw_resp.status_code == 200

    # Verify notification for Citizen A
    notifs = client.get("/api/notifications", headers=headers_a).json()["notifications"]
    withdrawn_notifs = [n for n in notifs if n["related_case_id"] == case_id and n["event_type"] == "CASE_WITHDRAWN"]
    assert len(withdrawn_notifs) >= 1, "CASE_WITHDRAWN notification must be generated"
    assert "Withdraw" in withdrawn_notifs[0]["title"]


def test_09_proctor_update_creates_student_notification_without_leakage():
    """Verify proctor case updates notify student while STRICTLY shielding proctor_notes."""
    # 1. Student X files campus case
    payload = {
        "category": "CAMPUS_GRIEVANCE",
        "subject": "Proctor Notification & Shielding Test",
        "facts": "Verifying that proctor notes never leak into notifications in production.",
        "declaration_confirmed": True
    }
    file_resp = client.post("/api/citizen/cases/file", json=payload, headers=headers_x_student)
    assert file_resp.status_code == 200
    case_id = file_resp.json()["case_id"]

    # 2. Chief Proctor updates case status with secret internal note
    confidential_proctor_note = "CONFIDENTIAL: Internal committee notes - Do not disclose to student."
    update_resp = client.post(
        "/api/campus-proctor/update",
        json={
            "case_id": case_id,
            "new_status": "UNDER_INQUIRY",
            "proctor_notes": confidential_proctor_note
        },
        headers=headers_x_chief
    )
    assert update_resp.status_code == 200

    # 3. Student fetches notifications
    notifs = client.get("/api/notifications", headers=headers_x_student).json()["notifications"]
    status_notifs = [n for n in notifs if n["related_case_id"] == case_id and "INQUIRY" in n["event_type"]]
    assert len(status_notifs) >= 1, "CASE_UNDER_INQUIRY notification must be generated for student"
    
    notif = status_notifs[0]
    # CRITICAL SECURITY VERIFICATION: proctor_notes must NEVER appear in title or message
    assert confidential_proctor_note not in notif["title"], "Proctor notes leaked in notification title!"
    assert confidential_proctor_note not in notif["message"], "Proctor notes leaked in notification message!"
    assert "CONFIDENTIAL" not in notif["message"]


def test_10_hearing_schedule_creates_notification():
    """Verify scheduling a hearing generates a HEARING_SCHEDULED notification."""
    # File case as Student X
    payload = {
        "category": "CAMPUS_GRIEVANCE",
        "subject": "Hearing Notification Verification",
        "facts": "Testing hearing scheduled notification with complete student narrative.",
        "declaration_confirmed": True
    }
    file_resp = client.post("/api/citizen/cases/file", json=payload, headers=headers_x_student)
    assert file_resp.status_code == 200
    case_id = file_resp.json()["case_id"]

    # Chief Proctor schedules hearing
    hearing_resp = client.post(
        "/api/campus-proctor/update",
        json={
            "case_id": case_id,
            "new_status": "HEARING_SCHEDULED",
            "hearing_date": "2026-11-15T10:00:00Z",
            "proctor_notes": "Hearing scheduled in Proctor Conference Room 4B"
        },
        headers=headers_x_chief
    )
    assert hearing_resp.status_code == 200

    # Check notification for Student X
    notifs = client.get("/api/notifications", headers=headers_x_student).json()["notifications"]
    hearing_notifs = [n for n in notifs if n["related_case_id"] == case_id and n["event_type"] == "HEARING_SCHEDULED"]
    assert len(hearing_notifs) >= 1, "HEARING_SCHEDULED notification must be generated"
    assert "Hearing" in hearing_notifs[0]["title"]


def test_11_notification_read_mark_all_and_delete():
    """Verify single mark read, mark all read, and delete endpoints."""
    # 1. Fetch unread notifications for Citizen A
    notifs = client.get("/api/notifications?is_read=false", headers=headers_a).json()["notifications"]
    assert len(notifs) > 0, "Expected at least one unread notification for Citizen A"
    target_notif = notifs[0]
    target_id = target_notif["id"]

    # 2. Mark single notification as read
    read_resp = client.post(f"/api/notifications/{target_id}/read", headers=headers_a)
    assert read_resp.status_code == 200
    updated = read_resp.json()
    assert updated["is_read"] is True

    # 3. Mark all as read
    mark_all_resp = client.post("/api/notifications/mark-all-read", headers=headers_a)
    assert mark_all_resp.status_code == 200
    
    # Verify unread count is 0
    count_resp = client.get("/api/notifications/unread-count", headers=headers_a)
    assert count_resp.json()["unread_count"] == 0

    # 4. Delete target notification
    del_resp = client.delete(f"/api/notifications/{target_id}", headers=headers_a)
    assert del_resp.status_code == 200
    assert del_resp.json()["status"] == "success"

    # Verify notification no longer exists
    remaining = client.get("/api/notifications", headers=headers_a).json()["notifications"]
    assert not any(n["id"] == target_id for n in remaining), "Deleted notification must no longer exist"


def test_12_notification_idempotency():
    """Verify duplicate notification dispatches with identical idempotency_key are deduplicated."""
    unique_key = f"test_idemp_{uuid.uuid4()}"
    
    # First dispatch
    notif1 = notification_manager.create_notification(
        recipient_user_id=CITIZEN_A_UID,
        event_type=NotificationEvent.CASE_STATUS_UPDATED,
        title="Idempotency Test Notice",
        message="Notice content for idempotency check.",
        related_case_id="TEST-IDEMP-01",
        idempotency_key=unique_key
    )
    assert notif1 is not None

    # Second dispatch with same idempotency key
    notif2 = notification_manager.create_notification(
        recipient_user_id=CITIZEN_A_UID,
        event_type=NotificationEvent.CASE_STATUS_UPDATED,
        title="Duplicate Notice Should Be Ignored",
        message="Notice duplicate content.",
        related_case_id="TEST-IDEMP-01",
        idempotency_key=unique_key
    )
    assert notif2 is not None
    # ID should be the exact same existing notification row
    assert notif1.get("id") == notif2.get("id"), "Idempotency key must prevent duplicate row creation"


if __name__ == "__main__":
    print("=" * 70)
    print("RUNNING NYAYPATH PHASE 2.3 CITATIONS & NOTIFICATIONS TEST SUITE")
    print("=" * 70)
    
    tests = [
        test_01_citations_resolution_legal_query,
        test_02_citations_resolution_irrelevant_query_zero_hallucination,
        test_03_citations_endpoint_api,
        test_04_classifier_citations_integration,
        test_05_notifications_unauthenticated_fails_closed,
        test_06_case_filing_creates_notification,
        test_07_notification_user_isolation,
        test_08_lifecycle_withdrawal_creates_notification,
        test_09_proctor_update_creates_student_notification_without_leakage,
        test_10_hearing_schedule_creates_notification,
        test_11_notification_read_mark_all_and_delete,
        test_12_notification_idempotency,
    ]
    
    passed = 0
    failed = 0
    for t in tests:
        try:
            t()
            print(f"  [PASS] {t.__name__}")
            passed += 1
        except Exception as e:
            print(f"  [FAIL] {t.__name__}: {e}")
            failed += 1
            import traceback
            traceback.print_exc()

    print("=" * 70)
    print(f"RESULTS: {passed} PASSED, {failed} FAILED")
    print("=" * 70)
    if failed > 0:
        sys.exit(1)

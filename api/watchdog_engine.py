import logging
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, List, Optional, Tuple

logger = logging.getLogger(__name__)

# Statutory RTI constants under RTI Act, 2005
RTI_NORMAL_DEADLINE_DAYS = 30  # Section 7(1)
RTI_LIFE_LIBERTY_DEADLINE_HOURS = 48  # Proviso to Section 7(1)
RTI_APIO_EXTRA_DAYS = 5  # Proviso to Section 5(2) (5 days added when received via APIO)
RTI_THIRD_PARTY_EXTRA_DAYS = 10  # Section 11(1) (10 days added for third party representation)
RTI_FIRST_APPEAL_WINDOW_DAYS = 30  # Section 19(1) (Within 30 days of expiry of PIO window)
SECTION_20_DAILY_PENALTY_INR = 250  # Section 20(1)
SECTION_20_MAX_PENALTY_INR = 25000  # Section 20(1) cap

# Authoritative Statutory SLA Rules Dictionary (Verified Enactment Date: 2005-06-15)
STATUTORY_SLA_RULES: Dict[str, Dict[str, Any]] = {
    "RTI_STANDARD": {
        "rule_name": "RTI Section 7(1) Standard Statutory Window",
        "statutory_source": "Section 7(1), Right to Information Act, 2005",
        "verified_date": "2005-06-15",
        "deadline_days": 30,
        "is_statutory": True,
        "notes": "Public Information Officer must provide information or reject the request within thirty (30) days of receipt."
    },
    "RTI_LIFE_LIBERTY": {
        "rule_name": "RTI Life and Liberty Expedited Window",
        "statutory_source": "Proviso to Section 7(1), Right to Information Act, 2005",
        "verified_date": "2005-06-15",
        "deadline_hours": 48,
        "is_statutory": True,
        "notes": "Where the information sought concerns the life or liberty of a person, it must be provided within forty-eight (48) hours of receipt."
    },
    "RTI_APIO_TRANSFER": {
        "rule_name": "RTI Application Received via Assistant PIO (APIO)",
        "statutory_source": "Proviso to Section 5(2), Right to Information Act, 2005",
        "verified_date": "2005-06-15",
        "deadline_days": 35,
        "is_statutory": True,
        "notes": "Where an application is submitted to an Assistant Public Information Officer, five (5) additional days are added to the normal response window."
    },
    "RTI_THIRD_PARTY": {
        "rule_name": "RTI Section 11(3) Third-Party Disclosure Determination",
        "statutory_source": "Section 11(3), Right to Information Act, 2005",
        "verified_date": "2005-06-15",
        "deadline_days": 40,
        "is_statutory": True,
        "notes": (
            "Section 11(3) mandates that the Public Information Officer shall make a decision within "
            "forty (40) days after receipt of request where statutory third-party process applies, following the 5-day "
            "notice requirement under Section 11(1) and the 10-day representation window under Section 11(2)."
        ),
        "notice_window_days": 5,  # Section 11(1)
        "representation_window_days": 10,  # Section 11(2)
        "decision_window_days": 40  # Section 11(3)
    }
}


def parse_iso_datetime(dt_str: Optional[str], default: Optional[datetime] = None) -> datetime:
    """Parses an ISO format datetime string safely into UTC aware datetime."""
    if not dt_str:
        return default or datetime.now(timezone.utc)
    try:
        clean_str = dt_str.replace("Z", "+00:00")
        dt = datetime.fromisoformat(clean_str)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except Exception as e:
        logger.warning(f"Failed to parse datetime '{dt_str}': {e}. Using default.")
        return default or datetime.now(timezone.utc)


def calculate_deadlines(
    filing_date_str: Optional[str] = None,
    life_liberty: bool = False,
    via_apio: bool = False,
    third_party: bool = False,
    fee_exclusion_days: int = 0
) -> Dict[str, Any]:
    """
    Deterministically computes statutory deadlines from a filing date according to verified RTI rules.
    Supports Section 7(1) standard, life-liberty exception, APIO addition (+5d), third-party (+10d),
    and fee calculation exclusions under Section 7(3)(a).
    """
    filing_dt = parse_iso_datetime(filing_date_str)
    
    if life_liberty:
        rule_key = "RTI_LIFE_LIBERTY"
        response_due_dt = filing_dt + timedelta(hours=RTI_LIFE_LIBERTY_DEADLINE_HOURS)
    else:
        total_days = RTI_NORMAL_DEADLINE_DAYS
        if via_apio:
            total_days += RTI_APIO_EXTRA_DAYS
            rule_key = "RTI_APIO_TRANSFER"
        elif third_party:
            total_days += RTI_THIRD_PARTY_EXTRA_DAYS
            rule_key = "RTI_THIRD_PARTY"
        else:
            rule_key = "RTI_STANDARD"

        # Apply statutory fee exclusion under Proviso to Section 7(3)(a)
        if fee_exclusion_days > 0:
            total_days += fee_exclusion_days

        response_due_dt = filing_dt + timedelta(days=total_days)

    first_appeal_due_dt = response_due_dt + timedelta(days=RTI_FIRST_APPEAL_WINDOW_DAYS)
    rule_info = STATUTORY_SLA_RULES[rule_key]

    return {
        "rule_key": rule_key,
        "rule_name": rule_info["rule_name"],
        "statutory_source": rule_info["statutory_source"],
        "verified_date": rule_info["verified_date"],
        "filing_date": filing_dt.isoformat(),
        "response_due_date": response_due_dt.isoformat(),
        "first_appeal_due_date": first_appeal_due_dt.isoformat(),
        "fee_exclusion_days_applied": fee_exclusion_days
    }


def calculate_section_20_penalty(
    response_due_date_str: str,
    response_received_at_str: Optional[str] = None,
    now: Optional[datetime] = None
) -> Dict[str, Any]:
    """
    Deterministically calculates Section 20(1) potential statutory penalty exposure.
    - Rs 250 / day for unjustified delay
    - Capped at Rs 25,000 maximum
    """
    current_dt = now or datetime.now(timezone.utc)
    due_dt = parse_iso_datetime(response_due_date_str, current_dt)
    
    if response_received_at_str:
        cutoff_dt = parse_iso_datetime(response_received_at_str, current_dt)
    else:
        cutoff_dt = current_dt

    if cutoff_dt <= due_dt:
        return {
            "is_overdue": False,
            "days_overdue": 0,
            "section_20_penalty_inr": 0,
            "penalty_rate_per_day": SECTION_20_DAILY_PENALTY_INR,
            "penalty_max_cap": SECTION_20_MAX_PENALTY_INR,
            "statutory_note": "Potential Section 20 penalty calculated under Section 20(1) of RTI Act, 2005."
        }

    diff = cutoff_dt - due_dt
    full_days_overdue = max(0, int(diff.total_seconds() // 86400))
    if diff.total_seconds() > 0 and full_days_overdue == 0:
        full_days_overdue = 1

    calculated_penalty = min(SECTION_20_MAX_PENALTY_INR, full_days_overdue * SECTION_20_DAILY_PENALTY_INR)

    return {
        "is_overdue": True,
        "days_overdue": full_days_overdue,
        "section_20_penalty_inr": calculated_penalty,
        "penalty_rate_per_day": SECTION_20_DAILY_PENALTY_INR,
        "penalty_max_cap": SECTION_20_MAX_PENALTY_INR,
        "statutory_note": "Potential statutory exposure under Section 20(1). Formal imposition subject to Information Commission proceedings."
    }


def notify_case_event(case_data: Dict[str, Any], event_type: str, event_metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Notification abstraction for watchdog events."""
    event = {
        "event_id": f"evt_{event_type}_{datetime.now(timezone.utc).timestamp()}",
        "event_type": event_type,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "case_id": case_data.get("case_id"),
        "metadata": event_metadata or {}
    }
    events = case_data.setdefault("watchdog_events", [])
    events.append(event)
    return event


def evaluate_watchdog_state(case: Dict[str, Any], now: Optional[datetime] = None) -> Dict[str, Any]:
    """
    Evaluates watchdog status, deterministic statutory deadlines, stage duration, and elapsed time.
    Strictly differentiates between verified statutory categories (RTI Act, 2005) and unconfigured categories.
    For non-statutory categories, returns 'No verified statutory deadline configured for this case.'
    """
    current_dt = now or datetime.now(timezone.utc)
    category = (case.get("category") or case.get("case_type") or "").upper()
    is_rti = "RTI" in category or category == "RIGHT_TO_INFORMATION"
    
    filing_date_str = case.get("filing_date") or case.get("created_at") or case.get("submission_date")
    filing_dt = parse_iso_datetime(filing_date_str, current_dt)

    # 1. Deterministic Elapsed Time Metrics
    elapsed_seconds = max(0, int((current_dt - filing_dt).total_seconds()))
    elapsed_days = elapsed_seconds // 86400
    elapsed_hours = (elapsed_seconds % 86400) // 3600
    case["time_elapsed_since_submission_seconds"] = elapsed_seconds
    case["time_elapsed_since_submission_formatted"] = f"{elapsed_days}d {elapsed_hours}h"

    # Stage duration metrics
    stage_entered_at_str = case.get("status_updated_at") or case.get("updated_at") or filing_date_str
    stage_entered_dt = parse_iso_datetime(stage_entered_at_str, filing_dt)
    stage_seconds = max(0, int((current_dt - stage_entered_dt).total_seconds()))
    stage_days = stage_seconds // 86400
    stage_hours = (stage_seconds % 86400) // 3600
    case["time_in_current_stage_seconds"] = stage_seconds
    case["time_in_current_stage_formatted"] = f"{stage_days}d {stage_hours}h"

    case["current_responsible_authority"] = (
        case.get("department") or case.get("institution_name") or
        ("Public Information Officer (PIO)" if is_rti else "Administrative Inquiry Committee")
    )

    # 2. Statutory SLA Evaluation (RTI Only)
    if is_rti:
        life_liberty = bool(case.get("life_liberty_flag") or case.get("life_liberty"))
        via_apio = bool(case.get("via_apio_flag") or case.get("via_apio") or case.get("received_via_apio"))
        third_party = bool(case.get("third_party_flag") or case.get("third_party"))

        # Fee calculation exclusion: Proviso to Section 7(3)(a)
        fee_exclusion_days = 0
        fee_int_str = case.get("fee_intimation_date")
        fee_paid_str = case.get("fee_paid_date")
        if fee_int_str and fee_paid_str:
            fee_int_dt = parse_iso_datetime(fee_int_str)
            fee_paid_dt = parse_iso_datetime(fee_paid_str)
            if fee_paid_dt > fee_int_dt:
                fee_exclusion_days = max(0, (fee_paid_dt.date() - fee_int_dt.date()).days)

        calculated = calculate_deadlines(
            filing_date_str=filing_date_str,
            life_liberty=life_liberty,
            via_apio=via_apio,
            third_party=third_party,
            fee_exclusion_days=fee_exclusion_days
        )

        response_due_date_str = calculated["response_due_date"]
        first_appeal_due_date_str = calculated["first_appeal_due_date"]
        response_due_dt = parse_iso_datetime(response_due_date_str)

        case["has_statutory_deadline"] = True
        case["statutory_rule_name"] = calculated["rule_name"]
        case["statutory_source"] = calculated["statutory_source"]
        case["statutory_verification_date"] = calculated["verified_date"]
        case["statutory_deadline_display"] = response_due_dt.strftime("%Y-%m-%d %H:%M UTC")
        case["statutory_deadline_message"] = None

        # Statutory Third-Party Breakdown (Section 11)
        if third_party:
            case["third_party_notice_due_date"] = (filing_dt + timedelta(days=5)).isoformat()
            case["third_party_notice_source"] = "Section 11(1), Right to Information Act, 2005 (Notice within 5 days of receipt)"
            case["third_party_representation_source"] = "Section 11(2), Right to Information Act, 2005 (Representation within 10 days of notice)"
            case["third_party_decision_source"] = "Section 11(3), Right to Information Act, 2005 (Decision within 40 days of request)"

        case["fee_exclusion_applied"] = fee_exclusion_days > 0
        if fee_exclusion_days > 0:
            case["fee_exclusion_statutory_source"] = "Proviso to Section 7(3)(a), Right to Information Act, 2005"
            case["fee_exclusion_days"] = fee_exclusion_days

        case["response_due_date"] = response_due_date_str
        case["first_appeal_due_date"] = first_appeal_due_date_str

        response_received_at_str = case.get("response_date") or case.get("pio_response_date")
        has_response = bool(response_received_at_str)

        penalty_info = calculate_section_20_penalty(
            response_due_date_str=response_due_date_str,
            response_received_at_str=response_received_at_str if has_response else None,
            now=current_dt
        )
        case["section_20_penalty_inr"] = penalty_info["section_20_penalty_inr"]

        time_remaining_seconds = max(0, int((response_due_dt - current_dt).total_seconds()))
        days_remaining = max(0, int((response_due_dt.date() - current_dt.date()).days))
        is_due_today = (response_due_dt.date() == current_dt.date()) or (0 < (response_due_dt - current_dt).total_seconds() <= 86400 and days_remaining == 0)
        is_overdue = current_dt > response_due_dt

        case["time_remaining_seconds"] = time_remaining_seconds
        case["days_remaining"] = days_remaining
        case["is_overdue"] = is_overdue
        case["days_overdue"] = penalty_info["days_overdue"]

        next_action = "Awaiting official PIO statutory disclosure" if not has_response else "Review response or proceed with first appeal"
    else:
        # Non-RTI Category: No arbitrary 30-day countdown
        case["has_statutory_deadline"] = False
        case["statutory_rule_name"] = None
        case["statutory_source"] = None
        case["statutory_verification_date"] = None
        case["statutory_deadline_display"] = None
        case["statutory_deadline_message"] = "No verified statutory deadline configured for this case."
        case["response_due_date"] = None
        case["first_appeal_due_date"] = None
        case["is_overdue"] = False
        case["days_remaining"] = None
        case["days_overdue"] = 0
        case["time_remaining_seconds"] = None
        case["section_20_penalty_inr"] = 0

        curr_st = (case.get("status") or "ACTIVE").upper()
        if curr_st in ("SUBMITTED", "PENDING", "FILED"):
            next_action = "Preliminary scrutiny and administrative assignment"
        elif curr_st in ("HEARING_SCHEDULED", "UNDER_INQUIRY"):
            next_action = "Committee inquiry and evidence examination"
        elif curr_st in ("RESOLVED", "CLOSED"):
            next_action = "Case concluded; verification of compliance"
        else:
            next_action = "Administrative review by dealing officer"

    case["next_expected_action"] = next_action

    # 3. Notification state and event emissions
    notification_state = case.setdefault("notification_state", {
        "started_sent": False,
        "seven_day_warning_sent": False,
        "three_day_warning_sent": False,
        "due_today_sent": False,
        "overdue_sent": False,
        "deemed_refusal_sent": False,
        "appeal_ready_sent": False,
        "response_received_sent": False
    })

    if case.get("watchdog_enabled", True) and not notification_state.get("started_sent"):
        notify_case_event(case, "WATCHDOG_STARTED", {
            "filing_date": filing_date_str,
            "has_statutory_deadline": case["has_statutory_deadline"]
        })
        notification_state["started_sent"] = True

    # 4. Status Determination
    watchdog_status = "ACTIVE"
    appeal_eligible = False

    if case.get("status") == "CLOSED":
        watchdog_status = "CLOSED"
    elif is_rti:
        if has_response:
            watchdog_status = "RESPONSE_RECEIVED"
            if not notification_state.get("response_received_sent"):
                notify_case_event(case, "RESPONSE_RECEIVED", {
                    "received_at": response_received_at_str,
                    "was_overdue": is_overdue,
                    "days_overdue": penalty_info["days_overdue"]
                })
                notification_state["response_received_sent"] = True
            if case.get("first_appeal_draft") or case.get("status") == "pio_analyzed":
                appeal_eligible = True
        elif is_overdue:
            watchdog_status = "DEEMED_REFUSAL"
            appeal_eligible = True
            if not notification_state.get("overdue_sent"):
                notify_case_event(case, "DEADLINE_BREACHED", {
                    "due_date": response_due_date_str,
                    "days_overdue": penalty_info["days_overdue"]
                })
                notification_state["overdue_sent"] = True
    else:
        # Non-RTI: follows case status directly
        watchdog_status = (case.get("status") or "ACTIVE").upper()

    case["watchdog_status"] = watchdog_status
    case["computed_status"] = watchdog_status
    case["appeal_eligible"] = appeal_eligible
    case["last_watchdog_check_at"] = current_dt.isoformat()

    return case


def run_scheduled_watchdog(case_manager_instance, now: Optional[datetime] = None) -> Dict[str, Any]:
    """Batch execution runner for Vercel Cron."""
    current_dt = now or datetime.now(timezone.utc)
    active_cases = case_manager_instance.list_active_cases()
    processed_count = 0
    updated_count = 0
    errors: List[str] = []

    for case in active_cases:
        case_id = case.get("id")
        if not case_id:
            continue
        processed_count += 1
        try:
            evaluated_case = evaluate_watchdog_state(case, now=current_dt)
            case_manager_instance.update_case(case_id, evaluated_case)
            updated_count += 1
        except Exception as e:
            err_msg = f"Error evaluating watchdog for case {case_id}: {e}"
            logger.error(err_msg)
            errors.append(err_msg)

    return {
        "status": "success" if not errors else "partial_success",
        "timestamp": current_dt.isoformat(),
        "processed_count": processed_count,
        "updated_count": updated_count,
        "error_count": len(errors),
        "errors": errors[:5]
    }

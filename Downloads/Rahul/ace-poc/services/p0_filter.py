"""ACE POC - P0 gating filter for cases and legislation."""
from datetime import datetime, timedelta

from config import settings
from dateutil import parser as date_parser


def passes_p0_case(
    court: str | None,
    decision_date: str | datetime | None,
    shepard_letters: str | None,
) -> tuple[bool, str]:
    """
    P0 filter for cases.
    Returns (passed: bool, reason: str).
    """
    if not court:
        return False, "Missing court"

    court_ok = any(
        p0 in (court or "") for p0 in settings.p0_courts
    ) or "Supreme" in (court or "") or "Circuit" in (court or "")

    if not court_ok:
        return False, f"Court '{court}' not in P0 list"

    if decision_date:
        try:
            if isinstance(decision_date, str):
                d = date_parser.parse(decision_date).date()
            else:
                d = decision_date.date() if hasattr(decision_date, "date") else decision_date
            cutoff = (datetime.utcnow() - timedelta(days=settings.case_decision_days_limit)).date()
            if d < cutoff:
                return False, f"Decision date {d} older than {settings.case_decision_days_limit} days"
        except Exception:
            pass  # If we can't parse, allow through for POC

    if shepard_letters:
        letters = [s.strip().upper() for s in (shepard_letters or "").split(",") if s.strip()]
        has_signal = any(
            p in letters for p in [p.upper() for p in settings.p0_shepard_letters]
        )
        if not has_signal and letters:
            return False, "No P0 Shepard signal"
    else:
        # No Shepard data - for POC we allow through; real system might require it
        pass

    return True, "Passed P0"


def passes_p0_legislation(
    effect_type: str | None,
    effective_date: str | datetime | None,
) -> tuple[bool, str]:
    """
    P0 filter for legislation.
    Returns (passed: bool, reason: str).
    """
    valid_effects = {"amended", "new", "added"}
    if effect_type and effect_type.lower() not in valid_effects:
        return False, f"Effect type '{effect_type}' not in allowed list"

    if effective_date:
        try:
            if isinstance(effective_date, str):
                d = date_parser.parse(effective_date).date()
            else:
                d = effective_date.date() if hasattr(effective_date, "date") else effective_date
            if d > datetime.utcnow().date():
                return False, "Effective date in future"
        except Exception:
            pass

    return True, "Passed P0"

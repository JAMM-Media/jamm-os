# app/core/tax_deadlines.py
"""
IRS filing deadline lookup for JAMM PX engagement types.

Each entry maps an EngagementType value to a (month, day) tuple
representing the standard IRS filing deadline.

For types with no fixed IRS deadline (advisory, bookkeeping, custom),
the value is None — no filing_deadline is auto-set on those engagements.

tax_return_706 is a special case: the IRS deadline is 9 months from the
date of death, which is client-specific. We store None here and require
the firm to set filing_deadline manually when creating a 706 engagement.
"""

from app.core.enums import EngagementType

# Maps EngagementType → (month, day) or None
TAX_DEADLINES: dict[str, tuple[int, int] | None] = {
    EngagementType.tax_return_1040:       (4, 15),   # April 15
    EngagementType.tax_return_1120:       (4, 15),   # April 15
    EngagementType.tax_return_1120s:      (3, 15),   # March 15
    EngagementType.tax_return_1065:       (3, 15),   # March 15
    EngagementType.tax_return_1041:       (4, 15),   # April 15
    EngagementType.tax_return_706:        None,       # 9 months from date of death — set manually
    EngagementType.amended_return_1040x:  None,       # No fixed IRS deadline
    EngagementType.extension_4868:        (4, 15),   # Must be filed by original deadline
    EngagementType.extension_7004:        (3, 15),   # Must be filed by original deadline (varies by entity)
    EngagementType.extension_8868:        (5, 15),   # May 15 for most exempt orgs
    EngagementType.payroll_tax_941:       None,       # Quarterly — no single annual deadline
    EngagementType.tax_planning_advisory: None,
    EngagementType.bookkeeping_monthly:   None,
    EngagementType.bookkeeping_quarterly: None,
    EngagementType.audit_representation:  None,
    EngagementType.other_advisory:        None,
    EngagementType.custom:                None,
}


def get_filing_deadline(engagement_type: str, tax_year: int | None = None) -> tuple[int, int] | None:
    """
    Return the (month, day) IRS filing deadline for a given engagement type,
    or None if no fixed deadline applies.

    tax_year is accepted for future use (e.g. weekend/holiday adjustments)
    but not yet applied — returns the standard deadline directly.
    """
    return TAX_DEADLINES.get(engagement_type)

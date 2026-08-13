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

    # Individual tax
    EngagementType.tax_return_1040nr:     (4, 15),   # June 15 applies when no US wage withholding, firms adjust manually per client

    # Business and entity tax
    EngagementType.tax_return_990:        (5, 15),   # May 15 for calendar-year exempt organizations
    EngagementType.tax_return_709:        (4, 15),
    EngagementType.amended_return_business: None,     # No fixed IRS deadline

    # Payroll and information reporting
    EngagementType.payroll_tax_940:       (1, 31),
    EngagementType.payroll_processing:    None,       # Recurring service, no filing deadline
    EngagementType.information_returns_1099_w2: (1, 31),  # Recipient copy and most filing deadlines

    # Sales tax
    EngagementType.sales_use_tax:         None,       # Varies by state, set manually

    # Foreign reporting
    EngagementType.fbar_international:    (4, 15),   # Automatic extension to October 15 applies

    # Bookkeeping and accounting
    EngagementType.bookkeeping_cleanup:   None,
    EngagementType.accounting_system_setup: None,

    # Financial statements
    EngagementType.financial_statement_compilation: None,
    EngagementType.financial_statement_review: None,
    EngagementType.financial_statement_audit: None,
    EngagementType.agreed_upon_procedures: None,

    # Advisory and representation
    EngagementType.fractional_cfo:        None,
    EngagementType.entity_formation:      None,
    EngagementType.irs_notice_resolution: None,
    EngagementType.tax_resolution:        None,

    # Specialty
    EngagementType.rd_tax_credit_study:   None,
    EngagementType.nonprofit_formation_exemption: None,  # Form 1023 has no fixed calendar deadline
    EngagementType.benefit_plan_5500:     (7, 31),   # Last day of seventh month after plan year end, July 31 for calendar-year plans
    EngagementType.business_valuation:    None,
    EngagementType.business_personal_property_tax: None,  # Varies by state and locality, set manually
    EngagementType.cost_segregation_study: None,
    EngagementType.transaction_advisory:  None,
}


def get_filing_deadline(engagement_type: str, tax_year: int | None = None) -> tuple[int, int] | None:
    """
    Return the (month, day) IRS filing deadline for a given engagement type,
    or None if no fixed deadline applies.

    tax_year is accepted for future use (e.g. weekend/holiday adjustments)
    but not yet applied — returns the standard deadline directly.
    """
    return TAX_DEADLINES.get(engagement_type)

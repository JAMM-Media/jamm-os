# app/core/intelligence_constants.py

"""
Every constant in this file is Andrew-owned and changed only by his decision.

Ratchet rule (mirrors the intelligence spec): tightening any threshold here
is allowed without sign-off. Loosening any threshold requires an explicit
manual decision by Andrew.
"""

# Andrew-owned. Significance alpha for the firm_facing gate bar.
FIRM_FACING_SIGNIFICANCE_ALPHA = 0.01

# Andrew-owned. Significance alpha for the internal gate bar.
INTERNAL_SIGNIFICANCE_ALPHA = 0.05

# Andrew-owned. Internal bar requires half the firm-facing data-sufficiency floors.
INTERNAL_SUFFICIENCY_FACTOR = 0.5

# Andrew-owned. Ceiling applied to every individual severity modifier before
# it is multiplied into a finding's severity_score.
SEVERITY_MODIFIER_CAP = 2.0

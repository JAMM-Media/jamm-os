# scripts/seed_demo_firm_config.py
"""
Config for scripts/seed_demo_firm.py.

All tunable parameters for the Cedar and Vance Advisors (DEMO) firm live here,
separated from the generation/choreography logic in seed_demo_firm.py.
Nothing in this file computes calendar dates directly - the window is always
relative to the run date, resolved at runtime in seed_demo_firm.py.
"""

FIRM = {
    "name": "Cedar and Vance Advisors (DEMO)",
    "slug": "cedar-and-vance-demo",
    "subscription_tier": "pro",
}

DEMO_PASSWORD = "DemoSeed2026!"

# ---------------------------------------------------------------------------
# Staff personas
# ---------------------------------------------------------------------------
# login_window: (hour_start, hour_end) local-clock hour range for weekday logins
# after_hours_window: (hour_start, hour_end) or None - only active persona types
#   get after-hours activity, and only in March/April
# weekend: whether persona works Saturdays during March/April
# time_entry_lag: "same_day" | "next_morning" | "catch_up_2_3_day"
# activity_weight: relative share of daily staff-activity events this persona drives
STAFF_PERSONAS = [
    {
        "key": "owner",
        "role": "firm_owner",
        "full_name": "Dana Vance",
        "email": "dana.vance@cedarvance-demo.com",
        "login_window": (7, 8),  # 7:15-7:45am modeled as a narrow morning band
        "login_minute_range": (15, 45),
        "after_hours_window": None,
        "weekend": False,
        "time_entry_lag": "same_day",
        "activity_weight": 0.10,
        "touches_hero_share": 0.9,  # touches nearly all hero engagements (reviewer)
        "chat_active": True,
    },
    {
        "key": "manager",
        "role": "manager",
        "full_name": "Priya Nair",
        "email": "priya.nair@cedarvance-demo.com",
        "login_window": (7, 9),
        "login_minute_range": (0, 59),
        "after_hours_window": (19, 22),
        "weekend": True,
        "time_entry_lag": "same_day",
        "activity_weight": 0.18,
        "touches_hero_share": 0.6,  # carries the complex hero clients
        "chat_active": True,
    },
    {
        "key": "preparer_a",
        "role": "staff",
        "full_name": "Marcus Ito",
        "email": "marcus.ito@cedarvance-demo.com",
        "login_window": (7, 9),
        "login_minute_range": (0, 59),
        "after_hours_window": None,
        "weekend": False,
        "time_entry_lag": "same_day",
        "activity_weight": 0.22,
        "touches_hero_share": 0.15,
        "chat_active": True,
    },
    {
        "key": "preparer_b",
        "role": "staff",
        "full_name": "Elena Cho",
        "email": "elena.cho@cedarvance-demo.com",
        "login_window": (7, 9),
        "login_minute_range": (0, 59),
        "after_hours_window": (19, 22),
        "weekend": False,
        "time_entry_lag": "catch_up_2_3_day",
        "activity_weight": 0.18,
        "touches_hero_share": 0.35,
        "chat_active": True,
        "revision_prone": True,  # more status moves back from review
    },
    {
        "key": "preparer_c",
        "role": "staff",
        "full_name": "Sam Whitfield",
        "email": "sam.whitfield@cedarvance-demo.com",
        "login_window": (7, 9),
        "login_minute_range": (0, 59),
        "after_hours_window": (19, 22),
        "weekend": False,
        "time_entry_lag": "next_morning",
        "activity_weight": 0.16,
        "touches_hero_share": 0.1,
        "chat_active": True,
    },
    {
        "key": "admin",
        "role": "staff",
        "full_name": "Jo Ferraro",
        "email": "jo.ferraro@cedarvance-demo.com",
        "login_window": (7, 9),
        "login_minute_range": (0, 59),
        "after_hours_window": None,
        "weekend": False,
        "time_entry_lag": "same_day",
        "activity_weight": 0.10,
        "touches_hero_share": 0.0,
        "chat_active": True,
        "non_billable": True,
        "invoice_batch_day": "friday",
        "invoice_batch_interval_days_normal": 7,
        "invoice_batch_interval_days_season": (10, 14),  # slips in March/April
    },
    {
        "key": "seasonal_preparer",
        "role": "staff",
        "full_name": "Toni Reyes",
        "email": "toni.reyes@cedarvance-demo.com",
        "login_window": (7, 9),
        "login_minute_range": (0, 59),
        "after_hours_window": None,
        "weekend": False,
        "time_entry_lag": "next_morning",
        "activity_weight": 0.06,
        "touches_hero_share": 0.05,
        "chat_active": False,
        # active_window is relative to the season: (start_month_day, end_month_day)
        # evaluated against the current simulated year, mid-Jan through Apr 30
        "active_window": ((1, 15), (4, 30)),
    },
]

# ---------------------------------------------------------------------------
# Hero tier - ~30 hand-configured clients
# ---------------------------------------------------------------------------
# invoice_tier: "pay_on_view" | "middle" | "slow_tail"
# upload_style: "batch" | "drip" | "chronic_slow"
# engagement_type: one of app.core.enums.EngagementType values
HERO_CLIENTS = []

# 8 chronically-slow-document clients
for i in range(1, 9):
    HERO_CLIENTS.append({
        "key": f"hero_slow_docs_{i}",
        "name": f"Slowpoke Holdings {i}",
        "tier": "hero",
        "engagement_type": "tax_return_1040" if i % 3 else "tax_return_1120s",
        "upload_style": "chronic_slow",
        "reminders_min": 3,
        "invoice_tier": "middle",
        "portal_activity": "low",
    })

# 2 pay-on-view exemplars
for i in range(1, 3):
    HERO_CLIENTS.append({
        "key": f"hero_pay_on_view_{i}",
        "name": f"Brightline Partners {i}",
        "tier": "hero",
        "engagement_type": "tax_return_1120",
        "upload_style": "batch",
        "invoice_tier": "pay_on_view",
        "portal_activity": "high",
    })

# 5 middle-band invoice exemplars
for i in range(1, 6):
    HERO_CLIENTS.append({
        "key": f"hero_middle_invoice_{i}",
        "name": f"Middleton Family Trust {i}",
        "tier": "hero",
        "engagement_type": "tax_return_1040",
        "upload_style": "drip",
        "invoice_tier": "middle",
        "portal_activity": "medium",
    })

# 3 slow-tail invoice exemplars (35-60 days, multiple reminders)
for i in range(1, 4):
    HERO_CLIENTS.append({
        "key": f"hero_slow_tail_{i}",
        "name": f"Lingering Ventures {i}",
        "tier": "hero",
        "engagement_type": "tax_return_1065",
        "upload_style": "batch",
        "invoice_tier": "slow_tail",
        "invoice_days_min": 35,
        "invoice_days_max": 60,
        "portal_activity": "medium",
    })

# 1 complex K-1 scope-creep exemplar
HERO_CLIENTS.append({
    "key": "hero_k1_complex",
    "name": "Ashcombe Family Partnership",
    "tier": "hero",
    "engagement_type": "tax_return_1065",
    "upload_style": "drip",
    "invoice_tier": "middle",
    "portal_activity": "medium",
    "scope_creep": True,
    "extra_hours_multiplier": 3.5,
})

# 4 model-citizen monthly bookkeeping clients
for i in range(1, 5):
    HERO_CLIENTS.append({
        "key": f"hero_model_citizen_{i}",
        "name": f"Steadfast Bookkeeping Co {i}",
        "tier": "hero",
        "engagement_type": "bookkeeping_monthly",
        "upload_style": "batch",
        "invoice_tier": "pay_on_view",
        "portal_activity": "high",
        "recurring": True,
    })

# remainder: ordinary hero clients, individually specified but unremarkable
for i in range(1, 8):
    HERO_CLIENTS.append({
        "key": f"hero_ordinary_{i}",
        "name": f"Ordinary & Associates {i}",
        "tier": "hero",
        "engagement_type": "tax_return_1040" if i % 2 else "tax_return_1120s",
        "upload_style": "drip",
        "invoice_tier": "middle",
        "portal_activity": "medium",
    })

# ---------------------------------------------------------------------------
# Population tier - ~400 generated clients
# ---------------------------------------------------------------------------
POPULATION = {
    "individual_count": 370,
    "business_count": 40,
    "bookkeeping_count": 15,
    # complexity band weights for individual returns
    "individual_bands": {"simple": 0.70, "middle": 0.25, "complex": 0.05},
    "upload_style_weights": {"batch": 0.5, "drip": 0.5},
    "invoice_tier_weights": {"pay_on_view": 0.2, "middle": 0.55, "slow_tail": 0.25},
    "portal_activity_weights": {"low": 0.3, "medium": 0.45, "high": 0.25},
}

# ---------------------------------------------------------------------------
# Choreography parameters
# ---------------------------------------------------------------------------
CHOREOGRAPHY = {
    "staff_login_cluster": (7, 9),  # 7:30-9:00am modeled loosely within this band
    "lunch_dip": (12, 13),
    "late_afternoon_admin_band": (16, 17.5),
    "portal_evening_peak": (19, 22),
    "portal_sunday_afternoon": (13, 17),
    "reminder_to_upload_within_hours": 48,
    "reminder_to_upload_share": 0.65,  # 60-70%, midpoint
    "monday_surge_multiplier": 1.4,
    "friday_completion_multiplier": 1.3,
    "deep_work_days": ("Tue", "Wed", "Thu"),
    "seasonal_arc": {
        # month_index is 0-based offset from the first simulated month
        "quiet_baseline_months": (0, 1),
        "sept_15_blip": True,
        "oct_15_spike": True,
        "year_end_planning_months": ("Nov", "Dec"),
        "holiday_silence": ((12, 23), (1, 1)),
        "january_wave": True,
        "february_upload_focus": True,
        "march_squeeze": True,
        "march_15_spike": True,
        "april_peak_start": (4, 1),
        "april_peak_end": (4, 15),
        "april_cliff_start": (4, 16),
        "april_cliff_drop_pct": 0.70,
        "april_cliff_end": (4, 30),
    },
}

WARMUP_EVENT_TYPE = "system.seed_warmup"

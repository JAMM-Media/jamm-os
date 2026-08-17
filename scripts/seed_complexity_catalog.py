# scripts/seed_complexity_catalog.py

"""Seed the system complexity catalog from docs/complexity_catalog_content_v1.md.

Transcribes the ratified content run (40 flags, 84 dimensions) into the five
system-owned catalog tables:

    complexity_flags
    complexity_dimensions
    complexity_dimension_units
    complexity_vocabulary_options
    complexity_flag_engagement_types

These five carry NO firm_id, per the August 13, 2026 carve-out documented in
app/models/complexity_flag.py. This script touches nothing else. It calls no
external service of any kind: no email, no S3, no behavioral log, no audit log.
Seeding system content is not a user action and has no actor.

Run from the project root:

    python scripts/seed_complexity_catalog.py

IDEMPOTENT UPSERTS ONLY. Every row is keyed by its stable key:

    flags        -> key
    dimensions   -> (flag key, dimension key)
    units        -> (dimension, unit key)
    options      -> (dimension, option key)
    mappings     -> (flag, engagement_type)

Running twice produces byte-identical database state. Nothing is ever deleted
by this script: a vocabulary option ID, once referenced by a firm's
firm_option_prices row, must persist, and option identity is shared across
every firm.

WHY FIELDS ARE COMPARED BEFORE THEY ARE ASSIGNED. _apply_changes sets only
fields whose value actually differs, and that comparison is what produces the
created / updated / unchanged counts in the summary.

It is NOT what makes the re-run leave updated_at alone, which was this
module's first guess and is wrong. Measured on August 16, 2026 rather than
assumed: assigning an identical value does put the row in session.dirty, but
SQLAlchemy's unit of work compares the net attribute history at flush time and
emits no UPDATE at all, so the onupdate never fires and the timestamp survives.
Idempotency therefore does not depend on this comparison. The summary's
accuracy does, which is reason enough to keep it.

WHAT THIS SCRIPT OWNS, AND WHAT IT DELIBERATELY DOES NOT.

Owned, and rewritten on every run to match the document: flag name, dimension
kind, hierarchy_rank, linkable, default_role, unit label, option label.

NOT owned, and written only at row creation:

    question_text  -> seeded NULL on every dimension and every unit by design.
                      Lead-facing wording is a later data edit (the columns
                      were built nullable for exactly this). A re-run must
                      never wipe wording somebody authored.
    is_active      -> the document describes no inactive content, so there is
                      nothing for the seed to assert here. Retiring a flag or
                      an option is a curation act, and a re-run must not undo
                      it.

Both are seeded NULL / default on create and then left alone forever after.

ENGAGEMENT TYPES ARE NEVER HAND-COPIED. The mappings below reference
EngagementType members from app/core/enums.py directly, and every one is
re-validated through EngagementType() at seed time. An unknown value is a hard
error that aborts the run before anything is written; it is never skipped.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.enums import DimensionKind, DimensionRole, EngagementType
from app.db.session import SessionLocal
from app.models.complexity_dimension import ComplexityDimension
from app.models.complexity_dimension_unit import ComplexityDimensionUnit
from app.models.complexity_flag import ComplexityFlag
from app.models.complexity_flag_engagement_type import ComplexityFlagEngagementType
from app.models.complexity_vocabulary_option import ComplexityVocabularyOption


class SeedError(RuntimeError):
    """Raised for any content fault. Aborts the run before anything is written."""


# The Other option every categorical dimension carries, in addition to its
# tabled vocabulary. Open Ruling A in the content document, ruled yes.
#
# It exists so an unknown situation has a real, stable option ID to be answered
# with instead of falling off the form. It must never carry a price: a priced
# Other would hand a lead with an unrecognised situation a computed number.
# pricing_config_service.set_option_price refuses it at save time.
OTHER_OPTION_KEY = "other"
OTHER_OPTION_LABEL = "Other"

# Built with chr() rather than written as the character itself, so this file
# obeys the same no-em-dash rule it enforces.
EM_DASH = chr(0x2014)

BOOLEAN = DimensionKind.boolean
NUMERIC = DimensionKind.numeric_range
CATEGORICAL = DimensionKind.categorical

PRICED = DimensionRole.priced
INFORMATIONAL = DimensionRole.informational
GUARD = DimensionRole.guard

# Part I header: applies-to for every individual flag unless the flag adds more.
INDIVIDUAL_TYPES = (
    EngagementType.tax_return_1040,
    EngagementType.tax_return_1040nr,
    EngagementType.amended_return_1040x,
    EngagementType.tax_planning_advisory,
)

# Part II header: applies-to for every business flag unless the flag adds more.
BUSINESS_TYPES = (
    EngagementType.tax_return_1120,
    EngagementType.tax_return_1120s,
    EngagementType.tax_return_1065,
    EngagementType.tax_return_990,
    EngagementType.amended_return_business,
    EngagementType.tax_planning_advisory,
)

# The four financial statement engagement types, shared by flag 23 (industry
# overlay, per its applies-to addition) and flag 32.
FINANCIAL_STATEMENT_TYPES = (
    EngagementType.financial_statement_compilation,
    EngagementType.financial_statement_review,
    EngagementType.financial_statement_audit,
    EngagementType.agreed_upon_procedures,
)


# ---------------------------------------------------------------------------
# The content, transcribed from docs/complexity_catalog_content_v1.md.
#
# Ordered exactly as the document orders it, Part I through Part VI. Keys are
# stable snake_case slugs chosen once here; they are permanent identifiers and
# must not be renamed. hierarchy_rank, linkable and default_role land exactly
# as tabled.
#
# Part VII (engagement types that deliberately carry no flags) produces no rows
# and appears nowhere below, which is the point of it.
# ---------------------------------------------------------------------------

CATALOG = [
    # -- PART I: INDIVIDUAL FLAGS -------------------------------------------
    {
        "key": "digital_assets",
        "name": "Digital assets and crypto",
        "engagement_types": INDIVIDUAL_TYPES,
        "dimensions": [
            {
                "key": "activity_type",
                "kind": CATEGORICAL,
                "default_role": PRICED,
                "hierarchy_rank": 10,
                "linkable": True,
                "options": [
                    ("exchange_trading", "Exchange trading"),
                    ("staking", "Staking"),
                    ("mining", "Mining"),
                    ("defi_and_liquidity_pools", "DeFi and liquidity pools"),
                    ("nfts", "NFTs"),
                    ("airdrops_and_forks", "Airdrops and forks"),
                    ("stablecoin_activity", "Stablecoin activity"),
                    ("self_custody_wallets", "Self-custody wallets"),
                    ("received_as_payment", "Received as payment"),
                    ("gifted_or_donated", "Gifted or donated"),
                    ("lost_stolen_or_exchange_collapse", "Lost, stolen or exchange collapse"),
                ],
            },
            {
                "key": "account_and_wallet_count",
                "kind": NUMERIC,
                "default_role": PRICED,
                "hierarchy_rank": 20,
                "linkable": True,
                "units": [
                    ("exchanges", "Exchanges"),
                    ("wallets", "Wallets"),
                    ("combined_accounts_and_wallets", "Combined accounts and wallets"),
                ],
            },
            {
                "key": "activity_volume",
                "kind": NUMERIC,
                "default_role": PRICED,
                "hierarchy_rank": 30,
                "linkable": True,
                "units": [
                    ("transaction_count", "Transaction count"),
                    ("total_proceeds", "Total proceeds ($)"),
                ],
            },
        ],
    },
    {
        "key": "k1s_received",
        "name": "K-1s received",
        "engagement_types": INDIVIDUAL_TYPES,
        "dimensions": [
            {
                "key": "source_type",
                "kind": CATEGORICAL,
                "default_role": PRICED,
                "hierarchy_rank": 10,
                "linkable": True,
                "options": [
                    ("partnership", "Partnership"),
                    ("s_corp", "S-corp"),
                    ("trust_or_estate", "Trust or estate"),
                    ("publicly_traded_partnership", "Publicly traded partnership"),
                    ("hedge_or_pe_fund", "Hedge or PE fund"),
                    ("foreign_partnership", "Foreign partnership"),
                ],
            },
            {
                "key": "k1_count",
                "kind": NUMERIC,
                "default_role": PRICED,
                "hierarchy_rank": 20,
                "linkable": True,
                "units": [("k1s_received", "K-1s received")],
            },
            {
                "key": "states_on_k1s",
                "kind": NUMERIC,
                "default_role": PRICED,
                "hierarchy_rank": 30,
                "linkable": True,
                "units": [("states", "States")],
            },
        ],
    },
    {
        "key": "rental_real_estate",
        "name": "Rental real estate",
        "engagement_types": INDIVIDUAL_TYPES,
        "dimensions": [
            {
                "key": "property_type",
                "kind": CATEGORICAL,
                "default_role": PRICED,
                "hierarchy_rank": 10,
                "linkable": True,
                "options": [
                    ("long_term_residential", "Long-term residential"),
                    ("short_term_rental", "Short-term rental"),
                    ("commercial", "Commercial"),
                    ("mixed_use_vacation", "Mixed-use vacation"),
                    ("out_of_state", "Out-of-state"),
                    ("foreign", "Foreign"),
                ],
            },
            {
                "key": "property_count",
                "kind": NUMERIC,
                "default_role": PRICED,
                "hierarchy_rank": 20,
                "linkable": True,
                "units": [("properties", "Properties")],
            },
            {
                "key": "gross_rents",
                "kind": NUMERIC,
                "default_role": GUARD,
                "hierarchy_rank": 30,
                "linkable": True,
                "units": [("total_gross_rents", "Total gross rents ($)")],
            },
            {
                "key": "situations",
                "kind": CATEGORICAL,
                "default_role": PRICED,
                "hierarchy_rank": 40,
                "linkable": False,
                "options": [
                    ("sold_or_disposed", "Sold or disposed"),
                    ("exchange_1031", "1031 exchange"),
                    ("first_year_in_service", "First year in service"),
                    ("cost_segregation_in_place", "Cost segregation in place"),
                    ("re_professional_status", "RE professional status"),
                ],
            },
        ],
    },
    {
        "key": "self_employment",
        "name": "Self-employment (Schedule C)",
        "engagement_types": INDIVIDUAL_TYPES,
        "dimensions": [
            {
                "key": "business_count",
                "kind": NUMERIC,
                "default_role": PRICED,
                "hierarchy_rank": 10,
                "linkable": True,
                "units": [("businesses", "Businesses")],
            },
            {
                "key": "gross_receipts",
                "kind": NUMERIC,
                "default_role": GUARD,
                "hierarchy_rank": 20,
                "linkable": True,
                "units": [("total_gross_receipts", "Total gross receipts ($)")],
            },
            {
                "key": "features",
                "kind": CATEGORICAL,
                "default_role": PRICED,
                "hierarchy_rank": 30,
                "linkable": False,
                "options": [
                    ("home_office", "Home office"),
                    ("vehicle", "Vehicle"),
                    ("employees", "Employees"),
                    ("contractors", "Contractors"),
                    ("inventory", "Inventory"),
                    ("first_year", "First year"),
                ],
            },
        ],
    },
    {
        "key": "investment_activity",
        "name": "Investment activity",
        "engagement_types": INDIVIDUAL_TYPES,
        "dimensions": [
            {
                "key": "account_count",
                "kind": NUMERIC,
                "default_role": PRICED,
                "hierarchy_rank": 10,
                "linkable": True,
                "units": [("brokerage_accounts", "Brokerage accounts")],
            },
            {
                "key": "transaction_volume",
                "kind": NUMERIC,
                "default_role": PRICED,
                "hierarchy_rank": 20,
                "linkable": True,
                "units": [("transactions_1099b", "1099-B transactions")],
            },
            {
                "key": "special_situations",
                "kind": CATEGORICAL,
                "default_role": PRICED,
                "hierarchy_rank": 30,
                "linkable": False,
                "options": [
                    ("options", "Options"),
                    ("heavy_trading_with_wash_sales", "Heavy trading with wash sales"),
                    ("trader_status_mark_to_market", "Trader status mark-to-market"),
                    ("worthless_securities", "Worthless securities"),
                    ("private_and_angel_investments", "Private and angel investments"),
                ],
            },
        ],
    },
    {
        "key": "equity_compensation",
        "name": "Equity compensation",
        "engagement_types": INDIVIDUAL_TYPES,
        "dimensions": [
            {
                "key": "compensation_type",
                "kind": CATEGORICAL,
                "default_role": PRICED,
                "hierarchy_rank": 10,
                "linkable": True,
                "options": [
                    ("rsus", "RSUs"),
                    ("isos_with_amt", "ISOs with AMT"),
                    ("espp", "ESPP"),
                    ("nsos", "NSOs"),
                    ("elections_83b", "83(b) elections"),
                ],
            },
            {
                "key": "event_volume",
                "kind": NUMERIC,
                "default_role": PRICED,
                "hierarchy_rank": 20,
                "linkable": True,
                "units": [
                    ("vesting_exercise_and_sale_events", "Vesting, exercise and sale events")
                ],
            },
        ],
    },
    {
        "key": "multi_state_individual",
        "name": "Multi-state (individual)",
        "engagement_types": INDIVIDUAL_TYPES,
        "dimensions": [
            {
                "key": "state_count",
                "kind": NUMERIC,
                "default_role": PRICED,
                "hierarchy_rank": 10,
                "linkable": True,
                "units": [("states", "States")],
            },
            {
                "key": "reason",
                "kind": CATEGORICAL,
                "default_role": INFORMATIONAL,
                "hierarchy_rank": 20,
                "linkable": False,
                "options": [
                    ("moved_during_year", "Moved during year"),
                    ("remote_work", "Remote work"),
                    ("nonresident_income", "Nonresident income"),
                    ("part_year_residency", "Part-year residency"),
                ],
            },
        ],
    },
    {
        "key": "international_individual",
        "name": "International (individual)",
        # Applies-to adds FBAR and international, per the flag's own note.
        "engagement_types": INDIVIDUAL_TYPES + (EngagementType.fbar_international,),
        "dimensions": [
            {
                "key": "international_type",
                "kind": CATEGORICAL,
                "default_role": PRICED,
                "hierarchy_rank": 10,
                "linkable": True,
                "options": [
                    ("foreign_accounts_fbar", "Foreign accounts (FBAR)"),
                    ("foreign_asset_reporting_8938", "Foreign asset reporting (8938)"),
                    ("earned_income_exclusion", "Earned income exclusion"),
                    ("foreign_tax_credit", "Foreign tax credit"),
                    ("foreign_pension", "Foreign pension"),
                    ("pfics", "PFICs"),
                    ("foreign_gifts_or_inheritance", "Foreign gifts or inheritance"),
                    ("foreign_entity_ownership", "Foreign entity ownership"),
                    ("foreign_rental", "Foreign rental"),
                ],
            },
            {
                "key": "account_count",
                "kind": NUMERIC,
                "default_role": PRICED,
                "hierarchy_rank": 20,
                "linkable": True,
                "units": [("foreign_accounts", "Foreign accounts")],
            },
            {
                "key": "entity_count",
                "kind": NUMERIC,
                "default_role": PRICED,
                "hierarchy_rank": 30,
                "linkable": True,
                "units": [("foreign_entities", "Foreign entities")],
            },
        ],
    },
    {
        "key": "prior_year_issues",
        "name": "Prior-year issues",
        "engagement_types": INDIVIDUAL_TYPES,
        "dimensions": [
            {
                "key": "unfiled_years",
                "kind": NUMERIC,
                "default_role": PRICED,
                "hierarchy_rank": 10,
                "linkable": True,
                "units": [("tax_years", "Tax years")],
            },
            {
                "key": "issue_type",
                "kind": CATEGORICAL,
                "default_role": PRICED,
                "hierarchy_rank": 20,
                "linkable": False,
                "options": [
                    ("amendment_needed", "Amendment needed"),
                    ("outstanding_notices", "Outstanding notices"),
                    ("existing_installment_agreement", "Existing installment agreement"),
                ],
            },
        ],
    },
    {
        "key": "life_events",
        "name": "Life events",
        "engagement_types": INDIVIDUAL_TYPES,
        "dimensions": [
            {
                "key": "events",
                "kind": CATEGORICAL,
                "default_role": PRICED,
                "hierarchy_rank": 10,
                "linkable": False,
                "options": [
                    ("home_sale", "Home sale"),
                    ("divorce", "Divorce"),
                    ("inheritance", "Inheritance"),
                    ("large_retirement_distributions", "Large retirement distributions"),
                    ("roth_conversions", "Roth conversions"),
                    ("adoption", "Adoption"),
                    ("dependent_complications", "Dependent complications"),
                    ("marriage", "Marriage"),
                    ("death_of_spouse", "Death of spouse"),
                ],
            },
        ],
    },
    {
        "key": "charitable_complexity",
        "name": "Charitable complexity",
        "engagement_types": INDIVIDUAL_TYPES,
        "dimensions": [
            {
                "key": "charitable_items",
                "kind": CATEGORICAL,
                "default_role": PRICED,
                "hierarchy_rank": 10,
                "linkable": False,
                "options": [
                    ("large_non_cash_gifts", "Large non-cash gifts"),
                    ("appraisal_required_gifts", "Appraisal-required gifts"),
                    ("donor_advised_funds", "Donor-advised funds"),
                    ("conservation_easements", "Conservation easements"),
                    (
                        "qualified_charitable_distributions",
                        "Qualified charitable distributions",
                    ),
                ],
            },
        ],
    },
    {
        "key": "household_employer",
        "name": "Household employer",
        "engagement_types": INDIVIDUAL_TYPES,
        "dimensions": [
            {
                "key": "household_employee_count",
                "kind": NUMERIC,
                "default_role": PRICED,
                "hierarchy_rank": 10,
                "linkable": False,
                "units": [("household_employees", "Household employees")],
            },
        ],
    },
    {
        "key": "special_statuses",
        "name": "Special statuses",
        "engagement_types": INDIVIDUAL_TYPES,
        "dimensions": [
            {
                "key": "status",
                "kind": CATEGORICAL,
                "default_role": PRICED,
                "hierarchy_rank": 10,
                "linkable": False,
                "options": [
                    ("clergy", "Clergy"),
                    ("military", "Military"),
                    ("expat", "Expat"),
                ],
            },
        ],
    },
    # -- PART II: BUSINESS FLAGS --------------------------------------------
    {
        "key": "business_profile",
        "name": "Business profile",
        "engagement_types": BUSINESS_TYPES,
        "dimensions": [
            {
                "key": "annual_revenue",
                "kind": NUMERIC,
                "default_role": GUARD,
                "hierarchy_rank": 10,
                "linkable": True,
                "units": [("gross_revenue", "Gross revenue ($)")],
            },
            {
                "key": "employee_count",
                "kind": NUMERIC,
                "default_role": PRICED,
                "hierarchy_rank": 20,
                "linkable": True,
                "units": [("w2_employees", "W-2 employees")],
            },
            {
                "key": "owner_count",
                "kind": NUMERIC,
                "default_role": PRICED,
                "hierarchy_rank": 30,
                "linkable": True,
                "units": [
                    ("owners_partners_shareholders", "Owners, partners and shareholders")
                ],
            },
        ],
    },
    {
        "key": "multi_state_nexus",
        "name": "Multi-state nexus",
        "engagement_types": BUSINESS_TYPES,
        "dimensions": [
            {
                "key": "state_count",
                "kind": NUMERIC,
                "default_role": PRICED,
                "hierarchy_rank": 10,
                "linkable": True,
                "units": [
                    ("states_with_filing_obligation", "States with filing obligation")
                ],
            },
            {
                "key": "nexus_trigger",
                "kind": CATEGORICAL,
                "default_role": INFORMATIONAL,
                "hierarchy_rank": 20,
                "linkable": False,
                "options": [
                    ("payroll_in_state", "Payroll in state"),
                    ("property_in_state", "Property in state"),
                    ("economic_nexus", "Economic nexus"),
                ],
            },
        ],
    },
    {
        "key": "books_condition",
        "name": "Books condition",
        "engagement_types": BUSINESS_TYPES,
        "dimensions": [
            {
                "key": "condition",
                "kind": CATEGORICAL,
                "default_role": PRICED,
                "hierarchy_rank": 10,
                "linkable": False,
                "options": [
                    ("clean", "Clean"),
                    ("needs_adjusting_entries", "Needs adjusting entries"),
                    ("needs_cleanup", "Needs cleanup"),
                    ("no_books", "No books"),
                ],
            },
        ],
    },
    {
        "key": "fixed_assets",
        "name": "Fixed assets",
        "engagement_types": BUSINESS_TYPES,
        "dimensions": [
            {
                "key": "asset_count",
                "kind": NUMERIC,
                "default_role": PRICED,
                "hierarchy_rank": 10,
                "linkable": True,
                "units": [("depreciable_assets", "Depreciable assets")],
            },
            {
                "key": "situations",
                "kind": CATEGORICAL,
                "default_role": PRICED,
                "hierarchy_rank": 20,
                "linkable": False,
                "options": [
                    ("major_purchases_this_year", "Major purchases this year"),
                    ("cost_segregation_in_place", "Cost segregation in place"),
                    ("disposals", "Disposals"),
                ],
            },
        ],
    },
    {
        "key": "inventory",
        "name": "Inventory",
        "engagement_types": BUSINESS_TYPES,
        "dimensions": [
            {
                "key": "carries_inventory",
                "kind": BOOLEAN,
                "default_role": PRICED,
                "hierarchy_rank": 10,
                "linkable": False,
            },
            {
                "key": "method",
                "kind": CATEGORICAL,
                "default_role": PRICED,
                "hierarchy_rank": 20,
                "linkable": False,
                "options": [
                    ("fifo", "FIFO"),
                    ("lifo", "LIFO"),
                    ("unicap_applies", "UNICAP applies"),
                ],
            },
        ],
    },
    {
        "key": "ownership_changes",
        "name": "Ownership changes",
        "engagement_types": BUSINESS_TYPES,
        "dimensions": [
            {
                "key": "change_type",
                "kind": CATEGORICAL,
                "default_role": PRICED,
                "hierarchy_rank": 10,
                "linkable": False,
                "options": [
                    ("new_owners_admitted", "New owners admitted"),
                    ("buyout_or_redemption", "Buyout or redemption"),
                    ("ownership_transfer", "Ownership transfer"),
                    ("election_754", "754 election"),
                    ("restructuring", "Restructuring"),
                ],
            },
        ],
    },
    {
        "key": "entity_lifecycle",
        "name": "Entity lifecycle",
        "engagement_types": BUSINESS_TYPES,
        "dimensions": [
            {
                "key": "lifecycle_stage",
                "kind": CATEGORICAL,
                "default_role": PRICED,
                "hierarchy_rank": 10,
                "linkable": False,
                "options": [
                    ("first_year_return", "First-year return"),
                    ("final_return", "Final return"),
                    ("short_year_return", "Short-year return"),
                ],
            },
        ],
    },
    {
        "key": "foreign_operations",
        "name": "Foreign operations",
        "engagement_types": BUSINESS_TYPES,
        "dimensions": [
            {
                "key": "foreign_activity",
                "kind": CATEGORICAL,
                "default_role": PRICED,
                "hierarchy_rank": 10,
                "linkable": True,
                "options": [
                    ("foreign_subsidiary", "Foreign subsidiary"),
                    ("foreign_owner", "Foreign owner"),
                    ("foreign_sales", "Foreign sales"),
                    ("gilti_exposure", "GILTI exposure"),
                ],
            },
            {
                "key": "entity_count",
                "kind": NUMERIC,
                "default_role": PRICED,
                "hierarchy_rank": 20,
                "linkable": True,
                "units": [("foreign_entities", "Foreign entities")],
            },
        ],
    },
    {
        "key": "special_items",
        "name": "Special items",
        "engagement_types": BUSINESS_TYPES,
        "dimensions": [
            {
                "key": "items",
                "kind": CATEGORICAL,
                "default_role": PRICED,
                "hierarchy_rank": 10,
                "linkable": False,
                "options": [
                    ("related_party_transactions", "Related-party transactions"),
                    ("shareholder_loans", "Shareholder loans"),
                    ("built_in_gains", "Built-in gains"),
                    ("accounting_method_change", "Accounting method change"),
                ],
            },
        ],
    },
    {
        "key": "industry_overlay",
        "name": "Industry overlay",
        # Applies-to adds the financial statement types, per the flag's note
        # that they share the business industry overlay.
        "engagement_types": BUSINESS_TYPES + FINANCIAL_STATEMENT_TYPES,
        "dimensions": [
            {
                "key": "industry",
                "kind": CATEGORICAL,
                "default_role": PRICED,
                "hierarchy_rank": 10,
                "linkable": False,
                "options": [
                    ("construction", "Construction"),
                    ("restaurants", "Restaurants"),
                    ("medical", "Medical"),
                    ("cannabis_280e", "Cannabis (280E)"),
                    ("farming", "Farming"),
                    ("nonprofit_ubi", "Nonprofit UBI"),
                ],
            },
        ],
    },
    # -- PART III: TRUSTS, ESTATES, GIFTS -----------------------------------
    {
        "key": "trust_complexity",
        "name": "Trust complexity",
        "engagement_types": (EngagementType.tax_return_1041,),
        "dimensions": [
            {
                "key": "trust_type",
                "kind": CATEGORICAL,
                "default_role": PRICED,
                "hierarchy_rank": 10,
                "linkable": True,
                "options": [
                    ("simple", "Simple"),
                    ("complex", "Complex"),
                    ("grantor", "Grantor"),
                    ("charitable_remainder_or_lead", "Charitable remainder or lead"),
                    ("special_needs", "Special needs"),
                ],
            },
            {
                "key": "beneficiary_count",
                "kind": NUMERIC,
                "default_role": PRICED,
                "hierarchy_rank": 20,
                "linkable": True,
                "units": [("beneficiaries", "Beneficiaries")],
            },
            {
                "key": "asset_complexity",
                "kind": CATEGORICAL,
                "default_role": PRICED,
                "hierarchy_rank": 30,
                "linkable": False,
                "options": [
                    ("closely_held_interests", "Closely held interests"),
                    ("real_property", "Real property"),
                    ("appraisal_required_assets", "Appraisal-required assets"),
                ],
            },
        ],
    },
    {
        "key": "estate_return_complexity",
        "name": "Estate return complexity",
        "engagement_types": (EngagementType.tax_return_706,),
        "dimensions": [
            {
                "key": "return_type",
                "kind": CATEGORICAL,
                "default_role": PRICED,
                "hierarchy_rank": 10,
                "linkable": True,
                "options": [
                    ("portability_only", "Portability-only"),
                    ("full_taxable", "Full taxable"),
                    ("state_estate_tax", "State estate tax"),
                ],
            },
            {
                "key": "gross_estate_value",
                "kind": NUMERIC,
                "default_role": GUARD,
                "hierarchy_rank": 20,
                "linkable": True,
                "units": [("gross_estate", "Gross estate ($)")],
            },
        ],
    },
    {
        "key": "gift_return_complexity",
        "name": "Gift return complexity",
        "engagement_types": (EngagementType.tax_return_709,),
        "dimensions": [
            {
                "key": "gift_type",
                "kind": CATEGORICAL,
                "default_role": PRICED,
                "hierarchy_rank": 10,
                "linkable": True,
                "options": [
                    ("cash_gifts", "Cash gifts"),
                    ("hard_to_value_gifts", "Hard-to-value gifts"),
                    ("gst_allocation", "GST allocation"),
                ],
            },
            {
                "key": "donee_count",
                "kind": NUMERIC,
                "default_role": PRICED,
                "hierarchy_rank": 20,
                "linkable": True,
                "units": [("donees", "Donees")],
            },
        ],
    },
    # -- PART IV: PAYROLL AND INFORMATION REPORTING -------------------------
    {
        "key": "payroll_complexity",
        "name": "Payroll complexity",
        "engagement_types": (
            EngagementType.payroll_tax_941,
            EngagementType.payroll_tax_940,
            EngagementType.payroll_processing,
        ),
        "dimensions": [
            {
                "key": "employee_count",
                "kind": NUMERIC,
                "default_role": PRICED,
                "hierarchy_rank": 10,
                "linkable": True,
                "units": [("employees", "Employees")],
            },
            {
                "key": "state_count",
                "kind": NUMERIC,
                "default_role": PRICED,
                "hierarchy_rank": 20,
                "linkable": True,
                "units": [("payroll_states", "Payroll states")],
            },
            {
                "key": "features",
                "kind": CATEGORICAL,
                "default_role": PRICED,
                "hierarchy_rank": 30,
                "linkable": False,
                "options": [
                    ("tipped_employees", "Tipped employees"),
                    ("contractor_mix", "Contractor mix"),
                    ("certified_payroll", "Certified payroll"),
                    ("garnishments", "Garnishments"),
                    ("retirement_plan_integration", "Retirement plan integration"),
                ],
            },
        ],
    },
    {
        "key": "information_return_volume",
        "name": "Information return volume",
        "engagement_types": (EngagementType.information_returns_1099_w2,),
        "dimensions": [
            {
                "key": "form_type",
                "kind": CATEGORICAL,
                "default_role": PRICED,
                "hierarchy_rank": 10,
                "linkable": True,
                "options": [
                    ("nec", "NEC"),
                    ("misc", "MISC"),
                    ("int", "INT"),
                    ("div", "DIV"),
                    ("k", "K"),
                    ("corrected_filings", "Corrected filings"),
                ],
            },
            {
                "key": "form_count",
                "kind": NUMERIC,
                "default_role": PRICED,
                "hierarchy_rank": 20,
                "linkable": True,
                "units": [("forms_filed", "Forms filed")],
            },
        ],
    },
    # -- PART V: SALES TAX, BOOKKEEPING, FINANCIAL STATEMENTS ---------------
    {
        "key": "sales_use_tax_complexity",
        "name": "Sales and use tax complexity",
        "engagement_types": (EngagementType.sales_use_tax,),
        "dimensions": [
            {
                "key": "state_count",
                "kind": NUMERIC,
                "default_role": PRICED,
                "hierarchy_rank": 10,
                "linkable": True,
                "units": [("registered_states", "Registered states")],
            },
            {
                "key": "filing_frequency",
                "kind": NUMERIC,
                "default_role": PRICED,
                "hierarchy_rank": 20,
                "linkable": True,
                "units": [("filings_per_year", "Filings per year")],
            },
            {
                "key": "channel",
                "kind": CATEGORICAL,
                "default_role": INFORMATIONAL,
                "hierarchy_rank": 30,
                "linkable": False,
                "options": [
                    ("physical_locations", "Physical locations"),
                    ("direct_ecommerce", "Direct e-commerce"),
                    ("marketplace_facilitator", "Marketplace facilitator"),
                    ("saas_and_digital_goods", "SaaS and digital goods"),
                    ("services_taxability", "Services taxability"),
                ],
            },
        ],
    },
    {
        "key": "bookkeeping_volume",
        "name": "Bookkeeping volume",
        "engagement_types": (
            EngagementType.bookkeeping_monthly,
            EngagementType.bookkeeping_quarterly,
            EngagementType.accounting_system_setup,
        ),
        "dimensions": [
            {
                "key": "monthly_transaction_volume",
                "kind": NUMERIC,
                "default_role": PRICED,
                "hierarchy_rank": 10,
                "linkable": True,
                "units": [("transactions_per_month", "Transactions per month")],
            },
            {
                "key": "account_count",
                "kind": NUMERIC,
                "default_role": PRICED,
                "hierarchy_rank": 20,
                "linkable": True,
                "units": [("bank_and_credit_accounts", "Bank and credit accounts")],
            },
            {
                "key": "monthly_revenue",
                "kind": NUMERIC,
                "default_role": GUARD,
                "hierarchy_rank": 30,
                "linkable": True,
                "units": [("monthly_revenue", "Monthly revenue ($)")],
            },
            {
                "key": "features",
                "kind": CATEGORICAL,
                "default_role": PRICED,
                "hierarchy_rank": 40,
                "linkable": False,
                "options": [
                    ("payroll_integration", "Payroll integration"),
                    ("inventory", "Inventory"),
                    ("ar_ap_management", "AR and AP management"),
                    ("multiple_entities", "Multiple entities"),
                    ("class_or_location_tracking", "Class or location tracking"),
                    ("foreign_currency", "Foreign currency"),
                ],
            },
        ],
    },
    {
        "key": "cleanup_scope",
        "name": "Cleanup scope",
        "engagement_types": (EngagementType.bookkeeping_cleanup,),
        "dimensions": [
            {
                "key": "starting_condition",
                "kind": CATEGORICAL,
                "default_role": PRICED,
                "hierarchy_rank": 10,
                "linkable": True,
                "options": [
                    ("no_books", "No books"),
                    ("spreadsheets", "Spreadsheets"),
                    ("messy_file", "Messy file"),
                    ("migration_needed", "Migration needed"),
                ],
            },
            {
                "key": "months_behind",
                "kind": NUMERIC,
                "default_role": PRICED,
                "hierarchy_rank": 20,
                "linkable": True,
                "units": [("months", "Months")],
            },
        ],
    },
    {
        "key": "financial_statement_profile",
        "name": "Financial statement profile",
        "engagement_types": FINANCIAL_STATEMENT_TYPES,
        "dimensions": [
            {
                "key": "revenue",
                "kind": NUMERIC,
                "default_role": GUARD,
                "hierarchy_rank": 10,
                "linkable": True,
                "units": [("annual_revenue", "Annual revenue ($)")],
            },
            {
                "key": "purpose",
                "kind": CATEGORICAL,
                "default_role": INFORMATIONAL,
                "hierarchy_rank": 20,
                "linkable": False,
                "options": [
                    ("bank_requirement", "Bank requirement"),
                    ("bonding", "Bonding"),
                    ("investors", "Investors"),
                    ("regulatory", "Regulatory"),
                ],
            },
            {
                "key": "first_time_engagement",
                "kind": BOOLEAN,
                "default_role": PRICED,
                "hierarchy_rank": 30,
                "linkable": False,
            },
        ],
    },
    # -- PART VI: ADVISORY, RESOLUTION, SPECIALTY ---------------------------
    {
        "key": "tax_resolution_scope",
        "name": "Tax resolution scope",
        "engagement_types": (EngagementType.tax_resolution,),
        "dimensions": [
            {
                "key": "resolution_path",
                "kind": CATEGORICAL,
                "default_role": PRICED,
                "hierarchy_rank": 10,
                "linkable": True,
                "options": [
                    ("offer_in_compromise", "Offer in compromise"),
                    ("installment_agreement", "Installment agreement"),
                    ("penalty_abatement", "Penalty abatement"),
                    ("innocent_spouse", "Innocent spouse"),
                    ("lien_or_levy_release", "Lien or levy release"),
                ],
            },
            {
                "key": "amount_owed",
                "kind": NUMERIC,
                "default_role": PRICED,
                "hierarchy_rank": 20,
                "linkable": True,
                "units": [("total_owed", "Total owed ($)")],
            },
            {
                "key": "years_involved",
                "kind": NUMERIC,
                "default_role": PRICED,
                "hierarchy_rank": 30,
                "linkable": True,
                "units": [("tax_years", "Tax years")],
            },
        ],
    },
    {
        "key": "audit_representation_scope",
        "name": "Audit representation scope",
        "engagement_types": (EngagementType.audit_representation,),
        "dimensions": [
            {
                "key": "audit_scope",
                "kind": CATEGORICAL,
                "default_role": PRICED,
                "hierarchy_rank": 10,
                "linkable": True,
                "options": [
                    ("correspondence", "Correspondence"),
                    ("office", "Office"),
                    ("field", "Field"),
                ],
            },
            {
                "key": "years_under_audit",
                "kind": NUMERIC,
                "default_role": PRICED,
                "hierarchy_rank": 20,
                "linkable": True,
                "units": [("tax_years", "Tax years")],
            },
        ],
    },
    {
        "key": "rd_credit_scope",
        "name": "R&D credit scope",
        "engagement_types": (EngagementType.rd_tax_credit_study,),
        "dimensions": [
            {
                "key": "study_type",
                "kind": CATEGORICAL,
                "default_role": PRICED,
                "hierarchy_rank": 10,
                "linkable": True,
                "options": [
                    ("first_study", "First study"),
                    ("renewal", "Renewal"),
                    ("payroll_offset_election", "Payroll offset election"),
                ],
            },
            {
                "key": "qualified_spend",
                "kind": NUMERIC,
                "default_role": PRICED,
                "hierarchy_rank": 20,
                "linkable": True,
                "units": [("qualified_research_spend", "Qualified research spend ($)")],
            },
        ],
    },
    {
        "key": "entity_formation_scope",
        "name": "Entity formation scope",
        "engagement_types": (EngagementType.entity_formation,),
        "dimensions": [
            {
                "key": "entity_type",
                "kind": CATEGORICAL,
                "default_role": PRICED,
                "hierarchy_rank": 10,
                "linkable": True,
                "options": [
                    ("single_member_llc", "Single-member LLC"),
                    ("multi_member_llc", "Multi-member LLC"),
                    ("s_election", "S-election"),
                    ("c_corp", "C-corp"),
                ],
            },
            {
                "key": "add_ons",
                "kind": CATEGORICAL,
                "default_role": PRICED,
                "hierarchy_rank": 20,
                "linkable": False,
                "options": [
                    ("ein", "EIN"),
                    ("state_registrations", "State registrations"),
                    (
                        "operating_agreement_coordination",
                        "Operating agreement coordination",
                    ),
                ],
            },
        ],
    },
    {
        "key": "irs_notice_scope",
        "name": "IRS notice scope",
        "engagement_types": (EngagementType.irs_notice_resolution,),
        "dimensions": [
            {
                "key": "notice_type",
                "kind": CATEGORICAL,
                "default_role": PRICED,
                "hierarchy_rank": 10,
                "linkable": False,
                "options": [
                    # NOTE: other_correspondence is a real tabled answer, not the
                    # universal Other. It is a specific kind of IRS notice and it
                    # is priceable. Only the exact key "other" is refused a price.
                    ("cp2000_underreporter", "CP2000 underreporter"),
                    ("balance_due_series", "Balance due series"),
                    ("penalty_notice", "Penalty notice"),
                    ("identity_verification", "Identity verification"),
                    ("other_correspondence", "Other correspondence"),
                ],
            },
            {
                "key": "tax_years_involved",
                "kind": NUMERIC,
                "default_role": PRICED,
                "hierarchy_rank": 20,
                "linkable": False,
                "units": [("tax_years", "Tax years")],
            },
        ],
    },
    {
        "key": "benefit_plan_filing",
        "name": "Benefit plan filing",
        "engagement_types": (EngagementType.benefit_plan_5500,),
        "dimensions": [
            {
                "key": "participant_count",
                "kind": NUMERIC,
                "default_role": PRICED,
                "hierarchy_rank": 10,
                "linkable": False,
                "units": [("plan_participants", "Plan participants")],
            },
            {
                "key": "filing_type",
                "kind": CATEGORICAL,
                "default_role": PRICED,
                "hierarchy_rank": 20,
                "linkable": False,
                "options": [
                    ("form_5500_ez", "5500-EZ"),
                    ("form_5500_sf", "5500-SF"),
                    ("full_5500_with_schedules", "Full 5500 with schedules"),
                ],
            },
        ],
    },
    {
        "key": "exemption_application_scope",
        "name": "Exemption application scope",
        "engagement_types": (EngagementType.nonprofit_formation_exemption,),
        "dimensions": [
            {
                "key": "application_path",
                "kind": CATEGORICAL,
                "default_role": PRICED,
                "hierarchy_rank": 10,
                "linkable": False,
                "options": [
                    ("form_1023_ez", "1023-EZ"),
                    ("full_1023", "Full 1023"),
                    ("form_1024", "1024"),
                    ("state_only_registration", "State-only registration"),
                ],
            },
        ],
    },
    {
        "key": "property_tax_filing_scope",
        "name": "Property tax filing scope",
        "engagement_types": (EngagementType.business_personal_property_tax,),
        "dimensions": [
            {
                "key": "jurisdiction_count",
                "kind": NUMERIC,
                "default_role": PRICED,
                "hierarchy_rank": 10,
                "linkable": False,
                "units": [("filing_jurisdictions", "Filing jurisdictions")],
            },
        ],
    },
]


# Pinned totals from the content document. The Appendix originally read 78
# dimensions; Andrew ruled on August 16, 2026 that this was an authoring
# miscount and that the tables are the ratified content. Corrected to 84 in the
# document in the same commit that added it.
EXPECTED_FLAG_COUNT = 40
EXPECTED_DIMENSION_COUNT = 84


# ---------------------------------------------------------------------------
# Counters
# ---------------------------------------------------------------------------

@dataclass
class TableCounts:
    created: int = 0
    updated: int = 0
    unchanged: int = 0

    @property
    def total(self) -> int:
        return self.created + self.updated + self.unchanged


@dataclass
class SeedSummary:
    flags: TableCounts = field(default_factory=TableCounts)
    dimensions: TableCounts = field(default_factory=TableCounts)
    units: TableCounts = field(default_factory=TableCounts)
    options: TableCounts = field(default_factory=TableCounts)
    mappings: TableCounts = field(default_factory=TableCounts)

    def rows(self):
        return [
            ("complexity_flags", self.flags),
            ("complexity_dimensions", self.dimensions),
            ("complexity_dimension_units", self.units),
            ("complexity_vocabulary_options", self.options),
            ("complexity_flag_engagement_types", self.mappings),
        ]

    @property
    def touched(self) -> int:
        """Rows this run actually wrote. Zero on a clean re-run."""
        return sum(counts.created + counts.updated for _, counts in self.rows())


def _apply_changes(row, values: dict) -> bool:
    """Assign only the fields whose value actually differs.

    The return value is what the created / updated / unchanged summary counts,
    so the comparison has to happen whether or not the assignment does. See the
    module docstring for why this is not what protects updated_at.
    """
    changed = False
    for attribute, value in values.items():
        if getattr(row, attribute) != value:
            setattr(row, attribute, value)
            changed = True
    return changed


def _record(counts: TableCounts, created: bool, changed: bool) -> None:
    if created:
        counts.created += 1
    elif changed:
        counts.updated += 1
    else:
        counts.unchanged += 1


# ---------------------------------------------------------------------------
# Content validation. All of it runs before a single row is written, so a
# content fault aborts with nothing half-seeded.
# ---------------------------------------------------------------------------

def _validated_engagement_value(flag_key: str, engagement_type) -> str:
    """The stored string for one mapping, validated against the real enum.

    Passing an EngagementType member back through EngagementType() returns the
    member; passing anything the enum does not contain raises ValueError. Either
    way the value that reaches the database has been proved to be a real member,
    and an unknown one is a hard error rather than a skipped row.
    """
    try:
        member = EngagementType(engagement_type)
    except ValueError as exc:
        raise SeedError(
            f"Flag '{flag_key}' maps to {engagement_type!r}, which is not a "
            "member of EngagementType in app/core/enums.py. Fix the mapping or "
            "the enum; the seed will not guess."
        ) from exc
    return member.value


def _check_no_em_dash(label: str, where: str) -> None:
    if EM_DASH in label:
        raise SeedError(
            f"Em dash found in {where}: {label!r}. House rule: no em dashes in "
            "any seeded string. Hyphens are fine."
        )


def validate_catalog() -> None:
    """Every content rule the document and the house rules impose, checked up
    front. Raises SeedError on the first fault."""
    flag_keys = set()

    for flag in CATALOG:
        flag_key = flag["key"]
        if flag_key in flag_keys:
            raise SeedError(f"Duplicate flag key: {flag_key!r}")
        flag_keys.add(flag_key)

        _check_no_em_dash(flag["name"], f"flag '{flag_key}' name")

        if not flag["engagement_types"]:
            raise SeedError(
                f"Flag '{flag_key}' has no engagement types. A flag nothing "
                "applies to would never be asked; Part VII types carry no flag "
                "at all rather than a flag with an empty mapping."
            )
        for engagement_type in flag["engagement_types"]:
            _validated_engagement_value(flag_key, engagement_type)

        dimension_keys = set()
        ranks = set()
        for dimension in flag["dimensions"]:
            dimension_key = dimension["key"]
            if dimension_key in dimension_keys:
                raise SeedError(
                    f"Duplicate dimension key {dimension_key!r} in flag "
                    f"'{flag_key}'. uq_complexity_dimensions_flag_key would "
                    "reject this."
                )
            dimension_keys.add(dimension_key)

            rank = dimension["hierarchy_rank"]
            if rank in ranks:
                raise SeedError(
                    f"Duplicate hierarchy_rank {rank} in flag '{flag_key}'. "
                    "Ranks are spaced by 10 and are unique within a flag so "
                    "chains flow strictly downhill."
                )
            ranks.add(rank)

            kind = dimension["kind"]
            units = dimension.get("units", [])
            options = dimension.get("options", [])

            if kind == DimensionKind.numeric_range:
                if not units:
                    raise SeedError(
                        f"Numeric dimension '{flag_key}.{dimension_key}' has no "
                        "units. numeric_range is the only kind that carries "
                        "units and a config cannot name one without them."
                    )
                if options:
                    raise SeedError(
                        f"Numeric dimension '{flag_key}.{dimension_key}' "
                        "carries vocabulary options."
                    )
            elif kind == DimensionKind.categorical:
                if not options:
                    raise SeedError(
                        f"Categorical dimension '{flag_key}.{dimension_key}' "
                        "has no vocabulary."
                    )
                if units:
                    raise SeedError(
                        f"Categorical dimension '{flag_key}.{dimension_key}' "
                        "carries units."
                    )
                if any(key == OTHER_OPTION_KEY for key, _ in options):
                    raise SeedError(
                        f"Categorical dimension '{flag_key}.{dimension_key}' "
                        f"already tables an option keyed {OTHER_OPTION_KEY!r}. "
                        "The universal Other option is added by this script; a "
                        "tabled one would collide with it."
                    )
            else:
                if units or options:
                    raise SeedError(
                        f"Boolean dimension '{flag_key}.{dimension_key}' must "
                        "carry no units and no options."
                    )

            seen_unit_keys = set()
            for unit_key, unit_label in units:
                if unit_key in seen_unit_keys:
                    raise SeedError(
                        f"Duplicate unit key {unit_key!r} on "
                        f"'{flag_key}.{dimension_key}'."
                    )
                seen_unit_keys.add(unit_key)
                _check_no_em_dash(
                    unit_label, f"unit '{flag_key}.{dimension_key}.{unit_key}' label"
                )

            seen_option_keys = set()
            for option_key, option_label in options:
                if option_key in seen_option_keys:
                    raise SeedError(
                        f"Duplicate option key {option_key!r} on "
                        f"'{flag_key}.{dimension_key}'."
                    )
                seen_option_keys.add(option_key)
                _check_no_em_dash(
                    option_label,
                    f"option '{flag_key}.{dimension_key}.{option_key}' label",
                )

    _check_no_em_dash(OTHER_OPTION_LABEL, "the universal Other option label")

    flag_count = len(CATALOG)
    dimension_count = sum(len(flag["dimensions"]) for flag in CATALOG)
    if flag_count != EXPECTED_FLAG_COUNT or dimension_count != EXPECTED_DIMENSION_COUNT:
        raise SeedError(
            f"Transcription count mismatch: {flag_count} flags and "
            f"{dimension_count} dimensions, expected {EXPECTED_FLAG_COUNT} and "
            f"{EXPECTED_DIMENSION_COUNT}. Reconcile against "
            "docs/complexity_catalog_content_v1.md rather than adjusting these "
            "constants."
        )


# ---------------------------------------------------------------------------
# The seed itself
# ---------------------------------------------------------------------------

def seed_complexity_catalog(db: Session) -> SeedSummary:
    """Upsert the whole catalog into the five system tables.

    Takes a session rather than making one so the test suite can run it against
    the test database. main() below owns the session for command line runs.

    Does not commit. The caller decides, which is what lets the tests run this
    inside their own transaction.
    """
    validate_catalog()
    summary = SeedSummary()

    for flag_content in CATALOG:
        flag_key = flag_content["key"]

        flag = db.execute(
            select(ComplexityFlag).where(ComplexityFlag.key == flag_key)
        ).scalar_one_or_none()

        if flag is None:
            # is_active is not passed: it is not document content and the model
            # default of true applies. See the module docstring.
            flag = ComplexityFlag(key=flag_key, name=flag_content["name"])
            db.add(flag)
            db.flush()
            _record(summary.flags, created=True, changed=True)
        else:
            changed = _apply_changes(flag, {"name": flag_content["name"]})
            _record(summary.flags, created=False, changed=changed)

        for dimension_content in flag_content["dimensions"]:
            dimension_key = dimension_content["key"]

            dimension = db.execute(
                select(ComplexityDimension).where(
                    ComplexityDimension.flag_id == flag.id,
                    ComplexityDimension.key == dimension_key,
                )
            ).scalar_one_or_none()

            owned = {
                "kind": dimension_content["kind"],
                "hierarchy_rank": dimension_content["hierarchy_rank"],
                "linkable": dimension_content["linkable"],
                "default_role": dimension_content["default_role"],
            }

            if dimension is None:
                # question_text is deliberately not passed and so lands NULL.
                dimension = ComplexityDimension(
                    flag_id=flag.id, key=dimension_key, **owned
                )
                db.add(dimension)
                db.flush()
                _record(summary.dimensions, created=True, changed=True)
            else:
                changed = _apply_changes(dimension, owned)
                _record(summary.dimensions, created=False, changed=changed)

            for unit_key, unit_label in dimension_content.get("units", []):
                unit = db.execute(
                    select(ComplexityDimensionUnit).where(
                        ComplexityDimensionUnit.dimension_id == dimension.id,
                        ComplexityDimensionUnit.key == unit_key,
                    )
                ).scalar_one_or_none()

                if unit is None:
                    # question_text deliberately omitted; lands NULL.
                    unit = ComplexityDimensionUnit(
                        dimension_id=dimension.id, key=unit_key, label=unit_label
                    )
                    db.add(unit)
                    _record(summary.units, created=True, changed=True)
                else:
                    changed = _apply_changes(unit, {"label": unit_label})
                    _record(summary.units, created=False, changed=changed)

            options = list(dimension_content.get("options", []))
            if options:
                # The universal Other, in addition to the tabled vocabulary.
                options.append((OTHER_OPTION_KEY, OTHER_OPTION_LABEL))

            for option_key, option_label in options:
                option = db.execute(
                    select(ComplexityVocabularyOption).where(
                        ComplexityVocabularyOption.dimension_id == dimension.id,
                        ComplexityVocabularyOption.key == option_key,
                    )
                ).scalar_one_or_none()

                if option is None:
                    # is_active deliberately omitted; model default applies.
                    option = ComplexityVocabularyOption(
                        dimension_id=dimension.id, key=option_key, label=option_label
                    )
                    db.add(option)
                    _record(summary.options, created=True, changed=True)
                else:
                    changed = _apply_changes(option, {"label": option_label})
                    _record(summary.options, created=False, changed=changed)

        for engagement_type in flag_content["engagement_types"]:
            value = _validated_engagement_value(flag_key, engagement_type)

            mapping = db.execute(
                select(ComplexityFlagEngagementType).where(
                    ComplexityFlagEngagementType.flag_id == flag.id,
                    ComplexityFlagEngagementType.engagement_type == value,
                )
            ).scalar_one_or_none()

            if mapping is None:
                mapping = ComplexityFlagEngagementType(
                    flag_id=flag.id, engagement_type=value
                )
                db.add(mapping)
                _record(summary.mappings, created=True, changed=True)
            else:
                # The row is its own key. Nothing to update, ever.
                _record(summary.mappings, created=False, changed=False)

    return summary


def print_summary(summary: SeedSummary) -> None:
    print()
    print("Complexity catalog seed")
    print("-" * 74)
    print(f"{'table':<38}{'created':>9}{'updated':>9}{'unchgd':>9}{'total':>9}")
    for table_name, counts in summary.rows():
        print(
            f"{table_name:<38}{counts.created:>9}{counts.updated:>9}"
            f"{counts.unchanged:>9}{counts.total:>9}"
        )
    print("-" * 74)
    if summary.touched == 0:
        print("Nothing written. The catalog already matches the document.")
    else:
        print(f"Rows written this run: {summary.touched}")
    print()


def main() -> None:
    db = SessionLocal()
    try:
        summary = seed_complexity_catalog(db)
        db.commit()
        print_summary(summary)
    finally:
        db.close()


if __name__ == "__main__":
    main()

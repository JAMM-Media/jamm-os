# JAMM PX Complexity Catalog — Content Run v1

**Date:** August 16, 2026
**Status:** Draft for Andrew's ratification, then Lori's audit. Produces data rows only, never migrations.
**Source:** Fee Schedule and Template System Build Reference v2, section 8 (structurally ratified Aug 12), finalized per the section 7 content-session scope: dimensions, kinds, unit menus, vocabularies, recommended default roles, hierarchy ranks, linkable markers, and engagement-type mappings.

---

## How to read this document

**Kinds:** `boolean` (exists or not, flat adder, no follow-up) / `numeric` (numeric range; firm tiers on a chosen unit) / `categorical` (system vocabulary; firm prices the options it covers).

**Default role:** the recommended starting role the tree builder pre-selects — `priced`, `informational`, or `guard`. Firms change it freely.

**Rank:** hierarchy rank, coarse to fine, LOWER = COARSER = parent-eligible. Ranks are spaced by 10 (10, 20, 30) so future insertions never renumber. Chains flow strictly downhill within a flag.

**Linkable:** `no` means the dimension never participates in dependency chains in either direction — it is always a flat layer.

**Tags:**
- `[LORI]` — arguable call, wants her twenty minutes.
- `[SPLIT]` — a section 8 "unit" promoted to its own dimension (see Structural Decision 1).
- `[ADDED]` — not in section 8; added so an engagement type isn't dimensionless when it plausibly shouldn't be. Strike freely.

Every categorical dimension carries an **Other** option (see Open Ruling A).

---

## Structural decisions made in this run (need Andrew's ratification)

**1. The volume split.** Section 8 sometimes lists count-of-things and volume-of-activity as *units of one dimension* (crypto: "volume — units: transaction count, total proceeds, exchanges and wallets"). But section 4.4's own rank example is "accounts before transactions before dollar volume" — a three-level chain — and one dimension can only be configured once per branch (the branch-uniqueness constraint) and cannot parent itself. So wherever the draft's "units" are really *different countable things a firm might tier on simultaneously or chain*, this run splits them into separate dimensions with distinct ranks. Wherever they are genuinely *alternative ways to count the same thing* (transaction count vs. total proceeds as measures of activity volume), they stay a unit menu on one dimension. Applied to: crypto, investment activity, international (individual), bookkeeping, tax resolution. Each is marked `[SPLIT]`.

**2. Multi-select adder categoricals are unlinkable.** Dimensions like self-employment "features" (home office, vehicle, employees...) or rental "situations" are lists where several answers apply at once and each priced option is a flat adder. Chaining under a multi-answer dimension is structurally ambiguous, so these ship `linkable: no`. Single-answer "type" categoricals (trust type, property type) stay linkable.

**3. Business returns become ten flags, not one.** Section 8 lists the business dimensions as one run-on block. This run splits them into ten flags (Business profile, Multi-state nexus, Books condition, Fixed assets, Inventory, Ownership changes, Entity lifecycle, Foreign operations, Special items, Industry overlay) because flags are the lead-facing "does this apply to you?" gates and a firm should be able to attach pricing to nexus without also fielding inventory questions.

**4. Rank conventions applied throughout.** Single-answer type categoricals rank 10 (coarsest — per-type pricing with counts underneath is the natural chain). Entity/account/property counts rank 20. Activity volumes and dollar figures rank 30. Unlinkable dimensions still carry a rank (for stable display ordering) but it is inert.

---

## Open rulings for Andrew (before the seed task file)

**A. Is "Other" a seeded vocabulary row or form behavior?** The universal quote law says Other always routes to quote, and Ben's form returns canonical option IDs. Recommendation: seed one `other` option row per categorical vocabulary so it has a real ID, and have the tree builder UI (and the save-time service) refuse to attach a price to it — Other must never be priceable. Needs your ruling because it touches Ben's contract surface.

**B. The `[ADDED]` flags.** Four engagement types (5500, IRS notice resolution, nonprofit formation, business personal property tax) had no section 8 dimensions but aren't in the quote-required-no-dimensions club either. I drafted minimal flags for them. Keep, trim, or strike.

**C. Boolean kind is barely used.** After the run, only two dimensions are `boolean` (inventory presence, first-time financial statement). Everything else that felt boolean is better as a categorical option (a life event) or the flag's own existence. Confirm you're comfortable with `boolean` being rare — it's correct, just worth a conscious yes.

---

# PART I — INDIVIDUAL FLAGS

Applies-to for all Part I flags unless noted: **1040, 1040-NR, 1040-X, tax planning**.

## 1. Digital assets / crypto
| Dimension | Kind | Units / Vocabulary | Default role | Rank | Linkable |
|---|---|---|---|---|---|
| Activity type | categorical | exchange trading, staking, mining, DeFi and liquidity pools, NFTs, airdrops and forks, stablecoin activity, self-custody wallets, received as payment, gifted or donated, lost/stolen/exchange collapse | priced | 10 | yes |
| Account & wallet count `[SPLIT]` | numeric | exchanges, wallets, combined accounts+wallets | priced | 20 | yes |
| Activity volume | numeric | transaction count, total proceeds ($) | priced | 30 | yes |

Notes: This is the doc's worked chaining example — accounts parenting transaction tiers is exactly the matrix section 4.3 describes. `[LORI]` Activity type as rank 10 means a firm can price staking-vs-mining with volume tiers underneath; sanity-check that real firms price crypto by activity type at all, or whether type should default informational.

## 2. K-1s received
| Dimension | Kind | Units / Vocabulary | Default role | Rank | Linkable |
|---|---|---|---|---|---|
| Source type | categorical | partnership, S-corp, trust or estate, publicly traded partnership, hedge or PE fund, foreign partnership | priced | 10 | yes |
| K-1 count | numeric | K-1s received | priced | 20 | yes |
| States on K-1s | numeric | states | priced | 30 | yes |

Notes: the doc's own example firm runs these as three flat stacked fees — the ranks only matter for firms that opt into chaining (e.g., pricing PTP K-1s per-form differently than plain partnership K-1s).

## 3. Rental real estate
| Dimension | Kind | Units / Vocabulary | Default role | Rank | Linkable |
|---|---|---|---|---|---|
| Property type | categorical | long-term residential, short-term rental, commercial, mixed-use vacation, out-of-state, foreign | priced | 10 | yes |
| Property count | numeric | properties | priced | 20 | yes |
| Gross rents | numeric | total gross rents ($) | guard | 30 | yes |
| Situations | categorical | sold or disposed, 1031 exchange, first year in service, cost segregation in place, RE professional status | priced | 40 | no |

Notes: gross rents defaults **guard** per the draft ("typical informational or guard") — a dollar tripwire is the more protective default; firms flip to informational freely. `[LORI]` confirm guard over informational as the shipped default.

## 4. Self-employment (Schedule C)
| Dimension | Kind | Units / Vocabulary | Default role | Rank | Linkable |
|---|---|---|---|---|---|
| Business count | numeric | businesses | priced | 10 | yes |
| Gross receipts | numeric | total gross receipts ($) | guard | 20 | yes |
| Features | categorical | home office, vehicle, employees, contractors, inventory, first year | priced | 30 | no |

## 5. Investment activity
| Dimension | Kind | Units / Vocabulary | Default role | Rank | Linkable |
|---|---|---|---|---|---|
| Account count `[SPLIT]` | numeric | brokerage accounts | priced | 10 | yes |
| Transaction volume | numeric | 1099-B transactions | priced | 20 | yes |
| Special situations | categorical | options, heavy trading with wash sales, trader status mark-to-market, worthless securities, private and angel investments | priced | 30 | no |

Notes: "types" renamed "special situations" — they're adders on top of ordinary investing, not mutually exclusive types. Unlinkable per Structural Decision 2.

## 6. Equity compensation
| Dimension | Kind | Units / Vocabulary | Default role | Rank | Linkable |
|---|---|---|---|---|---|
| Compensation type | categorical | RSUs, ISOs with AMT, ESPP, NSOs, 83(b) elections | priced | 10 | yes |
| Event volume | numeric | vesting/exercise/sale events | priced | 20 | yes |

## 7. Multi-state (individual)
| Dimension | Kind | Units / Vocabulary | Default role | Rank | Linkable |
|---|---|---|---|---|---|
| State count | numeric | states | priced | 10 | yes |
| Reason | categorical | moved during year, remote work, nonresident income, part-year residency | informational | 20 | no |

Notes: reason defaults **informational** — it arms the preparer for the call; the count is what moves price. `[LORI]`.

## 8. International (individual)
Applies-to adds: **FBAR and international** (standalone engagement type).
| Dimension | Kind | Units / Vocabulary | Default role | Rank | Linkable |
|---|---|---|---|---|---|
| International type | categorical | foreign accounts (FBAR), foreign asset reporting (8938), earned income exclusion, foreign tax credit, foreign pension, PFICs, foreign gifts or inheritance, foreign entity ownership, foreign rental | priced | 10 | yes |
| Account count `[SPLIT]` | numeric | foreign accounts | priced | 20 | yes |
| Entity count | numeric | foreign entities | priced | 30 | yes |

Notes: PFIC and foreign-entity work is exactly where firms chain (per-entity pricing under the entity-ownership option). The two counts are separate dimensions because a taxpayer plausibly has both, and both priced.

## 9. Prior-year issues
| Dimension | Kind | Units / Vocabulary | Default role | Rank | Linkable |
|---|---|---|---|---|---|
| Unfiled years | numeric | tax years | priced | 10 | yes |
| Issue type | categorical | amendment needed, outstanding notices, existing installment agreement | priced | 20 | no |

## 10. Life events
| Dimension | Kind | Units / Vocabulary | Default role | Rank | Linkable |
|---|---|---|---|---|---|
| Events | categorical | home sale, divorce, inheritance, large retirement distributions, Roth conversions, adoption, dependent complications, marriage, death of spouse | priced | 10 | no |

Notes: marriage and death of spouse added to the vocabulary (generous scoping; dormant options are free). `[LORI]` on the additions.

## 11. Charitable complexity
| Dimension | Kind | Units / Vocabulary | Default role | Rank | Linkable |
|---|---|---|---|---|---|
| Charitable items | categorical | large non-cash gifts, appraisal-required gifts, donor-advised funds, conservation easements, qualified charitable distributions | priced | 10 | no |

Notes: QCDs added. `[LORI]`.

## 12. Household employer
| Dimension | Kind | Units / Vocabulary | Default role | Rank | Linkable |
|---|---|---|---|---|---|
| Household employee count | numeric | household employees | priced | 10 | no |

Notes: the draft said "boolean or employee count" — resolved to the count. The flag's presence IS the boolean; a count captures Schedule H scale. One-dimension flag, nothing to chain.

## 13. Special statuses
| Dimension | Kind | Units / Vocabulary | Default role | Rank | Linkable |
|---|---|---|---|---|---|
| Status | categorical | clergy, military, expat | priced | 10 | no |

---

# PART II — BUSINESS FLAGS

Applies-to for all Part II flags unless noted: **1120, 1120-S, 1065, 990, amended business, tax planning**. (1041 gets its own Part III flags; see notes where a business flag also maps to 1041.)

## 14. Business profile
| Dimension | Kind | Units / Vocabulary | Default role | Rank | Linkable |
|---|---|---|---|---|---|
| Annual revenue | numeric | gross revenue ($) | guard | 10 | yes |
| Employee count | numeric | W-2 employees | priced | 20 | yes |
| Owner count | numeric | owners/partners/shareholders | priced | 30 | yes |

Notes: revenue defaults guard per the draft ("common guard"). Owner count is the K-1-prep cost driver on 1065/1120-S. `[LORI]` whether owner count should outrank employee count (owner count is arguably the coarser business descriptor). Rank order between 20 and 30 here is the run's least confident call.

## 15. Multi-state nexus
| Dimension | Kind | Units / Vocabulary | Default role | Rank | Linkable |
|---|---|---|---|---|---|
| State count | numeric | states with filing obligation | priced | 10 | yes |
| Nexus trigger | categorical | payroll in state, property in state, economic nexus | informational | 20 | no |

## 16. Books condition
| Dimension | Kind | Units / Vocabulary | Default role | Rank | Linkable |
|---|---|---|---|---|---|
| Condition | categorical | clean, needs adjusting entries, needs cleanup, no books | priced | 10 | no |

Notes: single-answer but unlinkable — nothing sensibly chains under a condition grade. Doubles as the cleanup cross-sell signal per the draft; that signal is a behavioral-log consumer, not a pricing feature.

## 17. Fixed assets
| Dimension | Kind | Units / Vocabulary | Default role | Rank | Linkable |
|---|---|---|---|---|---|
| Asset count | numeric | depreciable assets | priced | 10 | yes |
| Situations | categorical | major purchases this year, cost segregation in place, disposals | priced | 20 | no |

## 18. Inventory
| Dimension | Kind | Units / Vocabulary | Default role | Rank | Linkable |
|---|---|---|---|---|---|
| Carries inventory | boolean | — | priced | 10 | no |
| Method | categorical | FIFO, LIFO, UNICAP applies | priced | 20 | no |

## 19. Ownership changes
| Dimension | Kind | Units / Vocabulary | Default role | Rank | Linkable |
|---|---|---|---|---|---|
| Change type | categorical | new owners admitted, buyout or redemption, ownership transfer, 754 election, restructuring | priced | 10 | no |

## 20. Entity lifecycle
| Dimension | Kind | Units / Vocabulary | Default role | Rank | Linkable |
|---|---|---|---|---|---|
| Lifecycle stage | categorical | first-year return, final return, short-year return | priced | 10 | no |

## 21. Foreign operations
| Dimension | Kind | Units / Vocabulary | Default role | Rank | Linkable |
|---|---|---|---|---|---|
| Foreign activity | categorical | foreign subsidiary, foreign owner, foreign sales, GILTI exposure | priced | 10 | yes |
| Entity count `[ADDED]` | numeric | foreign entities | priced | 20 | yes |

Notes: entity count added because per-entity 5471/5472 pricing is the industry norm — this is the business mirror of flag 8's structure. `[LORI]`.

## 22. Special items
| Dimension | Kind | Units / Vocabulary | Default role | Rank | Linkable |
|---|---|---|---|---|---|
| Items | categorical | related-party transactions, shareholder loans, built-in gains, accounting method change | priced | 10 | no |

## 23. Industry overlay
Applies-to adds: **financial statements types (compilation, review, audit, AUP)** per the draft's "shares the business industry overlay."
| Dimension | Kind | Units / Vocabulary | Default role | Rank | Linkable |
|---|---|---|---|---|---|
| Industry | categorical | construction, restaurants, medical, cannabis (280E), farming, nonprofit UBI | priced | 10 | no |

---

# PART III — TRUSTS, ESTATES, GIFTS

## 24. Trust complexity — applies to **1041**
| Dimension | Kind | Units / Vocabulary | Default role | Rank | Linkable |
|---|---|---|---|---|---|
| Trust type | categorical | simple, complex, grantor, charitable remainder or lead, special needs | priced | 10 | yes |
| Beneficiary count | numeric | beneficiaries | priced | 20 | yes |
| Asset complexity | categorical | closely held interests, real property, appraisal-required assets | priced | 30 | no |

## 25. Estate return complexity — applies to **706**
| Dimension | Kind | Units / Vocabulary | Default role | Rank | Linkable |
|---|---|---|---|---|---|
| Return type | categorical | portability-only, full taxable, state estate tax | priced | 10 | yes |
| Gross estate value | numeric | gross estate ($) | guard | 20 | yes |

## 26. Gift return complexity — applies to **709**
| Dimension | Kind | Units / Vocabulary | Default role | Rank | Linkable |
|---|---|---|---|---|---|
| Gift type | categorical | cash gifts, hard-to-value gifts, GST allocation | priced | 10 | yes |
| Donee count | numeric | donees | priced | 20 | yes |

---

# PART IV — PAYROLL AND INFORMATION REPORTING

## 27. Payroll complexity — applies to **941, 940, payroll processing**
| Dimension | Kind | Units / Vocabulary | Default role | Rank | Linkable |
|---|---|---|---|---|---|
| Employee count | numeric | employees | priced | 10 | yes |
| State count | numeric | payroll states | priced | 20 | yes |
| Features | categorical | tipped employees, contractor mix, certified payroll, garnishments, retirement plan integration | priced | 30 | no |

## 28. Information return volume — applies to **1099/W-2**
| Dimension | Kind | Units / Vocabulary | Default role | Rank | Linkable |
|---|---|---|---|---|---|
| Form type | categorical | NEC, MISC, INT, DIV, K, corrected filings | priced | 10 | yes |
| Form count | numeric | forms filed | priced | 20 | yes |

Notes: type ranked above count so per-form-type per-form pricing (the common shape: $X per NEC, $Y per corrected) is a natural chain.

---

# PART V — SALES TAX, BOOKKEEPING, FINANCIAL STATEMENTS

## 29. Sales and use tax complexity — applies to **sales and use tax**
| Dimension | Kind | Units / Vocabulary | Default role | Rank | Linkable |
|---|---|---|---|---|---|
| State count | numeric | registered states | priced | 10 | yes |
| Filing frequency | numeric | filings per year | priced | 20 | yes |
| Channel | categorical | physical locations, direct e-commerce, marketplace facilitator, SaaS and digital goods, services taxability | informational | 30 | no |

Notes: channel defaults **informational** — it shapes the work's nature more than its unit price; state count and filing volume are the billable drivers. `[LORI]`.

## 30. Bookkeeping volume — applies to **bookkeeping monthly, bookkeeping quarterly, system setup**
| Dimension | Kind | Units / Vocabulary | Default role | Rank | Linkable |
|---|---|---|---|---|---|
| Monthly transaction volume `[SPLIT]` | numeric | transactions per month | priced | 10 | yes |
| Account count `[SPLIT]` | numeric | bank/credit accounts | priced | 20 | yes |
| Monthly revenue `[SPLIT]` | numeric | monthly revenue ($) | guard | 30 | yes |
| Features | categorical | payroll integration, inventory, AR/AP management, multiple entities, class or location tracking, foreign currency | priced | 40 | no |

Notes: the draft's "volume — units: transactions typical priced, revenue typical guard, accounts typical priced layer" was three dimensions wearing one label — its own text assigns them different roles and calls accounts a "layer," which is stacking language. Split accordingly.

## 31. Cleanup scope — applies to **bookkeeping cleanup**
| Dimension | Kind | Units / Vocabulary | Default role | Rank | Linkable |
|---|---|---|---|---|---|
| Starting condition | categorical | no books, spreadsheets, messy file, migration needed | priced | 10 | yes |
| Months behind | numeric | months | priced | 20 | yes |

Notes: condition above months so per-condition per-month pricing chains naturally (a messy-file month costs more than a spreadsheet month).

## 32. Financial statement profile — applies to **compilation, review, audit, agreed-upon procedures**
| Dimension | Kind | Units / Vocabulary | Default role | Rank | Linkable |
|---|---|---|---|---|---|
| Revenue | numeric | annual revenue ($) | guard | 10 | yes |
| Purpose | categorical | bank requirement, bonding, investors, regulatory | informational | 20 | no |
| First-time engagement | boolean | — | priced | 30 | no |

Notes: also carries flag 23 (industry overlay) via its applies-to mapping.

---

# PART VI — ADVISORY, RESOLUTION, SPECIALTY

## 33. Tax resolution scope — applies to **tax resolution**
| Dimension | Kind | Units / Vocabulary | Default role | Rank | Linkable |
|---|---|---|---|---|---|
| Resolution path | categorical | offer in compromise, installment agreement, penalty abatement, innocent spouse, lien or levy release | priced | 10 | yes |
| Amount owed `[SPLIT]` | numeric | total owed ($) | priced | 20 | yes |
| Years involved | numeric | tax years | priced | 30 | yes |

Notes: path above amount — OIC-vs-abatement is the fee driver; amount tiers under it. Per the draft, amount owed is "typically the priced dimension" and years a "layer" — the split honors that.

## 34. Audit representation scope — applies to **audit representation**
| Dimension | Kind | Units / Vocabulary | Default role | Rank | Linkable |
|---|---|---|---|---|---|
| Audit scope | categorical | correspondence, office, field | priced | 10 | yes |
| Years under audit | numeric | tax years | priced | 20 | yes |

## 35. R&D credit scope — applies to **R&D credit study**
| Dimension | Kind | Units / Vocabulary | Default role | Rank | Linkable |
|---|---|---|---|---|---|
| Study type | categorical | first study, renewal, payroll offset election | priced | 10 | yes |
| Qualified spend | numeric | qualified research spend ($) | priced | 20 | yes |

## 36. Entity formation scope — applies to **entity formation**
| Dimension | Kind | Units / Vocabulary | Default role | Rank | Linkable |
|---|---|---|---|---|---|
| Entity type | categorical | single-member LLC, multi-member LLC, S-election, C-corp | priced | 10 | yes |
| Add-ons | categorical | EIN, state registrations, operating agreement coordination | priced | 20 | no |

## 37. IRS notice scope `[ADDED]` — applies to **IRS notice resolution**
| Dimension | Kind | Units / Vocabulary | Default role | Rank | Linkable |
|---|---|---|---|---|---|
| Notice type | categorical | CP2000 / underreporter, balance due series, penalty notice, identity verification, other correspondence | priced | 10 | no |
| Tax years involved | numeric | tax years | priced | 20 | no |

## 38. Benefit plan filing `[ADDED]` — applies to **5500**
| Dimension | Kind | Units / Vocabulary | Default role | Rank | Linkable |
|---|---|---|---|---|---|
| Participant count | numeric | plan participants | priced | 10 | no |
| Filing type | categorical | 5500-EZ, 5500-SF, full 5500 with schedules | priced | 20 | no |

## 39. Exemption application scope `[ADDED]` — applies to **nonprofit formation and exemption**
| Dimension | Kind | Units / Vocabulary | Default role | Rank | Linkable |
|---|---|---|---|---|---|
| Application path | categorical | 1023-EZ, full 1023, 1024, state-only registration | priced | 10 | no |

## 40. Property tax filing scope `[ADDED]` — applies to **business personal property tax**
| Dimension | Kind | Units / Vocabulary | Default role | Rank | Linkable |
|---|---|---|---|---|---|
| Jurisdiction count | numeric | filing jurisdictions | priced | 10 | no |

---

# PART VII — ENGAGEMENT TYPES WITH NO FLAGS (deliberate)

Per Build Reference v2 section 4 and 8, these ship with **no complexity dimensions in v1** — quote-required or trivially flat by design:

- **Cost segregation, business valuation, transaction advisory** — quote-required by default, ruled in the doc.
- **Extensions (4868, 7004, 8868)** — flat administrative filings.
- **Tax planning, fractional CFO, other advisory, custom** — inherently scoped by conversation; "other advisory" and "custom" are catch paths.
- **Amended returns (1040-X, amended business)** — mapped to their base return's flags rather than carrying their own (see mappings above).
- **Payroll processing** — carried by flag 27.
- **FBAR** — carried by flag 8.

---

# APPENDIX — Seed-session implementation notes (for the task file, not for Lori)

1. Flag `key` values should be stable snake_case slugs (e.g. `digital_assets`, `k1s_received`); dimension keys unique within their flag per `uq_complexity_dimensions_flag_key`.
2. Every dimension in this document ships with `question_text` NULL — lead-facing wording is deliberately a later data edit (the schema was built nullable for exactly this).
3. `hierarchy_rank` and `linkable` land exactly as tabled; `default_role` lands as tabled.
4. Unit menus become `complexity_dimension_units` rows with their own nullable `question_text`.
5. Vocabularies become `complexity_vocabulary_options` rows; pending Open Ruling A, each categorical also seeds an `other` option.
6. Applies-to mappings become `complexity_flag_engagement_types` rows against the canonical enum values in `app/core/enums.py` — never hand-copied labels.
7. Counts: 40 flags, 84 dimensions. "Roughly 45 flags" from the doc remains true in spirit; the catalog absorbs additions as data rows. (This line originally read 78 dimensions. Counting the tables in Parts I through VI gives 84. Ruled by Andrew on August 16, 2026: the tables are the ratified content and 78 was an authoring miscount, corrected here. The seed script and tests/test_complexity_catalog_seed.py pin 84.)

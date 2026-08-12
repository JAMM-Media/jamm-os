# STANDING RULES
- All file operations use the absolute path /home/corby/jamm-os/. Never use /mnt/c/Users paths. Never use Windows-style paths.
- Never use relative paths. Always use full absolute paths starting with /home/corby/jamm-os/.
- Never use the built-in file read tool to inspect file contents. Always use bash: cat, grep, sed. The file read tool caches stale content. Trust bash output only.
- Path comment at top of every file
- Never use && to chain commands
- Always use SQLAlchemy 2.0 Mapped[] syntax. Never use Column() style.
- Always scope every database query to firm_id. No exceptions.
- Never put business logic in routers. Logic goes in services/ or crud/.
- Always use get_current_firm from app.dependencies.tenant for auth. Never read firm_id from the request body.
- Background tasks need their own SessionLocal() in a try/finally block. Never pass the request db session into a background task.
- List endpoints return { items: [], total: N }. Never a plain array.
- Never use em dashes anywhere in any string, copy, or comment.
- Always use "engagements" not "projects". Always use "magic-link" not "portal link". Always use "automation presets" not "automation rules".
- Never trust file contents shown in VS Code opened against the Windows copy (C:\Users\corby\jamm-os) or Windows File Explorer. Verify all file state via the WSL terminal (cat, ls -la, wc -l) before assuming a file is stale, empty, or correct.
- Generated snapshot files (codebase_snapshot.txt, frontend/frontend_snapshot.txt) are gitignored. Never manually stage, commit, or resurrect them. Regenerate only via ./update_all_snapshots.sh.
- Before the first commit of any session, confirm git config user.email is ben@jammpx.com. Never assume git identity is correct without checking.
- Before writing or modifying anything touching the Concierge agent, read /home/corby/jamm-os/JAMM_PX_Perfect_Assistant_Build.md in full. Every Concierge task should be traceable to something described in that document.
- If a Concierge tool call fails inside the tool-use loop, the failure must surface as a diagnosable logged event, never as a generic deflection presented to the firm owner as if it were a real answer. Check backend logs for "Tool execution failed" before concluding a knowledge gap exists rather than a broken tool call.

---

# ENVIRONMENT SANITY CHECK — MANDATORY BEFORE ANY OTHER STEP
This section exists because Claude Code twice reported stale route-conflict files (frontend/src/app/settings/, frontend/src/app/calendar/, frontend/src/app/(dashboard)/) as real, current, build-blocking evidence and asked for permission to delete them. Both times, those files did not exist in the real repo at /home/corby/jamm-os. They existed only on the separate Windows-side checkout at /mnt/c/Users/corby/jamm-os, a pre-rename leftover copy that is for viewing only and is never the source of truth. Some tool call had actually resolved against that path instead of the real WSL repo, and reported what it found there as if it were current.

Before running any other command in this task:
1. Run: pwd — the output must be exactly /home/corby/jamm-os or a path underneath it. If it is not, stop and cd /home/corby/jamm-os before doing anything else.
2. State explicitly in the report, as its own line, that no command in this task read, listed, or resolved any path under /mnt/c/Users or any other Windows-side location. This is not optional boilerplate, it is a real claim that must be true.
3. If at any point a command needs to check whether something exists "on disk," that means the real WSL filesystem under /home/corby/jamm-os, never the Windows copy, even implicitly, even as a fallback.

---

# VERIFY BEFORE ACT — MANDATORY FOR EVERY TASK
Before making any change to any file:
1. Run: pwd — confirm output is /home/corby/jamm-os. If it is not, run: cd /home/corby/jamm-os
2. Run grep using the full absolute path and paste the full bash output:
   grep -n "pattern" /home/corby/jamm-os/path/to/file
3. If the pattern is not found, run:
   cat /home/corby/jamm-os/path/to/file | grep -c "pattern"
   Paste that result too.
4. If both return zero, STOP and report exactly what bash returned. Do not proceed. Do not guess. Do not find the closest match. Do not trust the file read tool.
5. Only proceed when bash grep with the absolute path confirms the pattern exists on disk.

This rule cannot be skipped. If the task says "find this pattern" and bash grep cannot find it, the task description is wrong — not the file. Stop and wait for updated instructions.

---

# VERIFY AFTER ACT — MANDATORY FOR EVERY CHANGE
After every file change:
- Run grep -n for the exact new string using the full absolute path and paste the full output
- Never report a fix as working without showing the bash grep output
- Never report a file as created without running ls -la and showing the output
- If grep does not confirm the change, fix it before moving to the next step
- Trust bash output only — never the file read tool

---

# MIGRATION PROCEDURE
Before every migration: run alembic current first.
After autogenerate: read the generated file before running upgrade head. If it touches tables you did not intend, delete it and write a manual migration.
If alembic current shows a revision but no tables exist: run alembic stamp base, then alembic upgrade head.

---

# REPORTING DISCIPLINE — MANDATORY FOR EVERY TASK
This section exists because a past session confidently claimed specific files were stale untracked leftovers safe to delete, citing a real commit hash correctly, then drew a false conclusion from it. The files did not exist on disk at all. The commit was real. The conclusion was not. That is the failure mode this section guards against: not sloppy guessing, but a plausible-sounding narrative that outran the actual evidence.

- Quote literal command output verbatim in every summary. Never paraphrase output, never assert a conclusion in place of showing the output it came from. If a claim cannot be backed by pasted, real output in the same message, it does not go in the summary as fact.
- If evidence is ambiguous, incomplete, contradictory, or simply absent, say so explicitly and stop. Do not fill a gap in the evidence with a story that sounds coherent. An honest "I don't have enough evidence to conclude this" is always the correct output when that is the true state.
- Never take any action, including deletions, fixes, or refactors, beyond what CHANGE INSTRUCTIONS explicitly names, even if something discovered mid-task seems to obviously justify it. Surface it as a finding in the report and wait for a real instruction. Diagnosis and action are separate steps, not one motion.
- Before claiming any file doesn't belong, is stale, is dead code, or should be deleted, confirm both that it exists on disk (ls -la) and its real git tracking status (git status --short and git ls-files) in the same message as the claim itself, not as a follow-up only produced if challenged.

---

# Section 3 - The task

TASK: Build the Lead model and ReferralPartner model — the CRM's foundational data layer. Models, three new enums, one migration creating both tables, and Pydantic schemas. No API endpoints or CRUD service functions in this task — that's a separate follow-up.

USE: claude fable-5

ENVIRONMENT SANITY CHECK:

pwd

State plainly that no path in this task resolves against /mnt/c/Users or any Windows-side copy.

VERIFY BEFORE ACT:

cat app/models/client.py
cat app/models/firm.py | head -40
cat app/db/base_class.py
find app -iname "lead.py" -o -iname "referral_partner.py"
grep -rn "class Lead\b\|class ReferralPartner\b" app/ --include="*.py"
grep -n "ENGAGEMENT_TYPE\|engagement_type" app/core/enums.py app/models/engagement.py
ls app/schemas/
.venv/bin/alembic heads

Paste all real output. Confirm neither Lead nor ReferralPartner exists anywhere in the codebase today. Confirm the real current alembic head — do NOT trust any hash written elsewhere in this task or in prior context; a real chain conflict was found and fixed earlier tonight specifically because a stated head turned out to be stale. Get the real head fresh, right now, before writing down_revision.

WHAT THIS IS:

Per the CRM/Acquisition Tracker build contract, Section 8. Lead is a record distinct from Client — a prospect, not yet a signed client. ReferralPartner is a simple per-firm entity for tracking repeat external referrers (attorneys, banks, other firms) who are not themselves clients.

Ben's explicit design decision: stage, lost_reason, source_platform, and provenance all get STRICT database-level enum enforcement — sa.Enum(EnumClass, native_enum=False), matching the real existing pattern on Client.referral_source (confirmed tonight, see app/models/client.py). This is a deliberate departure from the Task/Engagement convention of plain String status columns with schema-level-only enums — Ben chose stricter DB enforcement specifically for these four fields, accepting that future value additions require a real migration each time, same as the ReferralSource extension completed earlier tonight.

referral_source on Lead reuses the EXISTING ReferralSource enum from app/core/enums.py verbatim — do not create a second copy or a Lead-specific version. This is what lets attribution flow forward from Lead to Client on conversion without translation, per the contract's explicit design intent.

CHANGE INSTRUCTIONS:

1. In app/core/enums.py, add three new enum classes, following the exact real style of the existing ReferralSource class (str, Enum, docstring, value=name pattern):

class LeadStage(str, Enum):
    """A lead's position in the acquisition pipeline. Ordered but skippable -- a walk-in ready to sign can jump straight to proposal."""
    identified = "identified"
    contacted = "contacted"
    call_booked = "call_booked"
    proposal = "proposal"
    won = "won"
    lost = "lost"

class LeadLostReason(str, Enum):
    """Captured at the transition to lost. unqualified is filtered-on-purpose and never counts against conversion metrics -- that distinction is sacred, per the build contract."""
    unqualified = "unqualified"
    unresponsive = "unresponsive"
    chose_competitor = "chose_competitor"
    price = "price"
    timing = "timing"
    other = "other"

class SourcePlatform(str, Enum):
    """Layer 2 attribution: the where. Auto-derived from utm_source when a lead arrives through a tracked link; manual picker is the fallback for leads with no link behind them. For cold_outreach leads (see ReferralSource), this same field carries the mechanism instead of a platform."""
    facebook = "facebook"
    instagram = "instagram"
    tiktok = "tiktok"
    linkedin = "linkedin"
    youtube = "youtube"
    x = "x"
    google = "google"
    bing = "bing"
    nextdoor = "nextdoor"
    email = "email"
    phone = "phone"
    dm = "dm"
    direct_mail = "direct_mail"
    other = "other"

class LeadProvenance(str, Enum):
    """How we know this lead's attribution. Precedence is substitution, never blending: crm_lead beats firm_entered beats client_reported. Lower tiers fill blanks only and never overwrite higher tiers."""
    crm_lead = "crm_lead"
    firm_entered = "firm_entered"
    client_reported = "client_reported"

2. Create app/models/lead.py, modeled structurally on app/models/client.py (confirm the real current shape from VERIFY BEFORE ACT before writing). Fields:

   - id: UUID pk, default uuid.uuid4
   - firm_id: FK firms.id, CASCADE, nullable=False, indexed -- matches every other firm-scoped model
   - name: String(200), nullable=False
   - email: String(255), nullable=True -- NOT unique (unlike Client.email), since duplicate leads from re-submission or multiple channels are expected and should not be blocked
   - phone: String(50), nullable=True
   - stage: sa.Enum(LeadStage, name="leadstage", native_enum=False), nullable=False, default=LeadStage.identified, server_default="identified"
   - lost_reason: sa.Enum(LeadLostReason, name="leadlostreason", native_enum=False), nullable=True
   - referral_source: sa.Enum(ReferralSource, name="referralsource", native_enum=False), nullable=True -- reuses the existing enum, same name= as Client's column so it's the same underlying Postgres-side type name
   - source_platform: sa.Enum(SourcePlatform, name="sourceplatform", native_enum=False), nullable=True
   - utm_campaign, utm_source, utm_medium, utm_content, utm_term: String(255), nullable=True each -- stored verbatim per contract Section 8, no parsing or normalization
   - referring_client_id: FK clients.id, ondelete SET NULL, nullable=True -- bare FK only, no relationship(), matching the exact real reasoning already documented on Client.referring_client_id (nothing needs to traverse it yet)
   - referral_partner_id: FK referral_partners.id, ondelete SET NULL, nullable=True -- bare FK only, same reasoning
   - service_interest: String(100), nullable=True -- freeform for now; no fixed enum exists for firm service types today (confirm from VERIFY BEFORE ACT output whether one exists on Engagement; if it does, leave a code comment noting the future alignment opportunity, do not force a shared enum in this task)
   - entity_type: String(20), nullable=True -- mirrors Client.entity_type's exact comment and convention (individual | business | trust | estate | non_profit)
   - revenue_band: String(50), nullable=True -- plain String, not one of the four strict fields
   - urgency: Text, nullable=True -- raw captured answer to the timeline/urgency question; free text since the exact question wording lives in the not-yet-available nurture tree
   - hot: Boolean, nullable=False, default=False, server_default="false"
   - provenance: sa.Enum(LeadProvenance, name="leadprovenance", native_enum=False), nullable=False -- NO default and NO server_default. This must be explicitly set by every creation path, never silently assumed, because precedence correctness depends on it being real every time.
   - first_response_time: Integer, nullable=True -- minutes elapsed from lead creation to first outbound firm response; computed and set later by a service layer this task does not build
   - created_at, updated_at: DateTime(timezone=True), same lambda pattern as every other model in this codebase
   - firm: relationship("Firm", back_populates="leads") -- note this requires adding a leads relationship to app/models/firm.py; add it following the exact real pattern used for Firm's other back_populates relationships (confirm real pattern from VERIFY BEFORE ACT firm.py output)

3. Create app/models/referral_partner.py:

   - id: UUID pk, default uuid.uuid4
   - firm_id: FK firms.id, CASCADE, nullable=False, indexed
   - name: String(200), nullable=False
   - type: String(50), nullable=True -- freeform (attorney, bank, other_firm, etc.), no enum specified by the contract
   - notes: Text, nullable=True
   - created_at, updated_at: DateTime(timezone=True), same pattern

4. Write ONE Alembic migration creating both tables and both new foreign key constraints, down_revision set to whatever the real current head is (confirmed fresh in VERIFY BEFORE ACT, not assumed). Add the three new enum types as VARCHAR-backed columns per the native_enum=False pattern -- confirm the real exact upgrade/downgrade shape from a table-creation migration elsewhere in this codebase (search for one if the earlier examples in this task aren't sufficient) rather than inventing the shape from scratch.

5. Create app/schemas/lead.py with LeadBase, LeadCreate, LeadUpdate, LeadOut -- following the exact real structure of app/schemas/task.py (confirmed from VERIFY BEFORE ACT): a *Base with shared fields, *Create for input, *Update with all-optional fields, *Out with id/timestamps and model_config = ConfigDict(from_attributes=True). Local Pydantic enums are NOT needed here since these four fields already have real backend enums in core/enums.py -- import and reuse LeadStage, LeadLostReason, SourcePlatform, LeadProvenance, ReferralSource directly in the schema, do not redeclare them.

6. Create app/schemas/referral_partner.py with ReferralPartnerBase, ReferralPartnerCreate, ReferralPartnerUpdate, ReferralPartnerOut, same structural pattern.

Do NOT create any API router, any CRUD service function, or any endpoint in this task. Data layer and schemas only.

VERIFY AFTER ACT:

.venv/bin/alembic heads
.venv/bin/alembic upgrade head

PGPASSWORD=postgres psql -h localhost -U postgres -d jammpx_dev -c "\d leads"
PGPASSWORD=postgres psql -h localhost -U postgres -d jammpx_dev -c "\d referral_partners"

git diff --stat

Paste all real output. Confirm both tables exist with the real column list matching what was specified above, confirm a single clean head, confirm the migration applied with no errors.

MANUAL VERIFICATION:

**Restart the backend.** Confirm it boots with no import errors -- this touches app/core/enums.py and app/models/firm.py, both imported widely, so a mistake here would fail loudly at startup. No frontend check needed, nothing in the UI references these yet.

GIT:

Do not commit until Ben confirms the backend restarts cleanly and both tables show the correct real shape in psql.
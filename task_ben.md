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

TASK 1 OF 2: Build the nurture engine's sequence data model -- Sequence, SequenceVersion, Step, StepEdge, SequenceGoal. This defines the SHAPE of a sequence only. No Enrollment, no lead-specific state, no step-execution logic -- those are a separate follow-up task.

USE: claude fable-5

ENVIRONMENT SANITY CHECK:

pwd

State plainly that no path in this task resolves against /mnt/c/Users or any Windows-side copy.

VERIFY BEFORE ACT:

cat app/models/automation_rule.py
cat app/models/lead.py
grep -n "class TriggerEvent" -A20 app/core/enums.py
.venv/bin/alembic heads

Paste all real output. Confirm the real current alembic head fresh, live -- do NOT trust any hash written in this task's own text, this exact mistake has happened multiple times tonight already. Confirm the real AutomationRule.preset_key pattern before reusing it on SequenceVersion.

WHAT THIS IS:

Per the CRM/Acquisition Tracker build contract, Section 6 (nurture engine) and Section 8 (data model requirements). A Sequence is a named nurture flow, firm-scoped. Every edit creates a new SequenceVersion, which is genuinely immutable once created -- nothing about a SequenceVersion, Step, StepEdge, or SequenceGoal row is ever updated after creation, only new versions are created. Enrollments (built in a separate task) pin to one specific version and finish on it even if the sequence is edited later.

CHANGE INSTRUCTIONS:

1. In app/core/enums.py, add:

class StepType(str, Enum):
    """One node in a nurture sequence's step graph."""
    trigger = "trigger"
    email = "email"
    wait_fixed = "wait_fixed"
    wait_until_event = "wait_until_event"
    branch = "branch"
    action = "action"
    goal = "goal"
    won = "won"
    dead_end = "dead_end"

Do not add any other new enum in this file for this task -- edge condition_label and phase are plain strings on the model (freeform, matching the real tree's own labels like "yes", "no", "timeout", "loop", "PHASE 1"), not enums, since the specific v1 preset's real label vocabulary is not yet encoded and forcing an enum now risks missing a real label when that encoding task happens later.

2. Create app/models/sequence.py with:

class Sequence(Base):
    __tablename__ = "sequences"
    id: UUID pk, default uuid4
    firm_id: FK firms.id, CASCADE, nullable=False, indexed
    name: String(200), nullable=False
    is_active: Boolean, nullable=False, default=True, server_default="true"
    current_version_id: FK sequence_versions.id, nullable=True, ondelete SET NULL -- nullable because a brand new Sequence has no version yet at the instant of creation
    created_at, updated_at: DateTime(timezone=True), standard lambda pattern
    firm: relationship("Firm", back_populates="sequences") -- add this relationship to app/models/firm.py following the exact real pattern confirmed from VERIFY BEFORE ACT

class SequenceVersion(Base):
    __tablename__ = "sequence_versions"
    id: UUID pk, default uuid4
    sequence_id: FK sequences.id, CASCADE, nullable=False, indexed
    version_number: Integer, nullable=False
    preset_lineage_key: String(100), nullable=True, indexed -- matches the real AutomationRule.preset_key pattern confirmed in VERIFY BEFORE ACT
    created_at: DateTime(timezone=True) -- NO updated_at on this model or any model in this task. Genuine immutability means there is nothing to update; an updated_at column would be a lie about what this table guarantees.
    created_by_user_id: FK users.id, nullable=True, ondelete SET NULL
    Add a real unique constraint on (sequence_id, version_number) -- two versions of the same sequence must never share a number.

class Step(Base):
    __tablename__ = "sequence_steps"
    id: UUID pk, default uuid4
    sequence_version_id: FK sequence_versions.id, CASCADE, nullable=False, indexed
    step_key: String(50), nullable=False -- preserves the real tree's own node IDs (T1, 22, R1, etc) when that preset gets encoded later
    step_type: sa.Enum(StepType, name="steptype", native_enum=False), nullable=False
    channel: String(20), nullable=True, default="email", server_default="email" -- the SMS seam from contract Section 6.8, always "email" today
    phase: String(50), nullable=True -- freeform, matches the real tree's own phase labels
    is_modified_from_preset: Boolean, nullable=False, default=False, server_default="false"
    config: JSON, nullable=False, default=dict, server_default="{}" -- type-specific config, shape not enforced at the DB level
    created_at: DateTime(timezone=True) only, no updated_at, same immutability reasoning as SequenceVersion
    Add a real unique constraint on (sequence_version_id, step_key) -- no two steps in one version can share a key.

class StepEdge(Base):
    __tablename__ = "sequence_step_edges"
    id: UUID pk, default uuid4
    from_step_id: FK sequence_steps.id, CASCADE, nullable=False, indexed
    to_step_id: FK sequence_steps.id, CASCADE, nullable=False, indexed
    condition_label: String(50), nullable=True -- freeform, e.g. "yes", "no", "timeout", "loop"
    loop_cap: Integer, nullable=True -- only set on edges that form a real loop back to an earlier step; null means not a loop edge
    created_at: DateTime(timezone=True) only, same immutability reasoning

class SequenceGoal(Base):
    __tablename__ = "sequence_goals"
    id: UUID pk, default uuid4
    sequence_version_id: FK sequence_versions.id, CASCADE, nullable=False, indexed
    goal_event: String(100), nullable=False -- e.g. "lead.call_booked", matches real behavioral event type strings
    target_step_id: FK sequence_steps.id, nullable=False
    applies_to_phase: String(50), nullable=True -- matches Step.phase; null means the goal applies across the whole version, not scoped to one phase
    created_at: DateTime(timezone=True) only, same immutability reasoning

All FKs use string names in relationship() where relationships exist, per standing rules. Bare FKs with no relationship() where nothing needs to traverse it yet, matching the exact real reasoning already used repeatedly tonight on Lead's own FKs.

3. Write ONE Alembic migration creating all five tables plus the two unique constraints. Get the real fresh alembic head from VERIFY BEFORE ACT, do not trust any hash in this text.

4. Create app/schemas/sequence.py with SequenceBase/Create/Update/Out, SequenceVersionOut (read-only, no Create/Update schemas -- nothing ever creates or updates a SequenceVersion directly through a generic schema; a version is only ever produced by a real "publish a new version" operation, which is a separate future task, not generic CRUD), StepOut, StepEdgeOut, SequenceGoalOut (all read-only for the same reason -- these belong to an immutable version and are never independently created via a generic endpoint).

Do NOT build any CRUD functions, any API router, or any endpoints in this task. Data layer and read-only schemas only. This is the shape; nothing yet reads or writes it through an API.

VERIFY AFTER ACT:

.venv/bin/alembic heads
.venv/bin/alembic upgrade head

PGPASSWORD=postgres psql -h localhost -U postgres -d jammpx_dev -c "\d sequences"
PGPASSWORD=postgres psql -h localhost -U postgres -d jammpx_dev -c "\d sequence_versions"
PGPASSWORD=postgres psql -h localhost -U postgres -d jammpx_dev -c "\d sequence_steps"
PGPASSWORD=postgres psql -h localhost -U postgres -d jammpx_dev -c "\d sequence_step_edges"
PGPASSWORD=postgres psql -h localhost -U postgres -d jammpx_dev -c "\d sequence_goals"

git diff --stat

Paste all real output. Confirm all five tables exist with the real specified shape, confirm both unique constraints exist, confirm a single clean alembic head, confirm the migration applied with no errors.

MANUAL VERIFICATION:

**Restart the backend.** Confirm clean boot, no import errors. No frontend or browser check needed -- nothing reads this data yet.

GIT:

Do not commit until Ben confirms the backend restarts cleanly and all five real table shapes are confirmed via psql.
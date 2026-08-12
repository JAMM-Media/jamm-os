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

TASK 2 OF 2: Build the Enrollment model -- how one lead moves through one specific SequenceVersion. Requires Task 1 (Sequence/SequenceVersion/Step/StepEdge/SequenceGoal) to already be shipped and confirmed on main.

USE: claude fable-5

ENVIRONMENT SANITY CHECK:

pwd

State plainly that no path in this task resolves against /mnt/c/Users or any Windows-side copy.

VERIFY BEFORE ACT:

git log --oneline -3
cat app/models/sequence.py
cat app/models/lead.py
.venv/bin/alembic heads

Paste all real output. Confirm Task 1's commit (153644d) is genuinely on this branch before building on top of it. Confirm the real fresh alembic head -- do not trust any hash in this text.

WHAT THIS IS:

Per contract Section 6.1 and 6.3: an Enrollment ties one Lead to one SequenceVersion (pinned at enroll time, never repointed even if the sequence gets a new version later), tracks which Step it's currently sitting at, when it next needs attention, and whether/why it has stopped. Per Section 6.1's global stop conditions: unsubscribe (suppression list, exits forever), converted to Client, staff removes from sequence. Per Section 6.1's re-enrollment rule: no concurrent duplicate enrollment in the same sequence for the same lead -- this task adds a real partial unique index enforcing that at the database level, not just application logic that could be bypassed by a bug.

Loop caps (contract example: rebook loop caps at 2) require real per-enrollment counting -- this task stores loop progress as a JSON field keyed by loop identifier, incremented by future step-execution logic (not built in this task), checked against StepEdge.loop_cap.

CHANGE INSTRUCTIONS:

1. In app/core/enums.py, add:

class EnrollmentStatus(str, Enum):
    """Where an enrollment stands. active is the only status still being walked forward by the engine."""
    active = "active"
    unsubscribed = "unsubscribed"
    converted = "converted"
    removed_by_staff = "removed_by_staff"
    completed_dead_end = "completed_dead_end"
    completed_won = "completed_won"

2. Create app/models/enrollment.py:

class Enrollment(Base):
    __tablename__ = "enrollments"
    id: UUID pk, default uuid4
    firm_id: FK firms.id, CASCADE, nullable=False, indexed -- denormalized from lead for direct tenant-scoped queries, matching how firm_id is handled on every other model in this codebase rather than always joining through Lead
    lead_id: FK leads.id, CASCADE, nullable=False, indexed
    sequence_id: FK sequences.id, nullable=False, indexed -- denormalized from sequence_version_id at creation time, needed for the real no-duplicate-concurrent-enrollment rule below
    sequence_version_id: FK sequence_versions.id, nullable=False, indexed -- the real pin, never changes after creation
    current_step_id: FK sequence_steps.id, nullable=True -- nullable only in the brief instant between creation and the first step assignment
    next_action_time: DateTime(timezone=True), nullable=True -- null means no pending scheduled action (e.g. genuinely stopped, or waiting on an event with no timer component)
    status: sa.Enum(EnrollmentStatus, name="enrollmentstatus", native_enum=False), nullable=False, default=EnrollmentStatus.active, server_default="active"
    loop_counts: JSON, nullable=False, default=dict, server_default="{}" -- e.g. {"rebook": 1}, keyed by a loop identifier, incremented by future step-execution logic
    enrolled_at: DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    stopped_at: DateTime(timezone=True), nullable=True -- set when status leaves active
    created_at, updated_at: DateTime(timezone=True), standard lambda pattern -- Enrollment is real mutable state, unlike everything in Task 1, so it DOES get updated_at
    lead: relationship("Lead", back_populates="enrollments") -- add this relationship to app/models/lead.py following the exact real pattern already used for Lead's other relationships

Add a real partial unique index: unique on (lead_id, sequence_id) WHERE status = 'active'. This is the real interpretation of the no-duplicate-concurrent-enrollment rule -- it is keyed on the SEQUENCE, not the specific version, since a lead should not be enrolled twice in "the nurture preset" even across two different versions of it. If this interpretation seems genuinely wrong against the contract text on a fresh re-read, flag it plainly in your summary rather than silently picking a different one.

3. Write ONE Alembic migration creating enrollments plus the partial unique index and the EnrollmentStatus enum. Get the real fresh alembic head from VERIFY BEFORE ACT.

4. Create app/schemas/enrollment.py with EnrollmentOut only (read-only) -- no Create/Update schema, since enrolling a lead is a real operation with side effects (checking the partial unique index, assigning the first real step, setting next_action_time), not a generic CRUD create. That real enroll operation is a separate future task, not built here.

Do NOT build any CRUD functions beyond a bare get_enrollment_for_firm lookup, any API router, or any step-execution logic in this task.

VERIFY AFTER ACT:

.venv/bin/alembic heads
.venv/bin/alembic upgrade head

PGPASSWORD=postgres psql -h localhost -U postgres -d jammpx_dev -c "\d enrollments"
PGPASSWORD=postgres psql -h localhost -U postgres -d jammpx_dev -c "\di" | grep -i enrollment

git diff --stat

Paste all real output. Confirm the table shape, confirm the partial unique index specifically shows its WHERE clause in the index listing, confirm clean single alembic head and clean upgrade.

MANUAL VERIFICATION:

**Restart the backend.** Confirm clean boot, no import errors.

GIT:

Do not commit until Ben confirms clean backend boot and the real partial unique index confirmed via psql.
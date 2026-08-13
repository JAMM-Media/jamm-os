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

TASK 4b OF N: Investigate and honestly report on sequence version-pinning, per Andrew's Step 4 instruction ("a lead enrolled in a sequence stays on the version it enrolled under; editing the sequence never affects mid-walk leads"). Real research already done before this task: no code anywhere in the codebase writes to Enrollment.sequence_version_id after creation, and no code anywhere writes to Sequence.current_version_id at all. There is currently no real operation to publish a new SequenceVersion or move a Sequence's current_version_id forward. This task must determine whether this guarantee is meaningfully testable today, and report honestly if it is not, rather than writing a test that exercises nothing real.

USE: claude sonnet

ENVIRONMENT SANITY CHECK:

pwd

State plainly that no path in this task resolves against /mnt/c/Users or any Windows-side copy.

VERIFY BEFORE ACT:

cat app/models/sequence.py
cat app/models/enrollment.py
grep -rln "publish\|new_version\|create_version" app/crud/ app/services/ app/api/ 2>/dev/null
grep -rn "sequence_version_id\|current_version_id" app/ --include="*.py" | grep -v "tests/"

Paste all real output. Independently confirm the research finding stated in this task's own description -- do not trust it blindly, verify it yourself with fresh real commands, since this exact kind of self-verification has been the standing discipline all session. If you find any real code path this task's description missed that DOES touch sequence_version_id or current_version_id after creation, stop and report that specifically, since it would mean the finding in this task's own description is wrong and the real testable behavior is different from what is assumed here.

WHAT THIS IS:

Andrew's Step 4 instruction treats version-pinning as a locked design guarantee to test. The real current state of the codebase is that no mechanism exists yet that could violate this guarantee, because no mechanism exists yet to change a sequence's current version at all. This is structurally different from, for example, the provenance-precedence guarantee tested in Step 3, where a real function (update_lead_with_precedence) actively enforces the rule against real attempted violations. Here there is no analogous function to test, because the feature that would need to respect pinning (editing a sequence, publishing a new version) has not been built.

CHANGE INSTRUCTIONS:

Create tests/test_sequence_version_pinning.py.

Do NOT write a test that fabricates a fake "edit the sequence" operation by directly mutating rows to simulate what a future publish operation might someday do. That would be testing invented behavior, not real shipped behavior, and would produce a green test that proves nothing about the real system today.

Instead, write these real, honest tests:

1. test_enrollment_sequence_version_id_is_set_at_creation_and_immutable_by_schema: create a real Sequence, a real SequenceVersion, and a real Enrollment pointing at that version. Confirm the real EnrollmentOut schema is read-only for this field where relevant, and confirm directly via the real database (a fresh query after creation) that the value matches what was set at creation. This proves the field holds its value through a normal read cycle, which is the truthful, narrow claim currently verifiable.

2. test_no_code_path_currently_modifies_enrollment_sequence_version_id: a real, deliberate structural test. Search the real committed source tree (using Python's ast module or a real grep-based check performed AT TEST TIME, not hardcoded as a static assumption) for any assignment to .sequence_version_id anywhere under app/ outside of app/models/enrollment.py's own column definition and test files. Assert this search finds nothing. This is a real, enforceable test: if someone later adds code that reassigns this field without updating this guard test, the test will fail and force a conscious decision, which is exactly the kind of protection appropriate for a guarantee that today exists by absence rather than by active enforcement.

3. test_creating_new_sequence_version_does_not_alter_existing_enrollment: create a Sequence, SequenceVersion 1, and an Enrollment pinned to version 1. Create a second real SequenceVersion (version 2) for the same Sequence, following the exact real immutable-creation pattern already used elsewhere in this codebase (a new row, not an edit). Re-fetch the original Enrollment from the database. Assert its sequence_version_id is unchanged and still equals version 1's id. This is a real, legitimate test of the actual guarantee, using only operations that genuinely exist today (creating a new version is real; nothing needs to be invented), and it would genuinely catch a regression if some future code carelessly updated all enrollments when a new version is created.

In the test file's module docstring, state plainly and honestly: full version-pinning as a behavioral guarantee (a sequence being actively edited, or a real publish operation, correctly leaving mid-walk enrollments untouched) is not fully testable today, because no real edit or publish operation exists yet. These tests verify what is genuinely true right now: the field is set correctly at creation, nothing currently touches it afterward, and creating a new version in isolation does not disturb existing enrollments. Testing the full guarantee under real editing conditions is a task for whenever the sequence-editing feature itself is built, and should be added at that time, not simulated now.

TEST DISCIPLINE:

Test #2 is a real guard test and must be watched to fail: temporarily add a genuine (but test-only, clearly marked) line of code somewhere real in app/ that assigns to .sequence_version_id, confirm test #2 goes red and correctly identifies the real file and line it found, remove the test-only line, confirm green again, then run git diff to confirm the working tree is clean. Report the real before and after output in your summary.

Never weaken an assertion to make a test pass. If this investigation surfaces something different from what this task assumes, report it plainly rather than forcing the originally planned tests to fit.

No em dashes anywhere in any test file, string, comment, or test name.

VERIFY AFTER ACT:

.venv/bin/pytest tests/test_sequence_version_pinning.py -v 2>&1 | tail -60

Paste the real, full output.

Then:

.venv/bin/pytest > /tmp/pytest_output_step4b.txt 2>&1
echo "REAL EXIT CODE: $?"
tail -40 /tmp/pytest_output_step4b.txt

Paste all real output.

MANUAL VERIFICATION:

Ben will independently re-run the real guard-test cycle for test #2 himself, live, same as every prior guard test this session, before treating this as complete.

GIT:

Do not commit until Ben confirms the real red/green cycle output he has watched directly, plus the real full suite output.
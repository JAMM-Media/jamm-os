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

TASK 4a OF N: Write tests for stage-transition validity, per Andrew's Step 4 instruction ("stage transitions follow the six-stage pipeline and invalid transitions are rejected"). Real research already done: transition_lead_stage currently has NO validation preventing an invalid transition beyond lost requiring lost_reason. This task must surface that gap honestly, not paper over it with tests asserting protection that does not exist.

USE: claude sonnet

ENVIRONMENT SANITY CHECK:

pwd

State plainly that no path in this task resolves against /mnt/c/Users or any Windows-side copy.

VERIFY BEFORE ACT:

grep -n "def transition_lead_stage" -A 60 app/crud/lead.py
grep -n "class LeadStage" -A 10 app/core/enums.py

Paste all real output, the full function this time, not just the first 40 lines already seen. Confirm the complete real current transition logic for every stage value, not just won and lost.

WHAT THIS IS:

Real finding from research done before this task: transition_lead_stage has no check on the lead's CURRENT stage before applying a new one. Nothing prevents transitioning a lead already at won back to any earlier stage, nothing prevents transitioning a lead at lost forward again, and stages other than won/lost are applied with zero validation of any kind (confirmed from the original build task's own stated design: "For any other stage value: apply normally, no special handling"). The contract's Section 7.1 says the pipeline is "ordered but skippable" -- meaning forward skips (e.g. identified straight to proposal, a walk-in ready to sign) are legitimate by design, but nothing in the contract suggests backward moves or moves off a terminal state (won, lost) should be allowed, and the code currently does not distinguish these cases at all.

CHANGE INSTRUCTIONS:

Create tests/test_stage_transitions.py.

First, write tests that document and prove the REAL CURRENT behavior honestly, even where that behavior is permissive:

1. test_forward_skip_is_allowed: a lead at identified can transition directly to proposal (skipping contacted and call_booked), per the contract's explicit "ordered but skippable" design. Assert this succeeds, since it is intentional, not a bug.

2. test_lost_requires_lost_reason: already proven live tonight, the automated version -- transitioning to lost with no lost_reason raises ValueError, with lost_reason it succeeds and both fields are set correctly.

3. test_won_creates_client_and_sets_converted_client_id: already proven live tonight, the automated version.

Then, write tests that PROBE the real gap rather than assume protection exists:

4. test_transition_from_won_backward_is_currently_unblocked: attempt to transition a lead already at won back to contacted. Per real current code, this will SUCCEED (no error, no rejection). Write this test to assert the real current behavior -- it succeeds -- with a clear comment and a clear test name stating this is a gap, not a verified-safe design, so this is honestly on record as a finding rather than silently passing as if it were intended protection.

5. test_transition_from_lost_forward_is_currently_unblocked: same real probe, attempting lost back to identified or forward to call_booked. Assert the real current permissive behavior, documented the same honest way.

Do NOT write any test asserting that invalid transitions ARE rejected, since that would be asserting behavior that does not exist in the real shipped code, which is exactly the kind of false-passing test Andrew's TEST DISCIPLINE section prohibits ("never weaken an assertion to make a test pass").

At the top of the test file, include a real, clearly labeled module docstring section titled "KNOWN GAP" stating plainly: transition_lead_stage does not validate that a requested stage transition is a legitimate forward move or reject transitions away from a terminal state (won, lost). This should be flagged to Andrew as a real product decision needed (should terminal states be locked? should backward moves require a reason, similar to lost_reason?) before this gap is either fixed or explicitly accepted as intentional flexibility.

VERIFY AFTER ACT:

.venv/bin/pytest tests/test_stage_transitions.py -v 2>&1 | tail -60

Paste the real, full output.

Then:

.venv/bin/pytest > /tmp/pytest_output_step4a.txt 2>&1
echo "REAL EXIT CODE: $?"
tail -40 /tmp/pytest_output_step4a.txt

Paste all real output. Confirm the real new test count and that the only failures present are the same 9 pre-existing Stripe failures.

MANUAL VERIFICATION:

No red/green guard-test cycle needed for this specific task, since these tests document real current behavior rather than guard a specific protection mechanism. Ben will review the KNOWN GAP docstring for accuracy and decide whether to raise it with Andrew before or alongside committing.

GIT:

Do not commit until Ben has reviewed the KNOWN GAP finding and confirms the real test output.
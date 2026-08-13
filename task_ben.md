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

TASK 3 OF N: Write tests codifying the locked attribution rules as law, per Andrew's direct instruction. Provenance precedence, UTM-derived source_platform protection, and attribution carrying forward on conversion. Much of this behavior was manually verified live earlier tonight -- this task turns that into real, repeatable, guarded automated coverage.

USE: claude fable-5

ENVIRONMENT SANITY CHECK:

pwd

State plainly that no path in this task resolves against /mnt/c/Users or any Windows-side copy.

VERIFY BEFORE ACT:

cat app/crud/lead.py
cat app/api/leads.py
grep -n "convert_lead_to_client\|transition_lead_stage" app/crud/lead.py
cat app/core/enums.py | grep -A20 "class LeadProvenance"
grep -n "source_platform" app/crud/lead.py app/api/leads.py app/api/intake.py
find tests -iname "*attribution*" -o -iname "*provenance*" -o -iname "*lead*"

Paste all real output. Confirm the real current tier-comparison logic in update_lead_with_precedence exactly as it exists today. Specifically confirm whether source_platform has ANY distinct protection mechanism separate from the general provenance-tier comparison, or whether it is treated identically to every other field. If no distinct mechanism exists for source_platform specifically -- meaning two updates at the SAME provenance tier could overwrite a UTM-derived source_platform with a manually picked one -- stop and report this as a real finding per Andrew's explicit instruction style (a gap between contract intent and shipped behavior matters more than a green test), rather than writing a test that asserts protection that does not actually exist. If it turns out the general provenance-tier logic already fully satisfies this rule in every real case, explain exactly why in your summary before writing the test, so the reasoning is on record.

WHAT THIS IS:

Per Andrew's Step 3 instruction, three locked product decisions to test as law, not as ordinary behavior:

1. Provenance precedence is substitution, never blending: crm_lead beats firm_entered beats client_reported. Lower tiers fill blanks only, never overwrite higher tiers. This was manually proven live earlier tonight via direct curl and psql verification against a real running server -- this task is the automated, repeatable version of that same proof.

2. A UTM-derived source_platform is never overwritten by a hand-picked one. Per VERIFY BEFORE ACT, confirm whether this is really a distinct guarantee or fully covered by rule 1 before writing this test.

3. Attribution captured at intake flows forward unchanged when a lead converts to a client. This was also manually proven live earlier tonight via convert_lead_to_client and a real psql check on the resulting Client row -- this task is the automated version.

CHANGE INSTRUCTIONS:

Create tests/test_attribution_rules.py:

1. test_higher_tier_provenance_blocks_lower_tier_overwrite_of_nonnull_field: create a lead with crm_lead provenance and a real non-null field value (e.g. phone). Attempt an update with firm_entered provenance on that same field. Assert the original value is unchanged and provenance remains crm_lead. This is the real automated version of tonight's manual curl proof -- match its real shape (same tier ordering, same blocked-overwrite behavior) using the actual CRUD function directly, not just the API layer, so the test is precise about which function is under test.

2. test_lower_tier_provenance_fills_null_field: create a lead with crm_lead provenance and a null field (e.g. revenue_band). Attempt an update with client_reported provenance setting that field. Assert it IS set, since lower tiers may fill blanks, only not overwrite. This proves the other real half of the substitution rule, not just the blocking half.

3. test_equal_tier_provenance_allows_normal_update: create a lead with firm_entered provenance. Update again with firm_entered provenance on a non-null field. Assert the update applies normally. This proves equal-tier updates are not incorrectly blocked, which the earlier manual testing tonight also confirmed.

4. Based on the real finding from VERIFY BEFORE ACT: either write test_utm_derived_source_platform_protected_from_manual_override if a real distinct mechanism exists, or write nothing and report the gap plainly if it does not, per Andrew's explicit instruction to report gaps rather than paper over them with an assertion that does not reflect real behavior.

5. test_attribution_flows_forward_unchanged_on_conversion: create a lead with real referral_source, referring_client_id, and entity_type values set. Transition it to won via the real transition_lead_stage function. Assert the resulting Client has the exact same values for all three fields, unchanged. This is the automated version of tonight's manual won-conversion proof.

6. test_dropped_fields_do_not_transfer_and_are_documented: per the real dropped-fields list already documented in tonight's commit history (stage, lost_reason, source_platform, utm_campaign, utm_source, utm_medium, utm_content, utm_term, referral_partner_id, revenue_band, urgency, hot, provenance, first_response_time), confirm the resulting Client model genuinely has no equivalent field for at least a few of these (pick 2 or 3 real representative ones, e.g. hot and urgency) so this documented gap is enforced by a real test, not just a commit message claim that could silently go stale.

TEST DISCIPLINE, applies to every test written in this task:

Test #1 (higher tier blocks lower tier) is the real guard test for this task. It must be watched to fail: temporarily modify update_lead_with_precedence so it always applies the update regardless of tier (e.g. remove the tier comparison entirely and always apply), run test #1, confirm it goes genuinely red with a real assertion failure showing the value was overwritten when it should not have been, restore the real code, re-run to confirm green, then run git diff on the touched source file and confirm it exactly matches the original committed state. Report the real before and after output in your summary, not a description of having done it -- Ben will independently re-run this exact cycle himself regardless of what you report, per tonight's established practice.

Never weaken an assertion to make a test pass. If any test in this task exposes a real defect in the already-shipped attribution logic, stop, do not modify the test to accommodate the defect, and report the defect plainly as a finding instead.

Tests create their own leads, firms, and any other data they need, and must not depend on seed data or test ordering.

No em dashes anywhere in any test file, string, comment, or test name.

VERIFY AFTER ACT:

.venv/bin/pytest tests/test_attribution_rules.py -v 2>&1 | tail -60

Paste the real, full output of this file running in isolation.

Then:

.venv/bin/pytest > /tmp/pytest_output_step3.txt 2>&1
echo "REAL EXIT CODE: $?"
tail -40 /tmp/pytest_output_step3.txt

Paste all real output. Confirm the real new test count, confirm the only real failures present are the same 9 pre-existing Stripe failures from before, and confirm the real total pass count increased by exactly the number of new tests added in this task.

MANUAL VERIFICATION:

Ben will independently re-run the real guard-test red/green cycle for test #1 himself, live, the same way as every prior guard test tonight, before treating this as complete.

GIT:

Do not commit until Ben confirms the real red/green cycle output he has watched directly, not a paraphrase, plus the real full suite output.
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

TASK: Real bug, root-caused via a Claude in Chrome DOM inspection after two prior fix attempts (z-index bump, then a shield element) both failed. The actual cause: every message row's floating toolbar exists in the DOM at all times across the entire message list, hidden only via opacity-0, with no pointer-events control. Since opacity does not affect hit-testing, these invisible toolbars remain fully interactive and can sit on top of other elements, including an open dropdown from a different row, at the exact screen coordinates that dropdown occupies. Measured live: hovering over the Edit button's visual location returns a descendant of a completely different, invisible row's toolbar via elementFromPoint, not the dropdown or its shield, which is why clicks in that region get intercepted by an invisible element instead of landing on the intended button.

USE: claude sonnet

ENVIRONMENT SANITY CHECK:

pwd

State plainly that no path in this task resolves against /mnt/c/Users or any Windows-side copy.

VERIFY BEFORE ACT:

sed -n '312,320p' "src/app/(app)/peer-network/page.tsx"

Paste the real output. Confirm the toolbar div's className includes the conditional: `${(showPicker || (isOwn && showMoreMenu)) ? 'opacity-100' : 'opacity-0 group-hover:opacity-100'}`, meaning when neither showPicker nor showMoreMenu is true and the row is not being hovered, the toolbar sits at opacity-0 with no accompanying pointer-events control.

If this does not match, stop and paste the real content instead of proceeding.

WHAT THIS IS:

Every message row in the feed renders its own MessageBubble, and every MessageBubble unconditionally renders this toolbar div, regardless of whether that specific row is currently hovered or has any menu open. Visibility is controlled purely by opacity and a CSS group-hover rule scoped to that row's own wrapper. Opacity does not remove an element from hit-testing, an opacity-0 element still receives pointer events and still participates in elementFromPoint resolution at its screen coordinates unless pointer-events is explicitly set to none. Live inspection confirmed this directly: with one row's dropdown open, a different row's invisible toolbar was the actual element returned by elementFromPoint over the dropdown's Edit button region, intercepting the click before it could reach the dropdown at all. This is a real defect independent of the specific dropdown bug, since any invisible interactive toolbar sitting on top of real content anywhere in the list could produce the same class of interference.

CHANGE INSTRUCTIONS:

On the toolbar div at the line confirmed in VERIFY BEFORE ACT, add `pointer-events-none` to the classes applied in the hidden (opacity-0) branch of the existing conditional, and `pointer-events-auto` to the classes applied in the visible (opacity-100) branch, so the toolbar is only interactive when actually visible, either because the row is hovered (group-hover, handled by the existing CSS rule needing its own pointer-events-auto companion) or because showPicker/showMoreMenu is true for that specific row.

Since group-hover:opacity-100 is a CSS pseudo-class transition and not a JS-driven boolean like showPicker/showMoreMenu, the pointer-events toggle for the hover case also needs to be CSS-driven: add `group-hover:pointer-events-auto` alongside the existing `group-hover:opacity-100` in the same conditional branch, so pointer-events only activates on actual hover of that specific row's own group, matching the same mechanism already used for opacity.

The full conditional should end up structured as: when showPicker or (isOwn and showMoreMenu) is true, apply `opacity-100 pointer-events-auto`. Otherwise, apply `opacity-0 pointer-events-none group-hover:opacity-100 group-hover:pointer-events-auto`. Write the exact template literal reflecting this logic, preserving every other existing class on this div unchanged.

Do not touch the shield element added in the prior task, leave it in place for now since removing it is out of scope for this task and it is not actively harmful. Do not touch any other opacity-0/group-hover element in the file (the timestamp span at line 298, or the DM/subgroup hide button at line 1403), this task is scoped to the message toolbar only, since that is the one confirmed to cause the reported bug.

VERIFY AFTER ACT:

sed -n '312,320p' "src/app/(app)/peer-network/page.tsx"

cd /home/corby/jamm-os/frontend
npm run build 2>&1

git diff --stat

VERIFY AFTER ACT must include the literal, pasted output of npm run build, not a summary or a claim that it passed. Confirm zero TypeScript errors from the real, literal output. If npm run build cannot execute in your session, state that plainly, but restate clearly that Ben must run it himself in his real WSL terminal before this is trusted as done.

MANUAL VERIFICATION:

**Restart the frontend.** Reload /peer-network. Hover a message you own that has another message directly below it. Open the more-options menu, move the mouse from the three-dot button down to Delete, the exact motion that failed in the two prior attempts, and confirm the row below no longer intercepts the click anywhere along that path. Actually click Delete and confirm the message is deleted. Also test Edit. Separately, confirm normal hover behavior still works correctly elsewhere in the list: hovering any row still reveals its own toolbar normally, and moving the mouse away still hides it. Report back plainly and specifically whether Delete now actually works, since this is the third attempt at the same bug and the first two both failed on this exact claim.

GIT:

Do not commit until Ben confirms in the browser.
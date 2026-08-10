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

TASK: The Peer Network thread panel (ThreadPanel) renders its parent message and reply messages with its own hand-rolled markup, entirely separate from MessageBubble, the component that received the flat-layout rebuild, the hover toolbar, reactions, and edit/delete. Confirmed by Ben live in the browser via screenshot comparison against Slack: thread panel messages still show the old dark-blue rounded bubble style with no avatar, and hovering a message inside the thread shows no toolbar at all, since ThreadPanel never calls MessageBubble. Fix: make ThreadPanel render both the parent message and every reply through MessageBubble, so the thread panel inherits the same look and functionality as the main feed permanently, instead of drifting out of sync again.

USE: claude sonnet

ENVIRONMENT SANITY CHECK:

pwd

State plainly that no path in this task resolves against /mnt/c/Users or any Windows-side copy.

VERIFY BEFORE ACT:

sed -n '193,225p' "src/app/(app)/peer-network/page.tsx"
sed -n '713,815p' "src/app/(app)/peer-network/page.tsx"
sed -n '1240,1262p' "src/app/(app)/peer-network/page.tsx"
sed -n '1494,1510p' "src/app/(app)/peer-network/page.tsx"

Paste the real output of all four. Confirm: MessageBubble's full prop signature, ThreadPanel's current hand-rolled rendering of the parent message and the replies.map() block with the rounded-[14px] bubble styling, the real call pattern for MessageBubble in the main feed (with onLabelClick, onEdit, onDelete, onReact, onReply, replyAuthors, lastReplyAt), and ThreadPanel's current call site showing only parentMessage, replies, myHandle, onClose, onSendReply as props.

If any of these does not match, stop and paste the real content instead of proceeding.

WHAT THIS IS:

ThreadPanel currently duplicates message rendering instead of reusing MessageBubble. This is the actual root cause of two things Ben found: the old bubble style persisting inside threads, and the complete absence of the hover toolbar (React, Reply, more-options) on any message inside a thread. The fix is not to re-style ThreadPanel's own markup to imitate MessageBubble. It is to make ThreadPanel call MessageBubble directly for both the parent message and each reply, so there is exactly one place this rendering logic lives, and future changes to MessageBubble automatically apply inside threads too.

CHANGE INSTRUCTIONS:

1. Expand ThreadPanel's props to accept: myMemberId (or however isOwn is currently determined for the caller, check the main feed's isOwn calculation and match it), onReact (emoji: string, messageId: string) => void or equivalent signature matching handleReact's real signature, onEditStart (messageId: string) => void matching setEditingMessageId's usage, onDeleteStart (messageId: string) => void matching setConfirmDeleteId's usage, and onLabelClick (memberId: string, currentLabel: string) => void matching setAliasTarget's usage. Name these consistently with how they are already named and used at the main feed's MessageBubble call site, do not invent new naming conventions.

2. Replace the hand-rolled parent message block (the div with author_display, renderBody, and formatTimestamp) with a real MessageBubble call, passing message={parentMessage}, grouped={false}, isOwn computed the same way the main feed computes it, displayLabel computed consistently with how the main feed computes it, onEdit and onDelete wired only when isOwn is true and the message is not deleted (matching the main feed's exact conditional pattern), onReact wired unless deleted, and onReply explicitly set to undefined, since replying to a message while already viewing its own thread is not a supported action.

3. Replace the replies.map() block's hand-rolled bubble markup with a real MessageBubble call per reply, using the same prop-wiring pattern as step 2, but since every reply message already has a parent_id set, onReply should also be undefined here, consistent with the fix already shipped that hides Reply entirely on any message with a parent_id.

4. Update the ThreadPanel call site (the one passing parentMessage, replies, myHandle, onClose, onSendReply) to also pass the newly required props, using the exact same handlers already in scope at that point (handleReact, setEditingMessageId, setConfirmDeleteId, setAliasTarget), the same ones already passed to the main feed's MessageBubble a few hundred lines earlier in this same file. Do not create new state or new handler functions, reuse what already exists.

5. Do not touch the compose box, the Send button, the thread header, or the parent/reply divider line at the top of the replies section. Those are unrelated to this bug.

VERIFY AFTER ACT:

sed -n '713,830p' "src/app/(app)/peer-network/page.tsx"
sed -n '1494,1515p' "src/app/(app)/peer-network/page.tsx"

cd /home/corby/jamm-os/frontend
npm run build 2>&1

git diff --stat

VERIFY AFTER ACT must include the literal, pasted output of npm run build, not a summary or a claim that it passed. Confirm zero TypeScript errors from the real, literal output. If npm run build cannot execute in your session, state that plainly and explicitly, but this does not excuse Ben from needing to run it himself before trusting this as done, restate that requirement clearly in your report.

Confirm the diff shows ThreadPanel now calling MessageBubble twice, once for the parent and once per reply, with the old rounded-[14px] bubble markup fully removed.

MANUAL VERIFICATION:

**Restart the frontend.** Reload /peer-network, open a thread with at least one reply. Confirm: the parent message and every reply now render as flat rows with avatar, sender name, and timestamp header, matching the main feed's style exactly, not the old blue bubble. Hover the parent message and confirm React and, if it is your own message, the more-options menu appear, but Reply does not. Hover a reply message and confirm the same, React and more-options where applicable, no Reply button. Confirm reacting to a message inside the thread actually works and the reaction shows up. Report back plainly whether this now matches the Slack reference screenshot Ben provided.

GIT:

Do not commit until Ben confirms in the browser.
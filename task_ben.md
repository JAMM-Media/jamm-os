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

# Section 3 - The task

# Task: Fix proxy route crashing on 204 No Content responses, and remove temporary diagnostic logging

USE: claude sonnet

## VERIFY BEFORE ACT

grep -n "PROXY FETCH ERROR" "/home/corby/jamm-os/frontend/src/app/api/backend/[...path]/route.ts"

Confirm the temporary diagnostic console.error lines added during live debugging are present in both catch blocks (the attemptRefresh function and the main proxyRequest function).

sed -n '155,169p' "/home/corby/jamm-os/frontend/src/app/api/backend/[...path]/route.ts"

Confirm the current final response-building block: const data = await res.text() followed by new NextResponse(data, { status: res.status, ... }), with no special handling for status codes that the Response constructor forbids from carrying a body.

## WHAT IS WRONG

Confirmed via direct server-side error logging: the proxy route crashes with "TypeError: Response constructor: Invalid response status code 204" whenever the backend returns a 204 No Content response (such as the newly-implemented POST /notes/mark-read endpoint, and likely also DELETE /notes/{note_id} and other 204-returning endpoints that may not have been exercised through this proxy path before). The Fetch API's Response constructor, per the HTTP spec, disallows any body -- including an empty string -- on responses with status 204, 205, or 304. The proxy unconditionally passes the awaited response text as the body to NextResponse regardless of status code, which throws for these specific status codes. The backend itself always behaves correctly (its own logs consistently show a clean 204), but the proxy crashes trying to relay that response to the browser, which the browser then sees as a 503 Service Unavailable with no indication of the real cause, since the crash happens inside the proxy's own catch block, which was previously swallowing the actual error entirely.

## ACTION

File: /home/corby/jamm-os/frontend/src/app/api/backend/[...path]/route.ts

Fix 1 -- handle no-body status codes correctly. Replace the final response-building block:

    const data = await res.text()
    return new NextResponse(data, {
      status: res.status,
      headers: {
        'Content-Type': contentType || 'application/json',
      },
    })

With a version that checks for the no-body status codes and constructs the response without a body in that case:

    if ([204, 205, 304].includes(res.status)) {
      return new NextResponse(null, { status: res.status })
    }
    const data = await res.text()
    return new NextResponse(data, {
      status: res.status,
      headers: {
        'Content-Type': contentType || 'application/json',
      },
    })

Fix 2 -- remove the temporary diagnostic logging added during live debugging, restoring both catch blocks to their clean form (or optionally keep lightweight logging if useful going forward -- your call, but remove the exact temporary "PROXY FETCH ERROR" marker text either way since it was explicitly a debugging aid, not intended as permanent instrumentation).

In the attemptRefresh function's catch block, revert to:

  } catch {
    return null
  }

In the main proxyRequest function's catch block, you may either revert fully to the original:

  } catch {
    return NextResponse.json(
      { detail: 'Backend unreachable' },
      { status: 503 }
    )
  }

or keep minimal, permanent error logging without the temporary marker text, at your discretion -- if logging is kept, use a professional log line rather than the ad-hoc debugging label used tonight.

Do not change the SSE streaming handling, the PDF response handling, the 401 refresh-and-retry logic, the multipart detection added in a prior fix, or any other part of this file.

## VERIFY AFTER ACT

grep -n "204, 205, 304" "/home/corby/jamm-os/frontend/src/app/api/backend/[...path]/route.ts"

Expected: present, in the new no-body status check.

grep -n "PROXY FETCH ERROR" "/home/corby/jamm-os/frontend/src/app/api/backend/[...path]/route.ts"

Expected: no matches -- temporary diagnostic marker fully removed.

cd /home/corby/jamm-os/frontend
npm run build

Expected: zero TypeScript errors.

## MANUAL VERIFICATION (the actual test)

1. Restart the frontend with a clean build.
2. Open a client's Notes panel, confirm POST /notes/mark-read now returns 204 successfully in the Network tab, no 503, no error.
3. Reload the page and reopen the same client's Notes panel, confirm previously-read notes now correctly persist as read.
4. Regression check: delete a note (which also returns 204 via DELETE /notes/{note_id}) and confirm that still works correctly too, since it shares the same status code and was likely silently broken by this same bug even before tonight's testing.
5. Regression check: ask the Concierge a normal question, confirm streaming responses still work correctly, unaffected by this change.
6. Regression check: download a morning briefing PDF, confirm PDF responses still work correctly.

Report what you observe at steps 2, 3, and 4 specifically.

## GIT

cd /home/corby/jamm-os
git add -A
git commit -m "fix: proxy route was crashing with 'Invalid response status code 204' whenever the backend returned a 204 No Content response, since the Fetch API's Response constructor forbids any body (even an empty string) on 204/205/304 status codes and the proxy unconditionally passed response text as the body regardless of status. This silently broke every 204-returning endpoint relayed through the proxy, surfacing now via the newly-implemented mark-as-read endpoint but likely also affecting note deletion and any other 204 response. Also removed temporary diagnostic logging added during live debugging."
git pull --rebase origin main
git push origin main

If conflicts on task.md use --theirs. Conflicts on source files use --ours.
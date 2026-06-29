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

# Task: Fix Next.js proxy route destroying multipart file uploads via hardcoded JSON Content-Type and text-based body reading

USE: claude sonnet

## VERIFY BEFORE ACT

cat "/home/corby/jamm-os/frontend/src/app/api/backend/[...path]/route.ts"

Confirm the current proxyRequest function: headers is built with a hardcoded 'Content-Type': 'application/json' with no read of the incoming request's actual Content-Type, and the body is read with await request.text() for any non-GET/HEAD method, with no special handling for multipart content.

## WHAT IS WRONG

Confirmed via extensive live testing: engagement letter PDF uploads fail with a 422 "file field required" error no matter what is fixed on the frontend component or the shared axios client, because every request in the app passes through this single proxy route on its way to the real backend, and this route unconditionally overwrites Content-Type with application/json and reads the body as text.

For a multipart/form-data request (a file upload), this is doubly destructive: the boundary-bearing Content-Type header the browser correctly generated is discarded and replaced with application/json, and the binary file bytes inside the body are corrupted by being decoded as UTF-8 text via request.text(). The backend therefore receives a body it cannot parse as multipart at all, reporting the file field as entirely missing, regardless of what the frontend actually sent.

This proxy is shared by every request type in the app (JSON bodies, SSE streaming, PDF responses already have special-cased handling further down in this same file), so the fix must add a new branch specifically for multipart requests without altering the existing JSON, streaming, or PDF-response handling that the rest of the app correctly depends on.

## ACTION

File: /home/corby/jamm-os/frontend/src/app/api/backend/[...path]/route.ts

In proxyRequest, after the existing cookieToken/incomingAuth header logic and before the body-reading block, detect the incoming request's actual Content-Type and branch on whether it is multipart:

  const incomingContentType = request.headers.get('Content-Type') ?? ''
  const isMultipart = incomingContentType.startsWith('multipart/form-data')

  const headers: Record<string, string> = isMultipart
    ? {}
    : { 'Content-Type': 'application/json' }
  if (isMultipart) {
    headers['Content-Type'] = incomingContentType
  }
  if (incomingAuth) {
    headers['Authorization'] = incomingAuth
  } else if (cookieToken) {
    headers['Authorization'] = `Bearer ${cookieToken}`
  }

This preserves the existing JSON default for every other request type, while forwarding the exact original Content-Type (boundary included) unchanged for multipart requests.

Then update the body-reading block to read multipart bodies as raw binary instead of text, since request.text() corrupts binary file content:

  if (!['GET', 'HEAD'].includes(request.method)) {
    if (isMultipart) {
      const arrayBuffer = await request.arrayBuffer()
      if (arrayBuffer.byteLength > 0) init.body = arrayBuffer
    } else {
      const body = await request.text()
      if (body) init.body = body
    }
  }

Do not change the streaming (SSE) response handling, the PDF response handling, the 401 refresh-and-retry logic, or any other part of this file. This task only changes how the incoming request's Content-Type and body are read and forwarded, specifically adding a multipart-aware branch alongside the existing JSON behavior, which must remain unchanged for every non-multipart request.

## VERIFY AFTER ACT

grep -n "isMultipart\|incomingContentType" "/home/corby/jamm-os/frontend/src/app/api/backend/[...path]/route.ts"

Expected: present, with both the header-branching and body-reading logic using it.

cd /home/corby/jamm-os/frontend
npm run build

Expected: zero TypeScript errors.

## MANUAL VERIFICATION (the actual test)

1. Restart the frontend (full kill and restart).
2. Open DevTools Network tab.
3. Upload the same PDF for engagement letter signature, click Send for Signature.
4. Confirm the request now succeeds with no 422 error.
5. Check the Network tab's request headers for this upload request specifically, confirm Content-Type now shows multipart/form-data with an actual boundary string, not application/json.
6. Regression check: ask the Concierge a normal question and confirm streaming responses still work exactly as before, unaffected by this change.
7. Regression check: download a morning briefing PDF (the existing Download briefing button) and confirm PDF responses still work exactly as before.
8. Regression check: perform any normal JSON-based action (e.g. creating a client, editing an engagement) and confirm those still work exactly as before.

Report what you observe at steps 4, 6, 7, and 8 specifically, since this file is shared by the entire app and a regression here would be far more damaging than the original bug.

## GIT

cd /home/corby/jamm-os
git add -A
git commit -m "fix: Next.js API proxy route was unconditionally overwriting every request's Content-Type with application/json and reading bodies as text, which silently destroyed multipart file uploads by stripping the boundary header and corrupting binary content; added a multipart-aware branch that forwards the original Content-Type and reads the body as raw binary for file uploads specifically, leaving JSON, streaming, and PDF-response handling unchanged"
git pull --rebase origin main
git push origin main

If conflicts on task.md use --theirs. Conflicts on source files use --ours.
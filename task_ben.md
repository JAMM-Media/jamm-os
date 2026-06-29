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

# Task: Fix engagement letter PDF upload still failing due to axios client's default JSON Content-Type overriding multipart auto-detection

USE: claude sonnet

## VERIFY BEFORE ACT

grep -n "Content-Type" /home/corby/jamm-os/frontend/src/lib/api.ts

Confirm the shared axios instance sets headers: { 'Content-Type': 'application/json' } as a default applied to all requests through this client.

sed -n '218,226p' /home/corby/jamm-os/frontend/src/components/engagements/SendEngagementLetterModal.tsx

Confirm the upload-and-prepare call currently passes no per-request headers override at all (the previous fix removed the incorrect manual multipart header but did not account for the client's own default JSON header still applying).

## WHAT IS WRONG

Confirmed via live testing, repeated after a clean dev server restart and hard refresh, ruling out stale cache: the engagement letter PDF upload still fails with the identical 422 "file field required" error even after removing the manual Content-Type: multipart/form-data header in a previous fix.

Root cause: the shared axios client in lib/api.ts sets Content-Type: application/json as a default header applied to every request. Removing the per-call header override was not sufficient, because axios still applies the client's own default header when no override is present. The browser only auto-generates the correct multipart boundary header when no Content-Type is set at all for that specific request. Since the default JSON header was still being applied, the request left the browser as Content-Type: application/json with a FormData body attached, which the server cannot parse into any fields, producing the same missing-file error as before.

## ACTION

File: /home/corby/jamm-os/frontend/src/components/engagements/SendEngagementLetterModal.tsx

Update the upload-and-prepare call to explicitly clear the Content-Type header for this one request, overriding the client's default so the browser can set the correct multipart boundary automatically:

        const uploadRes = await api.post(
          `/esign/upload-and-prepare?engagement_id=${engagementId}`,
          formData,
          { headers: { 'Content-Type': undefined } }
        )

Setting the header value to undefined (not omitting the headers option entirely) is required here, since omitting it lets the client's own default still apply. Explicitly setting it to undefined tells axios to skip sending that header for this request, allowing the browser's own multipart handling to take over.

Do not change the shared api client's default headers in lib/api.ts itself, since that default is correct and desired for the rest of the app's JSON-based requests. Do not change the FormData construction, the file field name, or any other part of this component.

## VERIFY AFTER ACT

grep -n "Content-Type.*undefined" /home/corby/jamm-os/frontend/src/components/engagements/SendEngagementLetterModal.tsx

Expected: present on the upload-and-prepare call.

cd /home/corby/jamm-os/frontend
npm run build

Expected: zero TypeScript errors.

## MANUAL VERIFICATION (the actual test)

1. Restart the frontend (kill and restart, do not rely on hot reload given today's history).
2. Open an engagement, click Send Engagement Letter, switch to Upload Your Own PDF.
3. Upload a real PDF, enter a fee amount, click Send for Signature.
4. Open DevTools Network tab before submitting, so the actual request can be inspected if it fails again.
5. If it still fails, report the exact Content-Type header shown on the outgoing request in the Network tab's request headers (not response), so we can see definitively whether it is still application/json, multipart with no boundary, or correctly multipart with a boundary string this time.
6. If it succeeds, confirm the success toast appears and the dashboard's Awaiting Signature section now shows this real document.

Report what you observe at step 6, or the exact request Content-Type header from step 5 if it still fails.

## GIT

cd /home/corby/jamm-os
git add -A
git commit -m "fix: engagement letter PDF upload still failed after the previous header fix because the shared axios client's default Content-Type: application/json was still being applied; explicitly clearing the header for this one request lets the browser set the correct multipart boundary"
git pull --rebase origin main
git push origin main

If conflicts on task.md use --theirs. Conflicts on source files use --ours.
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

# Task: Fix engagement letter PDF upload failing due to malformed multipart header, and fix the crash when displaying validation errors

USE: claude sonnet

## VERIFY BEFORE ACT

sed -n '195,235p' /home/corby/jamm-os/frontend/src/components/engagements/SendEngagementLetterModal.tsx

Confirm the current upload-and-prepare call sets headers: { 'Content-Type': 'multipart/form-data' } manually with no boundary parameter, and confirm the catch block's msg extraction assumes err.response.data.detail is always a string.

## WHAT IS WRONG

Confirmed via live testing and direct backend response inspection: uploading a PDF for engagement letter signature fails with a 422 error, "loc": ["body", "file"], "msg": "Field required", even though the frontend correctly builds a FormData with a file field attached under the exact name the backend expects.

Root cause: the request explicitly sets Content-Type: multipart/form-data with no boundary string. When this header is left unset, the browser's FormData handling sets it automatically with the required boundary delimiter, which the server needs to split the multipart body into individual fields. Manually overriding it without a boundary produces a body the server cannot parse into any fields at all, so FastAPI reports the file field as entirely missing rather than malformed.

Separately, when this (or any) validation error occurs, the catch block's error message extraction assumes response.data.detail is always a string. FastAPI validation errors return detail as an array of objects (each with type, loc, msg, input keys), not a string. Since the array is not undefined, the existing ?? 'Failed to send engagement letter' fallback never triggers, and the raw array of objects gets passed directly to toast.error(), which cannot render an object as text and crashes the entire app with "Objects are not valid as a React child."

## ACTION

File: /home/corby/jamm-os/frontend/src/components/engagements/SendEngagementLetterModal.tsx

Fix 1: Remove the manually-set Content-Type header on the upload-and-prepare call entirely, letting the client set it automatically with the correct boundary:

        const uploadRes = await api.post(
          `/esign/upload-and-prepare?engagement_id=${engagementId}`,
          formData
        )

Fix 2: Add a helper function near the top of this component (or inline in both catch blocks, since there are two upload paths -- template and PDF -- that each have their own catch block with the same fragile pattern) that safely extracts a displayable string from any error shape:

function extractErrorMessage(err: unknown): string {
  const detail = (err as { response?: { data?: { detail?: unknown } } })?.response?.data?.detail
  if (typeof detail === 'string') return detail
  if (Array.isArray(detail)) {
    return detail
      .map((d) => (typeof d === 'object' && d !== null && 'msg' in d ? String((d as { msg: unknown }).msg) : String(d)))
      .join(', ')
  }
  return 'Failed to send engagement letter'
}

Replace both catch blocks' message extraction (the template-based send path's catch block, and the PDF upload path's catch block) to use this helper:

      } catch (err: unknown) {
        toast.error(extractErrorMessage(err))
      }

This ensures any future validation error, not just this specific missing-file case, displays as readable text (e.g. "Field required") instead of crashing the app.

Do not change the FormData construction, the file field name, the engagement_id query parameter, or any other part of either submit path. Do not touch the backend.

## VERIFY AFTER ACT

grep -n "extractErrorMessage\|Content-Type.*multipart" /home/corby/jamm-os/frontend/src/components/engagements/SendEngagementLetterModal.tsx

Expected: extractErrorMessage present and used in both catch blocks; the manual multipart Content-Type header line is gone.

cd /home/corby/jamm-os/frontend
npm run build

Expected: zero TypeScript errors.

## MANUAL VERIFICATION (the actual test)

1. Restart the frontend.
2. Open an engagement, click Send Engagement Letter, switch to Upload Your Own PDF.
3. Upload a real PDF, enter a fee amount, click Send for Signature.
4. Confirm the upload now succeeds (no 422, no React crash) and the success toast appears.
5. Regression check: trigger a different validation error on purpose (e.g. submit with no fee amount entered) and confirm the error now displays as readable text in a toast instead of crashing the app.

Report what you observe at steps 4 and 5 specifically.

## GIT

cd /home/corby/jamm-os
git add -A
git commit -m "fix: engagement letter PDF upload was failing because a manually-set multipart Content-Type header lacked the required boundary string, causing the server to receive an unparseable body; also fixed validation error display crashing the app when FastAPI returns a structured error array instead of a string"
git pull --rebase origin main
git push origin main

If conflicts on task.md use --theirs. Conflicts on source files use --ours.
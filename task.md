# JAMM PX — Task Batch

Read every instruction in this file before writing a single line of code. Execute in the order listed.

---

## STANDING RULES

- Frontend: Next.js 14 App Router, TypeScript always, Tailwind CSS, shadcn/ui.
- Never touch files not listed in a task's scope.
- Never add new npm or pip packages unless explicitly instructed.

---

## TASK 1 — Fix content clipping: add overflow-y-auto to all list pages

**Problem:** The main content wrapper on list pages uses `h-full` which constrains height to the viewport. Without `overflow-y-auto`, rows below the fold are clipped and unreachable — no scrollbar appears.

**Fix:** Add `overflow-y-auto` to the outer content `<div>` on each affected page. The target div in each file has className `"flex flex-col h-full p-6 gap-4"`. Change it to `"flex flex-col h-full p-6 gap-4 overflow-y-auto"` in every file listed below.

**Files to edit — find `"flex flex-col h-full p-6 gap-4"` and add `overflow-y-auto` in each:**

1. `frontend/src/app/billing/page.tsx`
2. `frontend/src/app/billing/wip/page.tsx`
3. `frontend/src/app/calendar/page.tsx`
4. `frontend/src/app/clients/page.tsx`
5. `frontend/src/app/documents/page.tsx`
6. `frontend/src/app/engagements/page.tsx`
7. `frontend/src/app/tasks/page.tsx`

In each file, make only this one change — add `overflow-y-auto` to that specific div's className. Do not touch anything else in these files.

---

## EXECUTION ORDER

1. Task 1 — all seven files

After all tasks: report every file modified and confirm no TypeScript errors.
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

# Task: Build reusable JAMM-branded confirm modal, replace all 8 window.confirm() calls across the app

USE: claude sonnet

## VERIFY BEFORE ACT

cat /home/corby/jamm-os/frontend/src/components/ui/Modal.tsx

Confirm the existing Modal component's props (open, onClose, title, children, footer, size) and styling conventions, to build the new ConfirmModal on top of it rather than duplicating structure.

grep -n "window.confirm" -B 2 -A 3 /home/corby/jamm-os/frontend/src/components/concierge/ConciergePanel.tsx /home/corby/jamm-os/frontend/src/components/engagements/EditEngagementModal.tsx

Confirm all 8 current call sites match what is listed below, in case line numbers have shifted since this task was written.

## WHAT IS WRONG

The app uses the browser's native window.confirm() dialog in 8 places across 2 files. This dialog is rendered by the browser itself, not the page, so it cannot be styled, colored, or branded in any way -- it always shows as a generic "localhost:3000 says" box regardless of the app's actual design. This breaks visual consistency with the rest of the product, which has a fully custom design system including an existing branded Modal component. The fix is to build a reusable, JAMM-branded confirm modal and a matching hook that mimics window.confirm()'s ergonomics (an awaitable function returning true/false), then convert all 8 existing call sites to use it instead.

## ACTION

Step 1: Create a new reusable confirm modal component. Create /home/corby/jamm-os/frontend/src/components/ui/ConfirmModal.tsx:

// frontend/src/components/ui/ConfirmModal.tsx
'use client'
import { Modal } from './Modal'

interface ConfirmModalProps {
  open: boolean
  message: string
  confirmLabel?: string
  cancelLabel?: string
  destructive?: boolean
  onConfirm: () => void
  onCancel: () => void
}

export function ConfirmModal({
  open,
  message,
  confirmLabel = 'Confirm',
  cancelLabel = 'Cancel',
  destructive = false,
  onConfirm,
  onCancel,
}: ConfirmModalProps) {
  return (
    <Modal
      open={open}
      onClose={onCancel}
      title="Confirm"
      size="sm"
      footer={
        <>
          <button
            onClick={onCancel}
            className="text-[13px] font-medium px-3 py-1.5 rounded-[6px] border border-[0.5px] border-surface-border dark:border-dark-border text-[#6B7280] dark:text-[#9CA3AF] hover:border-brand hover:text-brand dark:hover:border-[#4A7FA5] dark:hover:text-[#4A7FA5] transition-colors"
          >
            {cancelLabel}
          </button>
          <button
            onClick={onConfirm}
            className={`text-[13px] font-medium px-3 py-1.5 rounded-[6px] transition-colors ${
              destructive
                ? 'bg-[#DC2626] text-white hover:bg-[#B91C1C]'
                : 'bg-brand dark:bg-[#4A7FA5] text-white hover:opacity-90'
            }`}
          >
            {confirmLabel}
          </button>
        </>
      }
    >
      <p className="text-[13px] text-[#374151] dark:text-[#D1D5DB] whitespace-pre-wrap leading-relaxed">
        {message}
      </p>
    </Modal>
  )
}

Step 2: Create a matching hook. Create /home/corby/jamm-os/frontend/src/lib/hooks/useConfirm.tsx:

// frontend/src/lib/hooks/useConfirm.tsx
'use client'
import { useState, useCallback, useRef } from 'react'
import { ConfirmModal } from '@/components/ui/ConfirmModal'

interface ConfirmOptions {
  message: string
  confirmLabel?: string
  cancelLabel?: string
  destructive?: boolean
}

export function useConfirm() {
  const [options, setOptions] = useState<ConfirmOptions | null>(null)
  const resolveRef = useRef<((value: boolean) => void) | null>(null)

  const confirm = useCallback((opts: ConfirmOptions | string): Promise<boolean> => {
    const normalized = typeof opts === 'string' ? { message: opts } : opts
    setOptions(normalized)
    return new Promise((resolve) => {
      resolveRef.current = resolve
    })
  }, [])

  const handleConfirm = useCallback(() => {
    resolveRef.current?.(true)
    resolveRef.current = null
    setOptions(null)
  }, [])

  const handleCancel = useCallback(() => {
    resolveRef.current?.(false)
    resolveRef.current = null
    setOptions(null)
  }, [])

  const ConfirmDialog = options ? (
    <ConfirmModal
      open={true}
      message={options.message}
      confirmLabel={options.confirmLabel}
      cancelLabel={options.cancelLabel}
      destructive={options.destructive}
      onConfirm={handleConfirm}
      onCancel={handleCancel}
    />
  ) : null

  return { confirm, ConfirmDialog }
}

This hook exposes an async confirm() function that behaves like window.confirm() (call it, await the result, get true or false) while actually rendering a real, branded modal behind the scenes. ConfirmDialog must be rendered somewhere in the component tree of whatever component calls useConfirm() -- typically near the top of that component's JSX return.

Step 3: Wire it into ConciergePanel.tsx. Import and call the hook near the other hooks at the top of the component:

const { confirm, ConfirmDialog } = useConfirm()

Render {ConfirmDialog} somewhere in the component's JSX return, near the top level (e.g. immediately after the outer wrapping div opens, before the header).

Convert all 7 window.confirm() call sites in this file. For each one, the containing function must be or become async if it is not already, and the call changes from a synchronous window.confirm(msg) returning a boolean directly, to an awaited confirm(msg) call:

Site 1 (line ~461, handleClearConversation): make the function async, change to:
    const confirmed = await confirm({ message: 'Clear this conversation? This cannot be undone.', confirmLabel: 'Clear', destructive: true })

Site 2 (line ~755, inside the client-resolve async block): already inside an async function, change to:
    const ok = await confirm('You have unsaved changes. Navigate away?')

Site 3 (line ~771, inside executeAction): already async, change to:
    const ok = await confirm('You have unsaved changes. Navigate away?')

Site 4 (line ~984, draft-send confirmation with dynamic message): the containing onClick handler must become async, change to:
    const confirmed = await confirm(`Open ${uiContext.entity_name ?? 'this client'}'s Messages tab with this draft ready to send?\n\nMessage:\n${draft}\n\nYou will have a final chance to review before sending.`)

Site 5 (line ~1346, STAFF_REASSIGN): the containing onClick handler must become async, change to:
    const confirmed = await confirm('Open the engagement to apply this reassignment?')

Site 6 (line ~1352, INVOICE_ITEMS): the containing onClick handler must become async, change to:
    const confirmed = await confirm('Open billing to create this invoice?')

Site 7 (line ~1367, second draft-send confirmation, duplicate of site 4's pattern with currentContent instead of draft): the containing onClick handler must become async, change to:
    const confirmed = await confirm(`Open ${uiContext.entity_name ?? 'this client'}'s Messages tab with this draft ready to send?\n\nMessage:\n${currentContent}\n\nYou will have a final chance to review before sending.`)

For any onClick={() => { ... }} handler that needs to become async, change it to onClick={async () => { ... }} -- React supports async event handlers without any special handling required.

Step 4: Wire it into EditEngagementModal.tsx the same way. Import useConfirm, call the hook, render {ConfirmDialog} in the component's JSX, and convert the one call site (line ~95):

    const confirmed = await confirm(`${uncheckedQcCount} checklist item${uncheckedQcCount > 1 ? 's are' : ' is'} not checked. Mark engagement as complete anyway?`)

The containing function must be or become async if it is not already.

Do not change the actual confirmation logic, messages, or subsequent behavior at any of the 8 sites -- only the mechanism used to ask the question. Do not touch any other file.

## VERIFY AFTER ACT

find /home/corby/jamm-os/frontend/src/components/ui/ConfirmModal.tsx /home/corby/jamm-os/frontend/src/lib/hooks/useConfirm.tsx

Expected: both files exist.

grep -c "window.confirm" /home/corby/jamm-os/frontend/src/components/concierge/ConciergePanel.tsx /home/corby/jamm-os/frontend/src/components/engagements/EditEngagementModal.tsx

Expected: 0 for both files -- every window.confirm() call replaced.

grep -c "await confirm(" /home/corby/jamm-os/frontend/src/components/concierge/ConciergePanel.tsx

Expected: 7.

grep -c "await confirm(" /home/corby/jamm-os/frontend/src/components/engagements/EditEngagementModal.tsx

Expected: 1.

cd /home/corby/jamm-os/frontend
npm run build

Expected: zero TypeScript errors.

## MANUAL VERIFICATION (the actual test)

1. Restart the frontend with a clean build.
2. Trigger the Clear Conversation confirm (ask a question, click the trash icon). Confirm the dialog now shows as a real, JAMM-branded modal matching the app's design (rounded corners, correct colors, proper Cancel/Clear buttons), not the native browser "localhost:3000 says" box.
3. Confirm clicking Cancel correctly cancels (conversation stays), and clicking Clear (styled as destructive/red) correctly clears.
4. Test at least one more of the 7 remaining ConciergePanel sites if reachable (e.g. trigger a scenario with unsaved changes and attempt navigation via a chip), confirm it also shows the new branded modal.
5. Test the EditEngagementModal site: attempt to mark an engagement complete with unchecked QC items, confirm the new branded modal appears there too.
6. Regression check: confirm Escape key still closes the new confirm modal (inherited from the base Modal component), and clicking the overlay outside the modal also closes it as a cancel.

Report what you observe at steps 2, 3, and 5 specifically.

## GIT

cd /home/corby/jamm-os
git add -A
git commit -m "feat: replace all 8 native window.confirm() dialogs across the app with a reusable, JAMM-branded ConfirmModal and useConfirm hook, built on the existing Modal component. Native browser confirm dialogs cannot be styled and always displayed as a generic localhost box, breaking visual consistency with the rest of the product's design system."
git pull --rebase origin main
git push origin main

If conflicts on task.md use --theirs. Conflicts on source files use --ours.
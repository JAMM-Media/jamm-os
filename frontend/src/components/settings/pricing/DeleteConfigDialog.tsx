// frontend/src/components/settings/pricing/DeleteConfigDialog.tsx
'use client'
//
// The delete confirmation, on the two-call pattern.
//
// THE WARNING BODY IS THE SERVER'S CENSUS, VERBATIM. The dialog does not open
// until DELETE has already been called once WITHOUT confirm and refused with a
// 422 whose detail counts exactly what would be destroyed: the dependent
// configurations, the tiers, the option prices. That text is rendered as
// received. Nothing here counts anything, and nothing here estimates: a
// client-side guess at a blast radius is a number nobody checked, and it would
// be wrong in precisely the cases where being right matters.
//
// Calling DELETE to obtain the warning is safe because the refusal path writes
// nothing. The server loads the config, counts, and raises before the first
// delete, so a refused delete is a free read.
//
// THE CONSEQUENCE COPY IS MODE DIFFERENTIATED, and the two modes are not
// variations of one sentence. Removing a question that prices on its own takes
// its amounts out of the fee and leaves the rest of the schedule alone.
// Removing one that sits inside another answer also leaves that answer with
// nothing pricing it, because its own price was cleared to make room. Those
// are different consequences and the dialog says which one applies.

const labelClass = 'text-[11px] font-medium text-[#6B7280] uppercase tracking-[0.05em]'

export type DeleteMode = 'additive' | 'matrix'

export default function DeleteConfigDialog({
  mode,
  questionLabel,
  parentLabel,
  census,
  onConfirm,
  onCancel,
  working,
}: {
  mode: DeleteMode
  questionLabel: string
  // Named in plain words for the matrix case. The census names ids and counts;
  // this says which answer on screen is about to be left unpriced.
  parentLabel: string | null
  census: string
  onConfirm: () => void
  onCancel: () => void
  working: boolean
}) {
  return (
    <div className="rounded-[6px] border border-red-300 dark:border-red-800 bg-red-50 dark:bg-red-900/20 p-3 flex flex-col gap-2">
      <span className={labelClass}>Remove {questionLabel}</span>

      {/* The server's own count of what goes. Verbatim, never summarised. */}
      <p className="text-[12px] text-brand dark:text-[#EDEEF0] whitespace-pre-line">{census}</p>

      {mode === 'additive' ? (
        <p className="text-[12px] text-[#6B7280]">
          This question prices on its own, and its amounts add to the fee. Removing it
          takes those amounts out of every quote from here on. Nothing else in this
          schedule changes, and leads simply stop being asked it.
        </p>
      ) : (
        <p className="text-[12px] text-[#6B7280]">
          This question sits inside {parentLabel === null ? 'another answer' : parentLabel}.
          The answer above it carries no price of its own, because that price was cleared
          to let this one price. Removing this question leaves that branch with nothing
          pricing it, so a lead who reaches it routes to quote until you price the answer
          above again or put another question inside it.
        </p>
      )}

      <div className="flex items-center gap-2">
        <button
          type="button"
          disabled={working}
          onClick={onConfirm}
          className="rounded-[6px] bg-red-600 text-white text-[13px] px-3 py-1.5 disabled:opacity-50"
        >
          Remove it permanently
        </button>
        <button
          type="button"
          disabled={working}
          onClick={onCancel}
          className="rounded-[6px] border border-surface-border dark:border-dark-border text-[13px] px-3 py-1.5 text-brand dark:text-[#EDEEF0] disabled:opacity-50"
        >
          Keep it
        </button>
      </div>
    </div>
  )
}

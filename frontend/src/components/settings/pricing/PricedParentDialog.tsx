// frontend/src/components/settings/pricing/PricedParentDialog.tsx
'use client'
//
// The priced-parent refusal, shown to the owner in the server's own words.
//
// THE BODY OF THIS DIALOG IS THE SERVER'S REFUSAL, VERBATIM. It arrives as the
// detail of the 422 that refused the create, it names the tier or option and
// the amount sitting on it, and it is rendered exactly as received. There is no
// generic replacement copy anywhere in this component and no client-side guess
// at what the refusal said. The one sentence this file adds of its own is the
// consequence of agreeing, which the refusal does not state: the price on the
// parent goes away.
//
// Confirming is an explicit, separate act. The refusal itself changes nothing,
// which is what makes showing it safe: a refused write is a free read.

const labelClass = 'text-[11px] font-medium text-[#6B7280] uppercase tracking-[0.05em]'

export default function PricedParentDialog({
  refusal,
  parentLabel,
  onConfirm,
  onCancel,
  working,
}: {
  refusal: string
  parentLabel: string
  onConfirm: () => void
  onCancel: () => void
  working: boolean
}) {
  return (
    <div className="rounded-[6px] border border-amber-300 dark:border-amber-700 bg-amber-50 dark:bg-amber-900/20 p-3 flex flex-col gap-2">
      <span className={labelClass}>This answer is priced</span>

      {/* Verbatim. Never summarised, never replaced. */}
      <p className="text-[12px] text-brand dark:text-[#EDEEF0] whitespace-pre-line">{refusal}</p>

      <p className="text-[12px] text-[#6B7280]">
        Prices live only at the end of a chain, so a question can price or it can have
        questions inside it, never both. Continuing clears the price on {parentLabel} and
        then adds the new question inside it. The new question prices instead, and the one
        above it stops carrying an amount of its own.
      </p>

      <div className="flex items-center gap-2">
        <button
          type="button"
          disabled={working}
          onClick={onConfirm}
          className="rounded-[6px] bg-brand text-white text-[13px] px-3 py-1.5 disabled:opacity-50"
        >
          Clear the price and add the question
        </button>
        <button
          type="button"
          disabled={working}
          onClick={onCancel}
          className="rounded-[6px] border border-surface-border dark:border-dark-border text-[13px] px-3 py-1.5 text-brand dark:text-[#EDEEF0] disabled:opacity-50"
        >
          Leave it as it is
        </button>
      </div>
    </div>
  )
}

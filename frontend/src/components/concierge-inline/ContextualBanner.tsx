// frontend/src/components/concierge-inline/ContextualBanner.tsx
'use client'

interface ContextualBannerProps {
  message: string
  count: number
  actionLabel: string
  onAction: () => void
  tone: 'green' | 'amber' | 'red'
}

export function ContextualBanner({ message, count, actionLabel, onAction, tone }: ContextualBannerProps) {
  const styles = {
    green: {
      wrapper: 'bg-status-green/15 ring-1 ring-status-green-text/40 shadow-[0_0_16px_rgba(6,95,70,0.25)]',
      text: 'text-status-green-text',
      button: 'border border-status-green-text/60 text-status-green-text font-normal hover:bg-status-green/20 transition-colors',
    },
    amber: {
      wrapper: 'bg-status-amber/15 ring-1 ring-status-amber-text/40 shadow-[0_0_16px_rgba(146,64,14,0.25)]',
      text: 'text-status-amber-text',
      button: 'border border-status-amber-text/60 text-status-amber-text font-normal hover:bg-status-amber/20 transition-colors',
    },
    red: {
      wrapper: 'bg-status-red/15 ring-1 ring-status-red-text/40 shadow-[0_0_16px_rgba(153,27,27,0.30)]',
      text: 'text-status-red-text',
      button: 'border border-status-red-text/60 text-status-red-text font-normal hover:bg-status-red/20 transition-colors',
    },
  }
  const { wrapper: wrapperClass, text: textClass, button: buttonClass } = styles[tone]

  return (
    <div className={`flex items-center gap-3 px-4 py-2.5 rounded-[8px] ${wrapperClass}`}>
      <div className={`flex items-baseline gap-1.5 flex-1 ${textClass}`}>
        <span className="text-[13px] font-bold flex-shrink-0">
          {count}
        </span>
        <p className="text-[13px] leading-[1.4]">
          {message}
        </p>
      </div>
      <button
        onClick={onAction}
        className={`text-[11px] px-3 py-1.5 rounded-[4px] flex-shrink-0 ${buttonClass}`}
      >
        {actionLabel}
      </button>
    </div>
  )
}

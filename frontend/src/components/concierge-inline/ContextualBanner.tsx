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
      wrapper: 'bg-status-green border-status-green-text',
      text: 'text-status-green-text',
      button: 'bg-status-green-text text-white hover:opacity-90',
    },
    amber: {
      wrapper: 'bg-status-amber border-status-amber-text',
      text: 'text-status-amber-text',
      button: 'bg-status-amber-text text-white hover:opacity-90',
    },
    red: {
      wrapper: 'bg-status-red border-status-red-text',
      text: 'text-status-red-text',
      button: 'bg-status-red-text text-white hover:opacity-90',
    },
  }
  const { wrapper: wrapperClass, text: textClass, button: buttonClass } = styles[tone]

  return (
    <div className={`flex items-center gap-3 px-4 py-2.5 rounded-[8px] border border-[0.5px] ${wrapperClass}`}>
      <span className={`text-[13px] font-bold flex-shrink-0 ${textClass}`}>
        {count}
      </span>
      <p className={`flex-1 text-[13px] leading-[1.4] ${textClass}`}>
        {message}
      </p>
      <button
        onClick={onAction}
        className={`text-[11px] font-medium px-3 py-1.5 rounded-[4px] flex-shrink-0 transition-colors ${buttonClass}`}
      >
        {actionLabel}
      </button>
    </div>
  )
}

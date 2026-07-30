// frontend/src/components/concierge-inline/GhostTextField.tsx
'use client'

interface GhostTextFieldProps {
  value: string
  onChange: (value: string) => void
  suggestedCompletion?: string
  placeholder?: string
  rows?: number
}

export function GhostTextField({
  value,
  onChange,
  suggestedCompletion,
  placeholder,
  rows = 3,
}: GhostTextFieldProps) {
  const sharedTypography = 'text-[13px] leading-[1.5] font-sans'
  const sharedPadding = 'px-3 py-2'

  return (
    <div
      className={`relative rounded-[6px] border border-[0.5px] border-surface-border dark:border-dark-border bg-surface-input dark:bg-dark-card focus-within:ring-1 focus-within:ring-brand-light focus-within:border-brand-light transition-shadow`}
    >
      {/* Ghost completion overlay -- shows value (invisible) + suggestion (muted) */}
      {suggestedCompletion && value && (
        <div
          aria-hidden
          className={`absolute inset-0 ${sharedPadding} ${sharedTypography} pointer-events-none select-none whitespace-pre-wrap break-words overflow-hidden rounded-[6px]`}
        >
          <span className="text-transparent">{value}</span>
          <span className="text-muted-foreground/50">{suggestedCompletion}</span>
        </div>
      )}
      <textarea
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        rows={rows}
        className={`relative w-full ${sharedPadding} ${sharedTypography} bg-transparent text-foreground placeholder:text-muted-foreground/60 focus:outline-none resize-none rounded-[6px]`}
      />
    </div>
  )
}

// frontend/src/components/ui/SelectInput.tsx

import { cn } from '@/lib/utils'

interface SelectInputProps extends React.SelectHTMLAttributes<HTMLSelectElement> {
  error?: boolean
  options: { value: string; label: string }[]
  placeholder?: string
}

export function SelectInput({
  error,
  options,
  placeholder,
  className,
  ...props
}: SelectInputProps) {
  return (
    <select
      className={cn(
        'h-9 w-full px-3 rounded-[6px] text-[13px] transition-colors appearance-none',
        'bg-surface-input dark:bg-dark-card',
        'border border-[0.5px]',
        'text-brand dark:text-[#EDEEF0]',
        'focus:outline-none',
        error
          ? 'border-status-red-text focus:border-status-red-text'
          : 'border-surface-border dark:border-dark-border focus:border-brand-light',
        className
      )}
      {...props}
    >
      {placeholder && (
        <option value="" disabled>
          {placeholder}
        </option>
      )}
      {options.map((opt) => (
        <option key={opt.value} value={opt.value}>
          {opt.label}
        </option>
      ))}
    </select>
  )
}

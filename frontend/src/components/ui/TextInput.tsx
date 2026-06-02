// frontend/src/components/ui/TextInput.tsx

import { cn } from '@/lib/utils'

interface TextInputProps extends React.InputHTMLAttributes<HTMLInputElement> {
  error?: boolean
}

export function TextInput({ error, className, ...props }: TextInputProps) {
  return (
    <input
      className={cn(
        'h-9 w-full px-3 rounded-[6px] text-[13px] transition-colors',
        'bg-surface-input dark:bg-dark-card',
        'border border-[0.5px]',
        'text-brand dark:text-[#EDEEF0]',
        'placeholder:text-[#9CA3AF]',
        'focus:outline-none',
        error
          ? 'border-status-red-text focus:border-status-red-text'
          : 'border-surface-border dark:border-dark-border focus:border-brand-light',
        className
      )}
      {...props}
    />
  )
}

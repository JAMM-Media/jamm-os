// frontend/src/components/ui/FormField.tsx

import { cn } from '@/lib/utils'

interface FormFieldProps {
  label: string
  required?: boolean
  error?: string
  hint?: string
  children: React.ReactNode
  className?: string
}

export function FormField({
  label,
  required,
  error,
  hint,
  children,
  className,
}: FormFieldProps) {
  return (
    <div className={cn('flex flex-col gap-1', className)}>
      <label className="flex items-center gap-1 text-[11px] font-medium text-brand dark:text-[#EDEEF0]">
        {label}
        {required && (
          <span className="w-[5px] h-[5px] rounded-full bg-[#E24B4A] flex-shrink-0" />
        )}
      </label>
      {children}
      {error && (
        <span className="text-[11px] text-status-red-text">{error}</span>
      )}
      {hint && !error && (
        <span className="text-[11px] text-[#6B7280]">{hint}</span>
      )}
    </div>
  )
}

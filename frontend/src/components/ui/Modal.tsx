// frontend/src/components/ui/Modal.tsx
'use client'

import { useEffect } from 'react'
import { X } from 'lucide-react'
import { cn } from '@/lib/utils'

interface ModalProps {
  open: boolean
  onClose: () => void
  title: string
  children: React.ReactNode
  footer?: React.ReactNode
  size?: 'sm' | 'md' | 'lg'
}

export function Modal({
  open,
  onClose,
  title,
  children,
  footer,
  size = 'md',
}: ModalProps) {
  // Close on Escape key
  useEffect(() => {
    if (!open) return
    const handler = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose()
    }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [open, onClose])

  // Prevent body scroll when modal is open
  useEffect(() => {
    if (open) {
      document.body.style.overflow = 'hidden'
    } else {
      document.body.style.overflow = ''
    }
    return () => { document.body.style.overflow = '' }
  }, [open])

  if (!open) return null

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4"
      aria-modal="true"
      role="dialog"
    >
      {/* Overlay */}
      <div
        className="absolute inset-0 bg-black/35"
        onClick={onClose}
      />

      {/* Modal panel */}
      <div
        className={cn(
          'relative z-10 w-full bg-surface-card dark:bg-dark-card rounded-modal border border-[0.5px] border-surface-border dark:border-dark-border shadow-lg flex flex-col max-h-[90vh]',
          size === 'sm' && 'max-w-sm',
          size === 'md' && 'max-w-lg',
          size === 'lg' && 'max-w-2xl',
        )}
      >
        {/* Header */}
        <div className="flex items-center justify-between px-4 py-3 border-b border-[0.5px] border-surface-border dark:border-dark-border flex-shrink-0">
          <span className="text-[13px] font-medium text-brand dark:text-[#EDEEF0]">
            {title}
          </span>
          <button
            onClick={onClose}
            className="p-1 rounded text-[#6B7280] hover:text-brand dark:hover:text-[#EDEEF0] hover:bg-surface-page dark:hover:bg-dark-page transition-colors"
            aria-label="Close modal"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        {/* Body */}
        <div className="px-4 py-4 overflow-y-auto flex-1">
          {children}
        </div>

        {/* Footer */}
        {footer && (
          <div className="flex items-center justify-end gap-2 px-4 py-3 border-t border-[0.5px] border-surface-border dark:border-dark-border flex-shrink-0">
            {footer}
          </div>
        )}
      </div>
    </div>
  )
}

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

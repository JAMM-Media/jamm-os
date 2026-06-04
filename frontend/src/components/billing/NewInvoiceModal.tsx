// frontend/src/components/billing/NewInvoiceModal.tsx
'use client'

import { Modal } from '@/components/ui/Modal'

interface NewInvoiceModalProps {
  open: boolean
  onClose: () => void
}

export function NewInvoiceModal({ open, onClose }: NewInvoiceModalProps) {
  return (
    <Modal
      open={open}
      onClose={onClose}
      title="New Invoice"
      size="md"
      footer={
        <button
          onClick={onClose}
          className="h-9 px-3 rounded-[6px] border border-[0.5px] border-brand dark:border-[#4A7FA5] text-brand dark:text-[#EDEEF0] text-[13px] font-medium hover:bg-surface-page dark:hover:bg-dark-page transition-colors"
        >
          Close
        </button>
      }
    >
      <p className="text-[13px] text-[#6B7280]">
        Invoice creation coming soon.
      </p>
    </Modal>
  )
}

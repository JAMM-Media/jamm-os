// frontend/src/lib/hooks/useAlert.tsx
'use client'
import { useState, useCallback } from 'react'
import { Modal } from '@/components/ui/Modal'

export function useAlert() {
  const [message, setMessage] = useState<string | null>(null)

  const alert = useCallback((msg: string) => {
    setMessage(msg)
  }, [])

  const handleClose = useCallback(() => {
    setMessage(null)
  }, [])

  const AlertDialog = message !== null ? (
    <Modal
      open={true}
      onClose={handleClose}
      title="Notice"
      size="sm"
      footer={
        <button
          onClick={handleClose}
          className="text-[12px] font-medium px-4 py-1.5 rounded-[6px] bg-brand text-white hover:opacity-90 transition-colors"
        >
          OK
        </button>
      }
    >
      <p className="text-[13px] text-foreground leading-[1.5]">{message}</p>
    </Modal>
  ) : null

  return { alert, AlertDialog }
}

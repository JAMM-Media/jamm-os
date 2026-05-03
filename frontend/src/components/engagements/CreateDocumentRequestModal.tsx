// path: frontend/src/components/engagements/CreateDocumentRequestModal.tsx
'use client'

import { useState, useEffect } from 'react'
import { X } from 'lucide-react'
import { toast } from 'sonner'
import { documentRequestsApi } from '@/lib/api/documentRequests'

interface ChecklistRow {
  label: string
  isRequired: boolean
}

interface CreateDocumentRequestModalProps {
  isOpen: boolean
  onClose: () => void
  engagementId: string
  clientId: string
  onSuccess: () => void
}

const emptyRow = (): ChecklistRow => ({ label: '', isRequired: true })
const initialRows = (): ChecklistRow[] => [emptyRow(), emptyRow(), emptyRow()]

export function CreateDocumentRequestModal({
  isOpen,
  onClose,
  engagementId,
  clientId,
  onSuccess,
}: CreateDocumentRequestModalProps) {
  const [title, setTitle] = useState('')
  const [dueDate, setDueDate] = useState('')
  const [items, setItems] = useState<ChecklistRow[]>(initialRows)
  const [submitting, setSubmitting] = useState(false)

  useEffect(() => {
    if (!isOpen) {
      setTitle('')
      setDueDate('')
      setItems(initialRows())
      setSubmitting(false)
    }
  }, [isOpen])

  useEffect(() => {
    if (isOpen) {
      document.body.style.overflow = 'hidden'
    } else {
      document.body.style.overflow = ''
    }
    return () => {
      document.body.style.overflow = ''
    }
  }, [isOpen])

  useEffect(() => {
    if (!isOpen) return
    const handler = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose()
    }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [isOpen, onClose])

  if (!isOpen) return null

  const validItems = items.filter((i) => i.label.trim() !== '')
  const canSubmit = title.trim() !== '' && validItems.length > 0

  function updateItem(index: number, updates: Partial<ChecklistRow>) {
    setItems((prev) =>
      prev.map((item, i) => (i === index ? { ...item, ...updates } : item))
    )
  }

  function removeItem(index: number) {
    setItems((prev) => prev.filter((_, i) => i !== index))
  }

  function addItem() {
    if (items.length >= 20) return
    setItems((prev) => [...prev, emptyRow()])
  }

  async function handleSubmit() {
    if (!canSubmit || submitting) return
    setSubmitting(true)
    const payload = {
      title: title.trim(),
      client_id: clientId,
      engagement_id: engagementId,
      ...(dueDate ? { due_date: dueDate } : {}),
      checklist_items: validItems.map((item) => ({
        id: crypto.randomUUID(),
        label: item.label.trim(),
        description: '',
        is_required: item.isRequired,
        status: 'pending' as const,
      })),
    }
    try {
      await documentRequestsApi.create(payload)
      toast.success('Document request sent.')
      onSuccess()
      onClose()
    } catch {
      toast.error('Could not send request — please try again.')
      setSubmitting(false)
    }
  }

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4"
      aria-modal="true"
      role="dialog"
    >
      <div className="absolute inset-0 bg-black/35" onClick={onClose} />

      <div className="relative z-10 w-full max-w-[560px] bg-[#EDEEF0] dark:bg-[#383838] rounded-[10px] border border-[0.5px] border-[#C8CDD6] dark:border-[#484848] shadow-lg flex flex-col max-h-[90vh]">
        {/* Header */}
        <div className="h-12 flex items-center justify-between px-4 border-b border-[0.5px] border-[#C8CDD6] dark:border-[#484848] flex-shrink-0">
          <span className="text-[13px] font-medium text-[#1F3148] dark:text-[#EDEEF0]">
            New Document Request
          </span>
          <button
            onClick={onClose}
            className="p-1 rounded text-[#6B7280] hover:text-[#1F3148] dark:hover:text-[#EDEEF0] transition-colors"
            aria-label="Close"
          >
            <X className="h-[14px] w-[14px]" />
          </button>
        </div>

        {/* Body */}
        <div className="px-4 py-4 overflow-y-auto flex-1 flex flex-col gap-4">
          {/* Request Title */}
          <div className="flex flex-col gap-1.5">
            <label className="flex items-center gap-1 text-[11px] font-medium text-[#1F3148] dark:text-[#EDEEF0]">
              Request Title
              <span className="w-[5px] h-[5px] rounded-full bg-[#E24B4A] flex-shrink-0" />
            </label>
            <input
              type="text"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="e.g. 2024 Tax Season Documents"
              className="w-full h-9 px-3 bg-[#F7F7F8] dark:bg-[#383838] border border-[0.5px] border-[#C8CDD6] focus:border-[#4A7FA5] outline-none rounded-[6px] text-[13px] text-[#1F3148] dark:text-[#EDEEF0] placeholder:text-[#9CA3AF] transition-colors"
            />
          </div>

          {/* Due Date */}
          <div className="flex flex-col gap-1.5">
            <label className="text-[11px] font-medium text-[#1F3148] dark:text-[#EDEEF0]">
              Due Date
            </label>
            <input
              type="date"
              value={dueDate}
              onChange={(e) => setDueDate(e.target.value)}
              className="w-full h-9 px-3 bg-[#F7F7F8] dark:bg-[#383838] border border-[0.5px] border-[#C8CDD6] focus:border-[#4A7FA5] outline-none rounded-[6px] text-[13px] text-[#1F3148] dark:text-[#EDEEF0] transition-colors"
            />
            <span className="text-[11px] text-[#6B7280]">Leave blank if no deadline.</span>
          </div>

          {/* Checklist Items */}
          <div className="flex flex-col gap-2">
            <div className="flex flex-col gap-0.5">
              <label className="flex items-center gap-1 text-[11px] font-medium text-[#1F3148] dark:text-[#EDEEF0]">
                Checklist Items
                <span className="w-[5px] h-[5px] rounded-full bg-[#E24B4A] flex-shrink-0" />
              </label>
              <p className="text-[11px] text-[#6B7280]">
                Add each document you need from the client.
              </p>
            </div>

            <div className="flex flex-col gap-2">
              {items.map((item, index) => (
                <div key={index} className="flex items-center gap-2">
                  <input
                    type="text"
                    value={item.label}
                    onChange={(e) => updateItem(index, { label: e.target.value })}
                    placeholder="e.g. W-2, 1099-DIV..."
                    className="flex-1 h-[34px] px-3 bg-[#F7F7F8] dark:bg-[#2D2D2D] border border-[0.5px] border-[#C8CDD6] focus:border-[#4A7FA5] outline-none rounded-[6px] text-[13px] text-[#1F3148] dark:text-[#EDEEF0] placeholder:text-[#9CA3AF] transition-colors"
                  />
                  <label className="flex items-center gap-1 text-[11px] text-[#6B7280] cursor-pointer whitespace-nowrap select-none">
                    <input
                      type="checkbox"
                      checked={item.isRequired}
                      onChange={(e) => updateItem(index, { isRequired: e.target.checked })}
                      className="w-3 h-3"
                    />
                    Req.
                  </label>
                  {items.length > 1 ? (
                    <button
                      onClick={() => removeItem(index)}
                      className="text-[#6B7280] hover:text-[#1F3148] dark:hover:text-[#EDEEF0] transition-colors flex-shrink-0"
                      aria-label="Remove item"
                    >
                      <X className="h-[14px] w-[14px]" />
                    </button>
                  ) : (
                    <span className="w-[14px] flex-shrink-0" />
                  )}
                </div>
              ))}
            </div>

            {items.length < 20 && (
              <button
                onClick={addItem}
                className="text-[11px] font-medium text-[#4A7FA5] hover:opacity-80 transition-opacity text-left w-fit"
              >
                + Add Item
              </button>
            )}
          </div>
        </div>

        {/* Footer */}
        <div className="flex items-center justify-end gap-2 px-4 py-3 border-t border-[0.5px] border-[#C8CDD6] dark:border-[#484848] flex-shrink-0">
          <button
            onClick={onClose}
            className="h-8 px-3 rounded-[6px] border border-[0.5px] border-[#1F3148] dark:border-[#EDEEF0] text-[#1F3148] dark:text-[#EDEEF0] text-[12px] font-medium hover:opacity-80 transition-opacity"
          >
            Cancel
          </button>
          <button
            onClick={handleSubmit}
            disabled={!canSubmit || submitting}
            className="h-8 px-3 rounded-[6px] bg-[#1F3148] dark:bg-[#3A6A94] text-white text-[12px] font-medium hover:opacity-90 transition-opacity disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {submitting ? 'Sending...' : 'Send Request'}
          </button>
        </div>
      </div>
    </div>
  )
}

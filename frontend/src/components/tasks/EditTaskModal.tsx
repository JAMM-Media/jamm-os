// path: frontend/src/components/tasks/EditTaskModal.tsx
'use client'

import { useState, useEffect } from 'react'
import { Loader2 } from 'lucide-react'
import { toast } from 'sonner'
import { Modal } from '@/components/ui/Modal'
import { FormField } from '@/components/ui/FormField'
import { TextInput } from '@/components/ui/TextInput'
import { SelectInput } from '@/components/ui/SelectInput'
import { tasksApi } from '@/lib/api'

const STATUS_OPTIONS = [
  { value: 'todo', label: 'To Do' },
  { value: 'in_progress', label: 'In Progress' },
  { value: 'done', label: 'Done' },
]

interface EditTaskModalProps {
  isOpen: boolean
  onClose: () => void
  task: { id: string; title: string; status: string; dueDate?: string; notes?: string; isCompleted?: boolean }
  onSuccess: () => void
}

interface FormState {
  title: string
  status: string
  dueDate: string
  notes: string
}

function toFormState(task: EditTaskModalProps['task']): FormState {
  return {
    title: task.title ?? '',
    status: task.status ?? 'todo',
    dueDate: task.dueDate ?? '',
    notes: task.notes ?? '',
  }
}

export function EditTaskModal({ isOpen, onClose, task, onSuccess }: EditTaskModalProps) {
  const [form, setForm] = useState<FormState>(() => toFormState(task))
  const [titleError, setTitleError] = useState('')
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    if (isOpen) {
      setForm(toFormState(task))
      setTitleError('')
    }
  }, [isOpen, task])

  function handleChange(field: keyof FormState, value: string) {
    setForm((prev) => ({ ...prev, [field]: value }))
    if (field === 'title') setTitleError('')
  }

  async function handleSave() {
    if (!form.title.trim()) {
      setTitleError('Task title is required.')
      return
    }

    const original = toFormState(task)
    const patch: Record<string, unknown> = {}
    if (form.title.trim() !== original.title) patch.title = form.title.trim()
    if (form.status !== original.status) patch.status = form.status || null
    if (form.dueDate !== original.dueDate) patch.due_date = form.dueDate || null
    if (form.notes !== original.notes) patch.notes = form.notes || null

    if (Object.keys(patch).length === 0) {
      onClose()
      return
    }

    setSaving(true)
    try {
      await tasksApi.update(task.id, patch)
      toast.success('Task updated successfully')
      onSuccess()
    } catch {
      toast.error('Failed to update task — please try again')
    } finally {
      setSaving(false)
    }
  }

  return (
    <Modal
      open={isOpen}
      onClose={onClose}
      title="Edit Task"
      size="md"
      footer={
        <>
          <button
            onClick={onClose}
            className="h-9 px-3 rounded-[6px] border border-[0.5px] border-[#1F3148] dark:border-[#4A7FA5] text-[#1F3148] dark:text-[#EDEEF0] bg-transparent text-[13px] font-medium hover:bg-surface-page dark:hover:bg-dark-page transition-colors"
          >
            Cancel
          </button>
          <button
            onClick={handleSave}
            disabled={saving}
            className="h-9 px-3 rounded-[6px] bg-[#1F3148] dark:bg-brand-btn text-white text-[13px] font-medium hover:opacity-90 transition-opacity disabled:opacity-50 flex items-center gap-1.5"
          >
            {saving && <Loader2 className="h-3.5 w-3.5 animate-spin" />}
            {saving ? 'Saving...' : 'Save'}
          </button>
        </>
      }
    >
      <div className="flex flex-col gap-4">
        <FormField label="Task Title" required error={titleError}>
          <TextInput
            placeholder="Prepare depreciation schedule"
            value={form.title}
            onChange={(e) => handleChange('title', e.target.value)}
            error={!!titleError}
          />
        </FormField>

        <div className="grid grid-cols-2 gap-3">
          <FormField label="Status">
            <SelectInput
              value={form.status}
              onChange={(e) => handleChange('status', e.target.value)}
              options={STATUS_OPTIONS}
              placeholder="Select status"
            />
          </FormField>
          <FormField label="Due Date">
            <TextInput
              type="date"
              value={form.dueDate}
              onChange={(e) => handleChange('dueDate', e.target.value)}
            />
          </FormField>
        </div>

        <FormField label="Notes">
          <textarea
            placeholder="Internal notes…"
            value={form.notes}
            onChange={(e) => handleChange('notes', e.target.value)}
            rows={3}
            className="w-full bg-[#F7F7F8] dark:bg-[#2D2D2D] border border-[0.5px] border-[#C8CDD6] dark:border-[#484848] focus:border-[#4A7FA5] focus:outline-none rounded-[6px] px-3 py-2 text-[13px] text-[#1F3148] dark:text-[#EDEEF0] placeholder:text-[#9CA3AF] resize-none"
          />
        </FormField>
      </div>
    </Modal>
  )
}

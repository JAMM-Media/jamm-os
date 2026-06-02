// frontend/src/components/tasks/NewTaskModal.tsx
'use client'

import { useState, useEffect } from 'react'
import { Modal } from '@/components/ui/Modal'
import { FormField } from '@/components/ui/FormField'
import { TextInput } from '@/components/ui/TextInput'
import { SelectInput } from '@/components/ui/SelectInput'
import api, { tasksApi, clientsApi, engagementsApi, type Task } from '@/lib/api'

interface NewTaskModalProps {
  open: boolean
  onClose: () => void
  onAdd: (task: Task) => void
}

interface FormState {
  title: string
  clientId: string
  engagementId: string
  dueDate: string
  assignedTo: string
}

interface FormErrors {
  title?: string
  clientId?: string
  engagementId?: string
  dueDate?: string
}

function validate(form: FormState): FormErrors {
  const errors: FormErrors = {}
  if (!form.title.trim()) errors.title = 'Title is required.'
  if (!form.clientId) errors.clientId = 'Please select a client.'
  if (!form.engagementId) errors.engagementId = 'Please select an engagement.'
  if (!form.dueDate) errors.dueDate = 'Due date is required.'
  return errors
}

export function NewTaskModal({ open, onClose, onAdd }: NewTaskModalProps) {
  const [form, setForm] = useState<FormState>({
    title: '',
    clientId: '',
    engagementId: '',
    dueDate: '',
    assignedTo: '',
  })
  const [errors, setErrors] = useState<FormErrors>({})
  const [submitting, setSubmitting] = useState(false)

  const [clients, setClients] = useState<Array<{ value: string; label: string }>>([])
  const [clientsLoading, setClientsLoading] = useState(false)
  const [engagements, setEngagements] = useState<Array<{ value: string; label: string }>>([])
  const [engagementsLoading, setEngagementsLoading] = useState(false)
  const [staff, setStaff] = useState<Array<{ value: string; label: string }>>([])
  const [staffLoading, setStaffLoading] = useState(false)

  useEffect(() => {
    if (!open) return
    setClientsLoading(true)
    clientsApi
      .list(0, 100)
      .then(({ items }) => setClients(items.map((c) => ({ value: c.id, label: c.name }))))
      .catch(() => setClients([]))
      .finally(() => setClientsLoading(false))
  }, [open])

  useEffect(() => {
    if (!open) return
    setStaffLoading(true)
    api.get('/users/').then((res) => {
      const items = Array.isArray(res.data) ? res.data : (res.data.items ?? [])
      setStaff(items.map((u: Record<string, unknown>) => ({
        value: String(u.id),
        label: String(u.full_name ?? u.name ?? ''),
      })))
    }).catch(() => setStaff([]))
      .finally(() => setStaffLoading(false))
  }, [open])

  useEffect(() => {
    if (!form.clientId) {
      setEngagements([])
      return
    }
    setEngagementsLoading(true)
    engagementsApi
      .list(0, 100, form.clientId)
      .then(({ items }) => setEngagements(items.map((e) => ({ value: e.id, label: e.name }))))
      .catch(() => setEngagements([]))
      .finally(() => setEngagementsLoading(false))
  }, [form.clientId])

  function handleChange(field: keyof FormState, value: string) {
    setForm((prev) => {
      const next = { ...prev, [field]: value }
      if (field === 'clientId') next.engagementId = ''
      return next
    })
    if (errors[field as keyof FormErrors]) {
      setErrors((prev) => ({ ...prev, [field]: undefined }))
    }
  }

  function handleClose() {
    setForm({ title: '', clientId: '', engagementId: '', dueDate: '', assignedTo: '' })
    setErrors({})
    onClose()
  }

  async function handleSubmit() {
    const validation = validate(form)
    if (Object.keys(validation).length > 0) {
      setErrors(validation)
      return
    }

    setSubmitting(true)
    try {
      const task = await tasksApi.create({
        title: form.title.trim(),
        client_id: form.clientId,
        engagement_id: form.engagementId,
        due_date: form.dueDate || undefined,
        assigned_to: form.assignedTo || undefined,
      })
      onAdd(task)
      handleClose()
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <Modal
      open={open}
      onClose={handleClose}
      title="New Task"
      size="md"
      footer={
        <>
          <button
            onClick={handleClose}
            className="h-9 px-3 rounded-[6px] border border-[0.5px] border-brand dark:border-[#4A7FA5] text-brand dark:text-[#EDEEF0] text-[13px] font-medium hover:bg-surface-page dark:hover:bg-dark-page transition-colors"
          >
            Cancel
          </button>
          <button
            onClick={handleSubmit}
            disabled={submitting}
            className="h-9 px-3 rounded-[6px] bg-brand dark:bg-brand-btn text-white text-[13px] font-medium hover:opacity-90 transition-opacity disabled:opacity-60"
          >
            Save Task
          </button>
        </>
      }
    >
      <div className="flex flex-col gap-4">

        {/* Title */}
        <FormField label="Task Title" required error={errors.title}>
          <TextInput
            placeholder="Prepare depreciation schedule"
            value={form.title}
            onChange={(e) => handleChange('title', e.target.value)}
            error={!!errors.title}
          />
        </FormField>

        {/* Client + Engagement */}
        <div className="grid grid-cols-2 gap-3">
          <FormField label="Client" required error={errors.clientId}>
            <SelectInput
              value={form.clientId}
              onChange={(e) => handleChange('clientId', e.target.value)}
              options={clients}
              placeholder={clientsLoading ? 'Loading...' : 'Select client'}
              error={!!errors.clientId}
            />
          </FormField>
          <FormField label="Engagement" required error={errors.engagementId}>
            <SelectInput
              value={form.engagementId}
              onChange={(e) => handleChange('engagementId', e.target.value)}
              options={engagements}
              placeholder={
                engagementsLoading ? 'Loading...' : form.clientId ? 'Select engagement' : 'Select client first'
              }
              error={!!errors.engagementId}
            />
          </FormField>
        </div>

        {/* Due Date */}
        <FormField label="Due Date" required error={errors.dueDate}>
          <TextInput
            type="date"
            value={form.dueDate}
            onChange={(e) => handleChange('dueDate', e.target.value)}
            error={!!errors.dueDate}
          />
        </FormField>

        {/* Assign To */}
        <FormField label="Assign To">
          <SelectInput
            value={form.assignedTo}
            onChange={(e) => handleChange('assignedTo', e.target.value)}
            disabled={staffLoading}
            options={[
              { value: '', label: staffLoading ? 'Loading...' : 'Unassigned' },
              ...staff,
            ]}
          />
        </FormField>

      </div>
    </Modal>
  )
}

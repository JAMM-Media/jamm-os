// frontend/src/components/engagements/NewEngagementModal.tsx
'use client'

import { useState } from 'react'
import { Modal } from '@/components/ui/Modal'
import { FormField } from '@/components/ui/FormField'
import { TextInput } from '@/components/ui/TextInput'
import { SelectInput } from '@/components/ui/SelectInput'
import { type Engagement, clientsApi, engagementsApi } from '@/lib/api'
import { toast } from 'sonner'
import { useFetch } from '@/lib/hooks/useFetch'

const ENGAGEMENT_TYPE_OPTIONS = [
  { value: 'tax_return', label: 'Tax Return' },
  { value: 'bookkeeping_monthly', label: 'Bookkeeping' },
  { value: 'payroll_tax_941', label: 'Payroll' },
  { value: 'tax_planning_advisory', label: 'Advisory' },
  { value: 'audit_representation', label: 'Audit' },
  { value: 'custom', label: 'Other' },
]

interface NewEngagementModalProps {
  open: boolean
  onClose: () => void
  onAdd: (engagement: Engagement) => void
  preselectedClientId?: string
}

interface FormState {
  name: string
  clientId: string
  engagementType: string
  endDate: string
}

interface FormErrors {
  name?: string
  clientId?: string
  engagementType?: string
  endDate?: string
}

function validate(form: FormState): FormErrors {
  const errors: FormErrors = {}
  if (!form.name.trim()) errors.name = 'Title is required.'
  if (!form.clientId) errors.clientId = 'Client is required.'
  if (!form.engagementType) errors.engagementType = 'Please select a type.'
  if (!form.endDate) errors.endDate = 'Due date is required.'
  return errors
}

export function NewEngagementModal({
  open,
  onClose,
  onAdd,
  preselectedClientId,
}: NewEngagementModalProps) {
  const [form, setForm] = useState<FormState>({
    name: '',
    clientId: preselectedClientId ?? '',
    engagementType: '',
    endDate: '',
  })
  const [errors, setErrors] = useState<FormErrors>({})
  const [submitting, setSubmitting] = useState(false)

  const { data: clientsData } = useFetch(() => clientsApi.list(0, 100), [])
  const clientOptions = (clientsData?.items ?? []).map((c) => ({ value: c.id, label: c.name }))

  function handleChange(field: keyof FormState, value: string) {
    setForm((prev) => ({ ...prev, [field]: value }))
    if (errors[field as keyof FormErrors]) {
      setErrors((prev) => ({ ...prev, [field]: undefined }))
    }
  }

  function handleClose() {
    setForm({
      name: '',
      clientId: preselectedClientId ?? '',
      engagementType: '',
      endDate: '',
    })
    setErrors({})
    setSubmitting(false)
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
      const created = await engagementsApi.create({
        name: form.name.trim(),
        client_id: form.clientId,
        engagement_type: form.engagementType || undefined,
        end_date: form.endDate || undefined,
      })
      onAdd(created)
      handleClose()
    } catch {
      toast.error('Failed to create engagement. Please try again.')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <Modal
      open={open}
      onClose={handleClose}
      title="New Engagement"
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
            className="h-9 px-4 rounded-[6px] bg-brand dark:bg-brand-btn text-white text-[13px] font-medium disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            {submitting ? 'Saving...' : 'Save'}
          </button>
        </>
      }
    >
      <div className="flex flex-col gap-4">

        {/* Client */}
        <FormField label="Client" required error={errors.clientId}>
          <SelectInput
            value={form.clientId}
            onChange={(e) => handleChange('clientId', e.target.value)}
            options={clientOptions}
            placeholder="Select client"
            error={!!errors.clientId}
          />
        </FormField>

        {/* Title */}
        <FormField label="Engagement Title" required error={errors.name}>
          <TextInput
            placeholder="2024 Tax Return — Corporate"
            value={form.name}
            onChange={(e) => handleChange('name', e.target.value)}
            error={!!errors.name}
          />
        </FormField>

        {/* Type + Due Date */}
        <div className="grid grid-cols-2 gap-3">
          <FormField label="Type" required error={errors.engagementType}>
            <SelectInput
              value={form.engagementType}
              onChange={(e) => handleChange('engagementType', e.target.value)}
              options={ENGAGEMENT_TYPE_OPTIONS}
              placeholder="Select type"
              error={!!errors.engagementType}
            />
          </FormField>
          <FormField label="Due Date" required error={errors.endDate}>
            <TextInput
              type="date"
              value={form.endDate}
              onChange={(e) => handleChange('endDate', e.target.value)}
              error={!!errors.endDate}
            />
          </FormField>
        </div>

      </div>
    </Modal>
  )
}

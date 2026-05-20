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

interface NewEngagementModalProps {
  open: boolean
  onClose: () => void
  onAdd: (engagement: Engagement) => void
  preselectedClientId?: string
}

interface FormErrors {
  name?: string
  clientId?: string
  engagementCategory?: string
  engagementType?: string
  endDate?: string
}

export function NewEngagementModal({
  open,
  onClose,
  onAdd,
  preselectedClientId,
}: NewEngagementModalProps) {
  const [form, setForm] = useState({
    name: '',
    clientId: preselectedClientId ?? '',
    engagementCategory: '',
    engagementType: '',
    endDate: '',
  })
  const [errors, setErrors] = useState<FormErrors>({})
  const [submitting, setSubmitting] = useState(false)

  const { data: clientsData } = useFetch(() => clientsApi.list(0, 100), [])
  const clientOptions = (clientsData?.items ?? []).map((c) => ({ value: c.id, label: c.name }))

  function validate(f: typeof form): FormErrors {
    const errs: FormErrors = {}
    if (!f.clientId) errs.clientId = 'Please select a client.'
    if (!f.name.trim()) errs.name = 'Please enter a title.'
    if (!f.engagementCategory) errs.engagementCategory = 'Please select a type.'
    const needsSubtype = ['tax_return', 'bookkeeping', 'payroll'].includes(f.engagementCategory)
    if (needsSubtype && !f.engagementType) errs.engagementType = 'Please select a form or subtype.'
    return errs
  }

  function handleChange(field: string, value: string) {
    setForm((prev) => {
      const next = { ...prev, [field]: value }
      if (field === 'engagementCategory') next.engagementType = ''
      return next
    })
    if (errors[field as keyof FormErrors]) setErrors((prev) => ({ ...prev, [field]: '' }))
  }

  function handleClose() {
    setForm({
      name: '',
      clientId: preselectedClientId ?? '',
      engagementCategory: '',
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

    const finalType = form.engagementType || form.engagementCategory || undefined

    setSubmitting(true)
    try {
      const created = await engagementsApi.create({
        name: form.name.trim(),
        client_id: form.clientId,
        engagement_type: finalType,
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

        {/* Category */}
        <FormField label="Type" required error={errors.engagementCategory}>
          <SelectInput
            value={form.engagementCategory}
            onChange={(e) => handleChange('engagementCategory', e.target.value)}
            placeholder="Select type"
            error={!!errors.engagementCategory}
            options={[
              { value: 'tax_return', label: 'Tax Return' },
              { value: 'bookkeeping', label: 'Bookkeeping' },
              { value: 'payroll', label: 'Payroll' },
              { value: 'advisory', label: 'Advisory' },
              { value: 'audit', label: 'Audit' },
              { value: 'other', label: 'Other' },
            ]}
          />
        </FormField>

        {/* Tax Return subtype */}
        {form.engagementCategory === 'tax_return' && (
          <FormField label="Form" required error={errors.engagementType}>
            <SelectInput
              value={form.engagementType}
              onChange={(e) => handleChange('engagementType', e.target.value)}
              placeholder="Select form"
              error={!!errors.engagementType}
              options={[
                { value: 'tax_return_1040', label: '1040 — Individual' },
                { value: 'tax_return_1120', label: '1120 — C-Corporation' },
                { value: 'tax_return_1120s', label: '1120-S — S-Corporation' },
                { value: 'tax_return_1065', label: '1065 — Partnership' },
                { value: 'tax_return_1041', label: '1041 — Trust / Estate Income' },
                { value: 'tax_return_706', label: '706 — Estate Tax' },
                { value: 'amended_return_1040x', label: '1040-X — Amended Return' },
                { value: 'extension_4868', label: '4868 — Individual Extension' },
                { value: 'extension_7004', label: '7004 — Business Extension' },
                { value: 'extension_8868', label: '8868 — Exempt Org Extension' },
              ]}
            />
          </FormField>
        )}

        {/* Bookkeeping subtype */}
        {form.engagementCategory === 'bookkeeping' && (
          <FormField label="Frequency" required error={errors.engagementType}>
            <SelectInput
              value={form.engagementType}
              onChange={(e) => handleChange('engagementType', e.target.value)}
              placeholder="Select frequency"
              error={!!errors.engagementType}
              options={[
                { value: 'bookkeeping_monthly', label: 'Monthly Bookkeeping' },
                { value: 'bookkeeping_quarterly', label: 'Quarterly Bookkeeping' },
              ]}
            />
          </FormField>
        )}

        {/* Payroll subtype */}
        {form.engagementCategory === 'payroll' && (
          <FormField label="Form" required error={errors.engagementType}>
            <SelectInput
              value={form.engagementType}
              onChange={(e) => handleChange('engagementType', e.target.value)}
              placeholder="Select form"
              error={!!errors.engagementType}
              options={[
                { value: 'payroll_tax_941', label: '941 — Quarterly Payroll Tax' },
              ]}
            />
          </FormField>
        )}

        {/* Due Date */}
        <FormField label="Due Date" required error={errors.endDate}>
          <TextInput
            type="date"
            value={form.endDate}
            onChange={(e) => handleChange('endDate', e.target.value)}
            error={!!errors.endDate}
          />
        </FormField>

      </div>
    </Modal>
  )
}

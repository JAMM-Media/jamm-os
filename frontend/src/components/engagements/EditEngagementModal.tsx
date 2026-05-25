// path: frontend/src/components/engagements/EditEngagementModal.tsx
'use client'

import { useState, useEffect } from 'react'
import { Loader2 } from 'lucide-react'
import { toast } from 'sonner'
import { Modal } from '@/components/ui/Modal'
import { FormField } from '@/components/ui/FormField'
import { TextInput } from '@/components/ui/TextInput'
import { SelectInput } from '@/components/ui/SelectInput'
import { engagementsApi } from '@/lib/api'

const STATUS_OPTIONS = [
  { value: 'draft', label: 'Draft' },
  { value: 'active', label: 'Active' },
  { value: 'in_review', label: 'In Review' },
  { value: 'completed', label: 'Completed' },
  { value: 'archived', label: 'Archived' },
]

const ENGAGEMENT_TYPE_OPTIONS = [
  { value: 'tax_return', label: 'Tax Return' },
  { value: 'bookkeeping_monthly', label: 'Bookkeeping' },
  { value: 'payroll_tax_941', label: 'Payroll' },
  { value: 'tax_planning_advisory', label: 'Advisory' },
  { value: 'audit_representation', label: 'Audit' },
  { value: 'custom', label: 'Other' },
]

interface EditEngagementModalProps {
  isOpen: boolean
  onClose: () => void
  engagement: { id: string; name: string; status: string; engagementType?: string; endDate?: string; description?: string }
  onSuccess: (opts?: { statusBecameCompleted?: boolean }) => void
  uncheckedQcCount?: number
}

interface FormState {
  name: string
  status: string
  engagementType: string
  endDate: string
  description: string
}

function toFormState(engagement: EditEngagementModalProps['engagement']): FormState {
  return {
    name: engagement.name ?? '',
    status: (engagement.status ?? '').replace(/-/g, '_'),
    engagementType: engagement.engagementType ?? '',
    endDate: engagement.endDate ?? '',
    description: engagement.description ?? '',
  }
}

export function EditEngagementModal({ isOpen, onClose, engagement, onSuccess, uncheckedQcCount = 0 }: EditEngagementModalProps) {
  const [form, setForm] = useState<FormState>(() => toFormState(engagement))
  const [nameError, setNameError] = useState('')
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    if (isOpen) {
      setForm(toFormState(engagement))
      setNameError('')
    }
  }, [isOpen, engagement])

  function handleChange(field: keyof FormState, value: string) {
    setForm((prev) => ({ ...prev, [field]: value }))
    if (field === 'name') setNameError('')
  }

  async function handleSave() {
    if (!form.name.trim()) {
      setNameError('Engagement name is required.')
      return
    }

    const original = toFormState(engagement)
    const patch: Record<string, unknown> = {}
    if (form.name.trim() !== original.name) patch.name = form.name.trim()
    if (form.status !== original.status) patch.status = form.status || null
    if (form.engagementType !== original.engagementType) patch.engagement_type = form.engagementType || null
    if (form.endDate !== original.endDate) patch.end_date = form.endDate || null
    if (form.description !== original.description) patch.description = form.description || null

    if (Object.keys(patch).length === 0) {
      onClose()
      return
    }

    if (patch.status === 'completed' && uncheckedQcCount > 0) {
      const confirmed = window.confirm(
        `${uncheckedQcCount} checklist item${uncheckedQcCount > 1 ? 's are' : ' is'} not checked. Mark engagement as complete anyway?`
      )
      if (!confirmed) return
    }

    setSaving(true)
    try {
      await engagementsApi.update(engagement.id, patch)
      toast.success('Engagement updated successfully')
      const statusBecameCompleted =
        patch.status === 'completed' && original.status !== 'completed'
      onSuccess({ statusBecameCompleted })
    } catch {
      toast.error('Failed to update engagement — please try again')
    } finally {
      setSaving(false)
    }
  }

  return (
    <Modal
      open={isOpen}
      onClose={onClose}
      title="Edit Engagement"
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
        <FormField label="Engagement Name" required error={nameError}>
          <TextInput
            placeholder="2024 Tax Return — Corporate"
            value={form.name}
            onChange={(e) => handleChange('name', e.target.value)}
            error={!!nameError}
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
          <FormField label="Engagement Type">
            <SelectInput
              value={form.engagementType}
              onChange={(e) => handleChange('engagementType', e.target.value)}
              options={ENGAGEMENT_TYPE_OPTIONS}
              placeholder="Select type"
            />
          </FormField>
        </div>

        <FormField label="End Date">
          <TextInput
            type="date"
            value={form.endDate}
            onChange={(e) => handleChange('endDate', e.target.value)}
          />
        </FormField>

        <FormField label="Description">
          <textarea
            placeholder="Internal notes…"
            value={form.description}
            onChange={(e) => handleChange('description', e.target.value)}
            rows={3}
            className="w-full bg-[#F7F7F8] dark:bg-[#2D2D2D] border border-[0.5px] border-[#C8CDD6] dark:border-[#484848] focus:border-[#4A7FA5] focus:outline-none rounded-[6px] px-3 py-2 text-[13px] text-[#1F3148] dark:text-[#EDEEF0] placeholder:text-[#9CA3AF] resize-none"
          />
        </FormField>
      </div>
    </Modal>
  )
}

// path: frontend/src/components/clients/EditClientModal.tsx
'use client'

import { useState, useEffect } from 'react'
import { Loader2 } from 'lucide-react'
import { toast } from 'sonner'
import { Modal } from '@/components/ui/Modal'
import { FormField } from '@/components/ui/FormField'
import { TextInput } from '@/components/ui/TextInput'
import { SelectInput } from '@/components/ui/SelectInput'
import { clientsApi, type Client } from '@/lib/api'
import { setFormDirty } from '@/lib/events/conciergeEvents'

const ENTITY_TYPE_OPTIONS = [
  { value: 'individual', label: 'Individual' },
  { value: 'business', label: 'Business' },
  { value: 'trust', label: 'Trust' },
  { value: 'estate', label: 'Estate' },
  { value: 'non_profit', label: 'Non-Profit' },
]

const SUBTYPE_OPTIONS: Record<string, { value: string; label: string }[]> = {
  business: [
    { value: 'sole_proprietor', label: 'Sole Proprietor' },
    { value: 'partnership', label: 'Partnership' },
    { value: 'llc', label: 'LLC' },
    { value: 's_corp', label: 'S-Corp' },
    { value: 'c_corp', label: 'C-Corp' },
    { value: 'professional_corp', label: 'Professional Corp' },
  ],
  trust: [
    { value: 'revocable_trust', label: 'Revocable Trust' },
    { value: 'irrevocable_trust', label: 'Irrevocable Trust' },
    { value: 'charitable_trust', label: 'Charitable Trust' },
    { value: 'special_needs_trust', label: 'Special Needs Trust' },
  ],
  non_profit: [
    { value: 'public_charity', label: 'Public Charity (501c3)' },
    { value: 'private_foundation', label: 'Private Foundation (501c3)' },
    { value: 'social_welfare', label: 'Social Welfare (501c4)' },
    { value: 'other_tax_exempt', label: 'Other Tax-Exempt' },
  ],
}

interface EditClientModalProps {
  isOpen: boolean
  onClose: () => void
  client: Client
  onSuccess: () => void
}

interface FormState {
  name: string
  email: string
  phone: string
  entity_type: string
  entity_subtype: string
  company_name: string
  notes: string
  business_description: string
}

function toFormState(client: Client): FormState {
  return {
    name: client.name ?? '',
    email: client.email ?? '',
    phone: client.phone ?? '',
    entity_type: client.entityType ?? '',
    entity_subtype: client.entitySubtype ?? '',
    company_name: client.companyName ?? '',
    notes: client.notes ?? '',
    business_description: client.businessDescription ?? '',
  }
}

export function EditClientModal({ isOpen, onClose, client, onSuccess }: EditClientModalProps) {
  const [form, setForm] = useState<FormState>(() => toFormState(client))
  const [nameError, setNameError] = useState('')
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    if (isOpen) {
      setForm(toFormState(client))
      setNameError('')
    }
  }, [isOpen, client])

  function handleChange(field: keyof FormState, value: string) {
    setFormDirty(true)
    if (field === 'entity_type' && (value === 'individual' || value === 'estate')) {
      setForm((prev) => ({ ...prev, entity_type: value, entity_subtype: '' }))
    } else {
      setForm((prev) => ({ ...prev, [field]: value }))
    }
    if (field === 'name') setNameError('')
  }

  async function handleSave() {
    if (!form.name.trim()) {
      setNameError('Client name is required.')
      return
    }

    const original = toFormState(client)
    const patch: Record<string, unknown> = {}
    if (form.name.trim() !== original.name) patch.name = form.name.trim()
    if (form.email !== original.email) patch.email = form.email || null
    if (form.phone !== original.phone) patch.phone = form.phone || null
    if (form.entity_type !== original.entity_type) patch.entity_type = form.entity_type || null
    if (form.entity_subtype !== original.entity_subtype) patch.entity_subtype = form.entity_subtype || null
    if (form.company_name !== original.company_name) patch.company_name = form.company_name || null
    if (form.notes !== original.notes) patch.notes = form.notes || null
    if (form.business_description !== original.business_description) patch.business_description = form.business_description || null

    if (Object.keys(patch).length === 0) {
      onClose()
      return
    }

    setSaving(true)
    try {
      await clientsApi.update(client.id, patch)
      setFormDirty(false)
      toast.success('Client updated successfully')
      onSuccess()
    } catch {
      toast.error('Failed to update client — please try again')
    } finally {
      setSaving(false)
    }
  }

  return (
    <Modal
      open={isOpen}
      onClose={onClose}
      title="Edit Client"
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
        <div className="grid grid-cols-2 gap-3">
          <FormField label="Client Name" required error={nameError}>
            <TextInput
              placeholder="Full name"
              value={form.name}
              onChange={(e) => handleChange('name', e.target.value)}
              error={!!nameError}
            />
          </FormField>
          <FormField label="Phone">
            <TextInput
              type="tel"
              placeholder="(212) 555-0100"
              value={form.phone}
              onChange={(e) => handleChange('phone', e.target.value)}
            />
          </FormField>
        </div>

        <FormField label="Email">
          <TextInput
            type="email"
            placeholder="client@example.com"
            value={form.email}
            onChange={(e) => handleChange('email', e.target.value)}
          />
        </FormField>

        <FormField label="Entity Type">
          <SelectInput
            value={form.entity_type}
            onChange={(e) => handleChange('entity_type', e.target.value)}
            options={ENTITY_TYPE_OPTIONS}
            placeholder="Select type"
          />
        </FormField>

        {SUBTYPE_OPTIONS[form.entity_type] && (
          <FormField label="Entity Subtype">
            <SelectInput
              value={form.entity_subtype}
              onChange={(e) => handleChange('entity_subtype', e.target.value)}
              options={[{ value: '', label: '-- Select subtype --' }, ...SUBTYPE_OPTIONS[form.entity_type]]}
              placeholder="-- Select subtype --"
            />
          </FormField>
        )}

        <FormField label="What does this client's business do? (optional)">
          <TextInput
            placeholder="e.g. landscaping and lawn care services"
            value={form.business_description}
            onChange={(e) => handleChange('business_description', e.target.value)}
          />
        </FormField>

        <FormField label="Company Name">
          <TextInput
            placeholder="Acme Corp"
            value={form.company_name}
            onChange={(e) => handleChange('company_name', e.target.value)}
          />
        </FormField>

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

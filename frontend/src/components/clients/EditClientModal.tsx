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

const ENTITY_TYPE_OPTIONS = [
  { value: 'individual', label: 'Individual' },
  { value: 'business', label: 'Business' },
  { value: 'trust', label: 'Trust' },
  { value: 'estate', label: 'Estate' },
]

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
  company_name: string
  notes: string
}

function toFormState(client: Client): FormState {
  return {
    name: client.name ?? '',
    email: client.email ?? '',
    phone: client.phone ?? '',
    entity_type: client.entityType ?? '',
    company_name: client.companyName ?? '',
    notes: client.notes ?? '',
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
    setForm((prev) => ({ ...prev, [field]: value }))
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
    if (form.company_name !== original.company_name) patch.company_name = form.company_name || null
    if (form.notes !== original.notes) patch.notes = form.notes || null

    if (Object.keys(patch).length === 0) {
      onClose()
      return
    }

    setSaving(true)
    try {
      await clientsApi.update(client.id, patch)
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

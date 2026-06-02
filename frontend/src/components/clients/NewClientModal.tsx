// frontend/src/components/clients/NewClientModal.tsx
'use client'

import { useState, useEffect } from 'react'
import { Modal } from '@/components/ui/Modal'
import { FormField } from '@/components/ui/FormField'
import { TextInput } from '@/components/ui/TextInput'
import { SelectInput } from '@/components/ui/SelectInput'
import { clientsApi, type Client } from '@/lib/api'
import { toast } from 'sonner'
import { setFormDirty } from '@/lib/events/conciergeEvents'

const ENTITY_TYPE_OPTIONS = [
  { value: 'individual', label: 'Individual' },
  { value: 'business', label: 'Business' },
  { value: 'trust', label: 'Trust' },
  { value: 'estate', label: 'Estate' },
]

interface NewClientModalProps {
  open: boolean
  onClose: () => void
  onAdd: (client: Client) => void
  initialName?: string
}

interface FormState {
  name: string
  email: string
  phone: string
  entity_type: string
}

interface FormErrors {
  name?: string
  email?: string
  entity_type?: string
}

function validate(form: FormState): FormErrors {
  const errors: FormErrors = {}
  if (!form.name.trim()) errors.name = 'Client name is required.'
  if (form.email && !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(form.email)) {
    errors.email = 'Enter a valid email address.'
  }
  return errors
}

export function NewClientModal({ open, onClose, onAdd, initialName }: NewClientModalProps) {
  const [form, setForm] = useState<FormState>({
    name: initialName ?? '',
    email: '',
    phone: '',
    entity_type: '',
  })

  useEffect(() => {
    if (open && initialName) setForm((prev) => ({ ...prev, name: initialName }))
  }, [open, initialName])
  const [errors, setErrors] = useState<FormErrors>({})
  const [submitting, setSubmitting] = useState(false)

  function handleChange(field: keyof FormState, value: string) {
    setFormDirty(true)
    setForm((prev) => ({ ...prev, [field]: value }))
    if (errors[field as keyof FormErrors]) {
      setErrors((prev) => ({ ...prev, [field]: undefined }))
    }
  }

  function handleClose() {
    setFormDirty(false)
    setForm({ name: '', email: '', phone: '', entity_type: '' })
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
      const newClient = await clientsApi.create({
        name: form.name.trim(),
        email: form.email.trim() || undefined,
        phone: form.phone.trim() || undefined,
        entity_type: form.entity_type || undefined,
      })
      onAdd(newClient)
      handleClose()
    } catch (err: unknown) {
      const message = (err as { response?: { data?: { detail?: string } } })
        ?.response?.data?.detail ?? 'Failed to create client'
      toast.error(message)
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <Modal
      open={open}
      onClose={handleClose}
      title="New Client"
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
            className="h-9 px-3 rounded-[6px] bg-brand dark:bg-brand-btn text-white text-[13px] font-medium hover:opacity-90 transition-opacity disabled:opacity-50"
          >
            {submitting ? 'Saving...' : 'Save Client'}
          </button>
        </>
      }
    >
      <div className="flex flex-col gap-4">
        {/* Row 1: Name + Entity Type */}
        <div className="grid grid-cols-2 gap-3">
          <FormField label="Client Name" required error={errors.name}>
            <TextInput
              placeholder="Acme Corp"
              value={form.name}
              onChange={(e) => handleChange('name', e.target.value)}
              error={!!errors.name}
            />
          </FormField>
          <FormField label="Entity Type" error={errors.entity_type}>
            <SelectInput
              value={form.entity_type}
              onChange={(e) => handleChange('entity_type', e.target.value)}
              options={ENTITY_TYPE_OPTIONS}
              placeholder="Select type"
              error={!!errors.entity_type}
            />
          </FormField>
        </div>

        {/* Row 2: Email + Phone */}
        <div className="grid grid-cols-2 gap-3">
          <FormField label="Email" error={errors.email}>
            <TextInput
              type="email"
              placeholder="jane@acmecorp.com"
              value={form.email}
              onChange={(e) => handleChange('email', e.target.value)}
              error={!!errors.email}
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
      </div>
    </Modal>
  )
}

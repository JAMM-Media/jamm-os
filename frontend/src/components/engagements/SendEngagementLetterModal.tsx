// frontend/src/components/engagements/SendEngagementLetterModal.tsx
'use client'

import { useState, useEffect } from 'react'
import { Modal } from '@/components/ui/Modal'
import { FormField } from '@/components/ui/FormField'
import { TextInput } from '@/components/ui/TextInput'
import { SelectInput } from '@/components/ui/SelectInput'
import api from '@/lib/api'
import { toast } from 'sonner'

interface Template {
  id: string
  name: string
  engagement_type: string | null
  variable_fields: string[]
}

interface SendEngagementLetterModalProps {
  open: boolean
  onClose: () => void
  onSent: () => void
  engagementId: string
  engagementType: string | null
  clientName: string
  engagementName: string
  filingDeadline: string | null
  endDate: string | null
}

export function SendEngagementLetterModal({
  open,
  onClose,
  onSent,
  engagementId,
  engagementType,
  clientName,
  engagementName,
  filingDeadline,
  endDate,
}: SendEngagementLetterModalProps) {
  const [templates, setTemplates] = useState<Template[]>([])
  const [selectedTemplateId, setSelectedTemplateId] = useState('')
  const [feeAmount, setFeeAmount] = useState('')
  const [loading, setLoading] = useState(false)
  const [fetching, setFetching] = useState(false)
  const [errors, setErrors] = useState<{ template?: string; fee?: string }>({})

  useEffect(() => {
    if (!open) return
    setFetching(true)
    api.get('/esign/templates?limit=50')
      .then((res) => {
        const items: Template[] = res.data?.items ?? []
        // Sort: matching engagement type first, then generic (null type) templates
        const sorted = [
          ...items.filter((t) => t.engagement_type === engagementType),
          ...items.filter((t) => t.engagement_type !== engagementType && !t.engagement_type),
          ...items.filter((t) => t.engagement_type !== engagementType && t.engagement_type),
        ]
        setTemplates(sorted)
        // Pre-select the best match
        if (sorted.length > 0) setSelectedTemplateId(sorted[0].id)
      })
      .catch(() => toast.error('Failed to load templates'))
      .finally(() => setFetching(false))
  }, [open, engagementType])

  function handleClose() {
    setSelectedTemplateId('')
    setFeeAmount('')
    setErrors({})
    onClose()
  }

  async function handleSend() {
    const errs: typeof errors = {}
    if (!selectedTemplateId) errs.template = 'Please select a template.'
    if (!feeAmount.trim()) errs.fee = 'Please enter the fee amount.'
    if (Object.keys(errs).length > 0) {
      setErrors(errs)
      return
    }

    setLoading(true)
    try {
      // Step 1: Prepare — renders template to PDF, creates draft envelope
      const prepareRes = await api.post('/esign/prepare', {
        template_id: selectedTemplateId,
        engagement_id: engagementId,
        fee_amount: feeAmount.trim(),
      })
      const envelopeId = prepareRes.data?.id
      if (!envelopeId) throw new Error('No envelope ID returned from prepare')

      // Step 2: Send — sends envelope to Dropbox Sign, emails client
      await api.post(`/esign/envelopes/${envelopeId}/send`)

      toast.success('Engagement letter sent for signature')
      onSent()
      handleClose()
    } catch (err: unknown) {
      const msg =
        (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail
        ?? 'Failed to send engagement letter'
      toast.error(msg)
    } finally {
      setLoading(false)
    }
  }

  const displayDate = filingDeadline || endDate
  const formattedDate = displayDate
    ? new Date(displayDate).toLocaleDateString('en-US', { month: 'long', day: 'numeric', year: 'numeric' })
    : '—'

  const templateOptions = templates.map((t) => ({ value: t.id, label: t.name }))

  return (
    <Modal
      isOpen={open}
      onClose={handleClose}
      title="Send Engagement Letter"
      footer={
        <>
          <button
            onClick={handleClose}
            className="h-9 px-4 rounded-[6px] border border-surface-border dark:border-dark-border text-brand dark:text-[#EDEEF0] text-[13px] font-medium hover:bg-surface-card dark:hover:bg-dark-card transition-colors"
          >
            Cancel
          </button>
          <button
            onClick={handleSend}
            disabled={loading || fetching}
            className="h-9 px-4 rounded-[6px] bg-brand dark:bg-brand-btn text-white text-[13px] font-medium disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            {loading ? 'Sending...' : 'Send for Signature'}
          </button>
        </>
      }
    >
      <div className="flex flex-col gap-4">
        {/* Auto-populated preview */}
        <div className="bg-surface-page dark:bg-[#252525] rounded-[6px] p-3 flex flex-col gap-2">
          <p className="text-[11px] font-medium text-[#6B7280] uppercase tracking-[0.05em]">Auto-populated from engagement</p>
          <div className="grid grid-cols-2 gap-x-4 gap-y-1.5">
            <div>
              <p className="text-[11px] text-[#6B7280]">Client</p>
              <p className="text-[12px] font-medium text-brand dark:text-[#EDEEF0]">{clientName || '—'}</p>
            </div>
            <div>
              <p className="text-[11px] text-[#6B7280]">Engagement</p>
              <p className="text-[12px] font-medium text-brand dark:text-[#EDEEF0]">{engagementName || '—'}</p>
            </div>
            <div>
              <p className="text-[11px] text-[#6B7280]">Date</p>
              <p className="text-[12px] font-medium text-brand dark:text-[#EDEEF0]">{new Date().toLocaleDateString('en-US', { month: 'long', day: 'numeric', year: 'numeric' })}</p>
            </div>
            <div>
              <p className="text-[11px] text-[#6B7280]">Deadline</p>
              <p className="text-[12px] font-medium text-brand dark:text-[#EDEEF0]">{formattedDate}</p>
            </div>
          </div>
        </div>

        {/* Template selection */}
        <FormField label="Letter Template" required error={errors.template}>
          {fetching ? (
            <div className="h-9 rounded-[6px] bg-[#D5D8DE] dark:bg-[#444444] animate-pulse" />
          ) : templates.length === 0 ? (
            <p className="text-[12px] text-[#6B7280]">No templates found. Add templates in Settings → Letter Templates.</p>
          ) : (
            <SelectInput
              value={selectedTemplateId}
              onChange={(e) => {
                setSelectedTemplateId(e.target.value)
                if (errors.template) setErrors((prev) => ({ ...prev, template: undefined }))
              }}
              options={templateOptions}
              placeholder="Select a template"
              error={!!errors.template}
            />
          )}
        </FormField>

        {/* Fee amount */}
        <FormField label="Fee Amount" required error={errors.fee}>
          <TextInput
            value={feeAmount}
            onChange={(e) => {
              setFeeAmount(e.target.value)
              if (errors.fee) setErrors((prev) => ({ ...prev, fee: undefined }))
            }}
            placeholder="e.g. $750 or $1,200"
            error={!!errors.fee}
          />
        </FormField>

        <p className="text-[11px] text-[#6B7280]">
          The client will receive an email from Dropbox Sign with a link to review and sign the letter. You will be notified when they sign.
        </p>
      </div>
    </Modal>
  )
}

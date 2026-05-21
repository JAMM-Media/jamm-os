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
  const [feeSchedule, setFeeSchedule] = useState<Record<string, string>>({})
  const [mode, setMode] = useState<'template' | 'upload'>('template')
  const [uploadFile, setUploadFile] = useState<File | null>(null)
  const [uploadSubject, setUploadSubject] = useState('')
  const [dragOver, setDragOver] = useState(false)

  useEffect(() => {
    if (!open) return
    api.get('/users/firm').then((res) => {
      const schedule: Record<string, string> = res.data?.settings?.fee_schedule ?? {}
      setFeeSchedule(schedule)
      // Auto-populate fee immediately when schedule loads
      if (engagementType && schedule[engagementType]) {
        setFeeAmount((prev) => prev || `$${schedule[engagementType]}`)
      }
    }).catch(() => {})
  }, [open, engagementType])

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
  }, [open])

  function handleClose() {
    setSelectedTemplateId('')
    setFeeAmount('')
    setErrors({})
    setMode('template')
    setUploadFile(null)
    setUploadSubject('')
    setDragOver(false)
    onClose()
  }

  async function handleSend() {
    if (mode === 'template') {
      const errs: typeof errors = {}
      if (!selectedTemplateId) errs.template = 'Please select a template.'
      if (!feeAmount.trim()) errs.fee = 'Please enter the fee amount.'
      if (Object.keys(errs).length > 0) { setErrors(errs); return }

      setLoading(true)
      try {
        const prepareRes = await api.post('/esign/prepare', {
          template_id: selectedTemplateId,
          engagement_id: engagementId,
          fee_amount: feeAmount.trim(),
        })
        const envelopeId = prepareRes.data?.id
        if (!envelopeId) throw new Error('No envelope ID returned')
        await api.post(`/esign/envelopes/${envelopeId}/send`)
        toast.success('Engagement letter sent for signature')
        onSent()
        handleClose()
      } catch (err: unknown) {
        const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ?? 'Failed to send engagement letter'
        toast.error(msg)
      } finally {
        setLoading(false)
      }
    } else {
      // Upload path
      const errs: typeof errors = {}
      if (!uploadFile) errs.template = 'Please select a PDF file.'
      if (Object.keys(errs).length > 0) { setErrors(errs); return }

      setLoading(true)
      try {
        const formData = new FormData()
        formData.append('file', uploadFile!)

        const uploadRes = await api.post(
          `/esign/upload-and-prepare?engagement_id=${engagementId}`,
          formData,
          { headers: { 'Content-Type': 'multipart/form-data' } }
        )
        const envelopeId = uploadRes.data?.id
        if (!envelopeId) throw new Error('No envelope ID returned')
        await api.post(`/esign/envelopes/${envelopeId}/send`)
        toast.success('Engagement letter sent for signature')
        onSent()
        handleClose()
      } catch (err: unknown) {
        const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ?? 'Failed to send engagement letter'
        toast.error(msg)
      } finally {
        setLoading(false)
      }
    }
  }

  const displayDate = filingDeadline || endDate
  const formattedDate = displayDate
    ? new Date(displayDate).toLocaleDateString('en-US', { month: 'long', day: 'numeric', year: 'numeric' })
    : '—'

  const templateOptions = templates.map((t) => ({
    value: t.id,
    label: t.engagement_type === engagementType
      ? `${t.name} ★`
      : t.name,
  }))

  return (
    <Modal
      open={open}
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
        {/* Mode toggle */}
        <div className="flex rounded-[6px] border border-surface-border dark:border-dark-border overflow-hidden">
          <button
            onClick={() => { setMode('template'); setErrors({}) }}
            className={`flex-1 py-2 text-[12px] font-medium transition-colors ${
              mode === 'template'
                ? 'bg-brand dark:bg-brand-btn text-white'
                : 'bg-surface-card dark:bg-dark-card text-[#6B7280] hover:text-brand'
            }`}
          >
            Use a Template
          </button>
          <button
            onClick={() => { setMode('upload'); setErrors({}) }}
            className={`flex-1 py-2 text-[12px] font-medium transition-colors ${
              mode === 'upload'
                ? 'bg-brand dark:bg-brand-btn text-white'
                : 'bg-surface-card dark:bg-dark-card text-[#6B7280] hover:text-brand'
            }`}
          >
            Upload Your Own PDF
          </button>
        </div>

        {mode === 'template' && (
          <>
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
          </>
        )}

        {mode === 'upload' && (
          <div className="flex flex-col gap-4">
            {/* Auto-populated preview — same as template path */}
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
              </div>
            </div>

            {/* File upload area */}
            <FormField label="Engagement Letter PDF" required error={errors.template}>
              <div
                onDragOver={(e) => { e.preventDefault(); setDragOver(true) }}
                onDragLeave={() => setDragOver(false)}
                onDrop={(e) => {
                  e.preventDefault()
                  setDragOver(false)
                  const file = e.dataTransfer.files[0]
                  if (file?.type === 'application/pdf') {
                    setUploadFile(file)
                    if (errors.template) setErrors((prev) => ({ ...prev, template: undefined }))
                  } else {
                    toast.error('Please upload a PDF file')
                  }
                }}
                className={`relative flex flex-col items-center justify-center gap-2 p-6 rounded-[6px] border border-dashed transition-colors cursor-pointer ${
                  dragOver
                    ? 'border-brand bg-surface-card dark:bg-dark-card'
                    : errors.template
                    ? 'border-red-400 bg-surface-page dark:bg-[#252525]'
                    : 'border-surface-border dark:border-dark-border bg-surface-page dark:bg-[#252525] hover:border-brand'
                }`}
                onClick={() => document.getElementById('esign-pdf-upload')?.click()}
              >
                <input
                  id="esign-pdf-upload"
                  type="file"
                  accept="application/pdf"
                  className="hidden"
                  onChange={(e) => {
                    const file = e.target.files?.[0]
                    if (file) {
                      setUploadFile(file)
                      if (errors.template) setErrors((prev) => ({ ...prev, template: undefined }))
                    }
                  }}
                />
                {uploadFile ? (
                  <>
                    <div className="w-8 h-8 rounded-[6px] bg-status-green flex items-center justify-center">
                      <svg width="16" height="16" fill="none" stroke="#065F46" strokeWidth={2} viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
                      </svg>
                    </div>
                    <p className="text-[12px] font-medium text-brand dark:text-[#EDEEF0]">{uploadFile.name}</p>
                    <p className="text-[11px] text-[#6B7280]">{(uploadFile.size / 1024).toFixed(0)} KB · Click to replace</p>
                  </>
                ) : (
                  <>
                    <svg width="24" height="24" fill="none" stroke="currentColor" strokeWidth={1.5} viewBox="0 0 24 24" className="text-[#6B7280]">
                      <path strokeLinecap="round" strokeLinejoin="round" d="M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5m-13.5-9L12 3m0 0l4.5 4.5M12 3v13.5" />
                    </svg>
                    <p className="text-[12px] font-medium text-brand dark:text-[#EDEEF0]">Drop your PDF here or click to browse</p>
                    <p className="text-[11px] text-[#6B7280]">PDF files only</p>
                  </>
                )}
              </div>
            </FormField>

            <p className="text-[11px] text-[#6B7280]">
              The client will receive an email from Dropbox Sign with a link to review and sign the document. You will be notified when they sign.
            </p>
          </div>
        )}
      </div>
    </Modal>
  )
}

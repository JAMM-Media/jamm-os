// frontend/src/components/clients/DocumentExpirySection.tsx
'use client'
import { formatLocalDate } from '@/lib/utils'

import { useState } from 'react'
import { toast } from 'sonner'
import { CalendarClock } from 'lucide-react'
import { useAuth } from '@/lib/hooks/useAuth'
import { useFetch } from '@/lib/hooks/useFetch'
import {
  documentExpiryApi,
  type DocumentExpiryRecord,
  type DocumentExpiryCreatePayload,
} from '@/lib/api/documentExpiryApi'
import { documentsApi, type Document } from '@/lib/api/documents'
import { Modal } from '@/components/ui/Modal'

const DOCUMENT_TYPES = [
  'Engagement Letter',
  'Power of Attorney',
  'State Authorization',
  'Other',
]

function getExpiryStatus(expiresOn: string): 'expired' | 'expiring_soon' | 'active' {
  const today = new Date()
  today.setHours(0, 0, 0, 0)
  const expiry = new Date(expiresOn)
  expiry.setHours(0, 0, 0, 0)
  if (expiry < today) return 'expired'
  const daysLeft = Math.round((expiry.getTime() - today.getTime()) / 86400000)
  if (daysLeft <= 60) return 'expiring_soon'
  return 'active'
}

function getDaysLeft(expiresOn: string): number {
  const today = new Date()
  today.setHours(0, 0, 0, 0)
  const expiry = new Date(expiresOn)
  expiry.setHours(0, 0, 0, 0)
  return Math.round((expiry.getTime() - today.getTime()) / 86400000)
}

function fmtDate(d: string): string {
  return formatLocalDate(d, { month: 'short', day: 'numeric', year: 'numeric' })
}

const STATUS_BADGE: Record<
  'expired' | 'expiring_soon' | 'active',
  { bg: string; text: string; label: string }
> = {
  active: { bg: 'var(--color-status-green)', text: 'var(--color-status-green-text)', label: 'Active' },
  expiring_soon: { bg: 'var(--color-status-amber)', text: 'var(--color-status-amber-text)', label: 'Expiring Soon' },
  expired: { bg: 'var(--color-status-red)', text: 'var(--color-status-red-text)', label: 'Expired' },
}

interface AddModalProps {
  clientId: string
  onClose: () => void
  onSuccess: () => void
}

function AddExpiryModal({ clientId, onClose, onSuccess }: AddModalProps) {
  const [documentType, setDocumentType] = useState('')
  const [description, setDescription] = useState('')
  const [expiresOn, setExpiresOn] = useState('')
  const [documentId, setDocumentId] = useState('')
  const [isSaving, setIsSaving] = useState(false)

  const { data: docsRaw } = useFetch(
    () => documentsApi.list(0, 100, clientId).then((r) => r.items),
    [clientId]
  )
  const clientDocs: Document[] = Array.isArray(docsRaw) ? docsRaw : []

  async function handleSave() {
    if (!documentType) {
      toast.error('Please select a document type.')
      return
    }
    if (!expiresOn) {
      toast.error('Please enter an expiry date.')
      return
    }

    const payload: DocumentExpiryCreatePayload = {
      client_id: clientId,
      document_type: documentType,
      expires_on: expiresOn,
      ...(description ? { description } : {}),
      ...(documentId ? { document_id: documentId } : {}),
    }

    setIsSaving(true)
    try {
      await documentExpiryApi.create(payload)
      toast.success('Document expiry record added.')
      onSuccess()
    } catch {
      toast.error('Failed to add expiry record. Please try again.')
    } finally {
      setIsSaving(false)
    }
  }

  return (
    <Modal
      open
      onClose={onClose}
      title="Add Document Expiry"
      size="md"
      footer={
        <>
          <button
            type="button"
            onClick={onClose}
            className="h-8 px-3 rounded-[6px] text-[12px] font-medium text-muted-foreground hover:text-brand dark:hover:text-foreground transition-colors"
          >
            Cancel
          </button>
          <button
            type="button"
            onClick={handleSave}
            disabled={isSaving}
            className="h-8 px-3 rounded-[6px] bg-brand dark:bg-brand-btn text-white text-[12px] font-medium hover:opacity-90 transition-opacity disabled:opacity-50"
          >
            {isSaving ? 'Saving…' : 'Save'}
          </button>
        </>
      }
    >
      <div className="flex flex-col gap-4">
        {/* Document type */}
        <div className="flex flex-col gap-1.5">
          <span className="text-[12px] font-medium text-brand dark:text-foreground">
            Document Type <span className="text-status-red-text">*</span>
          </span>
          <select
            value={documentType}
            onChange={(e) => setDocumentType(e.target.value)}
            className="h-8 px-2.5 rounded-[6px] border border-[0.5px] border-surface-border dark:border-dark-border bg-surface-page dark:bg-dark-page text-[12px] text-brand dark:text-foreground focus:outline-none focus:ring-1 focus:ring-brand"
          >
            <option value="">Select type…</option>
            {DOCUMENT_TYPES.map((t) => (
              <option key={t} value={t}>{t}</option>
            ))}
          </select>
        </div>

        {/* Description */}
        <div className="flex flex-col gap-1.5">
          <span className="text-[12px] font-medium text-brand dark:text-foreground">
            Description{' '}
            <span className="text-[11px] font-normal text-muted-foreground">(optional)</span>
          </span>
          <input
            type="text"
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            placeholder="e.g. 2024 engagement letter"
            className="h-8 px-2.5 rounded-[6px] border border-[0.5px] border-surface-border dark:border-dark-border bg-surface-page dark:bg-dark-page text-[12px] text-brand dark:text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-1 focus:ring-brand"
          />
        </div>

        {/* Expiry date */}
        <div className="flex flex-col gap-1.5">
          <span className="text-[12px] font-medium text-brand dark:text-foreground">
            Expiry Date <span className="text-status-red-text">*</span>
          </span>
          <input
            type="date"
            value={expiresOn}
            onChange={(e) => setExpiresOn(e.target.value)}
            className="h-8 px-2.5 rounded-[6px] border border-[0.5px] border-surface-border dark:border-dark-border bg-surface-page dark:bg-dark-page text-[12px] text-brand dark:text-foreground focus:outline-none focus:ring-1 focus:ring-brand"
          />
        </div>

        {/* Linked document */}
        <div className="flex flex-col gap-1.5">
          <span className="text-[12px] font-medium text-brand dark:text-foreground">
            Linked Document{' '}
            <span className="text-[11px] font-normal text-muted-foreground">(optional)</span>
          </span>
          <select
            value={documentId}
            onChange={(e) => setDocumentId(e.target.value)}
            className="h-8 px-2.5 rounded-[6px] border border-[0.5px] border-surface-border dark:border-dark-border bg-surface-page dark:bg-dark-page text-[12px] text-brand dark:text-foreground focus:outline-none focus:ring-1 focus:ring-brand"
          >
            <option value="">None</option>
            {clientDocs.map((doc) => (
              <option key={doc.id} value={doc.id}>
                {doc.name}
              </option>
            ))}
          </select>
        </div>
      </div>
    </Modal>
  )
}

interface DocumentExpirySectionProps {
  clientId: string
}

export function DocumentExpirySection({ clientId }: DocumentExpirySectionProps) {
  const { user } = useAuth()
  const canManage = user?.role === 'manager' || user?.role === 'firm_owner'
  const [showModal, setShowModal] = useState(false)

  const {
    data: expiriesRaw,
    isLoading,
    refetch,
  } = useFetch(
    () =>
      documentExpiryApi
        .list(clientId)
        .then((r) => r.data as DocumentExpiryRecord[]),
    [clientId]
  )

  const expiries: DocumentExpiryRecord[] = Array.isArray(expiriesRaw) ? expiriesRaw : []

  function handleModalSuccess() {
    setShowModal(false)
    refetch()
  }

  return (
    <>
      {/* Header row */}
      <div className="flex items-center justify-between mb-4">
        <span
          style={{ fontSize: 16, fontWeight: 500 }}
          className="text-brand dark:text-foreground"
        >
          Document Expiry Tracking
        </span>
        {canManage && (
          <button
            type="button"
            onClick={() => setShowModal(true)}
            style={{ height: 32, borderRadius: 6, fontSize: 12, fontWeight: 500 }}
            className="px-3 bg-brand text-white hover:opacity-90 transition-opacity"
          >
            + Add
          </button>
        )}
      </div>

      {/* Content */}
      {isLoading ? (
        <div className="flex flex-col gap-3">
          {Array.from({ length: 2 }).map((_, i) => (
            <div
              key={i}
              className="bg-surface-card dark:bg-dark-card rounded-[8px]"
              style={{ padding: '12px 14px' }}
            >
              <div className="flex items-center justify-between mb-2">
                <div className="h-3 w-36 bg-surface-border dark:bg-dark-border animate-pulse rounded" />
                <div className="h-[22px] w-20 bg-surface-border dark:bg-dark-border animate-pulse rounded-full" />
              </div>
              <div className="h-2.5 w-48 bg-surface-border dark:bg-dark-border animate-pulse rounded mb-1" />
              <div className="h-2.5 w-32 bg-surface-border dark:bg-dark-border animate-pulse rounded" />
            </div>
          ))}
        </div>
      ) : expiries.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-16 gap-[10px]">
          <div className="flex items-center justify-center w-10 h-10 rounded-[10px] bg-surface-card dark:bg-dark-card border border-[0.5px] border-surface-border dark:border-dark-border">
            <CalendarClock className="h-[18px] w-[18px] text-muted-foreground" />
          </div>
          <p className="text-[13px] font-medium text-brand dark:text-foreground">
            No documents tracked for expiry.
          </p>
          <p className="text-[12px] text-muted-foreground text-center max-w-xs">
            Add one to get alerts before they lapse.
          </p>
          {canManage && (
            <button
              type="button"
              onClick={() => setShowModal(true)}
              style={{ height: 32, borderRadius: 6, fontSize: 12, fontWeight: 500 }}
              className="mt-1 px-3 bg-brand text-white hover:opacity-90 transition-opacity"
            >
              + Add
            </button>
          )}
        </div>
      ) : (
        <div className="flex flex-col gap-3">
          {expiries.map((rec) => {
            const statusKey = getExpiryStatus(rec.expires_on)
            const badge = STATUS_BADGE[statusKey]
            const daysLeft = getDaysLeft(rec.expires_on)

            return (
              <div
                key={rec.id}
                style={{ borderRadius: 8, padding: '12px 14px' }}
                className="bg-surface-card dark:bg-dark-card"
              >
                {/* Top row */}
                <div className="flex items-center justify-between mb-1">
                  <span
                    style={{ fontSize: 13, fontWeight: 500 }}
                    className="text-brand dark:text-foreground"
                  >
                    {rec.document_type}
                  </span>
                  <span
                    style={{
                      height: 22,
                      fontSize: 11,
                      fontWeight: 500,
                      borderRadius: 9999,
                      padding: '0 10px',
                      background: badge.bg,
                      color: badge.text,
                      display: 'inline-flex',
                      alignItems: 'center',
                    }}
                  >
                    {badge.label}
                  </span>
                </div>

                {/* Description */}
                {rec.description && (
                  <p style={{ fontSize: 12 }} className="text-muted-foreground mb-0.5">
                    {rec.description}
                  </p>
                )}

                {/* Expiry date */}
                <p style={{ fontSize: 12 }} className="text-muted-foreground mb-0.5">
                  Expires {fmtDate(rec.expires_on)}
                </p>

                {/* Days until expiry */}
                <p style={{ fontSize: 11 }} className="text-muted-foreground">
                  {daysLeft < 0
                    ? `${Math.abs(daysLeft)} days ago`
                    : daysLeft === 0
                    ? 'Expires today'
                    : `in ${daysLeft} days`}
                </p>
              </div>
            )
          })}
        </div>
      )}

      {showModal && (
        <AddExpiryModal
          clientId={clientId}
          onClose={() => setShowModal(false)}
          onSuccess={handleModalSuccess}
        />
      )}
    </>
  )
}

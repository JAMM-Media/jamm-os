// frontend/src/components/templates/DeletedTemplates.tsx
'use client'

import { useState, useCallback, useEffect } from 'react'
import { toast } from 'sonner'
import api from '@/lib/api'
import { formatEngagementType } from '@/lib/utils'
import { cn } from '@/lib/utils'

// ── Types ─────────────────────────────────────────────────────────────────────

interface DeletedEngagementTemplate {
  id: string
  name: string
  engagement_type: string | null
  is_active: boolean
}

interface DeletedTaxOrganizerTemplate {
  id: string
  name: string
  organizer_type: string
  is_default: boolean
  is_active: boolean
}

interface DeletedLetterTemplate {
  id: string
  name: string
  engagement_type: string | null
  is_active: boolean
}

interface DeletedQcTemplate {
  id: string
  name: string
  engagement_type: string | null
  items: string[]
  is_active: boolean
}

const ORGANIZER_TYPE_LABELS: Record<string, string> = {
  individual: 'Individual',
  business: 'Business',
  rental: 'Rental',
  custom: 'Custom',
}

type InternalTab = 'engagement' | 'tax_organizers' | 'letters' | 'qc_checklists'

const INTERNAL_TABS: { key: InternalTab; label: string }[] = [
  { key: 'engagement', label: 'Engagement Templates' },
  { key: 'tax_organizers', label: 'Tax Organizers' },
  { key: 'letters', label: 'Engagement Letters' },
  { key: 'qc_checklists', label: 'QC Checklists' },
]

// ── Engagement Templates deleted sub-tab ──────────────────────────────────────

function DeletedEngagementTemplates() {
  const [templates, setTemplates] = useState<DeletedEngagementTemplate[]>([])
  const [loading, setLoading] = useState(true)
  const [restoring, setRestoring] = useState<string | null>(null)

  const fetchTemplates = useCallback(async () => {
    setLoading(true)
    try {
      const { data } = await api.get('/api/v1/engagement-templates/?active_only=false')
      const all = Array.isArray(data) ? data : []
      setTemplates(
        all
          .filter((t: Record<string, unknown>) => t.is_active === false)
          .map((t: Record<string, unknown>) => ({
            id: String(t.id),
            name: String(t.name ?? ''),
            engagement_type: t.engagement_type ? String(t.engagement_type) : null,
            is_active: Boolean(t.is_active),
          }))
      )
    } catch {
      toast.error('Failed to load deleted templates')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { fetchTemplates() }, [fetchTemplates])

  async function handleRestore(id: string) {
    setRestoring(id)
    try {
      await api.patch(`/api/v1/engagement-templates/${id}`, { is_active: true })
      toast.success('Template restored')
      setTemplates((prev) => prev.filter((t) => t.id !== id))
    } catch {
      toast.error('Failed to restore template')
    } finally {
      setRestoring(null)
    }
  }

  if (loading) {
    return (
      <div className="flex flex-col gap-2">
        {[1, 2, 3].map((i) => (
          <div key={i} className="h-14 rounded-[8px] bg-[#D5D8DE] dark:bg-[#444] animate-pulse" />
        ))}
      </div>
    )
  }

  if (templates.length === 0) {
    return (
      <p className="text-[13px] text-[#9CA3AF] py-8 text-center">
        No deleted engagement templates
      </p>
    )
  }

  return (
    <div className="flex flex-col gap-2">
      {templates.map((t) => (
        <div
          key={t.id}
          className="bg-surface-card dark:bg-dark-card rounded-[8px] p-3 flex items-center justify-between"
        >
          <div className="flex items-center gap-2 flex-wrap">
            <span className="text-[13px] font-medium text-[#9CA3AF]">{t.name}</span>
            {t.engagement_type && (
              <span className="px-2 py-0.5 rounded-full bg-blue-100/50 dark:bg-blue-900/20 text-[10px] font-medium text-blue-500/70 dark:text-blue-400/60">
                {formatEngagementType(t.engagement_type)}
              </span>
            )}
            <span className="px-2 py-0.5 rounded-full bg-red-100 dark:bg-red-900/20 text-[10px] font-medium text-red-500 dark:text-red-400">
              Deleted
            </span>
          </div>
          <button
            onClick={() => handleRestore(t.id)}
            disabled={restoring === t.id}
            className="text-brand dark:text-[#4A7FA5] border border-surface-border dark:border-dark-border rounded-[6px] px-3 py-1.5 text-[12px] hover:bg-surface-card dark:hover:bg-dark-card disabled:opacity-50 transition-colors flex-shrink-0"
          >
            {restoring === t.id ? 'Restoring…' : 'Restore'}
          </button>
        </div>
      ))}
    </div>
  )
}

// ── Tax Organizers deleted sub-tab ────────────────────────────────────────────

function DeletedTaxOrganizerTemplates() {
  const [templates, setTemplates] = useState<DeletedTaxOrganizerTemplate[]>([])
  const [loading, setLoading] = useState(true)
  const [restoring, setRestoring] = useState<string | null>(null)

  const fetchTemplates = useCallback(async () => {
    setLoading(true)
    try {
      const { data } = await api.get('/tax-organizers/templates')
      const all = Array.isArray(data) ? data : []
      setTemplates(
        all
          .filter((t: Record<string, unknown>) => t.is_active === false)
          .map((t: Record<string, unknown>) => ({
            id: String(t.id),
            name: String(t.name ?? ''),
            organizer_type: String(t.organizer_type ?? 'custom'),
            is_default: Boolean(t.is_default),
            is_active: Boolean(t.is_active),
          }))
      )
    } catch {
      toast.error('Failed to load deleted tax organizer templates')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { fetchTemplates() }, [fetchTemplates])

  async function handleRestore(id: string) {
    setRestoring(id)
    try {
      await api.patch(`/tax-organizers/templates/${id}`, { is_active: true })
      toast.success('Template restored')
      setTemplates((prev) => prev.filter((t) => t.id !== id))
    } catch {
      toast.error('Failed to restore template')
    } finally {
      setRestoring(null)
    }
  }

  if (loading) {
    return (
      <div className="flex flex-col gap-2">
        {[1, 2, 3].map((i) => (
          <div key={i} className="h-14 rounded-[8px] bg-[#D5D8DE] dark:bg-[#444] animate-pulse" />
        ))}
      </div>
    )
  }

  if (templates.length === 0) {
    return (
      <p className="text-[13px] text-[#9CA3AF] py-8 text-center">
        No deleted tax organizer templates
      </p>
    )
  }

  return (
    <div className="flex flex-col gap-2">
      {templates.map((t) => (
        <div
          key={t.id}
          className="bg-surface-card dark:bg-dark-card rounded-[8px] p-3 flex items-center justify-between"
        >
          <div className="flex items-center gap-2 flex-wrap">
            <span className="text-[13px] font-medium text-[#9CA3AF]">{t.name}</span>
            <span className="px-2 py-0.5 rounded-full bg-blue-100/50 dark:bg-blue-900/20 text-[10px] font-medium text-blue-500/70 dark:text-blue-400/60">
              {ORGANIZER_TYPE_LABELS[t.organizer_type] ?? t.organizer_type}
            </span>
            {t.is_default && (
              <span className="px-2 py-0.5 rounded-full bg-[#E5E7EB]/60 dark:bg-[#333]/60 text-[10px] font-medium text-[#9CA3AF]">
                Default
              </span>
            )}
            <span className="px-2 py-0.5 rounded-full bg-red-100 dark:bg-red-900/20 text-[10px] font-medium text-red-500 dark:text-red-400">
              Deleted
            </span>
          </div>
          <button
            onClick={() => handleRestore(t.id)}
            disabled={restoring === t.id}
            className="text-brand dark:text-[#4A7FA5] border border-surface-border dark:border-dark-border rounded-[6px] px-3 py-1.5 text-[12px] hover:bg-surface-card dark:hover:bg-dark-card disabled:opacity-50 transition-colors flex-shrink-0"
          >
            {restoring === t.id ? 'Restoring…' : 'Restore'}
          </button>
        </div>
      ))}
    </div>
  )
}

// ── Engagement Letters deleted sub-tab ────────────────────────────────────────

function DeletedLetterTemplates() {
  const [templates, setTemplates] = useState<DeletedLetterTemplate[]>([])
  const [loading, setLoading] = useState(true)
  const [restoring, setRestoring] = useState<string | null>(null)

  const fetchTemplates = useCallback(async () => {
    setLoading(true)
    try {
      const { data } = await api.get('/esign/templates?limit=50')
      const all = Array.isArray(data?.items) ? data.items : Array.isArray(data) ? data : []
      setTemplates(
        all
          .filter((t: Record<string, unknown>) => t.is_active === false)
          .map((t: Record<string, unknown>) => ({
            id: String(t.id),
            name: String(t.name ?? ''),
            engagement_type: t.engagement_type ? String(t.engagement_type) : null,
            is_active: Boolean(t.is_active),
          }))
      )
    } catch {
      toast.error('Failed to load deleted letter templates')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { fetchTemplates() }, [fetchTemplates])

  async function handleRestore(id: string) {
    setRestoring(id)
    try {
      await api.patch(`/esign/templates/${id}`, { is_active: true })
      toast.success('Template restored')
      setTemplates((prev) => prev.filter((t) => t.id !== id))
    } catch {
      toast.error('Failed to restore template')
    } finally {
      setRestoring(null)
    }
  }

  if (loading) {
    return (
      <div className="flex flex-col gap-2">
        {[1, 2, 3].map((i) => (
          <div key={i} className="h-14 rounded-[8px] bg-[#D5D8DE] dark:bg-[#444] animate-pulse" />
        ))}
      </div>
    )
  }

  if (templates.length === 0) {
    return (
      <p className="text-[13px] text-[#9CA3AF] py-8 text-center">
        No deleted engagement letter templates
      </p>
    )
  }

  return (
    <div className="flex flex-col gap-2">
      {templates.map((t) => (
        <div
          key={t.id}
          className="bg-surface-card dark:bg-dark-card rounded-[8px] p-3 flex items-center justify-between"
        >
          <div className="flex items-center gap-2 flex-wrap">
            <span className="text-[13px] font-medium text-[#9CA3AF]">{t.name}</span>
            {t.engagement_type && (
              <span className="px-2 py-0.5 rounded-full bg-blue-100/50 dark:bg-blue-900/20 text-[10px] font-medium text-blue-500/70 dark:text-blue-400/60">
                {formatEngagementType(t.engagement_type)}
              </span>
            )}
            <span className="px-2 py-0.5 rounded-full bg-red-100 dark:bg-red-900/20 text-[10px] font-medium text-red-500 dark:text-red-400">
              Deleted
            </span>
          </div>
          <button
            onClick={() => handleRestore(t.id)}
            disabled={restoring === t.id}
            className="text-brand dark:text-[#4A7FA5] border border-surface-border dark:border-dark-border rounded-[6px] px-3 py-1.5 text-[12px] hover:bg-surface-card dark:hover:bg-dark-card disabled:opacity-50 transition-colors flex-shrink-0"
          >
            {restoring === t.id ? 'Restoring…' : 'Restore'}
          </button>
        </div>
      ))}
    </div>
  )
}

// ── QC Checklists deleted sub-tab ─────────────────────────────────────────────

function DeletedQcTemplates() {
  const [templates, setTemplates] = useState<DeletedQcTemplate[]>([])
  const [loading, setLoading] = useState(true)
  const [restoring, setRestoring] = useState<string | null>(null)

  const fetchTemplates = useCallback(async () => {
    setLoading(true)
    try {
      const { data } = await api.get('/qc-checklists/templates/?include_inactive=true')
      const all = Array.isArray(data) ? data : []
      setTemplates(
        all
          .filter((t: Record<string, unknown>) => t.is_active === false)
          .map((t: Record<string, unknown>) => ({
            id: String(t.id),
            name: String(t.name ?? ''),
            engagement_type: t.engagement_type ? String(t.engagement_type) : null,
            items: Array.isArray(t.items) ? (t.items as string[]) : [],
            is_active: Boolean(t.is_active),
          }))
      )
    } catch {
      toast.error('Failed to load deleted QC checklist templates')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { fetchTemplates() }, [fetchTemplates])

  async function handleRestore(id: string) {
    setRestoring(id)
    try {
      await api.post(`/qc-checklists/templates/${id}/restore`)
      toast.success('Template restored')
      setTemplates((prev) => prev.filter((t) => t.id !== id))
    } catch {
      toast.error('Failed to restore template')
    } finally {
      setRestoring(null)
    }
  }

  if (loading) {
    return (
      <div className="flex flex-col gap-2">
        {[1, 2, 3].map((i) => (
          <div key={i} className="h-14 rounded-[8px] bg-[#D5D8DE] dark:bg-[#444] animate-pulse" />
        ))}
      </div>
    )
  }

  if (templates.length === 0) {
    return (
      <p className="text-[13px] text-[#9CA3AF] py-8 text-center">
        No deleted QC checklist templates
      </p>
    )
  }

  return (
    <div className="flex flex-col gap-2">
      {templates.map((t) => (
        <div
          key={t.id}
          className="bg-surface-card dark:bg-dark-card rounded-[8px] p-3 flex items-center justify-between"
        >
          <div className="flex items-center gap-2 flex-wrap">
            <span className="text-[13px] font-medium text-[#9CA3AF]">{t.name}</span>
            {t.engagement_type && (
              <span className="px-2 py-0.5 rounded-full bg-blue-100/50 dark:bg-blue-900/20 text-[10px] font-medium text-blue-500/70 dark:text-blue-400/60">
                {formatEngagementType(t.engagement_type)}
              </span>
            )}
            <span className="px-2 py-0.5 rounded-full bg-[#E5E7EB]/60 dark:bg-[#333]/60 text-[10px] font-medium text-[#9CA3AF]">
              {t.items.length} item{t.items.length !== 1 ? 's' : ''}
            </span>
            <span className="px-2 py-0.5 rounded-full bg-red-100 dark:bg-red-900/20 text-[10px] font-medium text-red-500 dark:text-red-400">
              Deleted
            </span>
          </div>
          <button
            onClick={() => handleRestore(t.id)}
            disabled={restoring === t.id}
            className="text-brand dark:text-[#4A7FA5] border border-surface-border dark:border-dark-border rounded-[6px] px-3 py-1.5 text-[12px] hover:bg-surface-card dark:hover:bg-dark-card disabled:opacity-50 transition-colors flex-shrink-0"
          >
            {restoring === t.id ? 'Restoring…' : 'Restore'}
          </button>
        </div>
      ))}
    </div>
  )
}

// ── Main Component ────────────────────────────────────────────────────────────

export default function DeletedTemplates() {
  const [activeTab, setActiveTab] = useState<InternalTab>('engagement')

  return (
    <div className="flex flex-col gap-4">
      {/* Internal sub-tab bar */}
      <div className="flex items-end gap-0 border-b border-surface-border dark:border-dark-border">
        {INTERNAL_TABS.map((tab) => (
          <button
            key={tab.key}
            onClick={() => setActiveTab(tab.key)}
            className={cn(
              'px-4 py-2.5 text-[13px] transition-colors relative',
              activeTab === tab.key
                ? 'text-brand dark:text-[#4A7FA5] font-medium'
                : 'text-[#6B7280] hover:text-brand dark:hover:text-[#EDEEF0] font-normal',
            )}
          >
            {tab.label}
            {activeTab === tab.key && (
              <span className="absolute bottom-0 left-0 right-0 h-[2px] bg-brand dark:bg-[#4A7FA5]" />
            )}
          </button>
        ))}
      </div>

      {/* Sub-tab content */}
      <div className="bg-surface-page dark:bg-dark-page">
        {activeTab === 'engagement' && <DeletedEngagementTemplates />}
        {activeTab === 'tax_organizers' && <DeletedTaxOrganizerTemplates />}
        {activeTab === 'letters' && <DeletedLetterTemplates />}
        {activeTab === 'qc_checklists' && <DeletedQcTemplates />}
      </div>
    </div>
  )
}

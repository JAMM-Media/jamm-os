// path: frontend/src/app/engagements/page.tsx
'use client'

import { useState, useEffect } from 'react'
import { toast } from 'sonner'
import { ViewToggle } from '@/components/ui/ViewToggle'
import { EngagementTable } from '@/components/engagements/EngagementTable'
import { EngagementCard } from '@/components/engagements/EngagementCard'
import { EngagementEmptyState } from '@/components/engagements/EngagementEmptyState'
import { NewEngagementModal } from '@/components/engagements/NewEngagementModal'
import { SaveAsTemplateModal } from '@/components/engagements/SaveAsTemplateModal'
import { AckFileUploader } from '@/components/engagements/AckFileUploader'
import { engagementsApi, clientsApi, type Engagement, type Client } from '@/lib/api'
import { useFetch } from '@/lib/hooks/useFetch'
import { useAuth } from '@/lib/hooks/useAuth'
import { Search, X, ChevronDown, Loader2 } from 'lucide-react'
import { ContextualBanner } from '@/components/concierge-inline/ContextualBanner'
import { emitConciergeAction } from '@/lib/events/conciergeEvents'
import api from '@/lib/api'
import { useConfirm } from '@/lib/hooks/useConfirm'

type ViewMode = 'table' | 'card'

const ENGAGEMENT_STATUSES = ['planning', 'active', 'in_review', 'completed', 'archived']

function EngagementsTableSkeleton() {
  return (
    <div className="rounded-modal border border-[0.5px] border-surface-border dark:border-dark-border overflow-hidden">
      {Array.from({ length: 5 }).map((_, i) => (
        <div key={i} className="flex items-center gap-4 px-4 py-3 border-b border-[0.5px] border-[#D5D8DE] dark:border-dark-card last:border-0">
          <div className="h-4 w-40 flex-1 bg-[#D5D8DE] dark:bg-[#444444] animate-pulse rounded flex-shrink-0" />
          <div className="h-4 w-24  bg-[#D5D8DE] dark:bg-[#444444] animate-pulse rounded flex-shrink-0" />
          <div className="h-4 w-28  bg-[#D5D8DE] dark:bg-[#444444] animate-pulse rounded flex-shrink-0" />
          <div className="h-4 w-20  bg-[#D5D8DE] dark:bg-[#444444] animate-pulse rounded flex-shrink-0" />
          <div className="h-[22px] w-16 bg-[#D5D8DE] dark:bg-[#444444] animate-pulse rounded-full flex-shrink-0" />
          <div className="h-4 w-6  bg-[#D5D8DE] dark:bg-[#444444] animate-pulse rounded flex-shrink-0" />
        </div>
      ))}
    </div>
  )
}

export default function EngagementsPage() {
  const { user } = useAuth()
  const [view, setView] = useState<ViewMode>('table')
  const [search, setSearch] = useState('')
  const [statusFilter, setStatusFilter] = useState<string>('all')
  const [categoryFilter, setCategoryFilter] = useState<string>('all')
  const [formFilter, setFormFilter] = useState<string>('all')
  const [clientFilter, setClientFilter] = useState<string>('all')
  const [dueDateSort, setDueDateSort] = useState<string>('asc')
  const [localEngagements, setLocalEngagements] = useState<Engagement[]>([])
  const [modalOpen, setModalOpen] = useState(false)
  const [bulkCreateOpen, setBulkCreateOpen] = useState(false)
  const [bulkLetterOpen, setBulkLetterOpen] = useState(false)
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set())
  const [bulkLoading, setBulkLoading] = useState(false)
  const { confirm, ConfirmDialog } = useConfirm()

  async function getUncheckedCounts(ids: string[]): Promise<Record<string, number>> {
    if (ids.length === 0) return {}
    const { data } = await api.get(`/qc-checklists/unchecked-counts?engagement_ids=${ids.join(",")}`)
    return data as Record<string, number>
  }
  const [statusDropOpen, setStatusDropOpen] = useState(false)
  const [statusOverrides, setStatusOverrides] = useState<Record<string, string>>({})
  const [saveAsTemplateEngagement, setSaveAsTemplateEngagement] = useState<Engagement | null>(null)
  const [ackUploaderOpen, setAckUploaderOpen] = useState(false)

  useEffect(() => {
    const raw = sessionStorage.getItem('jamm_concierge_pending')
    if (!raw) return
    try {
      const action = JSON.parse(raw)
      if (Date.now() - (action._ts ?? 0) > 10000) {
        sessionStorage.removeItem('jamm_concierge_pending')
        return
      }
      if (action.modal === 'new-engagement') {
        sessionStorage.removeItem('jamm_concierge_pending')
        setModalOpen(true)
      }
    } catch {
      sessionStorage.removeItem('jamm_concierge_pending')
    }
  }, [])

  const { data, isLoading, error } = useFetch(() => engagementsApi.list(0, 100), [])
  const { data: clientsData, isLoading: clientsLoading } = useFetch(() => clientsApi.list(0, 100), [])
  const { data: stalledData } = useFetch(() => api.get('/engagements/stalled').then((r) => r.data as { stalled_count: number; engagements: unknown[] }), [])
  const serverEngagements = data?.items ?? []
  const allEngagements = [...localEngagements, ...serverEngagements].map((e) =>
    statusOverrides[e.id] ? { ...e, status: statusOverrides[e.id] } : e
  )

  const clientMap: Record<string, string> = Object.fromEntries(
    (clientsData?.items ?? []).map((c) => [c.id, c.name])
  )

  function getEngagementCategory(engagementType: string | null): string {
    if (!engagementType) return 'other'
    if (engagementType.startsWith('tax_return') || engagementType.startsWith('amended_return') || engagementType.startsWith('extension')) return 'tax_return'
    if (engagementType.startsWith('bookkeeping')) return 'bookkeeping'
    if (engagementType.startsWith('payroll')) return 'payroll'
    if (engagementType === 'tax_planning_advisory') return 'advisory'
    if (engagementType === 'audit_representation') return 'audit'
    if (engagementType === 'other_advisory') return 'advisory'
    if (engagementType === 'custom') return 'other'
    return 'other'
  }

  const filtered = allEngagements
    .filter((e) => {
      if (search && !e.name.toLowerCase().includes(search.toLowerCase())) return false
      if (statusFilter !== 'all' && e.status !== statusFilter) return false
      if (categoryFilter !== 'all' && getEngagementCategory(e.engagementType) !== categoryFilter) return false
      if (formFilter !== 'all' && e.engagementType !== formFilter) return false
      if (clientFilter !== 'all' && e.clientId !== clientFilter) return false
      return true
    })
    .sort((a, b) => {
      const aDate = a.filingDeadline ? new Date(a.filingDeadline).getTime() : Infinity
      const bDate = b.filingDeadline ? new Date(b.filingDeadline).getTime() : Infinity
      return dueDateSort === 'asc' ? aDate - bDate : bDate - aDate
    })

  function handleAdd(engagement: Engagement) {
    setLocalEngagements((prev) => [engagement, ...prev])
  }

  function handleSelect(id: string, checked: boolean) {
    setSelectedIds((prev) => {
      const next = new Set(prev)
      if (checked) next.add(id)
      else next.delete(id)
      return next
    })
  }

  function handleSelectAll(checked: boolean) {
    if (checked) setSelectedIds(new Set(filtered.map((e) => e.id)))
    else setSelectedIds(new Set())
  }

  async function handleBulkStatus(newStatus: string) {
    setStatusDropOpen(false)
    const ids = Array.from(selectedIds)
    if (newStatus === 'completed') {
      const counts = await getUncheckedCounts(ids)
      const affectedCount = Object.values(counts).filter((c) => c > 0).length
      if (affectedCount > 0) {
        const confirmed = await confirm(
          `${affectedCount} of the ${ids.length} selected engagements have unchecked QC checklist items. Mark all as complete anyway?`
        )
        if (!confirmed) return
      }
    }
    setBulkLoading(true)
    setLocalEngagements((les) =>
      les.map((e) => selectedIds.has(e.id) ? { ...e, status: newStatus } : e)
    )
    setStatusOverrides((prev) => {
      const next = { ...prev }
      ids.forEach((id) => { next[id] = newStatus })
      return next
    })
    try {
      await engagementsApi.bulkUpdate(ids, { status: newStatus })
      setSelectedIds(new Set())
      toast.success(`Updated ${ids.length} engagement${ids.length !== 1 ? 's' : ''}`)
    } catch {
      toast.error('Bulk update failed')
    } finally {
      setBulkLoading(false)
    }
  }

  async function handlePushDeadline() {
    setBulkLoading(true)
    const ids = Array.from(selectedIds)
    try {
      await engagementsApi.bulkUpdate(ids, { deadline_push_days: 7 })
      setSelectedIds(new Set())
      toast.success(`Pushed deadline by 7 days for ${ids.length} engagement${ids.length !== 1 ? 's' : ''}`)
    } catch {
      toast.error('Deadline push failed')
    } finally {
      setBulkLoading(false)
    }
  }

  const selCount = selectedIds.size

  if (error) {
    return (
        <div className="flex flex-col h-full p-6 items-center justify-center">
          <p className="text-sm text-[#DC2626]">Failed to load engagements.</p>
        </div>
    )
  }

  return (
    <>
      {ConfirmDialog}
      <div className="flex flex-col p-6 gap-4">

        <h1 className="text-2xl font-medium text-brand dark:text-[#EDEEF0]">
          Engagements
        </h1>

        {(stalledData?.stalled_count ?? 0) > 0 && user?.concierge_suggestions_enabled !== false && (
          <ContextualBanner
            tone='amber'
            count={stalledData!.stalled_count}
            message={`stalled engagement${stalledData!.stalled_count === 1 ? '' : 's'} with no activity in over 2 weeks.`}
            actionLabel='Ask Concierge'
            onAction={() => {
              emitConciergeAction({ type: 'open-panel' })
              emitConciergeAction({ type: 'prefill-panel-input', prefillMessage: 'How many stalled engagements do I have?' })
            }}
          />
        )}

        <div className="flex items-center gap-3">
          <div className="relative flex-1">
            <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 h-4 w-4 text-[#6B7280]" />
            <input
              type="text"
              placeholder="Search engagements..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="w-full h-9 pl-8 pr-3 rounded-[6px] bg-surface-input dark:bg-dark-card border border-[0.5px] border-surface-border dark:border-dark-border text-[13px] text-brand dark:text-[#EDEEF0] placeholder:text-[#9CA3AF] focus:outline-none focus:border-brand-light transition-colors"
            />
          </div>
          <ViewToggle value={view} onChange={setView} />
          <button
            onClick={() => setBulkCreateOpen(true)}
            className="h-9 px-3 rounded-[6px] border border-brand dark:border-[#4A7FA5] text-brand dark:text-[#EDEEF0] text-[13px] font-medium hover:bg-surface-page dark:hover:bg-dark-page transition-colors whitespace-nowrap flex-shrink-0 bg-transparent"
          >
            Create for Multiple Clients
          </button>
          <button
            onClick={() => setModalOpen(true)}
            className="h-9 px-3 rounded-[6px] bg-brand dark:bg-brand-btn text-white text-[13px] font-medium hover:opacity-90 transition-opacity whitespace-nowrap flex-shrink-0"
          >
            + New Engagement
          </button>
        </div>

        {/* Filter bar */}
        <div className="flex items-center gap-2 flex-wrap">
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            className="text-[12px] h-8 px-2 rounded-[6px] border border-surface-border dark:border-dark-border bg-surface-card dark:bg-dark-card text-brand dark:text-[#EDEEF0] cursor-pointer"
          >
            <option value="all">All Statuses</option>
            <option value="draft">Draft</option>
            <option value="planning">Planning</option>
            <option value="active">Active</option>
            <option value="in_review">In Review</option>
            <option value="completed">Completed</option>
            <option value="archived">Archived</option>
          </select>

          {/* Category filter */}
          <select
            value={categoryFilter}
            onChange={(e) => {
              setCategoryFilter(e.target.value)
              setFormFilter('all')
            }}
            className="text-[12px] h-8 px-2 rounded-[6px] border border-surface-border dark:border-dark-border bg-surface-card dark:bg-dark-card text-brand dark:text-[#EDEEF0] cursor-pointer"
          >
            <option value="all">All Types</option>
            <option value="tax_return">Tax Return</option>
            <option value="bookkeeping">Bookkeeping</option>
            <option value="payroll">Payroll</option>
            <option value="advisory">Advisory</option>
            <option value="audit">Audit</option>
            <option value="other">Other</option>
          </select>

          {/* Form filter — only shown when category is tax_return */}
          {categoryFilter === 'tax_return' && (
            <select
              value={formFilter}
              onChange={(e) => setFormFilter(e.target.value)}
              className="text-[12px] h-8 px-2 rounded-[6px] border border-surface-border dark:border-dark-border bg-surface-card dark:bg-dark-card text-brand dark:text-[#EDEEF0] cursor-pointer"
            >
              <option value="all">All Forms</option>
              <option value="tax_return_1040">1040</option>
              <option value="tax_return_1120">1120</option>
              <option value="tax_return_1120s">1120-S</option>
              <option value="tax_return_1065">1065</option>
              <option value="tax_return_1041">1041</option>
              <option value="tax_return_706">706</option>
              <option value="amended_return_1040x">1040-X Amended</option>
              <option value="extension_4868">4868 Extension</option>
              <option value="extension_7004">7004 Extension</option>
              <option value="extension_8868">8868 Extension</option>
            </select>
          )}

          {/* Bookkeeping subtype filter */}
          {categoryFilter === 'bookkeeping' && (
            <select
              value={formFilter}
              onChange={(e) => setFormFilter(e.target.value)}
              className="text-[12px] h-8 px-2 rounded-[6px] border border-surface-border dark:border-dark-border bg-surface-card dark:bg-dark-card text-brand dark:text-[#EDEEF0] cursor-pointer"
            >
              <option value="all">All Frequencies</option>
              <option value="bookkeeping_monthly">Monthly</option>
              <option value="bookkeeping_quarterly">Quarterly</option>
            </select>
          )}

          {/* Payroll subtype filter */}
          {categoryFilter === 'payroll' && (
            <select
              value={formFilter}
              onChange={(e) => setFormFilter(e.target.value)}
              className="text-[12px] h-8 px-2 rounded-[6px] border border-surface-border dark:border-dark-border bg-surface-card dark:bg-dark-card text-brand dark:text-[#EDEEF0] cursor-pointer"
            >
              <option value="all">All Forms</option>
              <option value="payroll_tax_941">941 — Quarterly Payroll</option>
            </select>
          )}

          {/* Client filter */}
          <select
            value={clientFilter}
            onChange={(e) => setClientFilter(e.target.value)}
            className="text-[12px] h-8 px-2 rounded-[6px] border border-surface-border dark:border-dark-border bg-surface-card dark:bg-dark-card text-brand dark:text-[#EDEEF0] cursor-pointer"
          >
            <option value="all">All Clients</option>
            {(clientsData?.items ?? [])
              .slice()
              .sort((a, b) => a.name.localeCompare(b.name))
              .map((c) => (
                <option key={c.id} value={c.id}>{c.name}</option>
              ))}
          </select>

          {/* Due date sort */}
          <select
            value={dueDateSort}
            onChange={(e) => setDueDateSort(e.target.value)}
            className="text-[12px] h-8 px-2 rounded-[6px] border border-surface-border dark:border-dark-border bg-surface-card dark:bg-dark-card text-brand dark:text-[#EDEEF0] cursor-pointer"
          >
            <option value="asc">Due Date ↑ Earliest</option>
            <option value="desc">Due Date ↓ Latest</option>
          </select>

          {(statusFilter !== 'all' || categoryFilter !== 'all' || formFilter !== 'all' || clientFilter !== 'all') && (
            <button
              onClick={() => { setStatusFilter('all'); setCategoryFilter('all'); setFormFilter('all'); setClientFilter('all'); setDueDateSort('asc') }}
              className="text-[11px] text-[#6B7280] hover:text-brand underline"
            >
              Clear filters
            </button>
          )}

          {(statusFilter !== 'all' || categoryFilter !== 'all' || formFilter !== 'all' || clientFilter !== 'all') && (
            <span className="text-[11px] text-[#6B7280]">
              Showing {filtered.length} of {allEngagements.length} engagements
            </span>
          )}
        </div>

        {isLoading && localEngagements.length === 0 ? (
          <EngagementsTableSkeleton />
        ) : filtered.length === 0 && search === '' ? (
          <EngagementEmptyState onNew={() => setModalOpen(true)} />
        ) : filtered.length === 0 ? (
          <div className="flex flex-col items-center justify-center flex-1 py-24 gap-2">
            <p className="text-[13px] font-medium text-brand dark:text-[#EDEEF0]">
              No results for &ldquo;{search}&rdquo;
            </p>
            <p className="text-[12px] text-[#6B7280]">
              Try a different title, client, or staff name.
            </p>
          </div>
        ) : view === 'table' ? (
          <EngagementTable
            engagements={filtered}
            clientMap={clientMap}
            lookupsLoading={clientsLoading}
            selectedIds={selectedIds}
            onSelect={handleSelect}
            onSelectAll={handleSelectAll}
            onSaveAsTemplate={setSaveAsTemplateEngagement}
          />
        ) : (
          <div className="grid grid-cols-1 xl:grid-cols-2 gap-3">
            {filtered.map((eng) => (
              <EngagementCard key={eng.id} engagement={eng} clientMap={clientMap} lookupsLoading={clientsLoading} />
            ))}
          </div>
        )}

        {/* IRS Acknowledgment File upload — collapsible, secondary to main list */}
        <div className="rounded-[8px] border border-surface-border dark:border-dark-border overflow-hidden">
          <button
            onClick={() => setAckUploaderOpen((o) => !o)}
            className="w-full flex items-center justify-between px-4 py-3 bg-surface-card dark:bg-dark-card hover:bg-[#F9FAFB] dark:hover:bg-[#252D3A] transition-colors"
          >
            <span className="text-[13px] font-medium text-brand dark:text-[#EDEEF0]">IRS Acknowledgment File</span>
            <ChevronDown
              className={`h-4 w-4 text-[#6B7280] transition-transform ${ackUploaderOpen ? 'rotate-180' : ''}`}
            />
          </button>
          {ackUploaderOpen && (
            <div className="px-4 py-4 border-t border-surface-border dark:border-dark-border bg-white dark:bg-[#1E2A3B]">
              <AckFileUploader />
            </div>
          )}
        </div>

        <NewEngagementModal
          open={modalOpen}
          onClose={() => setModalOpen(false)}
          onAdd={handleAdd}
        />

        {saveAsTemplateEngagement && (
          <SaveAsTemplateModal
            engagement={saveAsTemplateEngagement}
            onClose={() => setSaveAsTemplateEngagement(null)}
          />
        )}

        <BulkCreateEngagementModal
          open={bulkCreateOpen}
          onClose={() => setBulkCreateOpen(false)}
          clients={clientsData?.items ?? []}
          onSuccess={() => {
            setBulkCreateOpen(false)
            window.location.reload()
          }}
        />

        <BulkSendLetterModal
          open={bulkLetterOpen}
          onClose={() => setBulkLetterOpen(false)}
          selectedIds={selectedIds}
          engagements={filtered}
          clientMap={clientMap}
          onSuccess={() => {
            setBulkLetterOpen(false)
            setSelectedIds(new Set())
          }}
        />

        {/* Floating bulk action bar */}
        {selCount > 0 && (
          <div className="fixed bottom-6 left-1/2 -translate-x-1/2 z-50">
            <div className="bg-[#1F3148] dark:bg-[#1A2535] rounded-lg shadow-lg px-5 py-3 flex items-center gap-3">
              <span className="text-[13px] text-white font-medium whitespace-nowrap">
                {selCount} selected
              </span>

              {/* Change Status */}
              <div className="relative">
                <button
                  disabled={bulkLoading}
                  onClick={() => setStatusDropOpen((o) => !o)}
                  className="flex items-center gap-1 text-white text-[12px] border border-white/30 rounded px-3 py-1.5 hover:bg-white/10 disabled:opacity-50"
                >
                  Change Status <ChevronDown className="h-3 w-3" />
                </button>
                {statusDropOpen && (
                  <div className="absolute bottom-full mb-2 left-0 bg-white dark:bg-[#252525] border border-[#D5D8DE] dark:border-dark-border rounded-lg shadow-lg overflow-hidden min-w-[150px]">
                    {ENGAGEMENT_STATUSES.map((s) => (
                      <button
                        key={s}
                        onClick={() => handleBulkStatus(s)}
                        className="w-full text-left px-3 py-2 text-[12px] text-[#374151] dark:text-[#D1D5DB] hover:bg-[#F3F4F6] dark:hover:bg-[#333333]"
                      >
                        {s.replace(/_/g, ' ')}
                      </button>
                    ))}
                  </div>
                )}
              </div>

              {/* Push Deadline 7 Days */}
              <button
                disabled={bulkLoading}
                onClick={handlePushDeadline}
                className="text-white text-[12px] border border-white/30 rounded px-3 py-1.5 hover:bg-white/10 disabled:opacity-50 whitespace-nowrap"
              >
                Push Deadline 7 Days
              </button>

              {/* Send Engagement Letter */}
              <button
                disabled={bulkLoading}
                onClick={() => setBulkLetterOpen(true)}
                className="text-white text-[12px] border border-white/30 rounded px-3 py-1.5 hover:bg-white/10 disabled:opacity-50 whitespace-nowrap"
              >
                Send Engagement Letter
              </button>

              {/* Clear */}
              <button
                onClick={() => setSelectedIds(new Set())}
                className="text-white/60 hover:text-white transition-colors ml-1"
              >
                <X className="h-4 w-4" />
              </button>
            </div>
          </div>
        )}

      </div>
    </>
  )
}

// ---------------------------------------------------------------------------
// BULK CREATE ENGAGEMENT MODAL
// ---------------------------------------------------------------------------

const ENGAGEMENT_TYPE_OPTIONS = [
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
  { value: 'bookkeeping_monthly', label: 'Monthly Bookkeeping' },
  { value: 'bookkeeping_quarterly', label: 'Quarterly Bookkeeping' },
  { value: 'payroll_tax_941', label: '941 — Quarterly Payroll Tax' },
  { value: 'tax_planning_advisory', label: 'Tax Planning / Advisory' },
  { value: 'audit_representation', label: 'Audit Representation' },
  { value: 'other_advisory', label: 'Other Advisory' },
  { value: 'custom', label: 'Custom' },
]

interface BulkCreateEngagementModalProps {
  open: boolean
  onClose: () => void
  clients: Client[]
  onSuccess: () => void
}

function BulkCreateEngagementModal({ open, onClose, clients, onSuccess }: BulkCreateEngagementModalProps) {
  const [step, setStep] = useState<1 | 2>(1)
  const [clientSearch, setClientSearch] = useState('')
  const [selectedClientIds, setSelectedClientIds] = useState<Set<string>>(new Set())
  const [form, setForm] = useState({
    name: '',
    engagement_type: '',
    status: 'planning',
    start_date: '',
    end_date: '',
    notes: '',
  })
  const [submitting, setSubmitting] = useState(false)
  const [nameError, setNameError] = useState('')

  const activeClients = clients.filter((c) => c.isActive)
  const filteredClients = clientSearch
    ? activeClients.filter((c) => c.name.toLowerCase().includes(clientSearch.toLowerCase()))
    : activeClients

  function handleClose() {
    setStep(1)
    setClientSearch('')
    setSelectedClientIds(new Set())
    setForm({ name: '', engagement_type: '', status: 'planning', start_date: '', end_date: '', notes: '' })
    setNameError('')
    onClose()
  }

  function toggleClient(id: string) {
    setSelectedClientIds((prev) => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }

  function selectAll() {
    setSelectedClientIds(new Set(filteredClients.map((c) => c.id)))
  }

  function deselectAll() {
    setSelectedClientIds(new Set())
  }

  async function handleSubmit() {
    if (!form.name.trim()) {
      setNameError('Engagement name is required.')
      return
    }
    setNameError('')
    setSubmitting(true)
    try {
      const payload: Record<string, unknown> = {
        client_ids: Array.from(selectedClientIds),
        name: form.name.trim(),
        status: form.status || 'planning',
      }
      if (form.engagement_type) payload.engagement_type = form.engagement_type
      if (form.start_date) payload.start_date = form.start_date
      if (form.end_date) payload.end_date = form.end_date
      if (form.notes.trim()) payload.notes = form.notes.trim()

      const result = await engagementsApi.bulkCreate(payload as Parameters<typeof engagementsApi.bulkCreate>[0])
      toast.success(`Created ${result.created} engagement${result.created !== 1 ? 's' : ''} successfully`)
      onSuccess()
    } catch {
      toast.error('Failed to create engagements. Please try again.')
    } finally {
      setSubmitting(false)
    }
  }

  if (!open) return null

  const inputCls = 'w-full h-9 px-3 rounded-[6px] bg-surface-input dark:bg-dark-card border border-[0.5px] border-surface-border dark:border-dark-border text-[13px] text-brand dark:text-[#EDEEF0] placeholder:text-[#9CA3AF] focus:outline-none focus:border-brand-light transition-colors'
  const labelCls = 'text-[12px] font-medium text-[#374151] dark:text-[#D1D5DB] mb-1'

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 px-4">
      <div className="bg-white dark:bg-[#1E2A3B] rounded-[10px] shadow-xl w-full max-w-lg flex flex-col max-h-[90vh]">
        {/* Header */}
        <div className="px-6 pt-5 pb-4 border-b border-surface-border dark:border-dark-border flex-shrink-0">
          <h2 className="text-[15px] font-semibold text-brand dark:text-[#EDEEF0]">
            {step === 1
              ? 'Create Engagement — Step 1 of 2: Select Clients'
              : 'Create Engagement — Step 2 of 2: Engagement Details'}
          </h2>
        </div>

        {/* Body */}
        <div className="px-6 py-4 flex-1 overflow-y-auto">
          {step === 1 ? (
            <div className="flex flex-col gap-3">
              <input
                type="text"
                placeholder="Search clients..."
                value={clientSearch}
                onChange={(e) => setClientSearch(e.target.value)}
                className={inputCls}
              />
              <div className="flex items-center gap-3 text-[12px]">
                <button onClick={selectAll} className="text-brand dark:text-[#4A9ED6] hover:underline">Select all</button>
                <button onClick={deselectAll} className="text-[#6B7280] hover:underline">Deselect all</button>
                <span className="ml-auto text-[#6B7280]">{selectedClientIds.size} client{selectedClientIds.size !== 1 ? 's' : ''} selected</span>
              </div>
              <div className="border border-surface-border dark:border-dark-border rounded-[6px] overflow-y-auto max-h-64">
                {filteredClients.length === 0 ? (
                  <div className="px-4 py-6 text-center text-[13px] text-[#6B7280]">No clients found</div>
                ) : (
                  filteredClients.map((client) => (
                    <label
                      key={client.id}
                      className="flex items-center gap-3 px-4 py-2.5 cursor-pointer hover:bg-[#F9FAFB] dark:hover:bg-[#252D3A] border-b border-surface-border dark:border-dark-border last:border-0"
                    >
                      <input
                        type="checkbox"
                        checked={selectedClientIds.has(client.id)}
                        onChange={() => toggleClient(client.id)}
                        className="rounded border-surface-border"
                      />
                      <span className="text-[13px] text-brand dark:text-[#EDEEF0]">{client.name}</span>
                    </label>
                  ))
                )}
              </div>
            </div>
          ) : (
            <div className="flex flex-col gap-4">
              <p className="text-[12px] text-[#6B7280]">
                This will create {selectedClientIds.size} engagement{selectedClientIds.size !== 1 ? 's' : ''} — one for each selected client.
              </p>

              <div>
                <p className={labelCls}>Engagement Name <span className="text-red-500">*</span></p>
                <input
                  type="text"
                  placeholder="e.g. 2024 Tax Return"
                  value={form.name}
                  onChange={(e) => { setForm((f) => ({ ...f, name: e.target.value })); setNameError('') }}
                  className={inputCls + (nameError ? ' border-red-500' : '')}
                />
                {nameError && <p className="text-[11px] text-red-500 mt-1">{nameError}</p>}
              </div>

              <div>
                <p className={labelCls}>Engagement Type</p>
                <select
                  value={form.engagement_type}
                  onChange={(e) => setForm((f) => ({ ...f, engagement_type: e.target.value }))}
                  className={inputCls}
                >
                  <option value="">None</option>
                  {ENGAGEMENT_TYPE_OPTIONS.map((o) => (
                    <option key={o.value} value={o.value}>{o.label}</option>
                  ))}
                </select>
              </div>

              <div>
                <p className={labelCls}>Status</p>
                <select
                  value={form.status}
                  onChange={(e) => setForm((f) => ({ ...f, status: e.target.value }))}
                  className={inputCls}
                >
                  <option value="planning">Planning</option>
                  <option value="active">Active</option>
                  <option value="draft">Draft</option>
                </select>
              </div>

              <div>
                <p className={labelCls}>Start Date</p>
                <input type="date" value={form.start_date} onChange={(e) => setForm((f) => ({ ...f, start_date: e.target.value }))} className={inputCls} />
              </div>

              <div>
                <p className={labelCls}>End Date / Filing Deadline</p>
                <input type="date" value={form.end_date} onChange={(e) => setForm((f) => ({ ...f, end_date: e.target.value }))} className={inputCls} />
              </div>

              <div>
                <p className={labelCls}>Notes</p>
                <textarea
                  value={form.notes}
                  onChange={(e) => setForm((f) => ({ ...f, notes: e.target.value }))}
                  placeholder="Optional notes..."
                  rows={3}
                  className="w-full px-3 py-2 rounded-[6px] bg-surface-input dark:bg-dark-card border border-[0.5px] border-surface-border dark:border-dark-border text-[13px] text-brand dark:text-[#EDEEF0] placeholder:text-[#9CA3AF] focus:outline-none focus:border-brand-light transition-colors resize-none"
                />
              </div>

              <p className="text-[12px] text-[#6B7280] font-medium">
                This will create {selectedClientIds.size} engagement{selectedClientIds.size !== 1 ? 's' : ''} — one for each selected client.
              </p>
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="px-6 py-4 border-t border-surface-border dark:border-dark-border flex-shrink-0 flex justify-between">
          {step === 1 ? (
            <>
              <button
                onClick={handleClose}
                className="h-9 px-3 rounded-[6px] border border-[0.5px] border-brand dark:border-[#4A7FA5] text-brand dark:text-[#EDEEF0] text-[13px] font-medium hover:bg-surface-page dark:hover:bg-dark-page transition-colors"
              >
                Cancel
              </button>
              <button
                onClick={() => setStep(2)}
                disabled={selectedClientIds.size === 0}
                className="h-9 px-4 rounded-[6px] bg-brand dark:bg-brand-btn text-white text-[13px] font-medium disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
              >
                Next →
              </button>
            </>
          ) : (
            <>
              <button
                onClick={() => setStep(1)}
                className="h-9 px-3 rounded-[6px] border border-[0.5px] border-brand dark:border-[#4A7FA5] text-brand dark:text-[#EDEEF0] text-[13px] font-medium hover:bg-surface-page dark:hover:bg-dark-page transition-colors"
              >
                ← Back
              </button>
              <button
                onClick={handleSubmit}
                disabled={submitting}
                className="h-9 px-4 rounded-[6px] bg-brand dark:bg-brand-btn text-white text-[13px] font-medium disabled:opacity-50 disabled:cursor-not-allowed transition-colors flex items-center gap-2"
              >
                {submitting && <Loader2 className="h-3.5 w-3.5 animate-spin" />}
                {submitting ? 'Creating...' : `Create ${selectedClientIds.size} Engagement${selectedClientIds.size !== 1 ? 's' : ''}`}
              </button>
            </>
          )}
        </div>
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// BULK SEND LETTER MODAL
// ---------------------------------------------------------------------------

interface BulkSendLetterModalProps {
  open: boolean
  onClose: () => void
  selectedIds: Set<string>
  engagements: Engagement[]
  clientMap: Record<string, string>
  onSuccess: () => void
}

interface LetterTemplate {
  id: string
  name: string
  engagement_type: string | null
}

function BulkSendLetterModal({ open, onClose, selectedIds, engagements, clientMap, onSuccess }: BulkSendLetterModalProps) {
  const [templates, setTemplates] = useState<LetterTemplate[]>([])
  const [templateId, setTemplateId] = useState('')
  const [feeAmounts, setFeeAmounts] = useState<Record<string, string>>({})
  const [fetching, setFetching] = useState(false)
  const [submitting, setSubmitting] = useState(false)
  const [partialErrors, setPartialErrors] = useState<string[]>([])
  const [showErrors, setShowErrors] = useState(false)

  const selectedEngagements = engagements.filter((e) => selectedIds.has(e.id))
  const n = selectedEngagements.length

  const groupMap = new Map<string, Engagement[]>()
  for (const eng of selectedEngagements) {
    const key = eng.engagementType ?? '__none__'
    if (!groupMap.has(key)) groupMap.set(key, [])
    groupMap.get(key)!.push(eng)
  }
  const groups = Array.from(groupMap.entries()).map(([key, engs]) => {
    const typeOption = ENGAGEMENT_TYPE_OPTIONS.find((o) => o.value === key)
    const label = key === '__none__' ? 'Custom / Other' : (typeOption?.label ?? key)
    return { key, label, engagements: engs }
  })

  useEffect(() => {
    if (!open) return
    setFetching(true)
    // Fee amounts are entered by hand. This used to prefill each engagement
    // type's fee from the firm settings blob key settings.fee_schedule, retired
    // August 15 2026 along with the writers that populated it. The firm fetch
    // that fed it has been dropped with it, since nothing else here used it.
    //
    // The pricing config service (GET /api/pricing/config) is the future source:
    // fee resolution belongs in the backend, and the resolved amount is stamped
    // onto the letter at send time per the engagement letter snapshot design.
    api.get('/esign/templates?limit=100')
      .then((templatesRes) => {
        const items: LetterTemplate[] = templatesRes.data?.items ?? []
        setTemplates(items)
        if (items.length > 0) setTemplateId(items[0].id)
      })
      .catch(() => toast.error('Failed to load templates'))
      .finally(() => setFetching(false))
  }, [open])

  function handleClose() {
    setTemplateId('')
    setFeeAmounts({})
    setPartialErrors([])
    setShowErrors(false)
    onClose()
  }

  async function handleSubmit() {
    if (!templateId) return
    setSubmitting(true)
    setPartialErrors([])
    setShowErrors(false)
    try {
      let totalSent = 0
      let totalFailed = 0
      const allErrors: string[] = []

      for (const group of groups) {
        const result = await engagementsApi.bulkSendLetter({
          engagement_ids: group.engagements.map((e) => e.id),
          template_id: templateId,
          fee_amount: feeAmounts[group.key] || undefined,
        })
        totalSent += result.sent
        totalFailed += result.failed
        allErrors.push(...result.errors)
      }

      if (totalFailed === 0) {
        toast.success(`Sent engagement letters to ${totalSent} client${totalSent !== 1 ? 's' : ''}`)
        onSuccess()
      } else if (totalSent > 0) {
        toast.warning(`Sent ${totalSent}, failed ${totalFailed}. Check errors below.`)
        setPartialErrors(allErrors)
        setShowErrors(true)
      } else {
        toast.error(`All ${totalFailed} sends failed.`)
        setPartialErrors(allErrors)
        setShowErrors(true)
      }
    } catch {
      toast.error('Bulk send failed. Please try again.')
    } finally {
      setSubmitting(false)
    }
  }

  if (!open) return null

  const inputCls = 'w-full h-9 px-3 rounded-[6px] bg-surface-input dark:bg-dark-card border border-[0.5px] border-surface-border dark:border-dark-border text-[13px] text-brand dark:text-[#EDEEF0] placeholder:text-[#9CA3AF] focus:outline-none focus:border-brand-light transition-colors'
  const labelCls = 'text-[12px] font-medium text-[#374151] dark:text-[#D1D5DB] mb-1'

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 px-4 pb-20">
      <div className="bg-white dark:bg-[#1E2A3B] rounded-[10px] shadow-xl w-full max-w-lg flex flex-col max-h-[75vh]">
        {/* Header */}
        <div className="px-6 pt-5 pb-4 border-b border-surface-border dark:border-dark-border flex-shrink-0">
          <h2 className="text-[15px] font-semibold text-brand dark:text-[#EDEEF0]">
            Send Engagement Letter to {n} Client{n !== 1 ? 's' : ''}
          </h2>
        </div>

        {/* Body */}
        <div className="px-6 py-4 flex-1 overflow-y-auto flex flex-col gap-4">
          <div>
            <p className={labelCls}>Letter Template <span className="text-red-500">*</span></p>
            {fetching ? (
              <div className="flex items-center gap-2 text-[13px] text-[#6B7280]">
                <Loader2 className="h-4 w-4 animate-spin" /> Loading templates...
              </div>
            ) : (
              <select
                value={templateId}
                onChange={(e) => setTemplateId(e.target.value)}
                className={inputCls}
              >
                <option value="">Select a template</option>
                {templates.map((t) => (
                  <option key={t.id} value={t.id}>{t.name}</option>
                ))}
              </select>
            )}
          </div>

          <div className="rounded-[6px] bg-[#FFFBEB] dark:bg-[#2D2206] border border-[#FCD34D] dark:border-[#92400E] px-3 py-2.5">
            <p className="text-[12px] text-[#92400E] dark:text-[#FCD34D]">
              This will generate and send a signature request to each selected client via Dropbox Sign. This action cannot be undone.
            </p>
          </div>

          {groups.map((group) => (
            <div key={group.key} className="border border-surface-border dark:border-dark-border rounded-[6px] p-3 flex flex-col gap-2">
              <div className="flex items-center justify-between">
                <p className="text-[13px] font-medium text-brand dark:text-[#EDEEF0]">{group.label}</p>
                <span className="text-[11px] text-[#6B7280]">{group.engagements.length} engagement{group.engagements.length !== 1 ? 's' : ''}</span>
              </div>
              <div>
                <p className={labelCls}>Fee Amount (optional)</p>
                <input
                  type="text"
                  placeholder="$0.00"
                  value={feeAmounts[group.key] ?? ''}
                  onChange={(e) => setFeeAmounts((prev) => ({ ...prev, [group.key]: e.target.value }))}
                  className={inputCls}
                />
                <p className="text-[11px] text-[#6B7280] mt-1">Leave blank to use the fee from the template.</p>
              </div>
              <div className="overflow-y-auto max-h-[120px]">
                <ul className="text-[12px] space-y-1">
                  {group.engagements.map((e) => (
                    <li key={e.id} className="flex items-baseline gap-1.5 min-w-0">
                      <span className="truncate font-medium text-brand dark:text-[#EDEEF0]">• {e.name}</span>
                      <span className="text-[#6B7280] whitespace-nowrap flex-shrink-0">
                        — {clientMap[e.clientId] ?? 'Unknown client'}
                      </span>
                    </li>
                  ))}
                </ul>
              </div>
            </div>
          ))}

          {showErrors && partialErrors.length > 0 && (
            <div className="rounded-[6px] bg-[#FEF2F2] dark:bg-[#2D0707] border border-[#FECACA] dark:border-[#7F1D1D] px-3 py-2.5">
              <p className="text-[12px] font-medium text-[#991B1B] dark:text-[#FCA5A5] mb-1">Errors:</p>
              <ul className="text-[12px] text-[#DC2626] dark:text-[#FCA5A5] space-y-0.5">
                {partialErrors.map((err, i) => (
                  <li key={i}>• {err}</li>
                ))}
              </ul>
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="px-6 py-4 border-t border-surface-border dark:border-dark-border flex-shrink-0 flex justify-between">
          <button
            onClick={handleClose}
            className="h-9 px-3 rounded-[6px] border border-[0.5px] border-brand dark:border-[#4A7FA5] text-brand dark:text-[#EDEEF0] text-[13px] font-medium hover:bg-surface-page dark:hover:bg-dark-page transition-colors"
          >
            Cancel
          </button>
          <button
            onClick={handleSubmit}
            disabled={submitting || !templateId}
            className="h-9 px-4 rounded-[6px] bg-brand dark:bg-brand-btn text-white text-[13px] font-medium disabled:opacity-50 disabled:cursor-not-allowed transition-colors flex items-center gap-2"
          >
            {submitting && <Loader2 className="h-3.5 w-3.5 animate-spin" />}
            {submitting ? 'Sending...' : `Send to ${n} Client${n !== 1 ? 's' : ''}`}
          </button>
        </div>
      </div>
    </div>
  )
}

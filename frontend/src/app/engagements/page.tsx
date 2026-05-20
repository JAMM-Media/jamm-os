// path: frontend/src/app/engagements/page.tsx
'use client'

import { useState } from 'react'
import { toast } from 'sonner'
import { AppShell } from '@/components/layout/AppShell'
import { ViewToggle } from '@/components/ui/ViewToggle'
import { EngagementTable } from '@/components/engagements/EngagementTable'
import { EngagementCard } from '@/components/engagements/EngagementCard'
import { EngagementEmptyState } from '@/components/engagements/EngagementEmptyState'
import { NewEngagementModal } from '@/components/engagements/NewEngagementModal'
import { engagementsApi, clientsApi, type Engagement } from '@/lib/api'
import { useFetch } from '@/lib/hooks/useFetch'
import { Search, X, ChevronDown } from 'lucide-react'

type ViewMode = 'table' | 'card'

const ENGAGEMENT_STATUSES = ['planning', 'active', 'in_review', 'completed', 'archived']

export default function EngagementsPage() {
  const [view, setView] = useState<ViewMode>('table')
  const [search, setSearch] = useState('')
  const [statusFilter, setStatusFilter] = useState<string>('all')
  const [categoryFilter, setCategoryFilter] = useState<string>('all')
  const [formFilter, setFormFilter] = useState<string>('all')
  const [localEngagements, setLocalEngagements] = useState<Engagement[]>([])
  const [modalOpen, setModalOpen] = useState(false)
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set())
  const [bulkLoading, setBulkLoading] = useState(false)
  const [statusDropOpen, setStatusDropOpen] = useState(false)
  const [statusOverrides, setStatusOverrides] = useState<Record<string, string>>({})

  const { data, isLoading, error } = useFetch(() => engagementsApi.list(0, 100), [])
  const { data: clientsData, isLoading: clientsLoading } = useFetch(() => clientsApi.list(0, 100), [])
  const serverEngagements = data?.items ?? []
  const allEngagements = [...localEngagements, ...serverEngagements].map((e) =>
    statusOverrides[e.id] ? { ...e, status: statusOverrides[e.id] } : e
  )

  const clientMap: Record<string, string> = Object.fromEntries(
    (clientsData?.items ?? []).map((c) => [c.id, c.name])
  )

  function getEngagementCategory(engagementType: string | null): string {
    if (!engagementType) return 'other'
    if (engagementType.startsWith('tax_return') || engagementType.startsWith('amended_return')) return 'tax_return'
    if (engagementType.startsWith('extension')) return 'tax_return'
    if (engagementType.startsWith('bookkeeping')) return 'bookkeeping'
    if (engagementType.startsWith('payroll')) return 'payroll'
    if (engagementType === 'tax_planning_advisory') return 'advisory'
    if (engagementType === 'audit_representation') return 'audit'
    return 'other'
  }

  const filtered = allEngagements.filter((e) => {
    if (search && !e.name.toLowerCase().includes(search.toLowerCase())) return false
    if (statusFilter !== 'all' && e.status !== statusFilter) return false
    if (categoryFilter !== 'all' && getEngagementCategory(e.engagementType) !== categoryFilter) return false
    if (formFilter !== 'all' && e.engagementType !== formFilter) return false
    return true
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
    setBulkLoading(true)
    const ids = Array.from(selectedIds)
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
      <AppShell>
        <div className="flex flex-col h-full p-6 items-center justify-center">
          <p className="text-sm text-[#DC2626]">Failed to load engagements.</p>
        </div>
      </AppShell>
    )
  }

  return (
    <AppShell>
      <div className="flex flex-col h-full p-6 gap-4 overflow-y-auto">

        <h1 className="text-2xl font-medium text-brand dark:text-[#EDEEF0]">
          Engagements
        </h1>

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

          {(statusFilter !== 'all' || categoryFilter !== 'all' || formFilter !== 'all') && (
            <button
              onClick={() => { setStatusFilter('all'); setCategoryFilter('all'); setFormFilter('all') }}
              className="text-[11px] text-[#6B7280] hover:text-brand underline"
            >
              Clear filters
            </button>
          )}

          {(statusFilter !== 'all' || categoryFilter !== 'all' || formFilter !== 'all') && (
            <span className="text-[11px] text-[#6B7280]">
              Showing {filtered.length} of {allEngagements.length} engagements
            </span>
          )}
        </div>

        {isLoading && localEngagements.length === 0 ? (
          <div className="rounded-modal border border-[0.5px] border-surface-border dark:border-dark-border overflow-hidden">
            {Array.from({ length: 5 }).map((_, i) => (
              <div
                key={i}
                className="flex gap-4 px-4 py-3 border-b border-[0.5px] border-[#D5D8DE] dark:border-dark-card last:border-0"
              >
                {Array.from({ length: 6 }).map((_, j) => (
                  <div key={j} className="h-4 flex-1 bg-[#D5D8DE] dark:bg-[#444444] animate-pulse rounded" />
                ))}
              </div>
            ))}
          </div>
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
          />
        ) : (
          <div className="grid grid-cols-1 xl:grid-cols-2 gap-3">
            {filtered.map((eng) => (
              <EngagementCard key={eng.id} engagement={eng} clientMap={clientMap} lookupsLoading={clientsLoading} />
            ))}
          </div>
        )}

        <NewEngagementModal
          open={modalOpen}
          onClose={() => setModalOpen(false)}
          onAdd={handleAdd}
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
    </AppShell>
  )
}

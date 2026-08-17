// path: frontend/src/app/(app)/leads/layout.tsx
'use client'

import { useState, useEffect } from 'react'
import { usePathname, useRouter } from 'next/navigation'
import Link from 'next/link'
import { Search, X, Flame, ChevronLeft, ChevronRight, ChevronDown, Plus } from 'lucide-react'
import { toast } from 'sonner'
import { leadsApi, type Lead } from '@/lib/api'
import { useFetch } from '@/lib/hooks/useFetch'
import { StatusBadge } from '@/components/ui/StatusBadge'
import { Modal } from '@/components/ui/Modal'
import { FormField } from '@/components/ui/FormField'
import { TextInput } from '@/components/ui/TextInput'
import { SelectInput } from '@/components/ui/SelectInput'
import { cn } from '@/lib/utils'
import type { BadgeVariant } from '@/components/ui/StatusBadge'

const PAGE_SIZE = 25

const LEAD_STAGES = [
  { value: '', label: 'All stages' },
  { value: 'identified', label: 'Identified' },
  { value: 'contacted', label: 'Contacted' },
  { value: 'call_booked', label: 'Call Booked' },
  { value: 'proposal', label: 'Proposal' },
  { value: 'won', label: 'Won' },
  { value: 'lost', label: 'Lost' },
]

const REFERRAL_SOURCE_OPTIONS = [
  { value: '', label: 'Unknown / not set' },
  { value: 'client_referral', label: 'Client Referral' },
  { value: 'professional_referral', label: 'Professional Referral' },
  { value: 'google_search', label: 'Google Search' },
  { value: 'social_media', label: 'Social Media' },
  { value: 'website', label: 'Website' },
  { value: 'cold_outreach', label: 'Cold Outreach' },
  { value: 'association_or_community', label: 'Association / Community' },
  { value: 'walk_in', label: 'Walk-in' },
  { value: 'other', label: 'Other' },
]

function formatDate(iso: string): string {
  if (!iso) return '-'
  return new Date(iso).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })
}

function formatSource(raw: string | null): string {
  if (!raw) return '-'
  return raw.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase())
}

function LeadsTableSkeleton({ slim, rowCount }: { slim: boolean; rowCount: number }) {
  return (
    <div className="rounded-[10px] bg-white dark:bg-dark-card border border-[0.5px] border-surface-border dark:border-dark-border overflow-hidden">
      <table className="w-full border-collapse">
        <thead>
          <tr className="bg-surface-card dark:bg-[#252525] border-b border-[0.5px] border-surface-border dark:border-dark-border">
            <th className="px-4 py-4 text-left text-[11px] font-semibold text-[#6B7280] uppercase tracking-[0.07em] whitespace-nowrap">
              Lead Name
            </th>
            {!slim && (
              <th className="px-4 py-4 text-left text-[11px] font-semibold text-[#6B7280] uppercase tracking-[0.07em] whitespace-nowrap">
                Email
              </th>
            )}
            <th className="px-4 py-4 text-left text-[11px] font-semibold text-[#6B7280] uppercase tracking-[0.07em] whitespace-nowrap">
              Stage
            </th>
            {!slim && (
              <>
                <th className="px-4 py-4 text-left text-[11px] font-semibold text-[#6B7280] uppercase tracking-[0.07em] whitespace-nowrap">
                  Referral Source
                </th>
                <th className="px-4 py-4 text-left text-[11px] font-semibold text-[#6B7280] uppercase tracking-[0.07em] whitespace-nowrap">
                  Date Added
                </th>
              </>
            )}
          </tr>
        </thead>
        <tbody>
          {Array.from({ length: rowCount }).map((_, i) => (
            <tr key={i} className="border-b border-[0.5px] border-surface-border dark:border-dark-border last:border-0">
              <td className="px-4 py-3">
                <div className="h-4 w-32 bg-[#D5D8DE] dark:bg-[#444444] animate-pulse rounded" />
              </td>
              {!slim && (
                <td className="px-4 py-3">
                  <div className="h-4 w-24 bg-[#D5D8DE] dark:bg-[#444444] animate-pulse rounded" />
                </td>
              )}
              <td className="px-4 py-3">
                <div className="h-4 w-20 bg-[#D5D8DE] dark:bg-[#444444] animate-pulse rounded" />
              </td>
              {!slim && (
                <>
                  <td className="px-4 py-3">
                    <div className="h-4 w-24 bg-[#D5D8DE] dark:bg-[#444444] animate-pulse rounded" />
                  </td>
                  <td className="px-4 py-3">
                    <div className="h-4 w-16 bg-[#D5D8DE] dark:bg-[#444444] animate-pulse rounded" />
                  </td>
                </>
              )}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

interface AddLeadModalProps {
  open: boolean
  onClose: () => void
  onCreated: () => void
}

function AddLeadModal({ open, onClose, onCreated }: AddLeadModalProps) {
  const [name, setName] = useState('')
  const [email, setEmail] = useState('')
  const [phone, setPhone] = useState('')
  const [referralSource, setReferralSource] = useState('')
  const [hot, setHot] = useState(false)
  const [nameError, setNameError] = useState('')
  const [submitting, setSubmitting] = useState(false)

  function handleClose() {
    setName('')
    setEmail('')
    setPhone('')
    setReferralSource('')
    setHot(false)
    setNameError('')
    onClose()
  }

  async function handleSubmit() {
    if (!name.trim()) {
      setNameError('Name is required.')
      return
    }
    setSubmitting(true)
    try {
      await leadsApi.create({
        name: name.trim(),
        email: email.trim() || undefined,
        phone: phone.trim() || undefined,
        referral_source: referralSource || undefined,
        hot,
      })
      toast.success('Lead added.')
      onCreated()
      handleClose()
    } catch (err: unknown) {
      const detail = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail
      toast.error(detail ?? 'Failed to create lead.')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <Modal
      open={open}
      onClose={handleClose}
      title="Add lead"
      size="sm"
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
            className="h-9 px-3 rounded-[6px] bg-brand dark:bg-brand-btn text-white text-[13px] font-medium hover:opacity-90 transition-opacity disabled:opacity-60"
          >
            {submitting ? 'Saving...' : 'Save lead'}
          </button>
        </>
      }
    >
      <div className="flex flex-col gap-4">
        <FormField label="Name" required error={nameError}>
          <TextInput
            placeholder="Jane Smith"
            value={name}
            onChange={(e) => { setName(e.target.value); if (nameError) setNameError('') }}
            error={!!nameError}
          />
        </FormField>
        <FormField label="Email">
          <TextInput
            type="email"
            placeholder="jane@example.com"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
          />
        </FormField>
        <FormField label="Phone">
          <TextInput
            type="tel"
            placeholder="+1 (555) 000-0000"
            value={phone}
            onChange={(e) => setPhone(e.target.value)}
          />
        </FormField>
        <FormField label="Referral source">
          <SelectInput
            value={referralSource}
            onChange={(e) => setReferralSource(e.target.value)}
            options={REFERRAL_SOURCE_OPTIONS}
          />
        </FormField>
        <label className="flex items-center gap-2 cursor-pointer select-none">
          <input
            type="checkbox"
            checked={hot}
            onChange={(e) => setHot(e.target.checked)}
            className="h-4 w-4 rounded border-surface-border accent-brand"
          />
          <span className="text-[13px] text-brand dark:text-[#EDEEF0]">Mark as hot lead</span>
          <Flame className="h-3.5 w-3.5 text-[#F59E0B]" />
        </label>
      </div>
    </Modal>
  )
}

export default function LeadsLayout({ children }: { children: React.ReactNode }) {
  const pathname = usePathname()
  const router = useRouter()

  // Detect selected lead from URL: /leads/<id> -> <id>, /leads -> null
  const selectedLeadId = pathname.startsWith('/leads/') ? pathname.slice('/leads/'.length) : null

  const [stageFilter, setStageFilter] = useState('')
  const [search, setSearch] = useState('')
  const [page, setPage] = useState(1)
  const [addLeadOpen, setAddLeadOpen] = useState(false)

  // Increment to force a list refetch after a detail-panel stage transition or new lead creation.
  const [refetchKey, setRefetchKey] = useState(0)

  // Summary fetch: high limit to ensure accurate per-stage counts in the strip.
  const { data: summaryData } = useFetch(
    () => leadsApi.list({ stage: stageFilter || undefined, limit: 500 }),
    [stageFilter, refetchKey]
  )

  // Table fetch: real server-side pagination.
  const { data: tableData, isLoading } = useFetch(
    () => leadsApi.list({
      stage: stageFilter || undefined,
      limit: PAGE_SIZE,
      offset: (page - 1) * PAGE_SIZE,
    }),
    [stageFilter, page, refetchKey]
  )

  // Listen for the custom event dispatched by the detail panel after a transition
  // so the list reflects the new stage without requiring a filter change.
  useEffect(() => {
    const handler = () => setRefetchKey((k) => k + 1)
    window.addEventListener('lead-updated', handler)
    return () => window.removeEventListener('lead-updated', handler)
  }, [])

  // Summary strip uses the high-limit fetch for accurate stage counts.
  const leads: Lead[] = summaryData?.items ?? []
  // Table rows use the paginated fetch.
  const tableLeads: Lead[] = tableData?.items ?? []
  const totalCount = tableData?.total ?? 0
  const totalPages = Math.max(1, Math.ceil(totalCount / PAGE_SIZE))

  // Client-side search filters the current page of table results.
  const filtered = search.trim()
    ? tableLeads.filter(
        (l) =>
          l.name.toLowerCase().includes(search.toLowerCase()) ||
          (l.email ?? '').toLowerCase().includes(search.toLowerCase())
      )
    : tableLeads

  const slim = selectedLeadId !== null

  return (
    <div className="flex h-full overflow-hidden">
      <AddLeadModal
        open={addLeadOpen}
        onClose={() => setAddLeadOpen(false)}
        onCreated={() => setRefetchKey((k) => k + 1)}
      />

      {/* Left: table column -- full width when no lead selected, fixed width when panel open */}
      <div className={cn(
        'flex flex-col flex-shrink-0 overflow-hidden',
        slim
          ? 'w-[420px] border-r border-surface-border dark:border-dark-border'
          : 'flex-1',
      )}>
        <div className="overflow-y-auto flex-1 p-6">
          {/* Page header */}
          <div className="flex items-center justify-between mb-5">
            <h1 className="text-[28px] font-bold text-brand dark:text-[#EDEEF0] tracking-tight">Pipeline</h1>
            <button
              onClick={() => setAddLeadOpen(true)}
              className="h-10 px-4 rounded-[7px] bg-brand dark:bg-brand-btn text-white text-[14px] font-semibold flex items-center gap-1.5 hover:opacity-90 transition-opacity"
            >
              <Plus className="h-4 w-4" />
              Add lead
            </button>
          </div>

          {/* Summary strip -- real per-stage counts. Hidden in slim mode. */}
          {!slim && leads.length > 0 && (
            <div className="bg-white dark:bg-dark-card border border-[0.5px] border-surface-border dark:border-dark-border rounded-card mb-4 overflow-hidden">
              <div className="flex items-stretch">
                {/* Total: visually separate from the stage breakdown -- extra right padding creates gap without a divider */}
                <div className="flex-none flex flex-col pl-5 pr-10 py-5">
                  <p className="text-[21px] font-bold text-brand dark:text-[#EDEEF0] leading-none tabular-nums">
                    {summaryData?.total ?? leads.length}
                  </p>
                  <p className="text-[11px] text-[#6B7280] mt-1.5 whitespace-nowrap">All leads</p>
                </div>
                {/* Per-stage counts with dividers between them */}
                <div className="flex-1 flex items-stretch divide-x divide-surface-border dark:divide-dark-border">
                  {([
                    { stage: 'identified',  label: 'Identified',  dot: '#9CA3AF' },
                    { stage: 'contacted',   label: 'Contacted',   dot: '#F59E0B' },
                    { stage: 'call_booked', label: 'Call Booked', dot: '#3B82F6' },
                    { stage: 'proposal',    label: 'Proposal',    dot: '#1E40AF' },
                    { stage: 'won',         label: 'Won',         dot: '#22C55E' },
                    { stage: 'lost',        label: 'Lost',        dot: '#EF4444' },
                  ] as const).map(({ stage, label, dot }) => (
                    <div key={stage} className="flex-1 flex flex-col px-5 py-5 min-w-0">
                      <p className="text-[21px] font-bold text-brand dark:text-[#EDEEF0] leading-none tabular-nums">
                        {leads.filter((l) => l.stage === stage).length}
                      </p>
                      <div className="flex items-center gap-1 mt-1.5">
                        <span className="h-[7px] w-[7px] rounded-full flex-shrink-0" style={{ backgroundColor: dot }} />
                        <span className="text-[11px] text-[#6B7280] whitespace-nowrap">{label}</span>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          )}

          {/* Search and stage filter toolbar */}
          <div className="flex items-center gap-3 mb-4 flex-wrap">
            <div className="relative">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-[#9CA3AF]" />
              <input
                type="text"
                placeholder="Search leads..."
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                className={cn(
                  'h-10 pl-9 pr-8 rounded-[6px] border border-[0.5px] border-surface-border dark:border-dark-border bg-surface-card dark:bg-dark-card text-[13px] text-brand dark:text-[#EDEEF0] placeholder:text-[#9CA3AF] focus:outline-none focus:border-brand dark:focus:border-[#4A7FA5]',
                  slim ? 'w-40' : 'w-72',
                )}
              />
              {search && (
                <button
                  onClick={() => setSearch('')}
                  className="absolute right-2.5 top-1/2 -translate-y-1/2 text-[#9CA3AF] hover:text-brand"
                >
                  <X className="h-3.5 w-3.5" />
                </button>
              )}
            </div>

            <div className="relative">
              <select
                value={stageFilter}
                onChange={(e) => { setStageFilter(e.target.value); setPage(1) }}
                className="h-10 pl-3 pr-7 rounded-[6px] border border-[0.5px] border-surface-border dark:border-dark-border bg-surface-card dark:bg-dark-card text-[13px] text-brand dark:text-[#EDEEF0] focus:outline-none focus:border-brand dark:focus:border-[#4A7FA5] appearance-none"
              >
                {LEAD_STAGES.map((s) => (
                  <option key={s.value} value={s.value}>{s.label}</option>
                ))}
              </select>
              <ChevronDown className="absolute right-2 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-[#9CA3AF] pointer-events-none" />
            </div>
          </div>

          {/* Table */}
          {isLoading ? (
            <LeadsTableSkeleton slim={slim} rowCount={filtered.length > 0 ? Math.min(10, filtered.length) : 3} />
          ) : filtered.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-16 gap-2">
              <p className="text-[14px] font-medium text-brand dark:text-[#EDEEF0]">No leads found</p>
              <p className="text-[13px] text-[#6B7280]">
                {stageFilter || search ? 'Try adjusting the filters.' : 'Leads will appear here once added.'}
              </p>
            </div>
          ) : (
            <>
            <div className="rounded-[10px] bg-white dark:bg-dark-card border border-[0.5px] border-surface-border dark:border-dark-border overflow-hidden">
              <table className="w-full border-collapse">
                <colgroup>
                  {slim ? (
                    <>
                      <col />
                      <col style={{ width: '32%' }} />
                    </>
                  ) : (
                    <>
                      <col style={{ width: '30%' }} />
                      <col style={{ width: '27%' }} />
                      <col style={{ width: '15%' }} />
                      <col style={{ width: '18%' }} />
                      <col style={{ width: '10%' }} />
                    </>
                  )}
                </colgroup>
                <thead>
                  <tr className="bg-surface-card dark:bg-[#252525] border-b border-[0.5px] border-surface-border dark:border-dark-border">
                    <th className="px-4 py-4 text-left text-[11px] font-semibold text-[#6B7280] uppercase tracking-[0.07em] whitespace-nowrap">
                      Lead Name
                    </th>
                    {!slim && (
                      <th className="px-4 py-4 text-left text-[11px] font-semibold text-[#6B7280] uppercase tracking-[0.07em] whitespace-nowrap">
                        Email
                      </th>
                    )}
                    <th className="px-4 py-4 text-left text-[11px] font-semibold text-[#6B7280] uppercase tracking-[0.07em] whitespace-nowrap">
                      Stage
                    </th>
                    {!slim && (
                      <>
                        <th className="px-4 py-4 text-left text-[11px] font-semibold text-[#6B7280] uppercase tracking-[0.07em] whitespace-nowrap">
                          Referral Source
                        </th>
                        <th className="px-4 py-4 text-left text-[11px] font-semibold text-[#6B7280] uppercase tracking-[0.07em] whitespace-nowrap">
                          Date Added
                        </th>
                      </>
                    )}
                  </tr>
                </thead>
                <tbody>
                  {filtered.map((lead, i) => (
                    <tr
                      key={lead.id}
                      onClick={() => router.push(`/leads/${lead.id}`)}
                      className={cn(
                        'transition-colors duration-100 cursor-pointer',
                        i !== filtered.length - 1 && 'border-b border-[0.5px] border-[#D5D8DE] dark:border-dark-card',
                        selectedLeadId === lead.id
                          ? 'bg-[#EEF2FF] dark:bg-[#1e2a40]'
                          : 'hover:bg-surface-card dark:hover:bg-[#323232]',
                      )}
                    >
                      <td className="px-4 py-3">
                        <div className="flex items-center gap-1.5 min-w-0">
                          {lead.hot && <Flame className="h-3.5 w-3.5 text-[#F59E0B] flex-shrink-0" />}
                          <Link
                            href={`/leads/${lead.id}`}
                            onClick={(e) => e.stopPropagation()}
                            className="text-[15px] font-semibold text-brand dark:text-[#EDEEF0] hover:text-brand-light dark:hover:text-[#4A7FA5] hover:underline truncate"
                          >
                            {lead.name}
                          </Link>
                        </div>
                      </td>
                      {!slim && (
                        <td className="px-4 py-3">
                          <span className="text-[12px] text-[#6B7280] dark:text-[#9CA3AF]">
                            {lead.email ?? '-'}
                          </span>
                        </td>
                      )}
                      <td className="px-4 py-3">
                        <StatusBadge variant={lead.stage as BadgeVariant} />
                      </td>
                      {!slim && (
                        <>
                          <td className="px-4 py-3">
                            <span className="text-[12px] text-[#6B7280] dark:text-[#9CA3AF]">
                              {formatSource(lead.referralSource)}
                            </span>
                          </td>
                          <td className="px-4 py-3">
                            <span className="text-[12px] text-[#6B7280] dark:text-[#9CA3AF]">
                              {formatDate(lead.createdAt)}
                            </span>
                          </td>
                        </>
                      )}
                    </tr>
                  ))}
                </tbody>
              </table>

            </div>
            {/* Pagination footnote -- outside the table card so it reads as a quiet annotation */}
            {totalCount > 0 && (
              <div className="flex items-center justify-between px-1 pt-2">
                <p className="text-[11px] text-[#6B7280]">
                  Showing {((page - 1) * PAGE_SIZE + 1).toLocaleString()} to {Math.min(page * PAGE_SIZE, totalCount).toLocaleString()} of {totalCount.toLocaleString()}
                </p>
                {totalPages > 1 && (
                  <div className="flex items-center gap-0.5">
                    <button
                      disabled={page === 1}
                      onClick={() => setPage((p) => p - 1)}
                      className="h-7 w-7 rounded-[4px] flex items-center justify-center text-[#9CA3AF] hover:bg-surface-card dark:hover:bg-[#2D3748] disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
                    >
                      <ChevronLeft className="h-3.5 w-3.5" />
                    </button>
                    {(() => {
                      const pages: (number | 'ellipsis')[] = []
                      for (let p = 1; p <= totalPages; p++) {
                        if (p === 1 || p === totalPages || Math.abs(p - page) <= 1) {
                          pages.push(p)
                        } else if (pages[pages.length - 1] !== 'ellipsis') {
                          pages.push('ellipsis')
                        }
                      }
                      return pages.map((p, i) =>
                        p === 'ellipsis' ? (
                          <span key={`e${i}`} className="px-1 text-[11px] text-[#9CA3AF]">...</span>
                        ) : (
                          <button
                            key={p}
                            onClick={() => setPage(p)}
                            className={cn(
                              'h-7 min-w-[28px] px-2 rounded-[4px] text-[11px] transition-colors',
                              p === page
                                ? 'bg-brand dark:bg-brand-btn text-white font-semibold'
                                : 'text-[#9CA3AF] hover:bg-surface-card dark:hover:bg-[#2D3748]',
                            )}
                          >
                            {p}
                          </button>
                        )
                      )
                    })()}
                    <button
                      disabled={page >= totalPages}
                      onClick={() => setPage((p) => p + 1)}
                      className="h-7 w-7 rounded-[4px] flex items-center justify-center text-[#9CA3AF] hover:bg-surface-card dark:hover:bg-[#2D3748] disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
                    >
                      <ChevronRight className="h-3.5 w-3.5" />
                    </button>
                  </div>
                )}
              </div>
            )}
            </>
          )}
        </div>
      </div>

      {/* Right: detail panel -- rendered only when a lead is selected */}
      {selectedLeadId && (
        <div className="flex-1 overflow-y-auto min-w-0">
          {children}
        </div>
      )}
    </div>
  )
}

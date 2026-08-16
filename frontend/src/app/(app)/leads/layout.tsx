// path: frontend/src/app/(app)/leads/layout.tsx
'use client'

import { useState, useEffect } from 'react'
import { usePathname, useRouter } from 'next/navigation'
import Link from 'next/link'
import { Search, X, Flame } from 'lucide-react'
import { leadsApi, type Lead } from '@/lib/api'
import { useFetch } from '@/lib/hooks/useFetch'
import { StatusBadge } from '@/components/ui/StatusBadge'
import { cn } from '@/lib/utils'
import type { BadgeVariant } from '@/components/ui/StatusBadge'

const LEAD_STAGES = [
  { value: '', label: 'All stages' },
  { value: 'identified', label: 'Identified' },
  { value: 'contacted', label: 'Contacted' },
  { value: 'call_booked', label: 'Call Booked' },
  { value: 'proposal', label: 'Proposal' },
  { value: 'won', label: 'Won' },
  { value: 'lost', label: 'Lost' },
]

const STAGE_LEFT_BORDER: Record<string, string> = {
  identified: 'border-l-[#9CA3AF]',
  contacted:  'border-l-[#F59E0B]',
  call_booked:'border-l-[#3B82F6]',
  proposal:   'border-l-[#1E40AF]',
  won:        'border-l-[#22C55E]',
  lost:       'border-l-[#EF4444]',
}

function formatDate(iso: string): string {
  if (!iso) return '-'
  return new Date(iso).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })
}

function formatSource(raw: string | null): string {
  if (!raw) return '-'
  return raw.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase())
}

function LeadsTableSkeleton({ slim }: { slim: boolean }) {
  return (
    <div className="rounded-[10px] bg-white dark:bg-dark-card shadow-sm overflow-hidden">
      {Array.from({ length: 6 }).map((_, i) => (
        <div key={i} className="flex items-center gap-4 px-5 py-3 border-b border-[0.5px] border-[#E2E8EF] dark:border-dark-border last:border-0">
          <div className="h-4 w-32 bg-[#D5D8DE] dark:bg-[#444444] animate-pulse rounded flex-1" />
          {!slim && <div className="h-4 w-24 bg-[#D5D8DE] dark:bg-[#444444] animate-pulse rounded flex-shrink-0" />}
          <div className="h-4 w-20 bg-[#D5D8DE] dark:bg-[#444444] animate-pulse rounded flex-shrink-0" />
        </div>
      ))}
    </div>
  )
}

export default function LeadsLayout({ children }: { children: React.ReactNode }) {
  const pathname = usePathname()
  const router = useRouter()

  // Detect selected lead from URL: /leads/<id> -> <id>, /leads -> null
  const selectedLeadId = pathname.startsWith('/leads/') ? pathname.slice('/leads/'.length) : null

  const [stageFilter, setStageFilter] = useState('')
  const [hotFilter, setHotFilter] = useState(false)
  const [search, setSearch] = useState('')

  // Increment to force a list refetch after a detail-panel stage transition.
  const [refetchKey, setRefetchKey] = useState(0)

  const { data, isLoading } = useFetch(
    () => leadsApi.list({ stage: stageFilter || undefined, hot: hotFilter || undefined }),
    [stageFilter, hotFilter, refetchKey]
  )

  // Listen for the custom event dispatched by the detail panel after a transition
  // so the list reflects the new stage without requiring a filter change.
  useEffect(() => {
    const handler = () => setRefetchKey((k) => k + 1)
    window.addEventListener('lead-updated', handler)
    return () => window.removeEventListener('lead-updated', handler)
  }, [])

  const leads: Lead[] = data?.items ?? []
  const filtered = search.trim()
    ? leads.filter(
        (l) =>
          l.name.toLowerCase().includes(search.toLowerCase()) ||
          (l.email ?? '').toLowerCase().includes(search.toLowerCase())
      )
    : leads

  const slim = selectedLeadId !== null

  return (
    <div className="flex h-full overflow-hidden">
      {/* Left: table column -- full width when no lead selected, fixed width when panel open */}
      <div className={cn(
        'flex flex-col flex-shrink-0 overflow-hidden',
        slim
          ? 'w-[420px] border-r border-[#E2E8EF] dark:border-dark-border'
          : 'flex-1',
      )}>
        <div className="overflow-y-auto flex-1 p-6">
          {/* Page header */}
          <div className="flex items-center justify-between mb-6">
            <div>
              <h1 className="text-[26px] font-semibold text-brand dark:text-[#EDEEF0] tracking-tight">Pipeline</h1>
              <p className="text-[13px] text-[#6B7280] mt-0.5">
                {data?.total !== undefined ? `${data.total} lead${data.total !== 1 ? 's' : ''}` : ''}
              </p>
            </div>
          </div>

          {/* Filters */}
          <div className="flex items-center gap-2 mb-5 flex-wrap">
            <div className="relative">
              <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-[#9CA3AF]" />
              <input
                type="text"
                placeholder="Search leads..."
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                className={cn(
                  'h-8 pl-8 pr-8 rounded-[6px] border border-[0.5px] border-surface-border dark:border-dark-border bg-white dark:bg-dark-card text-[12px] text-brand dark:text-[#EDEEF0] placeholder:text-[#9CA3AF] focus:outline-none focus:border-brand dark:focus:border-[#4A7FA5] shadow-sm',
                  slim ? 'w-36' : 'w-52',
                )}
              />
              {search && (
                <button
                  onClick={() => setSearch('')}
                  className="absolute right-2 top-1/2 -translate-y-1/2 text-[#9CA3AF] hover:text-brand"
                >
                  <X className="h-3.5 w-3.5" />
                </button>
              )}
            </div>

            <select
              value={stageFilter}
              onChange={(e) => setStageFilter(e.target.value)}
              className="h-8 px-2.5 rounded-[6px] border border-[0.5px] border-surface-border dark:border-dark-border bg-white dark:bg-dark-card text-[12px] text-brand dark:text-[#EDEEF0] focus:outline-none focus:border-brand dark:focus:border-[#4A7FA5] shadow-sm"
            >
              {LEAD_STAGES.map((s) => (
                <option key={s.value} value={s.value}>{s.label}</option>
              ))}
            </select>

            <button
              onClick={() => setHotFilter((v) => !v)}
              className={cn(
                'h-8 px-3 rounded-[6px] border border-[0.5px] text-[12px] font-medium flex items-center gap-1.5 transition-colors shadow-sm',
                hotFilter
                  ? 'bg-[#FEF3C7] border-[#F59E0B] text-[#B45309]'
                  : 'border-surface-border dark:border-dark-border bg-white dark:bg-dark-card text-[#6B7280] hover:text-brand dark:hover:text-[#EDEEF0]',
              )}
            >
              <Flame className="h-3.5 w-3.5" />
              Hot
            </button>
          </div>

          {/* Table */}
          {isLoading ? (
            <LeadsTableSkeleton slim={slim} />
          ) : filtered.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-16 gap-2">
              <p className="text-[14px] font-medium text-brand dark:text-[#EDEEF0]">No leads found</p>
              <p className="text-[13px] text-[#6B7280]">
                {stageFilter || hotFilter || search ? 'Try adjusting the filters.' : 'Leads will appear here once added.'}
              </p>
            </div>
          ) : (
            <div className="rounded-[10px] bg-white dark:bg-dark-card shadow-sm overflow-hidden">
              <table className="w-full border-collapse">
                <thead>
                  <tr className="bg-[#F8FAFC] dark:bg-[#1E2530] border-b border-[0.5px] border-[#E2E8EF] dark:border-dark-border">
                    <th className="px-5 py-3 text-left text-[11px] font-semibold text-[#6B7280] uppercase tracking-[0.07em] whitespace-nowrap">
                      Name
                    </th>
                    {!slim && (
                      <th className="px-5 py-3 text-left text-[11px] font-semibold text-[#6B7280] uppercase tracking-[0.07em] whitespace-nowrap">
                        Email
                      </th>
                    )}
                    <th className="px-5 py-3 text-left text-[11px] font-semibold text-[#6B7280] uppercase tracking-[0.07em] whitespace-nowrap">
                      Stage
                    </th>
                    {!slim && (
                      <>
                        <th className="px-5 py-3 text-left text-[11px] font-semibold text-[#6B7280] uppercase tracking-[0.07em] whitespace-nowrap">
                          Source
                        </th>
                        <th className="px-5 py-3 text-left text-[11px] font-semibold text-[#6B7280] uppercase tracking-[0.07em] whitespace-nowrap">
                          Added
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
                        'transition-colors cursor-pointer',
                        i !== filtered.length - 1 && 'border-b border-[0.5px] border-[#E8EDF3] dark:border-[#2D3440]',
                        selectedLeadId === lead.id
                          ? 'bg-[#EFF6FF] dark:bg-[#1E2D3D]'
                          : 'hover:bg-[#F1F5F9] dark:hover:bg-[#2D3748]',
                      )}
                    >
                      <td className={cn(
                        'px-5 py-3 border-l-[3px]',
                        STAGE_LEFT_BORDER[lead.stage] ?? 'border-l-[#9CA3AF]',
                      )}>
                        <div className="flex items-center gap-2 min-w-0">
                          {lead.hot && <Flame className="h-3.5 w-3.5 text-[#F59E0B] flex-shrink-0" />}
                          <Link
                            href={`/leads/${lead.id}`}
                            onClick={(e) => e.stopPropagation()}
                            className="text-[13px] font-semibold text-brand dark:text-[#EDEEF0] hover:text-brand-light dark:hover:text-[#4A7FA5] hover:underline truncate"
                          >
                            {lead.name}
                          </Link>
                        </div>
                      </td>
                      {!slim && (
                        <td className="px-5 py-3">
                          <span className="text-[13px] text-[#4B5563] dark:text-[#9CA3AF]">
                            {lead.email ?? '-'}
                          </span>
                        </td>
                      )}
                      <td className="px-5 py-3">
                        <StatusBadge variant={lead.stage as BadgeVariant} />
                      </td>
                      {!slim && (
                        <>
                          <td className="px-5 py-3">
                            <span className="text-[13px] text-[#4B5563] dark:text-[#9CA3AF]">
                              {formatSource(lead.referralSource)}
                            </span>
                          </td>
                          <td className="px-5 py-3">
                            <span className="text-[13px] text-[#4B5563] dark:text-[#9CA3AF]">
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

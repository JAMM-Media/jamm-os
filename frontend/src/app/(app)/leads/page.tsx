// path: frontend/src/app/(app)/leads/page.tsx
'use client'

import { useState } from 'react'
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

// Left-border accent color per stage, matching StatusBadge color tokens.
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

function LeadsTableSkeleton() {
  return (
    <div className="rounded-modal border border-[0.5px] border-surface-border dark:border-dark-border overflow-hidden">
      {Array.from({ length: 6 }).map((_, i) => (
        <div key={i} className="flex items-center gap-4 px-4 py-2.5 border-b border-[0.5px] border-[#D5D8DE] dark:border-dark-card last:border-0">
          <div className="h-4 w-40 bg-[#D5D8DE] dark:bg-[#444444] animate-pulse rounded flex-1" />
          <div className="h-4 w-28 bg-[#D5D8DE] dark:bg-[#444444] animate-pulse rounded flex-shrink-0" />
          <div className="h-4 w-24 bg-[#D5D8DE] dark:bg-[#444444] animate-pulse rounded flex-shrink-0" />
          <div className="h-4 w-20 bg-[#D5D8DE] dark:bg-[#444444] animate-pulse rounded flex-shrink-0" />
        </div>
      ))}
    </div>
  )
}

export default function LeadsPage() {
  const [stageFilter, setStageFilter] = useState('')
  const [hotFilter, setHotFilter] = useState(false)
  const [search, setSearch] = useState('')

  const { data, isLoading } = useFetch(
    () => leadsApi.list({ stage: stageFilter || undefined, hot: hotFilter || undefined }),
    [stageFilter, hotFilter]
  )

  const leads: Lead[] = data?.items ?? []

  const filtered = search.trim()
    ? leads.filter((l) =>
        l.name.toLowerCase().includes(search.toLowerCase()) ||
        (l.email ?? '').toLowerCase().includes(search.toLowerCase())
      )
    : leads

  return (
    <div className="p-6">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-medium text-brand dark:text-[#EDEEF0]">Pipeline</h1>
          <p className="text-[13px] text-[#6B7280] mt-0.5">
            {data?.total !== undefined ? `${data.total} lead${data.total !== 1 ? 's' : ''}` : ''}
          </p>
        </div>
      </div>

      {/* Filters */}
      <div className="flex items-center gap-3 mb-4 flex-wrap">
        <div className="relative">
          <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-[#9CA3AF]" />
          <input
            type="text"
            placeholder="Search leads..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="h-8 pl-8 pr-8 rounded-[6px] border border-[0.5px] border-surface-border dark:border-dark-border bg-surface-card dark:bg-dark-card text-[12px] text-brand dark:text-[#EDEEF0] placeholder:text-[#9CA3AF] focus:outline-none focus:border-brand dark:focus:border-[#4A7FA5] w-52"
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
          className="h-8 px-2.5 rounded-[6px] border border-[0.5px] border-surface-border dark:border-dark-border bg-surface-card dark:bg-dark-card text-[12px] text-brand dark:text-[#EDEEF0] focus:outline-none focus:border-brand dark:focus:border-[#4A7FA5]"
        >
          {LEAD_STAGES.map((s) => (
            <option key={s.value} value={s.value}>{s.label}</option>
          ))}
        </select>

        <button
          onClick={() => setHotFilter((v) => !v)}
          className={cn(
            'h-8 px-3 rounded-[6px] border border-[0.5px] text-[12px] font-medium flex items-center gap-1.5 transition-colors',
            hotFilter
              ? 'bg-[#FEF3C7] border-[#F59E0B] text-[#B45309]'
              : 'border-surface-border dark:border-dark-border bg-surface-card dark:bg-dark-card text-[#6B7280] hover:text-brand dark:hover:text-[#EDEEF0]'
          )}
        >
          <Flame className="h-3.5 w-3.5" />
          Hot
        </button>
      </div>

      {/* Table */}
      {isLoading ? (
        <LeadsTableSkeleton />
      ) : filtered.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-24 gap-2">
          <p className="text-[13px] font-medium text-brand dark:text-[#EDEEF0]">No leads found</p>
          <p className="text-[12px] text-[#6B7280]">
            {stageFilter || hotFilter || search ? 'Try adjusting the filters.' : 'Leads will appear here once added.'}
          </p>
        </div>
      ) : (
        <div className="rounded-modal border border-[0.5px] border-surface-border dark:border-dark-border overflow-hidden">
          <table className="w-full border-collapse">
            <thead>
              <tr className="bg-surface-card dark:bg-[#252525]">
                {['Name', 'Email', 'Stage', 'Source', 'Created'].map((col) => (
                  <th key={col} className="px-4 py-2.5 text-left text-[11px] font-medium text-[#6B7280] uppercase tracking-[0.05em] whitespace-nowrap">
                    {col}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {filtered.map((lead, i) => (
                <tr
                  key={lead.id}
                  className={cn(
                    'bg-[#E4E6EA] dark:bg-[#2D2D2D] hover:bg-[#DDDFE3] dark:hover:bg-[#323232] hover:shadow-sm transition-all',
                    i !== filtered.length - 1 && 'border-b border-[0.5px] border-[#D5D8DE] dark:border-[#383838]'
                  )}
                >
                  {/* First cell carries the stage accent border */}
                  <td className={cn(
                    'px-4 py-2.5 border-l-[3px]',
                    STAGE_LEFT_BORDER[lead.stage] ?? 'border-l-[#9CA3AF]'
                  )}>
                    <div className="flex items-center gap-2">
                      {lead.hot && <Flame className="h-3.5 w-3.5 text-[#F59E0B] flex-shrink-0" />}
                      <Link
                        href={`/leads/${lead.id}`}
                        className="text-[13px] font-medium text-brand dark:text-[#EDEEF0] hover:underline"
                      >
                        {lead.name}
                      </Link>
                    </div>
                  </td>
                  <td className="px-4 py-2.5">
                    <span className="text-[12px] text-[#374151] dark:text-[#9CA3AF]">
                      {lead.email ?? '-'}
                    </span>
                  </td>
                  <td className="px-4 py-2.5">
                    <StatusBadge variant={lead.stage as BadgeVariant} />
                  </td>
                  <td className="px-4 py-2.5">
                    <span className="text-[12px] text-[#374151] dark:text-[#9CA3AF]">
                      {formatSource(lead.referralSource)}
                    </span>
                  </td>
                  <td className="px-4 py-2.5">
                    <span className="text-[12px] text-[#374151] dark:text-[#9CA3AF]">
                      {formatDate(lead.createdAt)}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}

// frontend/src/components/dashboard/BriefingCard.tsx
'use client'

import { useState, useEffect } from 'react'
import Link from 'next/link'
import { useQuery } from '@tanstack/react-query'
import {
  Briefcase,
  Calendar,
  ChevronDown,
  ChevronUp,
  Clock,
  FileText,
  Users,
} from 'lucide-react'
import { surfaceItemsApi, type TierOneFact } from '@/lib/api/surfaceItems'

const MINIMIZED_KEY = 'jamm_briefing_minimized'

// ---------------------------------------------------------------------------
// Per-category icon
// ---------------------------------------------------------------------------

const CATEGORY_ICONS: Record<string, React.ElementType> = {
  overdue_invoices: FileText,
  irs_authorizations: Users,
  signature_requests: Clock,
  deadlines: Calendar,
  unbilled_work: Briefcase,
}

// ---------------------------------------------------------------------------
// Fact row rendering with bold key numbers
// ---------------------------------------------------------------------------

function FactText({ fact }: { fact: TierOneFact }) {
  const b = (s: string | number) => (
    <strong className="font-semibold text-brand dark:text-[#EDEEF0]">{s}</strong>
  )

  switch (fact.category) {
    case 'overdue_invoices': {
      const noun = fact.count === 1 ? 'invoice' : 'invoices'
      const total =
        fact.amount != null
          ? `$${fact.amount.toLocaleString('en-US', { maximumFractionDigits: 0 })}`
          : ''
      return (
        <span>
          {b(fact.count)} {noun} are overdue, with balances totaling {b(total)}
        </span>
      )
    }
    case 'irs_authorizations': {
      const noun = fact.count === 1 ? 'IRS authorization' : 'IRS authorizations'
      return (
        <span>
          {b(fact.count)} {noun} expiring
        </span>
      )
    }
    case 'signature_requests': {
      const noun = fact.count === 1 ? 'signature request' : 'signature requests'
      return (
        <span>
          {b(fact.count)} {noun} pending
        </span>
      )
    }
    case 'deadlines': {
      const noun = fact.count === 1 ? 'deadline' : 'deadlines'
      const blockers = fact.amount != null ? Math.round(fact.amount) : 0
      const itemNoun = blockers === 1 ? 'open item' : 'open items'
      return (
        <span>
          {b(fact.count)} {noun} with {b(blockers)} {itemNoun}
        </span>
      )
    }
    case 'unbilled_work': {
      const noun = fact.count === 1 ? 'engagement' : 'engagements'
      return (
        <span>
          {b(fact.count)} completed {noun} not yet invoiced
        </span>
      )
    }
    default:
      return <span>{fact.text}</span>
  }
}

function FactRow({ fact, isLast }: { fact: TierOneFact; isLast: boolean }) {
  const Icon = CATEGORY_ICONS[fact.category]
  return (
    <div
      data-category={fact.category}
      className={`flex items-center gap-2.5 py-2 ${
        !isLast ? 'border-b-[0.5px] border-surface-border dark:border-dark-border' : ''
      }`}
    >
      {Icon && (
        <div className="h-7 w-7 rounded-full bg-[#EFF6FF] dark:bg-[#1E3A5F] flex items-center justify-center flex-shrink-0">
          <Icon className="h-3.5 w-3.5 text-[#3B82F6] dark:text-[#60A5FA]" />
        </div>
      )}
      <span className="text-[12px] text-[#374151] dark:text-[#D1D5DB] leading-[1.5]">
        <FactText fact={fact} />
      </span>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Skeleton
// ---------------------------------------------------------------------------

function BriefingCardSkeleton() {
  return (
    <div className="flex flex-col border border-[0.5px] border-surface-border dark:border-dark-border rounded-[8px] bg-surface-card dark:bg-dark-card shadow-sm overflow-hidden mb-3">
      <div className="px-3 py-2 border-b border-surface-border dark:border-dark-border flex items-center gap-1.5">
        <div className="h-2.5 w-28 bg-[#D5D8DE] dark:bg-[#444444] animate-pulse rounded" />
      </div>
      <div className="px-3 py-2.5 flex flex-col gap-2">
        <div className="h-3 w-full bg-[#D5D8DE] dark:bg-[#444444] animate-pulse rounded" />
        <div className="h-3 w-4/5 bg-[#D5D8DE] dark:bg-[#444444] animate-pulse rounded" />
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Card
// ---------------------------------------------------------------------------

export function BriefingCard() {
  const [minimized, setMinimized] = useState(false)

  useEffect(() => {
    if (sessionStorage.getItem(MINIMIZED_KEY) === 'true') setMinimized(true)
  }, [])

  const { data, isLoading } = useQuery({
    queryKey: ['briefing-card'],
    queryFn: surfaceItemsApi.getBriefing,
    staleTime: 60_000,
  })

  if (isLoading) return <BriefingCardSkeleton />
  if (!data || data.items.length === 0) return null

  const facts = data.facts ?? []
  const summaryText = data.summary

  function toggleMinimized(e: React.MouseEvent) {
    e.stopPropagation()
    setMinimized((prev) => {
      const next = !prev
      sessionStorage.setItem(MINIMIZED_KEY, String(next))
      return next
    })
  }

  return (
    <div className="flex flex-col border border-[0.5px] border-surface-border dark:border-dark-border rounded-[8px] bg-surface-card dark:bg-dark-card shadow-sm overflow-hidden mb-3">
      <div className="px-3 py-2 border-b border-surface-border dark:border-dark-border flex items-center">
        <span className="text-[10px] font-semibold uppercase tracking-wide text-[#6B7280] flex-1">
          MORNING BRIEFING
        </span>
        {minimized && summaryText && (
          <p className="text-[12px] text-brand dark:text-[#EDEEF0] truncate max-w-[60%]">
            {summaryText}
          </p>
        )}
        <button
          onClick={toggleMinimized}
          aria-label={minimized ? 'Expand morning briefing' : 'Minimize morning briefing'}
          className="flex-shrink-0 text-[#9CA3AF] hover:text-brand dark:hover:text-[#EDEEF0] transition-colors ml-1"
        >
          {minimized
            ? <ChevronDown className="h-3.5 w-3.5" />
            : <ChevronUp className="h-3.5 w-3.5" />
          }
        </button>
      </div>

      {!minimized && (
        <div className="px-3 py-1.5">
          {facts.map((fact, i) => (
            <FactRow key={fact.category} fact={fact} isLast={i === facts.length - 1} />
          ))}
          <div className="flex justify-end pt-1 pb-1">
            <Link
              href="/briefing"
              className="text-[12px] text-[#6B7280] hover:text-brand dark:hover:text-[#EDEEF0] transition-colors"
            >
              View full briefing &rarr;
            </Link>
          </div>
        </div>
      )}
    </div>
  )
}

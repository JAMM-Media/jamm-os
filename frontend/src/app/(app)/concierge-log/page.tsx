// frontend/src/app/(app)/concierge-log/page.tsx
'use client'

import { useState, useEffect, useCallback } from 'react'
import api from '@/lib/api'

interface LogEntry {
  id: string
  question_text: string
  response_summary: string | null
  low_confidence: boolean
  possible_fabrication: boolean
  asked_at: string
  reviewed: boolean
}

function formatTs(iso: string): string {
  return new Date(iso).toLocaleString('en-US', {
    month: 'short',
    day: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
    hour12: true,
  })
}

function ConciergeLogSkeleton() {
  return (
    <div className="flex flex-col gap-2">
      {Array.from({ length: 5 }).map((_, i) => (
        <div key={i} className="rounded-[8px] border border-[0.5px] border-[#C8CDD6] dark:border-[#484848] bg-white dark:bg-[#2D2D2D] px-4 py-3">
          <div className="flex items-center gap-2 mb-2">
            <div className="h-3 w-24 bg-[#D5D8DE] dark:bg-[#444444] animate-pulse rounded" />
            <div className="h-3 w-16 bg-[#D5D8DE] dark:bg-[#444444] animate-pulse rounded" />
          </div>
          <div className="h-4 w-3/4 bg-[#D5D8DE] dark:bg-[#444444] animate-pulse rounded" />
        </div>
      ))}
    </div>
  )
}

export default function ConciergeLogPage() {
  const [entries, setEntries] = useState<LogEntry[]>([])
  const [total, setTotal] = useState(0)
  const [lowOnly, setLowOnly] = useState(true)
  const [fabricationOnly, setFabricationOnly] = useState(false)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [expanded, setExpanded] = useState<string | null>(null)

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const res = await api.get('/concierge/question-log', {
        params: {
          low_confidence_only: lowOnly,
          possible_fabrication_only: fabricationOnly,
          limit: 100,
          offset: 0,
        },
      })
      setEntries(res.data.items ?? [])
      setTotal(res.data.total ?? 0)
    } catch {
      setError('Failed to load. Make sure you are signed in as a firm owner.')
    } finally {
      setLoading(false)
    }
  }, [lowOnly, fabricationOnly])

  useEffect(() => { void load() }, [load])

  return (
    <div className="max-w-4xl mx-auto px-4 py-8">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-[18px] font-semibold text-[#1F3148] dark:text-[#EDEEF0]">Concierge Question Log</h1>
          <p className="text-[12px] text-[#6B7280] mt-0.5">Internal review tool. Not visible to firm staff.</p>
        </div>
        <div className="flex items-center gap-3">
          <label className="flex items-center gap-2 text-[12px] text-[#374151] dark:text-[#D1D5DB] cursor-pointer select-none">
            <input
              type="checkbox"
              checked={lowOnly}
              onChange={(e) => setLowOnly(e.target.checked)}
              className="rounded"
            />
            Low confidence only
          </label>
          <label className="flex items-center gap-2 text-[12px] text-[#374151] dark:text-[#D1D5DB] cursor-pointer select-none">
            <input
              type="checkbox"
              checked={fabricationOnly}
              onChange={(e) => setFabricationOnly(e.target.checked)}
              className="rounded"
            />
            Possible fabrication only
          </label>
          <span className="text-[11px] text-[#6B7280]">{total} result{total !== 1 ? 's' : ''}</span>
        </div>
      </div>

      {loading && <ConciergeLogSkeleton />}

      {error && (
        <p className="text-[13px] text-red-600">{error}</p>
      )}

      {!loading && !error && entries.length === 0 && (
        <p className="text-[13px] text-[#6B7280]">No entries found.</p>
      )}

      {!loading && !error && entries.length > 0 && (
        <div className="flex flex-col gap-2">
          {entries.map((e) => (
            <div
              key={e.id}
              className="rounded-[8px] border border-[0.5px] border-[#C8CDD6] dark:border-[#484848] bg-white dark:bg-[#2D2D2D] px-4 py-3"
            >
              <div className="flex items-start justify-between gap-3">
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 mb-1">
                    <span className="text-[11px] text-[#6B7280]">{formatTs(e.asked_at)}</span>
                    {e.low_confidence && (
                      <span className="inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-medium bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400">
                        low confidence
                      </span>
                    )}
                    {e.possible_fabrication && (
                      <span className="inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-medium bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400">
                        possible fabrication
                      </span>
                    )}
                  </div>
                  <p className="text-[13px] font-medium text-[#1F3148] dark:text-[#EDEEF0] leading-snug">
                    {e.question_text}
                  </p>
                </div>
                {e.response_summary && (
                  <button
                    onClick={() => setExpanded(expanded === e.id ? null : e.id)}
                    className="flex-shrink-0 text-[11px] text-[#4A7FA5] hover:underline"
                  >
                    {expanded === e.id ? 'Hide' : 'Response'}
                  </button>
                )}
              </div>
              {expanded === e.id && e.response_summary && (
                <div className="mt-2 pt-2 border-t border-[0.5px] border-[#E5E7EB] dark:border-[#3D3D3D]">
                  <p className="text-[12px] text-[#374151] dark:text-[#9CA3AF] whitespace-pre-wrap leading-relaxed">
                    {e.response_summary}
                  </p>
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

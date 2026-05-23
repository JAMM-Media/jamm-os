'use client'

import { useState, useCallback, useEffect, useRef } from 'react'
import { toast } from 'sonner'
import { Trash2, Loader2 } from 'lucide-react'
import api from '@/lib/api'
import { useAuth } from '@/lib/hooks/useAuth'

interface QcItem {
  id: string
  title: string
  is_checked: boolean
  checked_by_id: string | null
  checked_at: string | null
  is_from_template: boolean
  order: number
}

interface Props {
  engagementId: string
  engagementStatus: string
  onUncheckedCountChange?: (count: number) => void
}

export function QcChecklistTab({ engagementId, engagementStatus: _engagementStatus, onUncheckedCountChange }: Props) {
  const { user } = useAuth()
  const isManager = user?.role === 'firm_owner' || user?.role === 'manager'

  const [items, setItems] = useState<QcItem[]>([])
  const [loading, setLoading] = useState(true)
  const [newTitle, setNewTitle] = useState('')
  const [adding, setAdding] = useState(false)
  const [togglingId, setTogglingId] = useState<string | null>(null)
  const [deletingId, setDeletingId] = useState<string | null>(null)

  const onUncheckedCountChangeRef = useRef(onUncheckedCountChange)
  onUncheckedCountChangeRef.current = onUncheckedCountChange

  const fetchItems = useCallback(async () => {
    setLoading(true)
    try {
      const { data } = await api.get(`/qc-checklists/items/?engagement_id=${engagementId}`)
      const all: QcItem[] = Array.isArray(data)
        ? data.map((i: Record<string, unknown>) => ({
            id: String(i.id),
            title: String(i.title ?? ''),
            is_checked: Boolean(i.is_checked),
            checked_by_id: i.checked_by_id ? String(i.checked_by_id) : null,
            checked_at: i.checked_at ? String(i.checked_at) : null,
            is_from_template: Boolean(i.is_from_template),
            order: Number(i.order ?? 0),
          }))
        : []
      setItems(all)
      onUncheckedCountChangeRef.current?.(all.filter((i) => !i.is_checked).length)
    } catch {
      toast.error('Failed to load QC checklist')
    } finally {
      setLoading(false)
    }
  }, [engagementId])

  useEffect(() => { fetchItems() }, [fetchItems])

  async function handleToggle(item: QcItem) {
    setTogglingId(item.id)
    try {
      const endpoint = item.is_checked
        ? `/qc-checklists/items/${item.id}/uncheck`
        : `/qc-checklists/items/${item.id}/check`
      const { data } = await api.patch(endpoint)
      setItems((prev) => {
        const next = prev.map((i) =>
          i.id === item.id
            ? {
                ...i,
                is_checked: Boolean((data as Record<string, unknown>).is_checked),
                checked_by_id: (data as Record<string, unknown>).checked_by_id
                  ? String((data as Record<string, unknown>).checked_by_id)
                  : null,
                checked_at: (data as Record<string, unknown>).checked_at
                  ? String((data as Record<string, unknown>).checked_at)
                  : null,
              }
            : i
        )
        onUncheckedCountChangeRef.current?.(next.filter((i) => !i.is_checked).length)
        return next
      })
    } catch {
      toast.error('Failed to update item')
    } finally {
      setTogglingId(null)
    }
  }

  async function handleAddItem() {
    const title = newTitle.trim()
    if (!title) return
    setAdding(true)
    try {
      const { data } = await api.post('/qc-checklists/items/', {
        engagement_id: engagementId,
        title,
        is_from_template: false,
        order: items.length,
      })
      const newItem: QcItem = {
        id: String((data as Record<string, unknown>).id),
        title: String((data as Record<string, unknown>).title ?? ''),
        is_checked: false,
        checked_by_id: null,
        checked_at: null,
        is_from_template: false,
        order: Number((data as Record<string, unknown>).order ?? items.length),
      }
      setItems((prev) => {
        const next = [...prev, newItem]
        onUncheckedCountChangeRef.current?.(next.filter((i) => !i.is_checked).length)
        return next
      })
      setNewTitle('')
    } catch {
      toast.error('Failed to add item')
    } finally {
      setAdding(false)
    }
  }

  async function handleDelete(item: QcItem) {
    setDeletingId(item.id)
    try {
      await api.delete(`/qc-checklists/items/${item.id}`)
      setItems((prev) => {
        const next = prev.filter((i) => i.id !== item.id)
        onUncheckedCountChangeRef.current?.(next.filter((i) => !i.is_checked).length)
        return next
      })
    } catch {
      toast.error('Failed to delete item')
    } finally {
      setDeletingId(null)
    }
  }

  function formatCheckedAt(checkedAt: string | null) {
    if (!checkedAt) return ''
    const d = new Date(checkedAt)
    return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })
  }

  const checkedCount = items.filter((i) => i.is_checked).length
  const totalCount = items.length

  if (loading) {
    return (
      <div className="flex flex-col gap-2">
        {[1, 2, 3].map((i) => (
          <div key={i} className="h-10 rounded-[8px] bg-[#D5D8DE] dark:bg-[#333] animate-pulse" />
        ))}
      </div>
    )
  }

  return (
    <div className="flex flex-col gap-4">
      {/* Header */}
      <div className="flex items-center gap-2">
        <span className="text-[13px] font-medium text-brand dark:text-[#EDEEF0]">QC Checklist</span>
        <span className="px-2 py-0.5 rounded-full bg-[#E5E7EB] dark:bg-[#333] text-[11px] font-medium text-[#6B7280]">
          {checkedCount} of {totalCount} complete
        </span>
      </div>

      {/* Item list */}
      {items.length === 0 ? (
        <p className="text-[12px] text-[#6B7280] py-4 text-center">
          No checklist items. Add one below or create a QC template for this engagement type in Templates.
        </p>
      ) : (
        <div className="flex flex-col divide-y divide-surface-border dark:divide-dark-border border border-[0.5px] border-surface-border dark:border-dark-border rounded-[8px] overflow-hidden">
          {items.map((item) => (
            <div
              key={item.id}
              className="flex items-start gap-3 px-4 py-3 bg-surface-card dark:bg-dark-card group hover:bg-[#F9FAFB] dark:hover:bg-[#252525] transition-colors"
            >
              {/* Checkbox */}
              <button
                onClick={() => handleToggle(item)}
                disabled={togglingId === item.id}
                className="mt-0.5 flex-shrink-0 w-4 h-4 rounded border border-[#D1D5DB] dark:border-[#555] flex items-center justify-center transition-colors hover:border-brand disabled:opacity-50"
                style={{ background: item.is_checked ? '#1F3148' : 'transparent' }}
              >
                {togglingId === item.id ? (
                  <Loader2 className="h-2.5 w-2.5 animate-spin text-white" />
                ) : item.is_checked ? (
                  <svg className="h-2.5 w-2.5 text-white" fill="none" viewBox="0 0 12 12" stroke="currentColor" strokeWidth={2.5}>
                    <polyline points="2,6 5,9 10,3" />
                  </svg>
                ) : null}
              </button>

              {/* Content */}
              <div className="flex-1 min-w-0">
                <span
                  className={
                    'text-[13px] ' +
                    (item.is_checked
                      ? 'line-through text-[#9CA3AF]'
                      : 'text-brand dark:text-[#EDEEF0]')
                  }
                >
                  {item.title}
                </span>
                <div className="flex items-center gap-2 mt-0.5 flex-wrap">
                  {item.is_from_template && (
                    <span className="text-[10px] text-[#9CA3AF] px-1.5 py-0.5 rounded bg-[#F3F4F6] dark:bg-[#333]">
                      From template
                    </span>
                  )}
                  {item.is_checked && item.checked_at && (
                    <span className="text-[11px] text-[#9CA3AF]">
                      Checked {formatCheckedAt(item.checked_at)}
                    </span>
                  )}
                </div>
              </div>

              {/* Delete button — manual items only, or manager can delete any */}
              {(!item.is_from_template || isManager) && (
                <button
                  onClick={() => handleDelete(item)}
                  disabled={deletingId === item.id}
                  className="opacity-0 group-hover:opacity-100 flex-shrink-0 p-1 rounded text-[#9CA3AF] hover:text-red-500 hover:bg-[#FEF2F2] dark:hover:bg-red-900/20 transition-all disabled:opacity-50"
                >
                  {deletingId === item.id ? (
                    <Loader2 className="h-3.5 w-3.5 animate-spin" />
                  ) : (
                    <Trash2 className="h-3.5 w-3.5" />
                  )}
                </button>
              )}
            </div>
          ))}
        </div>
      )}

      {/* Add item inline */}
      <div className="flex items-center gap-2">
        <input
          type="text"
          value={newTitle}
          onChange={(e) => setNewTitle(e.target.value)}
          onKeyDown={(e) => { if (e.key === 'Enter') handleAddItem() }}
          placeholder="+ Add item..."
          disabled={adding}
          className="flex-1 h-9 px-3 rounded-md border border-[#D1D5DB] dark:border-[#444] bg-white dark:bg-[#252525] text-[13px] text-[#374151] dark:text-[#EDEEF0] placeholder:text-[#9CA3AF] focus:outline-none focus:border-brand-light disabled:opacity-50"
        />
        <button
          onClick={handleAddItem}
          disabled={adding || !newTitle.trim()}
          className="h-9 px-3 rounded-md bg-brand dark:bg-brand-btn text-white text-[12px] font-medium hover:opacity-90 disabled:opacity-50 transition-opacity flex items-center gap-1"
        >
          {adding && <Loader2 className="h-3 w-3 animate-spin" />}
          Add
        </button>
      </div>
    </div>
  )
}

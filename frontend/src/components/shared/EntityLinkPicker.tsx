// path: frontend/src/components/shared/EntityLinkPicker.tsx
'use client'

import { useState, useEffect, useRef, useCallback } from 'react'
import { Users, Briefcase, CheckSquare, FileText, ArrowLeft, Loader2 } from 'lucide-react'
import api from '@/lib/api'

export interface EntityLink {
  entityType: 'client' | 'engagement' | 'task' | 'document'
  entityId: string
  label: string
  href: string
}

interface EntityLinkPickerProps {
  anchorRef: React.RefObject<HTMLElement>
  onSelect: (link: EntityLink) => void
  onClose: () => void
}

type EntityType = EntityLink['entityType']

interface RecordRow {
  id: string
  label: string
  secondary?: string
}

const TYPE_CONFIG: Record<EntityType, { label: string; icon: React.ReactNode; endpoint: string; href: (id: string) => string }> = {
  client: {
    label: 'Clients',
    icon: <Users size={14} />,
    endpoint: '/clients/?limit=50',
    href: (id) => `/clients/${id}`,
  },
  engagement: {
    label: 'Engagements',
    icon: <Briefcase size={14} />,
    endpoint: '/engagements/?limit=50',
    href: (id) => `/engagements/${id}`,
  },
  task: {
    label: 'Tasks',
    icon: <CheckSquare size={14} />,
    endpoint: '/tasks/?limit=50',
    href: (id) => `/tasks/${id}`,
  },
  document: {
    label: 'Documents',
    icon: <FileText size={14} />,
    endpoint: '/documents/?limit=50',
    href: (id) => `/documents/${id}`,
  },
}

const TYPE_ORDER: EntityType[] = ['client', 'engagement', 'task', 'document']

function mapRecords(type: EntityType, items: Record<string, unknown>[]): RecordRow[] {
  if (type === 'client') {
    return items.map((r) => ({
      id: String(r.id),
      label: String(r.display_name ?? r.name ?? ''),
    }))
  }
  if (type === 'engagement') {
    return items.map((r) => ({
      id: String(r.id),
      label: String(r.name ?? ''),
      secondary: r.client_name ? String(r.client_name) : undefined,
    }))
  }
  if (type === 'task') {
    return items.map((r) => ({
      id: String(r.id),
      label: String(r.title ?? ''),
      secondary: r.client_name ? String(r.client_name) : undefined,
    }))
  }
  if (type === 'document') {
    return items.map((r) => ({
      id: String(r.id),
      label: String(r.name ?? r.file_name ?? ''),
    }))
  }
  return []
}

export function EntityLinkPicker({ anchorRef, onSelect, onClose }: EntityLinkPickerProps) {
  const [selectedType, setSelectedType] = useState<EntityType | null>(null)
  const [search, setSearch] = useState('')
  const [records, setRecords] = useState<RecordRow[]>([])
  const [loading, setLoading] = useState(false)
  const cacheRef = useRef<Partial<Record<EntityType, RecordRow[]>>>({})
  const searchInputRef = useRef<HTMLInputElement>(null)
  const pickerRef = useRef<HTMLDivElement>(null)

  // Position the picker above the anchor
  const [pos, setPos] = useState<{ bottom: number; left: number } | null>(null)

  useEffect(() => {
    if (!anchorRef.current) return
    const rect = anchorRef.current.getBoundingClientRect()
    setPos({
      bottom: window.innerHeight - rect.top + 6,
      left: rect.left,
    })
  }, [anchorRef])

  // Close on Escape or click outside
  useEffect(() => {
    const handleKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose()
    }
    const handleClick = (e: MouseEvent) => {
      if (pickerRef.current && !pickerRef.current.contains(e.target as Node)) onClose()
    }
    document.addEventListener('keydown', handleKey)
    document.addEventListener('mousedown', handleClick)
    return () => {
      document.removeEventListener('keydown', handleKey)
      document.removeEventListener('mousedown', handleClick)
    }
  }, [onClose])

  const loadType = useCallback(async (type: EntityType) => {
    if (cacheRef.current[type]) {
      setRecords(cacheRef.current[type]!)
      return
    }
    setLoading(true)
    try {
      const res = await api.get(TYPE_CONFIG[type].endpoint)
      const items: Record<string, unknown>[] = Array.isArray(res.data)
        ? res.data
        : (res.data?.items ?? [])
      const mapped = mapRecords(type, items)
      cacheRef.current[type] = mapped
      setRecords(mapped)
    } catch {
      setRecords([])
    } finally {
      setLoading(false)
    }
  }, [])

  const handleSelectType = (type: EntityType) => {
    setSelectedType(type)
    setSearch('')
    setRecords([])
    loadType(type)
    setTimeout(() => searchInputRef.current?.focus(), 0)
  }

  const handleBack = () => {
    setSelectedType(null)
    setSearch('')
    setRecords([])
  }

  const handleSelectRecord = (row: RecordRow) => {
    if (!selectedType) return
    onSelect({
      entityType: selectedType,
      entityId: row.id,
      label: row.label,
      href: TYPE_CONFIG[selectedType].href(row.id),
    })
    onClose()
  }

  const filtered = records.filter((r) =>
    r.label.toLowerCase().includes(search.toLowerCase())
  )

  if (!pos) return null

  return (
    <div
      ref={pickerRef}
      style={{
        position: 'fixed',
        bottom: pos.bottom,
        left: pos.left,
        width: 280,
        maxHeight: 320,
        zIndex: 100,
        borderRadius: 8,
        border: '0.5px solid var(--picker-border, #C8CDD6)',
        background: 'var(--picker-bg, #EDEEF0)',
        boxShadow: '0 4px 12px rgba(0,0,0,0.12)',
        display: 'flex',
        flexDirection: 'column',
        overflow: 'hidden',
      }}
      className="dark:[--picker-bg:#383838] dark:[--picker-border:#484848]"
    >
      {selectedType === null ? (
        /* Level 1 — entity type list */
        <div>
          {TYPE_ORDER.map((type) => {
            const cfg = TYPE_CONFIG[type]
            return (
              <button
                key={type}
                onClick={() => handleSelectType(type)}
                style={{ height: 36, padding: '0 14px 0 12px' }}
                className="flex items-center gap-2 w-full text-left hover:bg-[#D5D8DE] dark:hover:bg-[#2D2D2D] transition-colors"
              >
                <span className="text-[#6B7280]" style={{ fontSize: 14 }}>
                  {cfg.icon}
                </span>
                <span className="text-[13px] text-[#1F3148] dark:text-[#EDEEF0]">
                  {cfg.label}
                </span>
              </button>
            )
          })}
        </div>
      ) : (
        /* Level 2 — record list */
        <>
          {/* Header */}
          <div
            style={{
              padding: '10px 14px',
              borderBottom: '0.5px solid var(--picker-border, #C8CDD6)',
              display: 'flex',
              alignItems: 'center',
              gap: 8,
              flexShrink: 0,
            }}
            className="dark:[--picker-border:#484848]"
          >
            <button
              onClick={handleBack}
              className="text-[#6B7280] hover:text-[#1F3148] dark:hover:text-[#EDEEF0] transition-colors"
            >
              <ArrowLeft size={13} />
            </button>
            <span className="text-[12px] font-medium text-[#1F3148] dark:text-[#EDEEF0]">
              {TYPE_CONFIG[selectedType].label}
            </span>
          </div>

          {/* Search */}
          <input
            ref={searchInputRef}
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder={`Search ${TYPE_CONFIG[selectedType].label.toLowerCase()}...`}
            style={{
              width: '100%',
              fontSize: 11,
              padding: '8px 12px',
              borderBottom: '0.5px solid var(--picker-border, #C8CDD6)',
              background: 'transparent',
              outline: 'none',
              color: 'inherit',
              flexShrink: 0,
            }}
            className="dark:[--picker-border:#484848] text-[#1F3148] dark:text-[#EDEEF0] placeholder:text-[#9CA3AF]"
          />

          {/* Records list */}
          <div style={{ overflowY: 'auto', flex: 1 }}>
            {loading ? (
              <div className="flex items-center justify-center py-4">
                <Loader2 size={14} className="animate-spin text-[#6B7280]" />
              </div>
            ) : filtered.length === 0 ? (
              <div className="px-3 py-3 text-[12px] text-[#6B7280]">
                {search ? `No results for "${search}"` : 'No records found'}
              </div>
            ) : (
              filtered.map((row) => (
                <button
                  key={row.id}
                  onClick={() => handleSelectRecord(row)}
                  style={{ minHeight: 36, padding: '0 14px 0 12px' }}
                  className="flex flex-col justify-center w-full text-left hover:bg-[#D5D8DE] dark:hover:bg-[#2D2D2D] transition-colors"
                >
                  <span
                    className="text-[12px] font-medium text-[#1F3148] dark:text-[#EDEEF0] truncate block"
                    style={{ maxWidth: 248 }}
                  >
                    {row.label}
                  </span>
                  {row.secondary && (
                    <span
                      className="text-[11px] text-[#6B7280] dark:text-[#9CA3AF] truncate block"
                      style={{ maxWidth: 248 }}
                    >
                      {row.secondary}
                    </span>
                  )}
                </button>
              ))
            )}
          </div>
        </>
      )}
    </div>
  )
}

// frontend/src/components/dashboard/DashboardCustomizePanel.tsx
'use client'

import { useState, useRef, useEffect } from 'react'
import { X, GripVertical } from 'lucide-react'

export interface DashboardSection {
  key: string
  label: string
  visible: boolean
  order: number
}

interface DashboardCustomizePanelProps {
  isOpen: boolean
  onClose: () => void
  sections: DashboardSection[]
  onSave: (sections: DashboardSection[]) => void
}

export function DashboardCustomizePanel({
  isOpen,
  onClose,
  sections,
  onSave,
}: DashboardCustomizePanelProps) {
  const [local, setLocal] = useState<DashboardSection[]>(() =>
    [...sections].sort((a, b) => a.order - b.order)
  )
  const dragIndex = useRef<number | null>(null)
  const [draggingKey, setDraggingKey] = useState<string | null>(null)

  // Reset local state to the saved sections whenever the panel opens
  useEffect(() => {
    if (isOpen) {
      setLocal([...sections].sort((a, b) => a.order - b.order))
    }
  }, [isOpen, sections])

  function handleToggle(key: string) {
    setLocal((prev) =>
      prev.map((s) => (s.key === key ? { ...s, visible: !s.visible } : s))
    )
  }

  function handleDragStart(index: number) {
    dragIndex.current = index
    setDraggingKey(local[index].key)
  }

  function handleDragOver(e: React.DragEvent, index: number) {
    e.preventDefault()
    const from = dragIndex.current
    if (from === null || from === index) return
    setLocal((prev) => {
      const next = [...prev]
      const [moved] = next.splice(from, 1)
      next.splice(index, 0, moved)
      dragIndex.current = index
      return next.map((s, i) => ({ ...s, order: i }))
    })
  }

  function handleDragEnd() {
    dragIndex.current = null
    setDraggingKey(null)
  }

  function handleSave() {
    onSave(local)
    onClose()
  }

  if (!isOpen) return null

  return (
    <>
      {/* Backdrop */}
      <div
        className="fixed inset-0 z-40 bg-black/35"
        onClick={onClose}
      />

      {/* Panel */}
      <div className="fixed right-0 top-0 z-50 h-full w-[280px] bg-surface-card dark:bg-dark-card border-l border-[0.5px] border-surface-border dark:border-dark-border flex flex-col shadow-xl">
        {/* Header */}
        <div className="flex items-center justify-between px-4 py-3 border-b border-[0.5px] border-surface-border dark:border-dark-border">
          <span className="text-[14px] font-semibold text-brand dark:text-[#EDEEF0]">
            Customize dashboard
          </span>
          <button
            onClick={onClose}
            aria-label="Close customize panel"
            className="text-[#6B7280] hover:text-brand dark:hover:text-[#EDEEF0] transition-colors"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        {/* Section list */}
        <div className="flex-1 overflow-y-auto py-2">
          <p className="px-4 py-2 text-[11px] text-[#6B7280] uppercase tracking-wide font-medium">
            Show and reorder sections
          </p>
          {local.map((section, index) => (
            <div
              key={section.key}
              draggable
              onDragStart={() => handleDragStart(index)}
              onDragOver={(e) => handleDragOver(e, index)}
              onDragEnd={handleDragEnd}
              className={`flex items-center gap-2 px-4 py-2.5 hover:bg-surface-input dark:hover:bg-dark-page cursor-grab active:cursor-grabbing select-none transition-all duration-150 ease-in-out ${
                section.key === draggingKey ? 'opacity-20' : ''
              }`}
            >
              <GripVertical className="h-4 w-4 text-[#9CA3AF] flex-shrink-0" />
              <span className="flex-1 text-[13px] text-brand dark:text-[#EDEEF0]">
                {section.label}
              </span>
              {/* Toggle switch */}
              <button
                role="switch"
                aria-checked={section.visible}
                aria-label={`Toggle ${section.label}`}
                onClick={() => handleToggle(section.key)}
                className={`relative w-9 h-5 rounded-full transition-colors flex-shrink-0 overflow-hidden focus:outline-none ${
                  section.visible
                    ? 'bg-brand dark:bg-brand-btn'
                    : 'bg-[#D5D8DE] dark:bg-[#444444]'
                }`}
              >
                <span
                  className={`absolute top-[3px] left-[3px] w-3.5 h-3.5 rounded-full bg-white shadow transition-transform ${
                    section.visible ? 'translate-x-[16px]' : 'translate-x-0'
                  }`}
                />
              </button>
            </div>
          ))}
        </div>

        {/* Footer */}
        <div className="px-4 py-3 border-t border-[0.5px] border-surface-border dark:border-dark-border">
          <button
            onClick={handleSave}
            className="w-full h-9 rounded-[6px] bg-brand dark:bg-brand-btn text-white text-[13px] font-medium hover:opacity-90 transition-opacity"
          >
            Save
          </button>
        </div>
      </div>
    </>
  )
}

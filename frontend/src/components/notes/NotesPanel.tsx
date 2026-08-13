// frontend/src/components/notes/NotesPanel.tsx
'use client'

import { useState, useRef, useEffect } from 'react'
import { useQuery } from '@tanstack/react-query'
import { useNotes, Note } from './useNotes'
import api from '@/lib/api'

interface StaffMember {
  id: string
  name: string
  initials: string
}

interface NotesPanelProps {
  isOpen: boolean
  onClose: () => void
  entityType: 'client' | 'engagement' | 'task' | 'document'
  entityId: string
  contextLabel: string
}

function formatTimestamp(isoString: string): string {
  const date = new Date(isoString)
  return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' }) +
    ' · ' +
    date.toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit' })
}

function getMentionQuery(value: string, cursor: number): string | null {
  const before = value.slice(0, cursor)
  const lastAt = before.lastIndexOf('@')
  if (lastAt === -1) return null
  const afterAt = before.slice(lastAt + 1)
  if (/\n/.test(afterAt) || /\s{2}/.test(afterAt)) return null
  return afterAt
}

function renderNoteBody(body: string): React.ReactNode {
  if (!body) return <>{body}</>
  const parts: React.ReactNode[] = []
  const regex = /@(\S+(?:\s\S+)?)/g
  let last = 0
  let match
  let found = false
  while ((match = regex.exec(body)) !== null) {
    found = true
    if (match.index > last) parts.push(<span key={last}>{body.slice(last, match.index)}</span>)
    parts.push(
      <span key={match.index} className="font-semibold text-brand dark:text-foreground">
        {match[1]}
      </span>
    )
    last = match.index + match[0].length
  }
  if (last < body.length) parts.push(<span key={last}>{body.slice(last)}</span>)
  return found ? <>{parts}</> : <>{body}</>
}

function NoteCard({
  note,
  onDelete,
  canDelete,
}: {
  note: Note
  onDelete: (id: string) => void
  canDelete: boolean
}) {
  const [hovered, setHovered] = useState(false)

  const cardBg = note.isPrivate
    ? 'bg-status-amber dark:bg-[#2D2A1E]'
    : 'bg-surface-page dark:bg-dark-page'

  return (
    <div
      className={`${cardBg} rounded-[6px] p-[10px_12px] mb-2 relative`}
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
    >
      <div className="flex items-center justify-between mb-1">
        <div className="flex items-center gap-1.5">
          {note.isPrivate && (
            <svg width="12" height="12" viewBox="0 0 16 16" fill="none" aria-hidden="true">
              <path
                d="M11 7V5a3 3 0 0 0-6 0v2H4a1 1 0 0 0-1 1v6a1 1 0 0 0 1 1h8a1 1 0 0 0 1-1V8a1 1 0 0 0-1-1h-1Zm-4 0V5a1 1 0 1 1 2 0v2H7Z"
                fill="#6B7280"
              />
            </svg>
          )}
          <span className="text-[12px] font-medium text-brand dark:text-foreground">
            {note.authorName}
          </span>
        </div>
        <div className="flex items-center gap-1.5">
          <span className="text-[11px] text-muted-foreground">{formatTimestamp(note.createdAt)}</span>
          {canDelete && hovered && (
            <button
              onClick={() => onDelete(note.id)}
              aria-label="Delete note"
              className="text-muted-foreground hover:text-[#E24B4A] transition-colors"
            >
              <svg width="14" height="14" viewBox="0 0 16 16" fill="none" aria-hidden="true">
                <path
                  d="M6.5 1.75a.25.25 0 0 1 .25-.25h2.5a.25.25 0 0 1 .25.25V3h-3V1.75Zm4.5 1.25V1.75C11 .784 10.216 0 9.25 0h-2.5C5.784 0 5 .784 5 1.75V3H2.5a.75.75 0 0 0 0 1.5h.384l.698 8.382A1.75 1.75 0 0 0 5.325 14.5h5.35a1.75 1.75 0 0 0 1.743-1.618l.698-8.382h.384a.75.75 0 0 0 0-1.5H11ZM4.388 4.5h7.224l-.687 8.246a.25.25 0 0 1-.249.254h-5.35a.25.25 0 0 1-.249-.254L4.388 4.5Zm3.362 1.25a.75.75 0 0 0-.75.75v5.5a.75.75 0 0 0 1.5 0V6.5a.75.75 0 0 0-.75-.75Zm2.25.75a.75.75 0 0 0-1.5 0v5.5a.75.75 0 0 0 1.5 0V6.5Z"
                  fill="currentColor"
                />
              </svg>
            </button>
          )}
        </div>
      </div>
      <p className="text-[13px] text-foreground dark:text-muted-foreground leading-[1.6]">
        {renderNoteBody(note.body)}
      </p>
    </div>
  )
}

export function NotesPanel({
  isOpen,
  onClose,
  entityType,
  entityId,
  contextLabel,
}: NotesPanelProps) {
  const { notes, isLoading, addNote, deleteNote, markAsRead } = useNotes({ entityType, entityId })
  const [body, setBody] = useState('')
  const [isPrivate, setIsPrivate] = useState(false)
  const textareaRef = useRef<HTMLTextAreaElement>(null)

  const [showMentionPopover, setShowMentionPopover] = useState(false)
  const [mentionQuery, setMentionQuery] = useState('')
  const [mentionIndex, setMentionIndex] = useState(0)
  const { data: staffData } = useQuery({
    queryKey: ['users-list'],
    queryFn: () => api.get('/users/').then((res) => res.data),
    staleTime: 5 * 60 * 1000,
  })
  const staffList: StaffMember[] = (() => {
    const items = Array.isArray(staffData) ? staffData : (staffData?.items ?? [])
    return items.map((u: Record<string, unknown>) => ({
      id: String(u.id),
      name: String(u.full_name ?? u.name ?? ''),
      initials: String(u.full_name ?? u.name ?? '')
        .split(' ')
        .map((p: string) => p[0] ?? '')
        .join('')
        .slice(0, 2)
        .toUpperCase(),
    }))
  })()

  const filteredStaff = staffList.filter((s) =>
    s.name.toLowerCase().includes(mentionQuery.trim().toLowerCase())
  )

  // Mark as read when panel opens
  useEffect(() => {
    if (isOpen) {
      markAsRead()
      setTimeout(() => textareaRef.current?.focus(), 250)
    }
  }, [isOpen, markAsRead])

  // Staff role — for delete permissions, treat all notes as deletable by current user
  // (full role check requires auth context; placeholder uses authorName === 'You')
  const canDeleteNote = (note: Note) =>
    note.authorName === 'You'

  function handleSubmit() {
    if (!body.trim()) return
    addNote(body.trim(), isPrivate)
    setBody('')
    setIsPrivate(false)
    setShowMentionPopover(false)
  }

  function handleKeyDown(e: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (showMentionPopover && filteredStaff.length > 0) {
      if (e.key === 'ArrowDown') {
        e.preventDefault()
        setMentionIndex((prev) => (prev + 1) % filteredStaff.length)
        return
      }
      if (e.key === 'ArrowUp') {
        e.preventDefault()
        setMentionIndex((prev) => (prev - 1 + filteredStaff.length) % filteredStaff.length)
        return
      }
      if (e.key === 'Enter') {
        e.preventDefault()
        handleMentionSelect(filteredStaff[mentionIndex])
        return
      }
      if (e.key === 'Escape') {
        setShowMentionPopover(false)
        return
      }
    }
    if ((e.metaKey || e.ctrlKey) && e.key === 'Enter') {
      handleSubmit()
    }
  }

  function handleBodyChange(e: React.ChangeEvent<HTMLTextAreaElement>) {
    const value = e.target.value
    setBody(value)
    const cursor = e.currentTarget.selectionStart
    const query = getMentionQuery(value, cursor)
    if (query !== null) {
      setMentionQuery(query)
      setShowMentionPopover(true)
      setMentionIndex(0)
    } else {
      setShowMentionPopover(false)
    }
  }

  function handleMentionSelect(staff: StaffMember) {
    const cursor = textareaRef.current?.selectionStart ?? body.length
    const beforeCursor = body.slice(0, cursor)
    const lastAt = beforeCursor.lastIndexOf('@')
    if (lastAt !== -1) {
      const before = body.slice(0, lastAt)
      const after = body.slice(cursor)
      setBody(`${before}@${staff.name} ${after}`)
    }
    setShowMentionPopover(false)
    setTimeout(() => textareaRef.current?.focus(), 0)
  }

  return (
    <>
      {/* Overlay */}
      {isOpen && (
        <div
          onClick={onClose}
          style={{
            position: 'fixed',
            inset: 0,
            background: 'rgba(0,0,0,0.20)',
            zIndex: 39,
          }}
        />
      )}

      {/* Panel */}
      <div
        style={{
          position: 'fixed',
          right: 0,
          top: 0,
          width: 360,
          height: '100vh',
          zIndex: 40,
          transform: isOpen ? 'translateX(0)' : 'translateX(100%)',
          transition: 'transform 200ms ease-out',
          display: 'flex',
          flexDirection: 'column',
        }}
        className="bg-surface-card dark:bg-dark-card border-l border-[0.5px] border-surface-border dark:border-dark-border shadow-xl"
      >
        {/* Header */}
        <div
          className="flex items-center justify-between px-4 border-b border-[0.5px] border-surface-border dark:border-dark-border"
          style={{ height: 48, flexShrink: 0 }}
        >
          <div className="flex items-center gap-2">
            <svg width="14" height="14" viewBox="0 0 16 16" fill="none" aria-hidden="true">
              <path
                d="M11.013 1.427a1.75 1.75 0 0 1 2.474 2.474L4.92 12.467l-3.468.462.462-3.468L11.013 1.427Zm1.06 1.414-.707-.707-9.2 9.2-.23 1.73 1.73-.23 8.407-8.993Z"
                fill="currentColor"
                className="text-brand dark:text-foreground"
              />
            </svg>
            <span className="text-[13px] font-medium text-brand dark:text-foreground">
              Notes — {contextLabel}
            </span>
          </div>
          <button
            onClick={onClose}
            aria-label="Close notes panel"
            className="text-muted-foreground hover:text-brand dark:hover:text-foreground transition-colors"
          >
            <svg width="14" height="14" viewBox="0 0 16 16" fill="none" aria-hidden="true">
              <path
                d="M3.72 3.72a.75.75 0 0 1 1.06 0L8 6.94l3.22-3.22a.75.75 0 1 1 1.06 1.06L9.06 8l3.22 3.22a.75.75 0 1 1-1.06 1.06L8 9.06l-3.22 3.22a.75.75 0 0 1-1.06-1.06L6.94 8 3.72 4.78a.75.75 0 0 1 0-1.06Z"
                fill="currentColor"
              />
            </svg>
          </button>
        </div>

        {/* Notes list */}
        <div className="flex-1 overflow-y-auto p-4">
          {isLoading ? (
            <div className="space-y-3">
              {[1, 2, 3].map((i) => (
                <div
                  key={i}
                  className="rounded-[6px] p-[10px_12px] bg-surface-page dark:bg-dark-page mb-2"
                >
                  <div className="flex items-center justify-between mb-1.5">
                    <div className="h-3 w-24 bg-surface-border dark:bg-dark-border animate-pulse rounded" />
                    <div className="h-2.5 w-20 bg-surface-border dark:bg-dark-border animate-pulse rounded" />
                  </div>
                  <div className="h-2.5 w-full bg-surface-border dark:bg-dark-border animate-pulse rounded mb-1" />
                  <div className="h-2.5 w-3/4 bg-surface-border dark:bg-dark-border animate-pulse rounded" />
                </div>
              ))}
            </div>
          ) : notes.length === 0 ? (
            <div className="flex flex-col items-center justify-center h-full gap-[10px]">
              <div
                className="flex items-center justify-center rounded-lg bg-surface-card dark:bg-dark-card border border-[0.5px] border-surface-border dark:border-dark-border"
                style={{ width: 40, height: 40 }}
              >
                <svg width="18" height="18" viewBox="0 0 16 16" fill="none" aria-hidden="true">
                  <path
                    d="M11.013 1.427a1.75 1.75 0 0 1 2.474 2.474L4.92 12.467l-3.468.462.462-3.468L11.013 1.427Z"
                    fill="#6B7280"
                  />
                </svg>
              </div>
              <p className="text-[13px] font-medium text-brand dark:text-foreground">
                No notes yet
              </p>
              <p className="text-[12px] text-muted-foreground">Add the first note below.</p>
            </div>
          ) : (
            notes.map((note) => (
              <NoteCard
                key={note.id}
                note={note}
                onDelete={deleteNote}
                canDelete={canDeleteNote(note)}
              />
            ))
          )}
        </div>

        {/* Compose box */}
        <div
          className="p-4 border-t border-[0.5px] border-surface-border dark:border-dark-border"
          style={{ flexShrink: 0 }}
        >
          <div className="relative">
            {/* @mention popover */}
            {showMentionPopover && filteredStaff.length > 0 && (
              <div
                className="absolute bottom-full left-0 right-0 mb-1 bg-surface-card dark:bg-dark-card border border-surface-border dark:border-dark-border rounded-lg overflow-y-auto shadow-md z-10"
                style={{ maxHeight: '200px' }}
              >
                {filteredStaff.map((staff, idx) => (
                  <button
                    key={staff.id}
                    onMouseDown={(e) => {
                      e.preventDefault()
                      handleMentionSelect(staff)
                    }}
                    onMouseEnter={() => setMentionIndex(idx)}
                    className={`flex items-center gap-2 w-full px-3 py-2 text-[13px] text-foreground dark:text-muted-foreground transition-colors text-left ${
                      idx === mentionIndex
                        ? 'bg-surface-border dark:bg-dark-border'
                        : 'hover:bg-surface-border dark:hover:bg-dark-border'
                    }`}
                  >
                    <div
                      className="w-5 h-5 rounded-full flex items-center justify-center flex-shrink-0"
                      style={{ backgroundColor: '#4A7FA5' }}
                    >
                      <span className="text-white text-[10px] font-medium">{staff.initials}</span>
                    </div>
                    {staff.name}
                  </button>
                ))}
              </div>
            )}

            <textarea
              ref={textareaRef}
              value={body}
              onChange={handleBodyChange}
              onKeyDown={handleKeyDown}
              placeholder="Add a note..."
              className="w-full rounded-[6px] border border-[0.5px] border-surface-border focus:border-brand-light focus:outline-none bg-surface-input dark:bg-dark-page text-[13px] text-foreground dark:text-muted-foreground placeholder:text-muted-foreground p-2.5 resize-none transition-colors"
              style={{ minHeight: 72 }}
            />
          </div>

          <div className="flex items-center justify-between mt-2.5">
            <label className="flex items-center gap-1.5 cursor-pointer">
              <input
                type="checkbox"
                checked={isPrivate}
                onChange={(e) => setIsPrivate(e.target.checked)}
                className="rounded border-surface-border"
              />
              <span className="text-[11px] text-muted-foreground">Private note</span>
            </label>
            <button
              onClick={handleSubmit}
              disabled={!body.trim()}
              className="h-8 px-3 rounded-[6px] bg-brand dark:bg-brand-btn text-white text-[12px] font-medium transition-opacity disabled:opacity-50 disabled:cursor-not-allowed"
            >
              Add Note
            </button>
          </div>
        </div>
      </div>
    </>
  )
}

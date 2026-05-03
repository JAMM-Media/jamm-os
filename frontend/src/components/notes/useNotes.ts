// frontend/src/components/notes/useNotes.ts
'use client'

import { useState, useEffect, useCallback } from 'react'
import api from '@/lib/api'

export interface Note {
  id: string
  body: string
  isPrivate: boolean
  authorName: string
  authorRole: string
  createdAt: string
  isRead: boolean
}

interface UseNotesOptions {
  entityType: 'client' | 'engagement' | 'task' | 'document'
  entityId: string
}

interface UseNotesReturn {
  notes: Note[]
  unreadCount: number
  isLoading: boolean
  addNote: (body: string, isPrivate: boolean) => void
  deleteNote: (noteId: string) => void
  markAsRead: () => void
}

export function useNotes({ entityType, entityId }: UseNotesOptions): UseNotesReturn {
  const [notes, setNotes] = useState<Note[]>([])
  const [isLoading, setIsLoading] = useState(false)

  useEffect(() => {
    if (!entityId) return
    setIsLoading(true)
    api
      .get<Note[]>('/notes', { params: { entity_type: entityType, entity_id: entityId } })
      .then((res) => setNotes(res.data))
      .catch(() => setNotes([]))
      .finally(() => setIsLoading(false))
  }, [entityType, entityId])

  const unreadCount = notes.filter((n) => !n.isRead).length

  const addNote = useCallback(
    (body: string, isPrivate: boolean) => {
      const optimistic: Note = {
        id: `temp-${Date.now()}`,
        body,
        isPrivate,
        authorName: 'You',
        authorRole: 'staff',
        createdAt: new Date().toISOString(),
        isRead: true,
      }
      setNotes((prev) => [optimistic, ...prev])

      api
        .post<Note>('/notes', { body, entity_type: entityType, entity_id: entityId, is_private: isPrivate })
        .then((res) => {
          setNotes((prev) => prev.map((n) => (n.id === optimistic.id ? res.data : n)))
        })
        .catch(() => {
          setNotes((prev) => prev.filter((n) => n.id !== optimistic.id))
        })
    },
    [entityType, entityId],
  )

  const deleteNote = useCallback((noteId: string) => {
    setNotes((prev) => prev.filter((n) => n.id !== noteId))
    api.delete(`/notes/${noteId}`).catch(() => {})
  }, [])

  const markAsRead = useCallback(() => {
    setNotes((prev) => prev.map((n) => ({ ...n, isRead: true })))
    api
      .post('/notes/mark-read', { entity_type: entityType, entity_id: entityId })
      .catch(() => {})
  }, [entityType, entityId])

  return { notes, unreadCount, isLoading, addNote, deleteNote, markAsRead }
}

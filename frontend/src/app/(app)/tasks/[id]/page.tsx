// path: frontend/src/app/tasks/[id]/page.tsx
'use client'

import { useState, useEffect, useCallback } from 'react'
import { useParams } from 'next/navigation'
import { Breadcrumb } from '@/components/layout/Breadcrumb'
import { StatusBadge } from '@/components/ui/StatusBadge'
import { tasksApi, documentsApi } from '@/lib/api'
import type { TaskFileLink } from '@/lib/api'
import type { Document } from '@/lib/api'
import { useFetch } from '@/lib/hooks/useFetch'
import { NotesTab, NotesPanel, useNotes } from '@/components/notes'
import { EditTaskModal } from '@/components/tasks/EditTaskModal'
import { useAuth } from '@/lib/hooks/useAuth'

type BadgeVariant = Parameters<typeof StatusBadge>[0]['variant']

function TaskDetailBodySkeleton() {
  return (
    <div className="p-6 pt-0 flex flex-col gap-4">
      <div className="grid grid-cols-1 xl:grid-cols-4 gap-4">
        {Array.from({ length: 4 }).map((_, i) => (
          <div key={i} className="bg-surface-card dark:bg-dark-card rounded-card p-4">
            <div className="h-2.5 w-16 bg-[#D5D8DE] dark:bg-[#444444] animate-pulse rounded mb-2" />
            <div className="h-4 bg-[#D5D8DE] dark:bg-[#444444] animate-pulse rounded" style={{ width: `${50 + (i % 2) * 20}%` }} />
          </div>
        ))}
      </div>
    </div>
  )
}

export default function TaskDetailPage() {
  const params = useParams()
  const id = params.id as string
  const { data: task, isLoading, refetch } = useFetch(() => tasksApi.get(id), [id])
  const { user } = useAuth()
  const [notesOpen, setNotesOpen] = useState(false)
  const [isEditOpen, setIsEditOpen] = useState(false)
  const { unreadCount } = useNotes({ entityType: 'task', entityId: id })

  // Linked files state
  const [linkedFiles, setLinkedFiles] = useState<TaskFileLink[]>([])
  const [linkedFilesLoading, setLinkedFilesLoading] = useState(false)
  const [isPickerOpen, setIsPickerOpen] = useState(false)
  const [pickerDocs, setPickerDocs] = useState<Document[]>([])
  const [pickerLoading, setPickerLoading] = useState(false)
  const [linkingDocId, setLinkingDocId] = useState<string | null>(null)
  const [unlinkingId, setUnlinkingId] = useState<string | null>(null)

  const fetchLinkedFiles = useCallback(async () => {
    if (!task || task.taskType !== 'client') return
    setLinkedFilesLoading(true)
    try {
      const result = await tasksApi.listFiles(id)
      setLinkedFiles(result.items)
    } finally {
      setLinkedFilesLoading(false)
    }
  }, [id, task?.taskType])

  useEffect(() => {
    fetchLinkedFiles()
  }, [fetchLinkedFiles])

  const openPicker = async () => {
    if (!task) return
    setIsPickerOpen(true)
    setPickerLoading(true)
    try {
      const result = await documentsApi.list(0, 200, undefined, task.engagementId)
      setPickerDocs(result.items)
    } finally {
      setPickerLoading(false)
    }
  }

  const handleLinkFile = async (documentId: string) => {
    setLinkingDocId(documentId)
    try {
      await tasksApi.linkFile(id, documentId)
      await fetchLinkedFiles()
    } finally {
      setLinkingDocId(null)
    }
  }

  const handleUnlink = async (documentId: string) => {
    setUnlinkingId(documentId)
    try {
      await tasksApi.unlinkFile(id, documentId)
      setLinkedFiles((prev) => prev.filter((f) => f.id !== documentId))
    } finally {
      setUnlinkingId(null)
    }
  }

  useEffect(() => {
    if (!task || !user) return
    if (
      task.status === 'todo' &&
      task.assignedTo === user.id
    ) {
      tasksApi.update(task.id, { status: 'in_progress' }).then(() => refetch())
    }
  }, [task?.id, task?.status, user?.id])

  // Poll so managers/owners see the in_progress transition without manual reload
  useEffect(() => {
    if (!task || task.status === 'completed' || task.status === 'done') return
    const interval = setInterval(() => {
      refetch()
    }, 10000)
    return () => clearInterval(interval)
  }, [task?.status, refetch])

  if (isLoading) {
    return (
      <>
        <div className="p-6">
          <div className="h-4 w-32 bg-[#D5D8DE] dark:bg-[#444444] animate-pulse rounded mb-4" />
          <div className="h-8 w-64 bg-[#D5D8DE] dark:bg-[#444444] animate-pulse rounded mb-2" />
          <div className="h-4 w-48 bg-[#D5D8DE] dark:bg-[#444444] animate-pulse rounded" />
        </div>
        <TaskDetailBodySkeleton />
      </>
    )
  }

  if (!task) {
    return (
        <div className="flex items-center justify-center h-full p-6">
          <p className="text-[13px] text-[#6B7280]">Task not found.</p>
        </div>
    )
  }

  return (<>
      <div className="p-6">
        <Breadcrumb
          items={[
            { label: 'Tasks', href: '/tasks' },
            { label: task.title },
          ]}
        />
        <div className="flex items-start justify-between mb-6">
          <div>
            <h1 className="text-2xl font-medium text-brand dark:text-[#EDEEF0] mb-1">
              {task.title}
            </h1>
            <div className="flex items-center gap-2">
              <StatusBadge variant={task.status as BadgeVariant} />
              <span className="text-[12px] text-[#6B7280]">
                {task.dueDate ? `Due ${task.dueDate}` : 'No due date'}
              </span>
            </div>
          </div>
          <button onClick={() => setIsEditOpen(true)} className="h-9 px-3 rounded-[6px] bg-brand dark:bg-brand-btn text-white text-[13px] font-medium hover:opacity-90 transition-opacity">
            Edit Task
          </button>
        </div>

        <div className="grid grid-cols-1 xl:grid-cols-4 gap-4 mb-4">
          <div className="bg-surface-card dark:bg-dark-card rounded-card p-4">
            <p className="text-[11px] font-medium text-[#6B7280] uppercase tracking-[0.05em] mb-2">Status</p>
            <StatusBadge variant={task.status as BadgeVariant} />
          </div>
          <div className="bg-surface-card dark:bg-dark-card rounded-card p-4">
            <p className="text-[11px] font-medium text-[#6B7280] uppercase tracking-[0.05em] mb-2">Due Date</p>
            <p className="text-[13px] text-brand dark:text-[#EDEEF0]">{task.dueDate ?? '—'}</p>
          </div>
          <div className="bg-surface-card dark:bg-dark-card rounded-card p-4">
            <p className="text-[11px] font-medium text-[#6B7280] uppercase tracking-[0.05em] mb-2">Assigned To</p>
            <p className="text-[13px] text-brand dark:text-[#EDEEF0]">{task.assignedToName ?? task.assignedTo ?? '—'}</p>
          </div>
          <div className="bg-surface-card dark:bg-dark-card rounded-card p-4">
            <p className="text-[11px] font-medium text-[#6B7280] uppercase tracking-[0.05em] mb-2">Completed</p>
            <p className="text-[13px] text-brand dark:text-[#EDEEF0]">{task.status === 'done' || task.isCompleted ? 'Yes' : 'No'}</p>
          </div>
        </div>

        {task.notes && (
          <div className="bg-surface-card dark:bg-dark-card rounded-card p-4 mb-4">
            <p className="text-[11px] font-medium text-[#6B7280] uppercase tracking-[0.05em] mb-2">Notes</p>
            <p className="text-[13px] text-[#374151] dark:text-[#9CA3AF]">{task.notes}</p>
          </div>
        )}

        {/* Linked Files -- CLIENT tasks only */}
        {task.taskType === 'client' && (
          <div className="bg-surface-card dark:bg-dark-card rounded-card p-4">
            <div className="flex items-center justify-between mb-3">
              <p className="text-[11px] font-medium text-[#6B7280] uppercase tracking-[0.05em]">Linked Files</p>
              <button
                onClick={openPicker}
                className="text-[12px] text-brand-light dark:text-brand-light hover:underline"
              >
                Link a file
              </button>
            </div>
            {linkedFilesLoading ? (
              <p className="text-[12px] text-[#9CA3AF]">Loading...</p>
            ) : linkedFiles.length === 0 ? (
              <p className="text-[12px] text-[#9CA3AF]">No files linked to this task.</p>
            ) : (
              <ul className="flex flex-col gap-2">
                {linkedFiles.map((f) => (
                  <li key={f.linkId} className="flex items-center justify-between gap-2">
                    <div className="flex items-center gap-2 min-w-0">
                      <span className="text-[13px] text-brand dark:text-[#EDEEF0] truncate">{f.filename}</span>
                      {f.deletedAt && (
                        <span className="flex-shrink-0 text-[11px] text-[#9CA3AF] bg-[#F3F4F6] dark:bg-[#333333] border border-[0.5px] border-[#C8CDD6] dark:border-[#484848] px-1.5 py-0.5 rounded">
                          In trash
                        </span>
                      )}
                    </div>
                    <button
                      disabled={unlinkingId === f.id}
                      onClick={() => handleUnlink(f.id)}
                      className="flex-shrink-0 text-[12px] text-[#9CA3AF] hover:text-status-red-text transition-colors disabled:opacity-50"
                    >
                      {unlinkingId === f.id ? 'Removing...' : 'Remove'}
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </div>
        )}
      </div>

      <NotesTab unreadCount={unreadCount} onClick={() => setNotesOpen(true)} />
      <NotesPanel
        isOpen={notesOpen}
        onClose={() => setNotesOpen(false)}
        entityType="task"
        entityId={id}
        contextLabel={task.title}
      />
      {isEditOpen && (
        <EditTaskModal
          isOpen={isEditOpen}
          onClose={() => setIsEditOpen(false)}
          task={{
            ...task,
            dueDate: task.dueDate ?? undefined,
            notes: task.notes ?? undefined,
          }}
          onSuccess={() => { refetch(); setIsEditOpen(false) }}
        />
      )}

      {/* File picker modal -- reuses the fixed-overlay modal pattern from engagements/[id]/page.tsx */}
      {isPickerOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
          <div className="bg-[#EDEEF0] dark:bg-dark-card rounded-[10px] border border-[0.5px] border-[#C8CDD6] dark:border-[#484848] p-6 w-full max-w-sm shadow-lg">
            <p className="text-[13px] font-medium text-brand dark:text-[#EDEEF0] mb-4">
              Link a file from this engagement
            </p>
            {pickerLoading ? (
              <p className="text-[12px] text-[#9CA3AF] mb-4">Loading files...</p>
            ) : pickerDocs.length === 0 ? (
              <p className="text-[12px] text-[#9CA3AF] mb-4">No files available in this engagement.</p>
            ) : (
              <ul className="max-h-60 overflow-y-auto flex flex-col gap-0.5 mb-4 rounded-[6px] border border-[0.5px] border-[#C8CDD6] dark:border-[#484848] bg-white dark:bg-[#252525]">
                {pickerDocs.map((doc) => {
                  const alreadyLinked = linkedFiles.some((f) => f.id === doc.id)
                  const isLinking = linkingDocId === doc.id
                  return (
                    <li key={doc.id}>
                      <button
                        disabled={alreadyLinked || isLinking}
                        onClick={() => handleLinkFile(doc.id)}
                        className="w-full text-left px-3 py-2 text-[13px] text-[#1F3148] dark:text-[#EDEEF0] hover:bg-[#F3F4F6] dark:hover:bg-[#333333] disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                      >
                        {isLinking ? 'Linking...' : doc.name}
                        {alreadyLinked && (
                          <span className="text-[#9CA3AF] text-[11px] ml-2">already linked</span>
                        )}
                      </button>
                    </li>
                  )
                })}
              </ul>
            )}
            <div className="flex justify-end">
              <button
                onClick={() => setIsPickerOpen(false)}
                className="h-9 px-3 rounded-[6px] border border-[0.5px] border-[#1F3148] dark:border-[#4A7FA5] text-[#1F3148] dark:text-[#EDEEF0] bg-transparent text-[13px] font-medium hover:bg-surface-page dark:hover:bg-dark-page transition-colors"
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}
  </>)
}

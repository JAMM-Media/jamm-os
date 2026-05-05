// path: frontend/src/app/tasks/[id]/page.tsx
'use client'

import { useState } from 'react'
import { useParams } from 'next/navigation'
import { AppShell } from '@/components/layout/AppShell'
import { Breadcrumb } from '@/components/layout/Breadcrumb'
import { StatusBadge } from '@/components/ui/StatusBadge'
import { tasksApi } from '@/lib/api'
import { useFetch } from '@/lib/hooks/useFetch'
import { NotesTab, NotesPanel, useNotes } from '@/components/notes'
import { EditTaskModal } from '@/components/tasks/EditTaskModal'

type BadgeVariant = Parameters<typeof StatusBadge>[0]['variant']

export default function TaskDetailPage() {
  const params = useParams()
  const id = params.id as string
  const { data: task, isLoading, refetch } = useFetch(() => tasksApi.get(id), [id])
  const [notesOpen, setNotesOpen] = useState(false)
  const [isEditOpen, setIsEditOpen] = useState(false)
  const { unreadCount } = useNotes({ entityType: 'task', entityId: id })

  if (isLoading) {
    return (
      <AppShell>
        <div className="p-6">
          <div className="h-4 w-32 bg-[#D5D8DE] dark:bg-[#444444] animate-pulse rounded mb-4" />
          <div className="h-8 w-64 bg-[#D5D8DE] dark:bg-[#444444] animate-pulse rounded mb-2" />
          <div className="h-4 w-48 bg-[#D5D8DE] dark:bg-[#444444] animate-pulse rounded" />
        </div>
      </AppShell>
    )
  }

  if (!task) {
    return (
      <AppShell>
        <div className="flex items-center justify-center h-full p-6">
          <p className="text-[13px] text-[#6B7280]">Task not found.</p>
        </div>
      </AppShell>
    )
  }

  return (
    <AppShell>
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

        <div className="grid grid-cols-1 xl:grid-cols-3 gap-4 mb-4">
          <div className="bg-surface-card dark:bg-dark-card rounded-card p-4">
            <p className="text-[11px] font-medium text-[#6B7280] uppercase tracking-[0.05em] mb-2">Status</p>
            <StatusBadge variant={task.status as BadgeVariant} />
          </div>
          <div className="bg-surface-card dark:bg-dark-card rounded-card p-4">
            <p className="text-[11px] font-medium text-[#6B7280] uppercase tracking-[0.05em] mb-2">Due Date</p>
            <p className="text-[13px] text-brand dark:text-[#EDEEF0]">{task.dueDate ?? '—'}</p>
          </div>
          <div className="bg-surface-card dark:bg-dark-card rounded-card p-4">
            <p className="text-[11px] font-medium text-[#6B7280] uppercase tracking-[0.05em] mb-2">Completed</p>
            <p className="text-[13px] text-brand dark:text-[#EDEEF0]">{task.status === 'done' || task.isCompleted ? 'Yes' : 'No'}</p>
          </div>
        </div>

        {task.notes && (
          <div className="bg-surface-card dark:bg-dark-card rounded-card p-4">
            <p className="text-[11px] font-medium text-[#6B7280] uppercase tracking-[0.05em] mb-2">Notes</p>
            <p className="text-[13px] text-[#374151] dark:text-[#9CA3AF]">{task.notes}</p>
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
    </AppShell>
  )
}

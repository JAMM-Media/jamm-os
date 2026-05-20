// path: frontend/src/app/tasks/page.tsx
'use client'

import { useState, useRef } from 'react'
import { toast } from 'sonner'
import { AppShell } from '@/components/layout/AppShell'
import { ViewToggle } from '@/components/ui/ViewToggle'
import { TaskTable } from '@/components/tasks/TaskTable'
import { TaskCard } from '@/components/tasks/TaskCard'
import { TaskEmptyState } from '@/components/tasks/TaskEmptyState'
import { NewTaskModal } from '@/components/tasks/NewTaskModal'
import { tasksApi, clientsApi, engagementsApi, type Task } from '@/lib/api'
import { useFetch } from '@/lib/hooks/useFetch'
import { useAuth } from '@/lib/hooks/useAuth'
import { Search, X, ChevronDown } from 'lucide-react'
import api from '@/lib/api'

type ViewMode = 'table' | 'card'

const TASK_STATUSES = [
  { value: 'todo', label: 'To Do' },
  { value: 'in_progress', label: 'In Progress' },
  { value: 'done', label: 'Done' },
]

export default function TasksPage() {
  const [view, setView] = useState<ViewMode>('table')
  const [search, setSearch] = useState('')
  const [statusFilter, setStatusFilter] = useState<string>('all')
  const [myTasksOnly, setMyTasksOnly] = useState(false)
  const [localTasks, setLocalTasks] = useState<Task[]>([])
  const [modalOpen, setModalOpen] = useState(false)
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set())
  const [bulkLoading, setBulkLoading] = useState(false)
  const [statusDropOpen, setStatusDropOpen] = useState(false)
  const [reassignDropOpen, setReassignDropOpen] = useState(false)
  const [deleteConfirmOpen, setDeleteConfirmOpen] = useState(false)
  const [statusOverrides, setStatusOverrides] = useState<Record<string, string>>({})

  const { user } = useAuth()
  const { data, isLoading, error, refetch } = useFetch(() => tasksApi.list(0, 100), [])
  const { data: clientsData, isLoading: clientsLoading } = useFetch(() => clientsApi.list(0, 100), [])
  const { data: engagementsData, isLoading: engagementsLoading } = useFetch(() => engagementsApi.list(0, 100), [])
  const { data: usersData } = useFetch(() => api.get('/users/').then((r) => r.data), [])
  const [tasks, setTasks] = useState<Task[]>([])

  const serverTasks = data?.items ?? []
  const allTasks = [...localTasks, ...serverTasks].map((t) =>
    statusOverrides[t.id] ? { ...t, status: statusOverrides[t.id] } : t
  )

  const clientMap: Record<string, string> = Object.fromEntries(
    (clientsData?.items ?? []).map((c) => [c.id, c.name])
  )
  const engagementMap: Record<string, string> = Object.fromEntries(
    (engagementsData?.items ?? []).map((e) => [e.id, e.name])
  )
  const rawUsers: Array<{ id: string; full_name: string }> = Array.isArray(usersData)
    ? usersData
    : (usersData?.items ?? [])
  const userMap: Record<string, string> = Object.fromEntries(
    rawUsers.map((u) => [u.id, u.full_name])
  )
  const lookupsLoading = clientsLoading || engagementsLoading

  const filtered = allTasks
    .filter((t) => {
      if (search && !t.title.toLowerCase().includes(search.toLowerCase())) return false
      if (statusFilter !== 'all' && t.status !== statusFilter) return false
      if (myTasksOnly && t.assignedTo !== user?.id) return false
      return true
    })
    .sort((a, b) => {
      // When not filtering to my tasks, sort user's own tasks to the top
      if (!myTasksOnly) {
        const aMe = a.assignedTo === user?.id ? 0 : 1
        const bMe = b.assignedTo === user?.id ? 0 : 1
        return aMe - bMe
      }
      return 0
    })

  function handleAdd(task: Task) {
    setLocalTasks((prev) => [task, ...prev])
  }

  function handleSelect(id: string, checked: boolean) {
    setSelectedIds((prev) => {
      const next = new Set(prev)
      if (checked) next.add(id)
      else next.delete(id)
      return next
    })
  }

  function handleSelectAll(checked: boolean) {
    if (checked) setSelectedIds(new Set(filtered.map((t) => t.id)))
    else setSelectedIds(new Set())
  }

  async function handleBulkStatus(newStatus: string) {
    setStatusDropOpen(false)
    setBulkLoading(true)
    const ids = Array.from(selectedIds)
    const prev = filtered.map((t) => ({ ...t }))
    // optimistic update
    setLocalTasks((lts) => lts.map((t) => selectedIds.has(t.id) ? { ...t, status: newStatus } : t))
    setStatusOverrides((prev) => {
      const next = { ...prev }
      ids.forEach((id) => { next[id] = newStatus })
      return next
    })
    try {
      await tasksApi.bulkUpdate(ids, { status: newStatus })
      setSelectedIds(new Set())
      toast.success(`Updated ${ids.length} task${ids.length !== 1 ? 's' : ''}`)
    } catch {
      setLocalTasks(lts => lts.map((t, idx) => ({ ...prev[idx] ?? t })))
      toast.error('Bulk update failed')
    } finally {
      setBulkLoading(false)
    }
  }

  async function handleBulkReassign(userId: string) {
    setReassignDropOpen(false)
    setBulkLoading(true)
    const ids = Array.from(selectedIds)
    try {
      await tasksApi.bulkUpdate(ids, { assigned_to: userId })
      setSelectedIds(new Set())
      toast.success(`Reassigned ${ids.length} task${ids.length !== 1 ? 's' : ''}`)
      refetch()
    } catch {
      toast.error('Reassign failed')
    } finally {
      setBulkLoading(false)
    }
  }

  async function handleBulkDelete() {
    setDeleteConfirmOpen(false)
    setBulkLoading(true)
    const ids = Array.from(selectedIds)
    try {
      await Promise.all(ids.map((id) => tasksApi.delete(id)))
      setLocalTasks((lts) => lts.filter((t) => !selectedIds.has(t.id)))
      setSelectedIds(new Set())
      toast.success(`Deleted ${ids.length} task${ids.length !== 1 ? 's' : ''}`)
    } catch {
      toast.error('Delete failed')
    } finally {
      setBulkLoading(false)
    }
  }

  const selCount = selectedIds.size

  if (error) {
    return (
      <AppShell>
        <div className="flex flex-col h-full p-6 items-center justify-center">
          <p className="text-sm text-[#DC2626]">Failed to load tasks.</p>
        </div>
      </AppShell>
    )
  }

  return (
    <AppShell>
      <div className="flex flex-col h-full p-6 gap-4">

        <h1 className="text-2xl font-medium text-brand dark:text-[#EDEEF0]">
          Tasks
        </h1>

        <div className="flex items-center gap-3">
          <div className="relative flex-1">
            <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 h-4 w-4 text-[#6B7280]" />
            <input
              type="text"
              placeholder="Search tasks..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="w-full h-9 pl-8 pr-3 rounded-[6px] bg-surface-input dark:bg-dark-card border border-[0.5px] border-surface-border dark:border-dark-border text-[13px] text-brand dark:text-[#EDEEF0] placeholder:text-[#9CA3AF] focus:outline-none focus:border-brand-light transition-colors"
            />
          </div>
          <ViewToggle value={view} onChange={setView} />
          <button
            onClick={() => setModalOpen(true)}
            className="h-9 px-3 rounded-[6px] bg-brand dark:bg-brand-btn text-white text-[13px] font-medium hover:opacity-90 transition-opacity whitespace-nowrap flex-shrink-0"
          >
            + New Task
          </button>
        </div>

        {/* Filter bar */}
        <div className="flex items-center gap-2 flex-wrap">
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            className="text-[12px] h-8 px-2 rounded-[6px] border border-surface-border dark:border-dark-border bg-surface-card dark:bg-dark-card text-brand dark:text-[#EDEEF0] cursor-pointer"
          >
            <option value="all">All Statuses</option>
            <option value="todo">To Do</option>
            <option value="in_progress">In Progress</option>
            <option value="in_review">In Review</option>
            <option value="done">Done</option>
          </select>

          <button
            onClick={() => setMyTasksOnly((prev) => !prev)}
            className={`text-[12px] h-8 px-3 rounded-[6px] border font-medium transition-colors ${
              myTasksOnly
                ? 'bg-brand text-white border-brand'
                : 'border-surface-border dark:border-dark-border text-[#6B7280] dark:text-[#9CA3AF] bg-surface-card dark:bg-dark-card hover:text-brand'
            }`}
          >
            My Tasks
          </button>

          {(statusFilter !== 'all' || myTasksOnly) && (
            <button
              onClick={() => { setStatusFilter('all'); setMyTasksOnly(false) }}
              className="text-[11px] text-[#6B7280] hover:text-brand underline"
            >
              Clear filters
            </button>
          )}

          {(statusFilter !== 'all' || myTasksOnly) && (
            <span className="text-[11px] text-[#6B7280]">
              Showing {filtered.length} of {allTasks.length} tasks
            </span>
          )}
        </div>

        {isLoading && localTasks.length === 0 ? (
          <div className="rounded-modal border border-[0.5px] border-surface-border dark:border-dark-border overflow-hidden">
            {Array.from({ length: 5 }).map((_, i) => (
              <div
                key={i}
                className="flex gap-4 px-4 py-3 border-b border-[0.5px] border-[#D5D8DE] dark:border-dark-card last:border-0"
              >
                {Array.from({ length: 6 }).map((_, j) => (
                  <div key={j} className="h-4 flex-1 bg-[#D5D8DE] dark:bg-[#444444] animate-pulse rounded" />
                ))}
              </div>
            ))}
          </div>
        ) : filtered.length === 0 && search === '' ? (
          <TaskEmptyState onNew={() => setModalOpen(true)} />
        ) : filtered.length === 0 ? (
          <div className="flex flex-col items-center justify-center flex-1 py-24 gap-2">
            <p className="text-[13px] font-medium text-brand dark:text-[#EDEEF0]">
              No results for &ldquo;{search}&rdquo;
            </p>
            <p className="text-[12px] text-[#6B7280]">
              Try a different task, client, or staff name.
            </p>
          </div>
        ) : view === 'table' ? (
          <TaskTable
            tasks={filtered}
            clientMap={clientMap}
            engagementMap={engagementMap}
            userMap={userMap}
            lookupsLoading={lookupsLoading}
            selectedIds={selectedIds}
            onSelect={handleSelect}
            onSelectAll={handleSelectAll}
          />
        ) : (
          <div className="grid grid-cols-1 xl:grid-cols-2 gap-3">
            {filtered.map((task) => (
              <TaskCard key={task.id} task={task} clientMap={clientMap} engagementMap={engagementMap} lookupsLoading={lookupsLoading} />
            ))}
          </div>
        )}

        <NewTaskModal
          open={modalOpen}
          onClose={() => setModalOpen(false)}
          onAdd={handleAdd}
        />

        {/* Floating bulk action bar */}
        {selCount > 0 && (
          <div className="fixed bottom-6 left-1/2 -translate-x-1/2 z-50">
            <div className="bg-[#1F3148] dark:bg-[#1A2535] rounded-lg shadow-lg px-5 py-3 flex items-center gap-3">
              <span className="text-[13px] text-white font-medium whitespace-nowrap">
                {selCount} selected
              </span>

              {/* Change Status */}
              <div className="relative">
                <button
                  disabled={bulkLoading}
                  onClick={() => { setStatusDropOpen((o) => !o); setReassignDropOpen(false) }}
                  className="flex items-center gap-1 text-white text-[12px] border border-white/30 rounded px-3 py-1.5 hover:bg-white/10 disabled:opacity-50"
                >
                  Change Status <ChevronDown className="h-3 w-3" />
                </button>
                {statusDropOpen && (
                  <div className="absolute bottom-full mb-2 left-0 bg-white dark:bg-[#252525] border border-[#D5D8DE] dark:border-dark-border rounded-lg shadow-lg overflow-hidden min-w-[140px]">
                    {TASK_STATUSES.map((s) => (
                      <button
                        key={s.value}
                        onClick={() => handleBulkStatus(s.value)}
                        className="w-full text-left px-3 py-2 text-[12px] text-[#374151] dark:text-[#D1D5DB] hover:bg-[#F3F4F6] dark:hover:bg-[#333333]"
                      >
                        {s.label}
                      </button>
                    ))}
                  </div>
                )}
              </div>

              {/* Reassign */}
              <div className="relative">
                <button
                  disabled={bulkLoading}
                  onClick={() => { setReassignDropOpen((o) => !o); setStatusDropOpen(false) }}
                  className="flex items-center gap-1 text-white text-[12px] border border-white/30 rounded px-3 py-1.5 hover:bg-white/10 disabled:opacity-50"
                >
                  Reassign <ChevronDown className="h-3 w-3" />
                </button>
                {reassignDropOpen && (
                  <ReassignDropdown onSelect={handleBulkReassign} />
                )}
              </div>

              {/* Delete */}
              <button
                disabled={bulkLoading}
                onClick={() => setDeleteConfirmOpen(true)}
                className="text-white text-[12px] border border-white/30 rounded px-3 py-1.5 hover:bg-white/10 disabled:opacity-50"
              >
                Delete
              </button>

              {/* Clear */}
              <button
                onClick={() => setSelectedIds(new Set())}
                className="text-white/60 hover:text-white transition-colors ml-1"
              >
                <X className="h-4 w-4" />
              </button>
            </div>
          </div>
        )}

        {/* Delete confirmation */}
        {deleteConfirmOpen && (
          <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
            <div className="bg-white dark:bg-dark-card rounded-[10px] p-6 shadow-xl max-w-sm w-full mx-4">
              <p className="text-[14px] font-medium text-[#111827] dark:text-[#EDEEF0] mb-2">
                Delete {selCount} task{selCount !== 1 ? 's' : ''}?
              </p>
              <p className="text-[12px] text-[#6B7280] mb-5">This action cannot be undone.</p>
              <div className="flex gap-2 justify-end">
                <button
                  onClick={() => setDeleteConfirmOpen(false)}
                  className="px-4 py-2 text-[13px] rounded-[6px] border border-surface-border dark:border-dark-border text-[#374151] dark:text-[#D1D5DB] hover:bg-[#F9FAFB] dark:hover:bg-[#2A2A2A]"
                >
                  Cancel
                </button>
                <button
                  onClick={handleBulkDelete}
                  className="px-4 py-2 text-[13px] rounded-[6px] bg-red-600 text-white hover:bg-red-700"
                >
                  Delete
                </button>
              </div>
            </div>
          </div>
        )}

      </div>
    </AppShell>
  )
}

function ReassignDropdown({ onSelect }: { onSelect: (userId: string) => void }) {
  const { data, isLoading } = useFetch(() => api.get('/users/').then((r) => r.data), [])
  const users: Array<{ id: string; full_name: string }> = Array.isArray(data)
    ? data
    : (data?.items ?? [])

  return (
    <div className="absolute bottom-full mb-2 left-0 bg-white dark:bg-[#252525] border border-[#D5D8DE] dark:border-dark-border rounded-lg shadow-lg overflow-hidden min-w-[160px] max-h-48 overflow-y-auto">
      {isLoading ? (
        <div className="px-3 py-2 text-[12px] text-[#6B7280]">Loading…</div>
      ) : users.length === 0 ? (
        <div className="px-3 py-2 text-[12px] text-[#6B7280]">No staff found</div>
      ) : (
        users.map((u) => (
          <button
            key={u.id}
            onClick={() => onSelect(u.id)}
            className="w-full text-left px-3 py-2 text-[12px] text-[#374151] dark:text-[#D1D5DB] hover:bg-[#F3F4F6] dark:hover:bg-[#333333]"
          >
            {u.full_name}
          </button>
        ))
      )}
    </div>
  )
}

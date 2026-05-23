// path: frontend/src/app/engagements/[id]/page.tsx
'use client'

import { useState } from 'react'
import { useParams, useRouter } from 'next/navigation'
import { toast } from 'sonner'
import { useQueryClient } from '@tanstack/react-query'
import { AppShell } from '@/components/layout/AppShell'
import { Breadcrumb } from '@/components/layout/Breadcrumb'
import { engagementsApi, tasksApi, documentsApi } from '@/lib/api'
import { useFetch } from '@/lib/hooks/useFetch'
import { StatusBadge } from '@/components/ui/StatusBadge'
import { ExtensionPanel } from '@/components/engagements/ExtensionPanel'
import { DocumentRequestList } from '@/components/engagements/DocumentRequestList'
import { CreateDocumentRequestModal } from '@/components/engagements/CreateDocumentRequestModal'
import { EditEngagementModal } from '@/components/engagements/EditEngagementModal'
import { SendEngagementLetterModal } from '@/components/engagements/SendEngagementLetterModal'
import { TaskTable } from '@/components/tasks/TaskTable'
import { NotesTab, NotesPanel, useNotes } from '@/components/notes'
import { cn, formatEngagementType } from '@/lib/utils'
import api from '@/lib/api'
import { FileText } from 'lucide-react'
import { QcChecklistTab } from '@/components/engagements/QcChecklistTab'

type BadgeVariant = Parameters<typeof StatusBadge>[0]['variant']

const TABS = [
  { key: 'overview', label: 'Overview' },
  { key: 'tasks', label: 'Tasks' },
  { key: 'checklist', label: 'QC Checklist' },
  { key: 'documents', label: 'Documents' },
]

const labelClass = 'text-[11px] font-medium text-[#6B7280] uppercase tracking-[0.05em]'
const valueClass = 'text-[13px] text-brand dark:text-[#EDEEF0]'

function formatDate(dateStr: string | null | undefined): string {
  if (!dateStr) return '—'
  const d = new Date(dateStr)
  return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })
}

export default function EngagementDetailPage() {
  const params = useParams()
  const router = useRouter()
  const id = params.id as string
  const queryClient = useQueryClient()
  const [activeTab, setActiveTab] = useState('overview')
  const [notesOpen, setNotesOpen] = useState(false)
  const [showModal, setShowModal] = useState(false)
  const [isEditOpen, setIsEditOpen] = useState(false)
  const [sendLetterOpen, setSendLetterOpen] = useState(false)
  const [uncheckedQcCount, setUncheckedQcCount] = useState(0)

  const { unreadCount } = useNotes({ entityType: 'engagement', entityId: id })

  const { data: engagement, isLoading, refetch } = useFetch(
    () => engagementsApi.get(id),
    [id]
  )

  const { data: tasksData, isLoading: tasksLoading } = useFetch(
    () => tasksApi.list(0, 50, id),
    [id]
  )
  const tasks = tasksData?.items ?? []

  const { data: docsData, isLoading: docsLoading } = useFetch(
    () => documentsApi.list(0, 50, undefined, id),
    [id]
  )
  const documents = docsData?.items ?? []

  // Fetch client name for the taskTable clientMap
  const { data: clientData } = useFetch(
    () =>
      engagement?.clientId
        ? api.get<{ id: string; name: string }>(`/clients/${engagement.clientId}`).then((r) => r.data)
        : Promise.resolve(null),
    [engagement?.clientId]
  )
  const clientName = clientData?.name ?? ''
  const clientMap: Record<string, string> = engagement?.clientId && clientName
    ? { [engagement.clientId]: clientName }
    : {}
  const engagementMap: Record<string, string> = engagement
    ? { [engagement.id]: engagement.name }
    : {}

  if (isLoading) {
    return (
      <AppShell>
        <div className="p-6">
          <div className="h-6 w-48 bg-[#D5D8DE] dark:bg-[#444444] animate-pulse rounded mb-4" />
          <div className="h-8 w-72 bg-[#D5D8DE] dark:bg-[#444444] animate-pulse rounded mb-2" />
          <div className="h-4 w-56 bg-[#D5D8DE] dark:bg-[#444444] animate-pulse rounded" />
        </div>
      </AppShell>
    )
  }

  if (!engagement) {
    return (
      <AppShell>
        <div className="flex items-center justify-center h-full p-6">
          <p className="text-[13px] text-[#6B7280]">Engagement not found.</p>
        </div>
      </AppShell>
    )
  }

  return (
    <AppShell>
      <div className="p-6">
        <Breadcrumb
          items={[
            { label: 'Engagements', href: '/engagements' },
            { label: engagement.name },
          ]}
        />

        {/* Page header */}
        <div className="flex items-start justify-between mb-6">
          <div>
            <h1 className="text-2xl font-medium text-brand dark:text-[#EDEEF0] mb-1">
              {engagement.name}
            </h1>
            <div className="flex items-center gap-2">
              <StatusBadge variant={engagement.status as BadgeVariant} />
              <span className="text-[12px] text-[#6B7280]">
                {formatEngagementType(engagement.engagementType)}
                {engagement.endDate ? ` · Due ${engagement.endDate}` : ''}
              </span>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={() => setSendLetterOpen(true)}
              className="h-9 px-3 rounded-[6px] border border-brand dark:border-[#4A7FA5] text-brand dark:text-[#4A7FA5] text-[13px] font-medium hover:bg-surface-card dark:hover:bg-dark-card transition-colors"
            >
              Send Engagement Letter
            </button>
            <button
              onClick={() => setIsEditOpen(true)}
              className="h-9 px-3 rounded-[6px] bg-brand dark:bg-brand-btn text-white text-[13px] font-medium hover:opacity-90 transition-opacity"
            >
              Edit Engagement
            </button>
          </div>
        </div>

        {/* Tab bar */}
        <div className="flex items-end gap-0 border-b border-surface-border dark:border-dark-border mb-6">
          {TABS.map((tab) => (
            <button
              key={tab.key}
              onClick={() => setActiveTab(tab.key)}
              className={cn(
                'px-4 py-2.5 text-[13px] transition-colors relative',
                activeTab === tab.key
                  ? 'text-brand dark:text-[#4A7FA5] font-medium'
                  : 'text-[#6B7280] hover:text-brand dark:hover:text-[#EDEEF0] font-normal',
              )}
            >
              {tab.label}
              {activeTab === tab.key && (
                <span className="absolute bottom-0 left-0 right-0 h-[2px] bg-[#1F3148] dark:bg-[#4A7FA5]" />
              )}
            </button>
          ))}
        </div>

        {/* OVERVIEW TAB */}
        {activeTab === 'overview' && (
          <div className="flex flex-col gap-4">
            {/* Info card */}
            <div className="bg-surface-card dark:bg-dark-card rounded-[8px] p-4">
              <div className="grid grid-cols-2 gap-x-6 gap-y-4">
                <div className="flex flex-col gap-1">
                  <span className={labelClass}>Engagement type</span>
                  <span className={valueClass}>{formatEngagementType(engagement.engagementType)}</span>
                </div>
                <div className="flex flex-col gap-1">
                  <span className={labelClass}>Status</span>
                  <div className="w-fit">
                    <StatusBadge variant={engagement.status as BadgeVariant} />
                  </div>
                </div>
                <div className="flex flex-col gap-1">
                  <span className={labelClass}>Client</span>
                  {engagement.clientId ? (
                    <button
                      onClick={() => router.push(`/clients/${engagement.clientId}`)}
                      className="text-[13px] text-brand-light hover:underline text-left w-fit"
                    >
                      {clientName || engagement.clientId}
                    </button>
                  ) : (
                    <span className={valueClass}>—</span>
                  )}
                </div>
                <div className="flex flex-col gap-1">
                  <span className={labelClass}>Due date</span>
                  <span className={valueClass}>{formatDate(engagement.endDate)}</span>
                </div>
                <div className="flex flex-col gap-1">
                  <span className={labelClass}>Assigned to</span>
                  <span className={valueClass}>Unassigned</span>
                </div>
                <div className="flex flex-col gap-1">
                  <span className={labelClass}>Created</span>
                  <span className={valueClass}>{formatDate(engagement.createdAt)}</span>
                </div>
              </div>
            </div>

            {/* Extension panel */}
            <ExtensionPanel engagementId={id} clientId={engagement.clientId ?? ''} />
          </div>
        )}

        {/* TASKS TAB */}
        {activeTab === 'tasks' && (
          <>
            {tasksLoading ? (
              <div className="rounded-modal border border-[0.5px] border-surface-border dark:border-dark-border overflow-hidden">
                <table className="w-full border-collapse">
                  <thead>
                    <tr className="bg-surface-card dark:bg-[#252525]">
                      {['Task', 'Client', 'Engagement', 'Assigned To', 'Due Date', 'Status'].map((col) => (
                        <th key={col} className="px-4 py-2.5 text-left text-[11px] font-medium text-[#6B7280] uppercase tracking-[0.05em] whitespace-nowrap">
                          {col}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {Array.from({ length: 5 }).map((_, i) => (
                      <tr key={i}>
                        <td colSpan={6} className="px-4 py-3">
                          <div className="h-4 bg-[#D5D8DE] dark:bg-[#444444] animate-pulse rounded" />
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : tasks.length === 0 ? (
              <div className="flex flex-col items-center justify-center py-24 gap-[10px]">
                <p className="text-[13px] font-medium text-brand dark:text-[#EDEEF0]">
                  No tasks yet
                </p>
                <p className="text-[12px] text-[#6B7280]">
                  Tasks assigned to this engagement will appear here.
                </p>
                <button
                  onClick={() => console.log('New task')}
                  className="bg-brand text-white text-[12px] px-3 py-1.5 rounded-[6px] hover:opacity-90 transition-opacity mt-1"
                >
                  + New Task
                </button>
              </div>
            ) : (
              <TaskTable
                tasks={tasks}
                clientMap={clientMap}
                engagementMap={engagementMap}
              />
            )}
          </>
        )}

        {/* QC CHECKLIST TAB */}
        {activeTab === 'checklist' && (
          <QcChecklistTab
            engagementId={id}
            engagementStatus={engagement.status}
            onUncheckedCountChange={setUncheckedQcCount}
          />
        )}

        {/* DOCUMENTS TAB */}
        {activeTab === 'documents' && (
          <>
            {/* Toolbar */}
            <div className="flex items-center justify-between mb-4">
              <span className="text-[13px] font-medium text-[#1F3148] dark:text-[#EDEEF0]">
                Document Requests
              </span>
              <button
                onClick={() => setShowModal(true)}
                className="h-8 px-3 rounded-[6px] bg-[#1F3148] dark:bg-[#3A6A94] text-white text-[12px] font-medium hover:opacity-90 transition-opacity"
              >
                + New Request
              </button>
            </div>

            <DocumentRequestList
              engagementId={id}
              clientId={engagement.clientId ?? ''}
              onCreateClick={() => setShowModal(true)}
            />

            <CreateDocumentRequestModal
              isOpen={showModal}
              onClose={() => setShowModal(false)}
              engagementId={id}
              clientId={engagement.clientId ?? ''}
              onSuccess={() =>
                queryClient.invalidateQueries({ queryKey: ['document-requests', id] })
              }
            />

            {/* Uploaded Documents section */}
            <div className="flex items-center justify-between mt-6">
              <span className="text-[13px] font-medium text-[#1F3148] dark:text-[#EDEEF0]">
                Uploaded Documents
              </span>
            </div>

            {docsLoading ? (
              <div className="mt-3 rounded-[10px] border border-[0.5px] border-[#C8CDD6] dark:border-[#484848] overflow-hidden">
                {Array.from({ length: 3 }).map((_, i) => (
                  <div key={i} className="px-4 py-3 bg-[#E4E6EA] dark:bg-[#2D2D2D]">
                    <div className="h-4 bg-[#D5D8DE] dark:bg-[#444444] animate-pulse rounded" />
                  </div>
                ))}
              </div>
            ) : documents.length === 0 ? (
              <p className="mt-3 text-[12px] text-[#6B7280] text-center">
                No documents uploaded yet.
              </p>
            ) : (
              <div className="mt-3 rounded-[10px] border border-[0.5px] border-[#C8CDD6] dark:border-[#484848] overflow-hidden">
                <table className="w-full border-collapse">
                  <thead>
                    <tr className="bg-[#EDEEF0] dark:bg-[#252525]">
                      {['Name', 'Type', 'Uploaded', 'Status'].map((col) => (
                        <th
                          key={col}
                          className="px-4 py-2.5 text-left text-[11px] font-medium text-[#6B7280] uppercase tracking-[0.05em] whitespace-nowrap"
                        >
                          {col}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {documents.map((doc, i) => (
                      <tr
                        key={doc.id}
                        onClick={() => router.push(`/documents/${doc.id}`)}
                        className={cn(
                          'cursor-pointer transition-colors bg-[#E4E6EA] dark:bg-[#2D2D2D] hover:bg-[#DDDFE3] dark:hover:bg-[#323232]',
                          i !== documents.length - 1
                            ? 'border-b border-[0.5px] border-[#D5D8DE] dark:border-[#383838]'
                            : '',
                        )}
                      >
                        <td className="px-4 py-3">
                          <div className="flex items-center gap-2">
                            <FileText className="h-[14px] w-[14px] text-[#6B7280] flex-shrink-0" />
                            <span className="text-[12px] font-medium text-[#1F3148] dark:text-[#EDEEF0]">
                              {doc.name}
                            </span>
                          </div>
                        </td>
                        <td className="px-4 py-3">
                          <span className="text-[12px] text-[#374151] dark:text-[#9CA3AF]">
                            {doc.fileType ?? '—'}
                          </span>
                        </td>
                        <td className="px-4 py-3">
                          <span className="text-[12px] text-[#374151] dark:text-[#9CA3AF]">
                            {doc.uploadedAt ?? '—'}
                          </span>
                        </td>
                        <td className="px-4 py-3">
                          <StatusBadge variant={doc.status as BadgeVariant} />
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </>
        )}
      </div>

      <NotesTab unreadCount={unreadCount} onClick={() => setNotesOpen(true)} />
      <NotesPanel
        isOpen={notesOpen}
        onClose={() => setNotesOpen(false)}
        entityType="engagement"
        entityId={id}
        contextLabel={engagement.name}
      />
      {isEditOpen && (
        <EditEngagementModal
          isOpen={isEditOpen}
          onClose={() => setIsEditOpen(false)}
          engagement={{
            ...engagement,
            engagementType: engagement.engagementType ?? undefined,
            endDate: engagement.endDate ?? undefined,
            description: engagement.description ?? undefined,
          }}
          onSuccess={() => { refetch(); setIsEditOpen(false) }}
          uncheckedQcCount={uncheckedQcCount}
        />
      )}
      <SendEngagementLetterModal
        open={sendLetterOpen}
        onClose={() => setSendLetterOpen(false)}
        onSent={() => {
          setSendLetterOpen(false)
          toast.success('Engagement letter sent')
        }}
        engagementId={id}
        engagementType={engagement.engagementType}
        clientName={clientName}
        engagementName={engagement.name}
        filingDeadline={engagement.filingDeadline ?? null}
        endDate={engagement.endDate ?? null}
      />
    </AppShell>
  )
}

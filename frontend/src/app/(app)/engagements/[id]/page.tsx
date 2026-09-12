// path: frontend/src/app/engagements/[id]/page.tsx
'use client'

import { useState } from 'react'
import { useParams, useRouter } from 'next/navigation'
import { toast } from 'sonner'
import { useQueryClient } from '@tanstack/react-query'
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
import type { PendingDocument } from '@/lib/api'
import { FileText, FileSpreadsheet, File as FileGeneric, FileImage } from 'lucide-react'
import { QcChecklistTab } from '@/components/engagements/QcChecklistTab'
import { useAuth } from '@/lib/hooks/useAuth'
import { settingsApi, type FirmDetails } from '@/lib/api/settingsApi'

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

function relativeTime(isoStr: string): string {
  if (!isoStr) return ''
  const d = new Date(isoStr)
  const now = Date.now()
  const diffMs = now - d.getTime()
  const minutes = Math.floor(diffMs / 60000)
  const hours = Math.floor(diffMs / 3600000)
  const days = Math.floor(diffMs / 86400000)
  if (minutes < 1) return 'just now'
  if (minutes < 60) return `${minutes}m ago`
  if (hours < 24) return `${hours}h ago`
  if (days === 1) return 'yesterday'
  if (days < 30) return `${days} days ago`
  return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' })
}

function fileIconFromContentType(contentType: string): JSX.Element {
  if (contentType === 'application/pdf') {
    return <FileText size={15} style={{ color: '#EF4444' }} className="flex-shrink-0" />
  }
  if (
    contentType.includes('spreadsheet') ||
    contentType === 'text/csv' ||
    contentType === 'application/vnd.ms-excel' ||
    contentType === 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
  ) {
    return <FileSpreadsheet size={15} style={{ color: '#10B981' }} className="flex-shrink-0" />
  }
  if (contentType.startsWith('image/')) {
    return <FileImage size={15} style={{ color: '#8B5CF6' }} className="flex-shrink-0" />
  }
  if (contentType.includes('word') || contentType.includes('document')) {
    return <FileGeneric size={15} style={{ color: '#3B82F6' }} className="flex-shrink-0" />
  }
  return <FileGeneric size={15} style={{ color: '#9CA3AF' }} className="flex-shrink-0" />
}

function EngagementDetailBodySkeleton() {
  return (
    <div className="p-6 pt-0 flex flex-col gap-4">
      <div className="bg-surface-card dark:bg-dark-card rounded-[8px] p-4">
        <div className="grid grid-cols-2 gap-x-6 gap-y-4">
          {Array.from({ length: 6 }).map((_, i) => (
            <div key={i} className="flex flex-col gap-1">
              <div className="h-2.5 w-20 bg-[#D5D8DE] dark:bg-[#444444] animate-pulse rounded" />
              <div className="h-4 bg-[#D5D8DE] dark:bg-[#444444] animate-pulse rounded" style={{ width: `${45 + (i % 3) * 15}%` }} />
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}

export default function EngagementDetailPage() {
  const params = useParams()
  const router = useRouter()
  const id = params.id as string
  const queryClient = useQueryClient()
  const { user } = useAuth()
  const [activeTab, setActiveTab] = useState('overview')
  const [notesOpen, setNotesOpen] = useState(false)
  const [showModal, setShowModal] = useState(false)
  const [isEditOpen, setIsEditOpen] = useState(false)
  const [sendLetterOpen, setSendLetterOpen] = useState(false)
  const [uncheckedQcCount, setUncheckedQcCount] = useState(0)
  const [showReviewModal, setShowReviewModal] = useState(false)
  const [sendingReview, setSendingReview] = useState(false)
  const [approvingId, setApprovingId] = useState<string | null>(null)
  const [reassignDoc, setReassignDoc] = useState<PendingDocument | null>(null)
  const [reassignTargetId, setReassignTargetId] = useState('')
  const [reassignLoading, setReassignLoading] = useState(false)

  const { unreadCount } = useNotes({ entityType: 'engagement', entityId: id })

  const { data: firmData } = useFetch<FirmDetails>(
    () => settingsApi.getMyFirm().then((r) => r.data as FirmDetails),
    []
  )

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

  const { data: pendingDocsData, refetch: refetchPending } = useFetch(
    () => documentsApi.listPending(id),
    [id]
  )
  const pendingDocs = pendingDocsData?.items ?? []
  const pendingCount = pendingDocsData?.total ?? pendingDocs.length

  const { data: clientEngagementsData } = useFetch(
    () =>
      engagement?.clientId
        ? engagementsApi.list(0, 100, engagement.clientId)
        : Promise.resolve({ items: [], total: 0 }),
    [engagement?.clientId]
  )
  const clientEngagements = (clientEngagementsData?.items ?? []).filter((e) => e.id !== id)

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

  async function handleApprove(docId: string) {
    setApprovingId(docId)
    try {
      await documentsApi.approvePending(docId)
      toast.success('Document approved')
      refetchPending()
    } catch {
      toast.error('Failed to approve document')
    } finally {
      setApprovingId(null)
    }
  }

  async function handleReassign() {
    if (!reassignDoc || !reassignTargetId) return
    setReassignLoading(true)
    try {
      await documentsApi.reassignPending(reassignDoc.id, reassignTargetId)
      toast.success('Document reassigned')
      setReassignDoc(null)
      setReassignTargetId('')
      refetchPending()
    } catch {
      toast.error('Failed to reassign document')
    } finally {
      setReassignLoading(false)
    }
  }

  if (isLoading) {
    return (
      <>
        <div className="p-6">
          <div className="h-6 w-48 bg-[#D5D8DE] dark:bg-[#444444] animate-pulse rounded mb-4" />
          <div className="h-8 w-72 bg-[#D5D8DE] dark:bg-[#444444] animate-pulse rounded mb-2" />
          <div className="h-4 w-56 bg-[#D5D8DE] dark:bg-[#444444] animate-pulse rounded" />
        </div>
        <EngagementDetailBodySkeleton />
      </>
    )
  }

  if (!engagement) {
    return (
        <div className="flex items-center justify-center h-full p-6">
          <p className="text-[13px] text-[#6B7280]">Engagement not found.</p>
        </div>
    )
  }

  return (<>
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
              <span className="flex items-center gap-1.5">
                {tab.label}
                {tab.key === 'documents' && pendingCount > 0 && (
                  <span className="px-2 py-0.5 rounded-full bg-[#E5E7EB] dark:bg-[#333] text-[11px] font-medium text-[#6B7280]">
                    {pendingCount}
                  </span>
                )}
              </span>
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

            {/* Pending Documents section -- client-uploaded items awaiting triage */}
            {pendingDocs.length > 0 && (
              <div className="mt-6">
                <div className="flex items-center gap-2 mb-3">
                  <span className="text-[13px] font-medium text-[#1F3148] dark:text-[#EDEEF0]">
                    Pending Documents
                  </span>
                </div>
                <p className="text-[12px] text-[#6B7280] mb-3">
                  Review these documents your client uploaded to this engagement.
                </p>
                <div className="rounded-[10px] border border-[0.5px] border-[#C8CDD6] dark:border-[#484848] overflow-hidden">
                  {pendingDocs.map((doc, i) => (
                    <div
                      key={doc.id}
                      className={cn(
                        'flex items-start gap-3 px-4 py-3 bg-[#E4E6EA] dark:bg-[#2D2D2D]',
                        i !== pendingDocs.length - 1
                          ? 'border-b border-[0.5px] border-[#D5D8DE] dark:border-[#383838]'
                          : '',
                      )}
                    >
                      {/* File icon */}
                      <div className="mt-0.5 flex-shrink-0">
                        {fileIconFromContentType(doc.contentType)}
                      </div>

                      {/* Doc info */}
                      <div className="flex-1 min-w-0">
                        <p className="text-[13px] font-medium text-[#1F3148] dark:text-[#EDEEF0] truncate">
                          {doc.filename}
                        </p>
                        {doc.clientNote && (
                          <p className="text-[12px] text-[#6B7280] mt-0.5">{doc.clientNote}</p>
                        )}
                        <p className="text-[11px] text-[#9CA3AF] mt-0.5">
                          {relativeTime(doc.createdAt)}
                        </p>
                      </div>

                      {/* Actions */}
                      <div className="flex flex-col items-end gap-1.5 flex-shrink-0">
                        <button
                          disabled={approvingId === doc.id}
                          onClick={() => handleApprove(doc.id)}
                          className="h-8 px-3 rounded-[6px] bg-[#1F3148] dark:bg-[#3A6A94] text-white text-[12px] font-medium hover:opacity-90 transition-opacity disabled:opacity-50 whitespace-nowrap"
                        >
                          {approvingId === doc.id ? 'Approving...' : 'Approve'}
                        </button>
                        <button
                          onClick={() => {
                            setReassignDoc(doc)
                            setReassignTargetId('')
                          }}
                          className="text-[12px] text-[#6B7280] hover:text-[#1F3148] dark:hover:text-[#EDEEF0] transition-colors"
                        >
                          Reassign
                        </button>
                        <p className="text-[11px] text-[#9CA3AF]">
                          Move to another {clientName || 'client'} engagement
                        </p>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}

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
          onSuccess={(opts) => {
            refetch()
            setIsEditOpen(false)
            const canSendReview =
              user?.role === 'firm_owner' || user?.role === 'manager'
            const flagEnabled = firmData?.feature_flags?.review_requests_enabled === true
            if (opts?.statusBecameCompleted && canSendReview && flagEnabled) {
              setShowReviewModal(true)
            }
          }}
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

      {/* Reassign document modal */}
      {reassignDoc && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
          <div className="bg-[#EDEEF0] dark:bg-dark-card rounded-[10px] border border-[0.5px] border-[#C8CDD6] dark:border-[#484848] p-6 w-full max-w-sm shadow-lg">
            <p className="text-[13px] font-medium text-brand dark:text-[#EDEEF0] mb-4">
              Reassign document
            </p>

            {/* File name preview */}
            <div className="flex items-center gap-2 mb-4 p-3 rounded-[8px] bg-white dark:bg-[#252525] border border-[0.5px] border-[#C8CDD6] dark:border-[#484848]">
              {fileIconFromContentType(reassignDoc.contentType)}
              <span className="text-[12px] text-[#1F3148] dark:text-[#EDEEF0] truncate">{reassignDoc.filename}</span>
            </div>

            {/* Same-client constraint banner */}
            <div className="mb-4 px-3 py-2 rounded-[8px] bg-[#FEF9C3] dark:bg-[#3D3A1A] border border-[0.5px] border-[#FDE047] dark:border-[#6B6020]">
              <p className="text-[12px] text-[#713F12] dark:text-[#FDE68A]">
                Only {clientName || 'this client'} engagements are shown. Reassigning will move this document to the selected engagement.
              </p>
            </div>

            {/* Engagement picker */}
            <label className="block text-[11px] font-medium text-[#6B7280] uppercase tracking-[0.05em] mb-1.5">
              Select an engagement
            </label>
            <select
              value={reassignTargetId}
              onChange={(e) => setReassignTargetId(e.target.value)}
              className="w-full h-9 px-3 rounded-[6px] border border-[0.5px] border-[#C8CDD6] dark:border-[#484848] bg-white dark:bg-[#2D2D2D] text-[13px] text-[#1F3148] dark:text-[#EDEEF0] mb-5"
            >
              <option value="">Choose engagement...</option>
              {clientEngagements.map((eng) => (
                <option key={eng.id} value={eng.id}>
                  {eng.name}
                  {eng.endDate ? ` (due ${eng.endDate})` : ''}
                </option>
              ))}
            </select>

            <div className="flex items-center justify-end gap-2">
              <button
                onClick={() => { setReassignDoc(null); setReassignTargetId('') }}
                className="h-9 px-3 rounded-[6px] border border-[0.5px] border-[#1F3148] dark:border-[#4A7FA5] text-[#1F3148] dark:text-[#EDEEF0] bg-transparent text-[13px] font-medium hover:bg-surface-page dark:hover:bg-dark-page transition-colors"
              >
                Cancel
              </button>
              <button
                disabled={!reassignTargetId || reassignLoading}
                onClick={handleReassign}
                className="h-9 px-3 rounded-[6px] bg-[#1F3148] dark:bg-brand-btn text-white text-[13px] font-medium hover:opacity-90 transition-opacity disabled:opacity-50"
              >
                {reassignLoading ? 'Moving...' : 'Move Document'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Review request modal */}
      {showReviewModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
          <div className="bg-[#EDEEF0] dark:bg-dark-card rounded-[10px] border border-[0.5px] border-[#C8CDD6] dark:border-[#484848] p-6 w-full max-w-sm shadow-lg">
            <p className="text-[13px] font-medium text-brand dark:text-[#EDEEF0] mb-2">
              Engagement Complete
            </p>
            <p className="text-[13px] text-[#374151] dark:text-[#9CA3AF] leading-relaxed mb-5">
              Would you like to send {clientName || 'this client'} a review request? Happy clients
              will be directed to your Google review page.
            </p>
            <div className="flex items-center justify-end gap-2">
              <button
                onClick={() => setShowReviewModal(false)}
                className="h-9 px-3 rounded-[6px] border border-[0.5px] border-[#1F3148] dark:border-[#4A7FA5] text-[#1F3148] dark:text-[#EDEEF0] bg-transparent text-[13px] font-medium hover:bg-surface-page dark:hover:bg-dark-page transition-colors"
              >
                Skip
              </button>
              <button
                disabled={sendingReview}
                onClick={async () => {
                  if (!engagement.clientId) return
                  setSendingReview(true)
                  try {
                    await api.post('/review-requests/send', {
                      client_id: engagement.clientId,
                      engagement_id: engagement.id,
                    })
                    toast.success(`Review request sent to ${clientName || 'client'}`)
                  } catch (err: unknown) {
                    const detail =
                      (err as { response?: { data?: { detail?: string } } })?.response?.data
                        ?.detail
                    toast.error(detail ?? 'Failed to send review request')
                  } finally {
                    setSendingReview(false)
                    setShowReviewModal(false)
                  }
                }}
                className="h-9 px-3 rounded-[6px] bg-[#1F3148] dark:bg-brand-btn text-white text-[13px] font-medium hover:opacity-90 transition-opacity disabled:opacity-50"
              >
                {sendingReview ? 'Sending...' : 'Send Request'}
              </button>
            </div>
          </div>
        </div>
      )}
  </>)
}

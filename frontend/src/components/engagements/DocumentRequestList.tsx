// path: frontend/src/components/engagements/DocumentRequestList.tsx
'use client'

import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'
import { ChevronDown, ChevronUp } from 'lucide-react'
import {
  documentRequestsApi,
  type DocumentRequest,
  type ChecklistItem,
} from '@/lib/api/documentRequests'

interface DocumentRequestListProps {
  engagementId: string
  clientId: string
  onCreateClick: () => void
}

function formatDate(dateStr: string | null | undefined): string {
  if (!dateStr) return ''
  const d = new Date(dateStr)
  return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })
}

type ItemStatus = ChecklistItem['status']

function StatusIcon({ status }: { status: ItemStatus }) {
  if (status === 'approved') {
    return <span className="flex-shrink-0 w-2.5 h-2.5 rounded-full bg-[#10B981] inline-block" />
  }
  if (status === 'rejected') {
    return <span className="flex-shrink-0 w-2.5 h-2.5 rounded-full bg-[#DC2626] inline-block" />
  }
  if (status === 'uploaded') {
    return <span className="flex-shrink-0 w-2.5 h-2.5 rounded-full bg-[#3B82F6] inline-block" />
  }
  return <span className="flex-shrink-0 w-2.5 h-2.5 rounded-full bg-[#F59E0B] inline-block" />
}

function ProgressBar({ items }: { items: ChecklistItem[] }) {
  const total = items.length
  const done = items.filter(
    (i) => i.status === 'uploaded' || i.status === 'approved'
  ).length
  const pct = total === 0 ? 0 : (done / total) * 100

  let fillColor = '#C8CDD6'
  if (done === total && total > 0) fillColor = '#10B981'
  else if (done > 0) fillColor = '#F59E0B'

  return (
    <div className="mt-2 mb-1 h-[4px] rounded-[2px] bg-[#C8CDD6] dark:bg-[#484848] overflow-hidden">
      <div
        className="h-full rounded-[2px] transition-all duration-300"
        style={{ width: `${pct}%`, backgroundColor: fillColor }}
      />
    </div>
  )
}

function RequestCard({
  request,
  engagementId,
}: {
  request: DocumentRequest
  engagementId: string
}) {
  const [expanded, setExpanded] = useState(false)
  const [pendingItems, setPendingItems] = useState<Set<string>>(new Set())
  const queryClient = useQueryClient()

  const total = request.checklist_items.length
  const done = request.checklist_items.filter(
    (i) => i.status === 'uploaded' || i.status === 'approved'
  ).length
  const approvedCount = request.checklist_items.filter((i) => i.status === 'approved').length

  const mutation = useMutation({
    mutationFn: ({
      itemId,
      status,
    }: {
      itemId: string
      status: 'approved' | 'rejected'
    }) => documentRequestsApi.updateItem(request.id, itemId, status),
    onMutate: async ({ itemId, status }) => {
      setPendingItems((prev) => new Set(prev).add(itemId))
      await queryClient.cancelQueries({ queryKey: ['document-requests', engagementId] })
      const previous = queryClient.getQueryData<DocumentRequest[]>([
        'document-requests',
        engagementId,
      ])
      queryClient.setQueryData<DocumentRequest[]>(
        ['document-requests', engagementId],
        (old) =>
          old?.map((req) =>
            req.id === request.id
              ? {
                  ...req,
                  checklist_items: req.checklist_items.map((item) =>
                    item.id === itemId ? { ...item, status } : item
                  ),
                }
              : req
          )
      )
      return { previous }
    },
    onError: (_err, { itemId }, context) => {
      if (context?.previous) {
        queryClient.setQueryData(
          ['document-requests', engagementId],
          context.previous
        )
      }
      setPendingItems((prev) => {
        const next = new Set(prev)
        next.delete(itemId)
        return next
      })
      toast.error('Could not update item — please try again.')
    },
    onSuccess: (_data, { itemId, status }) => {
      setPendingItems((prev) => {
        const next = new Set(prev)
        next.delete(itemId)
        return next
      })
      toast.success(status === 'approved' ? 'Item approved.' : 'Item rejected.', {
        duration: 4000,
      })
      queryClient.invalidateQueries({ queryKey: ['document-requests', engagementId] })
    },
  })

  return (
    <div className="bg-[#EDEEF0] dark:bg-[#383838] rounded-[8px] border border-[0.5px] border-[#C8CDD6] dark:border-[#484848] px-4 py-[14px] mb-[10px]">
      <div
        className="flex items-center justify-between cursor-pointer"
        onClick={() => setExpanded((prev) => !prev)}
      >
        <div className="flex flex-col gap-[2px]">
          <span className="text-[13px] font-medium text-[#1F3148] dark:text-[#EDEEF0]">
            {request.title}
          </span>
          <span className="text-[11px] text-[#6B7280]">
            Sent {formatDate(request.created_at)}
            {request.due_date ? <> · Due {formatDate(request.due_date)}</> : null}
          </span>
        </div>
        <div className="flex items-center gap-3">
          <span className="text-[12px] text-[#6B7280]">
            {done} of {total} received
          </span>
          {expanded ? (
            <ChevronUp className="h-4 w-4 text-[#6B7280]" />
          ) : (
            <ChevronDown className="h-4 w-4 text-[#6B7280]" />
          )}
        </div>
      </div>

      <ProgressBar items={request.checklist_items} />

      {expanded && (
        <div className="mt-3 border-t border-[0.5px] border-[#C8CDD6] dark:border-[#484848] pt-3">
          {request.checklist_items.map((item) => (
            <div key={item.id} className="flex items-center gap-[10px] py-[6px]">
              <StatusIcon status={item.status} />
              <div className="flex items-center gap-1 flex-1 min-w-0">
                <span className="text-[13px] text-[#374151] dark:text-[#9CA3AF] truncate">
                  {item.label}
                </span>
                {item.is_required && (
                  <span className="flex-shrink-0 w-[5px] h-[5px] rounded-full bg-[#E24B4A]" />
                )}
              </div>
              {item.status === 'uploaded' && (
                <div className="flex items-center gap-1 flex-shrink-0">
                  <button
                    disabled={pendingItems.has(item.id)}
                    onClick={() => mutation.mutate({ itemId: item.id, status: 'approved' })}
                    title="Approve"
                    className="w-6 h-6 rounded-[4px] bg-[#D1FAE5] text-[#065F46] flex items-center justify-center disabled:opacity-50 hover:opacity-90 transition-opacity"
                  >
                    <svg width="12" height="12" viewBox="0 0 12 12" fill="none">
                      <path d="M2 6l3 3 5-5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
                    </svg>
                  </button>
                  <button
                    disabled={pendingItems.has(item.id)}
                    onClick={() => mutation.mutate({ itemId: item.id, status: 'rejected' })}
                    title="Reject"
                    className="w-6 h-6 rounded-[4px] bg-[#FEE2E2] text-[#DC2626] flex items-center justify-center disabled:opacity-50 hover:opacity-90 transition-opacity"
                  >
                    <svg width="12" height="12" viewBox="0 0 12 12" fill="none">
                      <path d="M3 3l6 6M9 3l-6 6" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
                    </svg>
                  </button>
                </div>
              )}
            </div>
          ))}
          {approvedCount > 0 && (
            <p className="text-[11px] text-[#065F46] mt-2">
              {approvedCount} item{approvedCount !== 1 ? 's' : ''} approved
            </p>
          )}
          <div className="flex items-center gap-4 mt-3 pt-2 border-t border-[0.5px] border-[#C8CDD6] dark:border-[#484848]">
            <div className="flex items-center gap-1.5">
              <span className="w-2.5 h-2.5 rounded-full bg-[#10B981] inline-block" />
              <span className="text-[10px] text-[#6B7280]">Approved</span>
            </div>
            <div className="flex items-center gap-1.5">
              <span className="w-2.5 h-2.5 rounded-full bg-[#3B82F6] inline-block" />
              <span className="text-[10px] text-[#6B7280]">Received</span>
            </div>
            <div className="flex items-center gap-1.5">
              <span className="w-2.5 h-2.5 rounded-full bg-[#F59E0B] inline-block" />
              <span className="text-[10px] text-[#6B7280]">Pending</span>
            </div>
            <div className="flex items-center gap-1.5">
              <span className="w-2.5 h-2.5 rounded-full bg-[#DC2626] inline-block" />
              <span className="text-[10px] text-[#6B7280]">Rejected</span>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

export function DocumentRequestList({
  engagementId,
  clientId: _clientId,
  onCreateClick,
}: DocumentRequestListProps) {
  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: ['document-requests', engagementId],
    queryFn: () => documentRequestsApi.list(engagementId),
  })

  if (isLoading) {
    return (
      <div>
        {Array.from({ length: 3 }).map((_, i) => (
          <div
            key={i}
            className="bg-[#D5D8DE] dark:bg-[#444444] rounded-[8px] h-[72px] mb-[10px] animate-pulse"
          />
        ))}
      </div>
    )
  }

  if (isError) {
    return (
      <div className="flex flex-col items-center justify-center py-24 gap-3">
        <p className="text-[13px] text-[#6B7280]">Failed to load document requests.</p>
        <button
          onClick={() => refetch()}
          className="bg-[#1F3148] dark:bg-[#3A6A94] text-white text-[12px] px-3 py-1.5 rounded-[6px] hover:opacity-90 transition-opacity"
        >
          Retry
        </button>
      </div>
    )
  }

  const requests = data ?? []

  if (requests.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-24 gap-[10px]">
        <div className="w-10 h-10 rounded-[8px] bg-[#EDEEF0] dark:bg-[#383838] border border-[0.5px] border-[#C8CDD6] dark:border-[#484848] flex items-center justify-center">
          <svg width="18" height="18" viewBox="0 0 18 18" fill="none">
            <path
              d="M3 4.5C3 3.67 3.67 3 4.5 3h4.086c.398 0 .78.158 1.06.44l3.915 3.914c.282.281.439.663.439 1.06V13.5C14 14.33 13.33 15 12.5 15h-8C3.67 15 3 14.33 3 13.5v-9z"
              stroke="#6B7280"
              strokeWidth="1.25"
              strokeLinejoin="round"
            />
            <path
              d="M8.5 3v3.5a1 1 0 001 1H13"
              stroke="#6B7280"
              strokeWidth="1.25"
              strokeLinecap="round"
            />
          </svg>
        </div>
        <p className="text-[13px] font-medium text-[#1F3148] dark:text-[#EDEEF0]">
          No document requests yet
        </p>
        <p className="text-[12px] text-[#6B7280] text-center max-w-[240px]">
          Create a checklist to request documents from your client.
        </p>
        <button
          onClick={onCreateClick}
          className="bg-[#1F3148] text-white text-[12px] font-medium px-3 py-1.5 rounded-[6px] hover:opacity-90 transition-opacity"
        >
          + New Request
        </button>
      </div>
    )
  }

  return (
    <div>
      {requests.map((request) => (
        <RequestCard key={request.id} request={request} engagementId={engagementId} />
      ))}
    </div>
  )
}

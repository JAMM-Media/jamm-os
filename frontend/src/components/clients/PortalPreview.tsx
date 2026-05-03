// frontend/src/components/clients/PortalPreview.tsx
'use client'

import { useState } from 'react'
import { useFetch } from '@/lib/hooks/useFetch'
import { portalPreviewApi, PortalPreviewData } from '@/lib/api/portalPreviewApi'
import { FileText, MessageSquare } from 'lucide-react'

interface PortalPreviewProps {
  clientId: string
  clientName: string
}

const PORTAL_TABS = ['To-do', 'Documents', 'Invoices', 'Messages'] as const
type PortalTab = (typeof PORTAL_TABS)[number]

function clientInitials(name: string): string {
  return name
    .split(' ')
    .filter(Boolean)
    .slice(0, 2)
    .map((w) => w[0].toUpperCase())
    .join('')
}

function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
  })
}

function formatDateTime(iso: string): string {
  return new Date(iso).toLocaleString('en-US', {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
  })
}

function formatUSD(amount: number): string {
  return amount.toLocaleString('en-US', { style: 'currency', currency: 'USD' })
}

function docRequestBadge(status: string): string {
  const s = status.toLowerCase()
  if (s === 'pending' || s === 'sent') return 'bg-[#FEF3C7] text-[#92400E]'
  if (s === 'complete' || s === 'completed') return 'bg-[#D1FAE5] text-[#065F46]'
  return 'bg-[#E5E7EB] text-[#1F3148]'
}

function invoiceBadge(status: string): string {
  const s = status.toLowerCase()
  if (s === 'paid') return 'bg-[#D1FAE5] text-[#065F46]'
  if (s === 'overdue') return 'bg-[#FEE2E2] text-[#991B1B]'
  if (s === 'sent' || s === 'unpaid' || s === 'pending') return 'bg-[#FEF3C7] text-[#92400E]'
  return 'bg-[#E5E7EB] text-[#1F3148]'
}

const BADGE_BASE = 'inline-flex items-center rounded-[9999px] px-2 font-medium'
const BADGE_STYLE = { fontSize: 11, height: 22 }

function SkeletonRows() {
  return (
    <>
      {Array.from({ length: 3 }).map((_, i) => (
        <div key={i} className="h-[52px] bg-[#383838] animate-pulse rounded-[8px] mb-2" />
      ))}
    </>
  )
}

export function PortalPreview({ clientId, clientName }: PortalPreviewProps) {
  const [activeTab, setActiveTab] = useState<PortalTab>('To-do')

  const { data: preview, isLoading } = useFetch(
    (): Promise<PortalPreviewData> =>
      portalPreviewApi.get(clientId).then((r) => r.data),
    [clientId]
  )

  const displayName = preview?.client_name ?? clientName
  const firstName = displayName.split(' ')[0] || displayName
  const initials = clientInitials(displayName)
  const documentRequests = preview?.document_requests ?? []
  const documents = preview?.documents ?? []
  const invoices = preview?.invoices ?? []
  const messages = preview?.messages

  return (
    <div className="bg-[#2D2D2D] rounded-[10px] overflow-hidden border border-[0.5px] border-[#484848]">
      {/* Label bar */}
      <div className="bg-[#252525] px-4 py-2 border-b border-[#484848]">
        <span
          style={{ fontSize: 11, letterSpacing: '0.05em' }}
          className="uppercase text-[#9CA3AF]"
        >
          Client Portal Preview
        </span>
      </div>

      {/* Simulated portal top bar */}
      <div className="bg-[#1F3148] px-4 py-3 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span style={{ fontSize: 12 }} className="text-white font-medium">
            {displayName}
          </span>
          <span style={{ fontSize: 10 }} className="text-[#7DA3C4]">
            Client Portal
          </span>
        </div>
        <div
          className="bg-[#3A6A94] rounded-full flex items-center justify-center text-white font-medium"
          style={{ width: 28, height: 28, fontSize: 10 }}
        >
          {initials}
        </div>
      </div>

      {/* Tab row */}
      <div className="bg-[#252525] px-4 flex border-b border-[#484848]">
        {PORTAL_TABS.map((tab) => {
          const isActive = activeTab === tab
          return (
            <button
              key={tab}
              onClick={() => setActiveTab(tab)}
              className="px-4 py-2.5 relative transition-colors"
              style={{
                fontSize: 13,
                color: isActive ? '#EDEEF0' : '#9CA3AF',
                cursor: 'pointer',
              }}
              onMouseEnter={(e) => {
                if (!isActive) (e.currentTarget as HTMLButtonElement).style.color = '#EDEEF0'
              }}
              onMouseLeave={(e) => {
                if (!isActive) (e.currentTarget as HTMLButtonElement).style.color = '#9CA3AF'
              }}
            >
              {tab}
              {isActive && (
                <span className="absolute bottom-0 left-0 right-0 h-[2px] bg-[#4A7FA5]" />
              )}
            </button>
          )
        })}
      </div>

      {/* Content area */}
      <div className="bg-[#2D2D2D] p-4">

        {/* TO-DO TAB */}
        {activeTab === 'To-do' && (
          isLoading ? (
            <SkeletonRows />
          ) : (
            <>
              <p style={{ fontSize: 14 }} className="font-medium text-[#EDEEF0]">
                Hello, {firstName}
              </p>
              <p style={{ fontSize: 11 }} className="text-[#9CA3AF] mt-0.5">
                {documentRequests.length === 0
                  ? 'No action items'
                  : `${documentRequests.length} item${documentRequests.length !== 1 ? 's' : ''} need${documentRequests.length === 1 ? 's' : ''} your attention`}
              </p>

              {documentRequests.length === 0 ? (
                <div className="flex items-center justify-center py-12">
                  <p style={{ fontSize: 13 }} className="text-[#9CA3AF]">
                    Nothing needs attention right now.
                  </p>
                </div>
              ) : (
                <>
                  <p
                    style={{ fontSize: 10, letterSpacing: '0.05em' }}
                    className="uppercase text-[#9CA3AF] mt-4 mb-2"
                  >
                    Action needed
                  </p>
                  {documentRequests.map((req) => (
                    <div
                      key={req.id}
                      className="bg-[#383838] rounded-[8px] mb-2 flex items-center justify-between"
                      style={{ padding: '12px 14px' }}
                    >
                      <div className="flex flex-col gap-1">
                        <span style={{ fontSize: 13 }} className="font-medium text-[#EDEEF0]">
                          {req.title}
                        </span>
                        <span style={{ fontSize: 11 }} className="text-[#9CA3AF]">
                          {req.items_completed} of {req.items_total} items uploaded
                        </span>
                        {req.due_date && (
                          <span style={{ fontSize: 11 }} className="text-[#9CA3AF]">
                            Due {formatDate(req.due_date)}
                          </span>
                        )}
                      </div>
                      <span
                        className={`${BADGE_BASE} ${docRequestBadge(req.status)}`}
                        style={BADGE_STYLE}
                      >
                        {req.status}
                      </span>
                    </div>
                  ))}
                </>
              )}
            </>
          )
        )}

        {/* DOCUMENTS TAB */}
        {activeTab === 'Documents' && (
          <>
            <p
              style={{ fontSize: 10, letterSpacing: '0.05em' }}
              className="uppercase text-[#9CA3AF] mb-3"
            >
              Documents
            </p>
            {isLoading ? (
              <SkeletonRows />
            ) : documents.length === 0 ? (
              <p style={{ fontSize: 12 }} className="text-[#9CA3AF] text-center py-8">
                No documents on file.
              </p>
            ) : (
              documents.map((doc) => (
                <div
                  key={doc.id}
                  className="bg-[#383838] rounded-[8px] p-3 flex items-center justify-between mb-2"
                >
                  <div className="flex items-center gap-2">
                    <FileText style={{ width: 14, height: 14 }} className="text-[#9CA3AF]" />
                    <span style={{ fontSize: 13 }} className="text-[#EDEEF0]">
                      {doc.name}
                    </span>
                  </div>
                  <span style={{ fontSize: 11 }} className="text-[#9CA3AF]">
                    {formatDate(doc.uploaded_at)}
                  </span>
                </div>
              ))
            )}
          </>
        )}

        {/* INVOICES TAB */}
        {activeTab === 'Invoices' && (
          <>
            <p
              style={{ fontSize: 10, letterSpacing: '0.05em' }}
              className="uppercase text-[#9CA3AF] mb-3"
            >
              Invoices
            </p>
            {isLoading ? (
              <SkeletonRows />
            ) : invoices.length === 0 ? (
              <p style={{ fontSize: 12 }} className="text-[#9CA3AF] text-center py-8">
                No invoices yet.
              </p>
            ) : (
              invoices.map((inv) => (
                <div
                  key={inv.id}
                  className="bg-[#383838] rounded-[8px] mb-2 flex items-center justify-between"
                  style={{ padding: '12px 14px' }}
                >
                  <div className="flex flex-col" style={{ gap: 2 }}>
                    <span style={{ fontSize: 13, fontWeight: 500 }} className="text-[#EDEEF0]">
                      {inv.invoice_number}
                    </span>
                    <span style={{ fontSize: 12 }} className="text-[#9CA3AF]">
                      {formatUSD(inv.amount_due)}
                    </span>
                    {inv.due_date && (
                      <span style={{ fontSize: 11 }} className="text-[#9CA3AF]">
                        Due {formatDate(inv.due_date)}
                      </span>
                    )}
                  </div>
                  <span
                    className={`${BADGE_BASE} ${invoiceBadge(inv.status)}`}
                    style={BADGE_STYLE}
                  >
                    {inv.status}
                  </span>
                </div>
              ))
            )}
          </>
        )}

        {/* MESSAGES TAB */}
        {activeTab === 'Messages' && (
          isLoading ? (
            <SkeletonRows />
          ) : !messages || (messages.unread_count === 0 && messages.last_message_at === null) ? (
            <div className="flex flex-col items-center justify-center py-8 gap-3">
              <div
                className="flex items-center justify-center rounded-[8px] bg-[#2A2A2A]"
                style={{ width: 40, height: 40 }}
              >
                <MessageSquare style={{ width: 20, height: 20 }} className="text-[#9CA3AF]" />
              </div>
              <p style={{ fontSize: 13 }} className="font-medium text-[#EDEEF0]">
                No messages yet
              </p>
              <p style={{ fontSize: 12 }} className="text-[#9CA3AF] text-center">
                Messages between your firm and this client will appear here.
              </p>
            </div>
          ) : (
            <div className="bg-[#383838] rounded-[8px] p-4">
              <div className="flex items-center justify-between">
                <span style={{ fontSize: 13 }} className="font-medium text-[#EDEEF0]">
                  Messages
                </span>
                {messages.unread_count > 0 && (
                  <span
                    className="inline-flex items-center rounded-[9999px] bg-[#3A6A94] text-[#EDEEF0] font-medium"
                    style={{ fontSize: 11, height: 20, padding: '0 8px' }}
                  >
                    {messages.unread_count} unread
                  </span>
                )}
              </div>
              {messages.last_message_at && (
                <p style={{ fontSize: 11, marginTop: 8 }} className="text-[#9CA3AF]">
                  Last message {formatDate(messages.last_message_at)}
                </p>
              )}
              <p style={{ fontSize: 11, marginTop: 12 }} className="text-[#6B7280] italic">
                Switch to the Messages tab to view the full conversation.
              </p>
            </div>
          )
        )}

      </div>

      {/* Generated at footer */}
      {preview?.generated_at && (
        <div className="bg-[#2D2D2D] px-4 pb-3">
          <p style={{ fontSize: 10 }} className="text-[#6B7280] text-right mt-3">
            Preview generated {formatDateTime(preview.generated_at)}
          </p>
        </div>
      )}
    </div>
  )
}

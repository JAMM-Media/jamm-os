// path: frontend/src/app/(dashboard)/inbox/page.tsx
'use client'

import { useState, useEffect, useRef, Suspense } from 'react'
import { useRouter, useSearchParams } from 'next/navigation'
import { Mail, X } from 'lucide-react'
import { toast } from 'sonner'
import { cn } from '@/lib/utils'
import api from '@/lib/api'
import Link from 'next/link'

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface ThreadSummary {
  thread_id: string
  subject: string
  from: string
  to: string
  date: string
  message_count: number
  snippet: string
  unread: boolean
  client_id: string | null
  client_name: string | null
}

interface ThreadMessage {
  message_id: string
  from: string
  to: string
  cc: string
  subject: string
  date: string
  body: string
  unread: boolean
}

interface ThreadDetail {
  thread_id: string
  messages: ThreadMessage[]
  provider: string
  client_id: string | null
  client_name: string | null
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function formatDate(raw: string): string {
  if (!raw) return ''
  try {
    const d = new Date(raw)
    const today = new Date()
    if (d.toDateString() === today.toDateString()) {
      return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
    }
    return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' })
  } catch {
    return raw
  }
}

function extractDisplayName(raw: string): string {
  if (!raw) return ''
  const match = raw.match(/^"?([^"<]+)"?\s*</)
  if (match) return match[1].trim()
  return raw.split('@')[0]
}

// ---------------------------------------------------------------------------
// Skeleton loaders
// ---------------------------------------------------------------------------

function ThreadListSkeleton() {
  return (
    <div className="space-y-0 animate-pulse">
      {[...Array(6)].map((_, i) => (
        <div key={i} className="px-3 py-3 border-b border-[#C8CDD6] dark:border-[#484848]">
          <div className="flex items-center justify-between mb-1.5">
            <div className="h-2.5 bg-[#D5D8DE] dark:bg-[#444444] rounded w-2/5" />
            <div className="h-2 bg-[#D5D8DE] dark:bg-[#444444] rounded w-1/6" />
          </div>
          <div className="h-2 bg-[#D5D8DE] dark:bg-[#444444] rounded w-3/4 mb-1" />
          <div className="h-2 bg-[#D5D8DE] dark:bg-[#444444] rounded w-full" />
        </div>
      ))}
    </div>
  )
}

function ThreadDetailSkeleton() {
  return (
    <div className="p-4 space-y-4 animate-pulse">
      <div className="h-4 bg-[#D5D8DE] dark:bg-[#444444] rounded w-2/3" />
      <div className="space-y-3">
        {[...Array(3)].map((_, i) => (
          <div key={i}>
            <div className="h-2.5 bg-[#D5D8DE] dark:bg-[#444444] rounded w-1/4 mb-2" />
            <div className="h-2 bg-[#D5D8DE] dark:bg-[#444444] rounded w-full mb-1" />
            <div className="h-2 bg-[#D5D8DE] dark:bg-[#444444] rounded w-5/6" />
          </div>
        ))}
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Compose modal
// ---------------------------------------------------------------------------

interface ComposeModalProps {
  provider: string
  onClose: () => void
}

function ComposeModal({ provider, onClose }: ComposeModalProps) {
  const [to, setTo] = useState('')
  const [subject, setSubject] = useState('')
  const [body, setBody] = useState('')
  const [sending, setSending] = useState(false)

  const handleSend = async () => {
    if (!to.trim() || !subject.trim() || !body.trim()) return
    setSending(true)
    try {
      await api.post('/api/v1/inbox/compose', { to, subject, body, provider })
      toast.success('Email sent')
      onClose()
    } catch {
      toast.error('Failed to send email')
    } finally {
      setSending(false)
    }
  }

  const inputClass =
    'w-full h-9 px-3 text-[13px] text-[#1F3148] dark:text-[#EDEEF0] bg-surface-input dark:bg-dark-card border border-[#C8CDD6] dark:border-[#484848] rounded-md outline-none focus:border-[#4A7FA5] dark:focus:border-[#4A7FA5] transition-colors placeholder:text-[#9CA3AF]'

  return (
    <div className="fixed inset-0 bg-black/[0.35] z-50 flex items-center justify-center">
      <div className="bg-surface-card dark:bg-dark-card rounded-[10px] border border-[#C8CDD6] dark:border-[#484848] p-6 w-[520px] shadow-xl">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-[15px] font-medium text-[#1F3148] dark:text-[#EDEEF0]">New Email</h2>
          <button
            onClick={onClose}
            className="text-[#6B7280] hover:text-[#1F3148] dark:hover:text-[#EDEEF0] transition-colors"
          >
            <X className="w-4 h-4" />
          </button>
        </div>
        <div className="space-y-3 mb-4">
          <div>
            <label className="block text-[11px] font-medium text-[#1F3148] dark:text-[#EDEEF0] mb-1">To</label>
            <input
              type="email"
              value={to}
              onChange={(e) => setTo(e.target.value)}
              placeholder="recipient@example.com"
              className={inputClass}
              autoFocus
            />
          </div>
          <div>
            <label className="block text-[11px] font-medium text-[#1F3148] dark:text-[#EDEEF0] mb-1">Subject</label>
            <input
              type="text"
              value={subject}
              onChange={(e) => setSubject(e.target.value)}
              placeholder="Subject"
              className={inputClass}
            />
          </div>
          <div>
            <label className="block text-[11px] font-medium text-[#1F3148] dark:text-[#EDEEF0] mb-1">Message</label>
            <textarea
              value={body}
              onChange={(e) => setBody(e.target.value)}
              placeholder="Write your message..."
              rows={6}
              className="w-full px-3 py-2 text-[13px] text-[#1F3148] dark:text-[#EDEEF0] bg-surface-input dark:bg-dark-card border border-[#C8CDD6] dark:border-[#484848] rounded-md outline-none focus:border-[#4A7FA5] dark:focus:border-[#4A7FA5] transition-colors placeholder:text-[#9CA3AF] resize-none"
            />
          </div>
        </div>
        <div className="flex justify-end gap-2">
          <button
            onClick={onClose}
            className="h-9 px-4 text-[13px] text-[#374151] dark:text-[#9CA3AF] hover:bg-[#D5D8DE] dark:hover:bg-dark-card rounded-md transition-colors"
          >
            Cancel
          </button>
          <button
            onClick={handleSend}
            disabled={sending || !to.trim() || !subject.trim() || !body.trim()}
            className="h-9 px-4 text-[13px] font-medium text-white bg-brand dark:bg-brand-btn rounded-md hover:opacity-90 disabled:opacity-50 disabled:cursor-not-allowed transition-opacity"
          >
            {sending ? 'Sending...' : 'Send'}
          </button>
        </div>
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------

function InboxContent() {
  const router = useRouter()
  const searchParams = useSearchParams()
  const initialThreadId = searchParams.get('thread_id')
  const initialProvider = searchParams.get('provider') ?? 'gmail'

  const [provider, setProvider] = useState<'gmail' | 'outlook'>(
    initialProvider === 'outlook' ? 'outlook' : 'gmail'
  )
  const [threads, setThreads] = useState<ThreadSummary[]>([])
  const [threadsLoading, setThreadsLoading] = useState(false)
  const [noIntegration, setNoIntegration] = useState(false)
  const [nextPageToken, setNextPageToken] = useState<string | null>(null)

  const [activeThreadId, setActiveThreadId] = useState<string | null>(initialThreadId)
  const [threadDetail, setThreadDetail] = useState<ThreadDetail | null>(null)
  const [detailLoading, setDetailLoading] = useState(false)

  const [replyBody, setReplyBody] = useState('')
  const [replySending, setReplySending] = useState(false)

  const [showCompose, setShowCompose] = useState(false)

  const replyRef = useRef<HTMLTextAreaElement>(null)

  // Fetch thread list on provider change
  useEffect(() => {
    setThreads([])
    setActiveThreadId(null)
    setThreadDetail(null)
    setNoIntegration(false)
    setNextPageToken(null)
    fetchThreads()
  }, [provider])

  // Load thread from URL param
  useEffect(() => {
    if (initialThreadId && threads.length > 0) {
      loadThread(initialThreadId)
    }
  }, [initialThreadId, threads.length])

  async function fetchThreads(pageToken?: string) {
    setThreadsLoading(true)
    try {
      const params = new URLSearchParams({ provider })
      if (pageToken) params.set('page_token', pageToken)
      const res = await api.get(`/api/v1/inbox/threads?${params}`)
      const data = res.data
      setThreads((prev) => (pageToken ? [...prev, ...data.threads] : data.threads))
      setNextPageToken(data.next_page_token ?? null)
      setNoIntegration(false)
    } catch (err: unknown) {
      const status = (err as { response?: { status?: number } })?.response?.status
      if (status === 404) {
        setNoIntegration(true)
      } else {
        toast.error('Failed to load inbox')
      }
    } finally {
      setThreadsLoading(false)
    }
  }

  async function loadThread(threadId: string) {
    setActiveThreadId(threadId)
    setDetailLoading(true)
    setThreadDetail(null)
    try {
      const res = await api.get(`/api/v1/inbox/threads/${threadId}?provider=${provider}`)
      setThreadDetail(res.data)
      // Mark as read in local state
      setThreads((prev) =>
        prev.map((t) => (t.thread_id === threadId ? { ...t, unread: false } : t))
      )
    } catch {
      toast.error('Failed to load thread')
    } finally {
      setDetailLoading(false)
    }
  }

  async function handleReply() {
    if (!replyBody.trim() || !threadDetail) return
    const firstMsg = threadDetail.messages[0]
    setReplySending(true)
    try {
      await api.post('/api/v1/inbox/reply', {
        thread_id: threadDetail.thread_id,
        to: firstMsg.from,
        subject: firstMsg.subject,
        body: replyBody.trim(),
        provider,
      })
      toast.success('Reply sent')
      setReplyBody('')
      // Reload thread to show sent message
      await loadThread(threadDetail.thread_id)
    } catch {
      toast.error('Failed to send reply')
    } finally {
      setReplySending(false)
    }
  }

  // ---------------------------------------------------------------------------
  // Render
  // ---------------------------------------------------------------------------

  return (<>
      <div className="flex h-full overflow-hidden">

        {/* ── Left panel: thread list ──────────────────────────────────────── */}
        <div
          className="flex-shrink-0 flex flex-col border-r border-[#C8CDD6] dark:border-[#484848] h-full bg-surface-page dark:bg-dark-page"
          style={{ width: '280px' }}
        >
          {/* Header */}
          <div className="px-3.5 pt-4 pb-2 flex-shrink-0">
            <div className="flex items-center justify-between mb-2">
              <h2 className="text-[13px] font-medium text-[#1F3148] dark:text-[#EDEEF0]">Inbox</h2>
              <button
                onClick={() => setShowCompose(true)}
                className="text-[11px] font-medium text-[#4A7FA5] hover:underline"
              >
                + Compose
              </button>
            </div>
            {/* Provider toggle */}
            <div className="flex gap-1">
              {(['gmail', 'outlook'] as const).map((p) => (
                <button
                  key={p}
                  onClick={() => setProvider(p)}
                  className={cn(
                    'flex-1 h-7 text-[11px] font-medium rounded-md transition-colors',
                    provider === p
                      ? 'bg-brand dark:bg-brand-btn text-white'
                      : 'text-[#6B7280] border border-[#C8CDD6] dark:border-[#484848] hover:bg-[#D5D8DE] dark:hover:bg-dark-card'
                  )}
                >
                  {p === 'gmail' ? 'Gmail' : 'Outlook'}
                </button>
              ))}
            </div>
          </div>

          {/* Thread list */}
          <div className="flex-1 overflow-y-auto">
            {noIntegration ? (
              <div className="flex flex-col items-center justify-center h-full px-4 text-center gap-3">
                <Mail className="w-8 h-8 text-[#6B7280]" />
                <p className="text-[13px] text-[#374151] dark:text-[#9CA3AF]">
                  Connect Gmail or Outlook in Settings to see your inbox.
                </p>
                <Link
                  href="/settings?tab=my_integrations"
                  className="text-[12px] font-medium text-[#4A7FA5] hover:underline"
                >
                  Go to My Integrations
                </Link>
              </div>
            ) : threadsLoading && threads.length === 0 ? (
              <ThreadListSkeleton />
            ) : threads.length === 0 ? (
              <div className="flex items-center justify-center h-full">
                <p className="text-[13px] text-[#6B7280]">Your inbox is empty.</p>
              </div>
            ) : (
              <>
                {threads.map((thread) => {
                  const isActive = thread.thread_id === activeThreadId
                  return (
                    <button
                      key={thread.thread_id}
                      onClick={() => loadThread(thread.thread_id)}
                      className={cn(
                        'w-full text-left px-3 py-3 border-b border-[#C8CDD6] dark:border-[#484848] transition-colors flex gap-2',
                        isActive
                          ? 'bg-[#EFF6FF] dark:bg-[#1e2a3a]'
                          : 'hover:bg-[#F3F4F6] dark:hover:bg-dark-card'
                      )}
                    >
                      {/* Unread dot */}
                      <div className="flex-shrink-0 pt-1.5">
                        {thread.unread ? (
                          <div className="w-1.5 h-1.5 rounded-full bg-[#4A7FA5]" />
                        ) : (
                          <div className="w-1.5 h-1.5" />
                        )}
                      </div>

                      <div className="flex-1 min-w-0">
                        <div className="flex items-center justify-between gap-1 mb-0.5">
                          <span
                            className={cn(
                              'text-[12px] truncate',
                              thread.unread
                                ? 'font-semibold text-[#1F3148] dark:text-[#EDEEF0]'
                                : 'font-normal text-[#374151] dark:text-[#9CA3AF]'
                            )}
                          >
                            {extractDisplayName(thread.from) || thread.from}
                          </span>
                          <span className="text-[11px] text-[#6B7280] flex-shrink-0">
                            {formatDate(thread.date)}
                          </span>
                        </div>
                        <p className="text-[12px] text-[#374151] dark:text-[#9CA3AF] truncate mb-0.5">
                          {thread.subject}
                        </p>
                        <p className="text-[11px] text-[#6B7280] truncate">
                          {thread.snippet}
                        </p>
                        {thread.client_name && (
                          <span className="inline-block mt-1 px-1.5 py-0.5 rounded-full text-[10px] font-medium bg-[#EFF6FF] dark:bg-[#1e2a3a] text-[#4A7FA5] border border-[#BFDBFE] dark:border-[#2a3d5a]">
                            {thread.client_name}
                          </span>
                        )}
                      </div>
                    </button>
                  )
                })}

                {nextPageToken && (
                  <button
                    onClick={() => fetchThreads(nextPageToken)}
                    disabled={threadsLoading}
                    className="w-full py-2.5 text-[12px] text-[#4A7FA5] hover:underline disabled:opacity-50"
                  >
                    {threadsLoading ? 'Loading...' : 'Load more'}
                  </button>
                )}
              </>
            )}
          </div>
        </div>

        {/* ── Right panel: thread detail ───────────────────────────────────── */}
        <div className="flex-1 flex flex-col h-full overflow-hidden bg-surface-page dark:bg-dark-page">
          {!activeThreadId ? (
            <div className="flex-1 flex items-center justify-center">
              <p className="text-[13px] text-[#6B7280]">Select a conversation to read it.</p>
            </div>
          ) : detailLoading ? (
            <div className="flex-1 overflow-y-auto">
              <ThreadDetailSkeleton />
            </div>
          ) : threadDetail ? (
            <>
              {/* Thread header */}
              <div className="flex-shrink-0 px-5 pt-4 pb-3 border-b border-[#C8CDD6] dark:border-[#484848]">
                <div className="flex items-start gap-2">
                  <h2 className="text-[14px] font-medium text-[#1F3148] dark:text-[#EDEEF0] flex-1 min-w-0">
                    {threadDetail.messages[0]?.subject || '(no subject)'}
                  </h2>
                  {threadDetail.client_name && threadDetail.client_id && (
                    <Link
                      href={`/clients/${threadDetail.client_id}`}
                      className="flex-shrink-0 px-2 py-0.5 rounded-full text-[11px] font-medium bg-[#EFF6FF] dark:bg-[#1e2a3a] text-[#4A7FA5] border border-[#BFDBFE] dark:border-[#2a3d5a] hover:underline"
                    >
                      {threadDetail.client_name}
                    </Link>
                  )}
                  {threadDetail.client_name && !threadDetail.client_id && (
                    <span className="flex-shrink-0 px-2 py-0.5 rounded-full text-[11px] font-medium bg-[#EFF6FF] dark:bg-[#1e2a3a] text-[#4A7FA5] border border-[#BFDBFE] dark:border-[#2a3d5a]">
                      {threadDetail.client_name}
                    </span>
                  )}
                </div>
              </div>

              {/* Messages */}
              <div className="flex-1 overflow-y-auto px-5 py-4 space-y-4">
                {threadDetail.messages.map((msg, idx) => (
                  <div key={msg.message_id}>
                    {/* Message header */}
                    <div className="flex items-baseline gap-2 mb-1 flex-wrap">
                      <span className="text-[12px] font-medium text-[#1F3148] dark:text-[#EDEEF0]">
                        {msg.from || '(unknown sender)'}
                      </span>
                      {msg.to && (
                        <span className="text-[11px] text-[#6B7280]">
                          to {msg.to}
                        </span>
                      )}
                      <span className="text-[11px] text-[#6B7280] ml-auto">
                        {formatDate(msg.date)}
                      </span>
                    </div>

                    {/* Message body */}
                    <pre
                      className="text-[13px] text-[#374151] dark:text-[#9CA3AF] whitespace-pre-wrap break-words font-sans leading-relaxed"
                    >
                      {msg.body || '(no content)'}
                    </pre>

                    {idx < threadDetail.messages.length - 1 && (
                      <div className="mt-4 border-b border-[#C8CDD6] dark:border-[#484848]" />
                    )}
                  </div>
                ))}
              </div>

              {/* Reply compose */}
              <div className="flex-shrink-0 border-t border-[#C8CDD6] dark:border-[#484848] px-4 py-3">
                <div className="flex items-end gap-2">
                  <textarea
                    ref={replyRef}
                    value={replyBody}
                    onChange={(e) => setReplyBody(e.target.value)}
                    placeholder="Write a reply..."
                    rows={2}
                    className="flex-1 resize-none bg-surface-input dark:bg-dark-page border border-[#C8CDD6] dark:border-[#484848] focus:border-[#4A7FA5] dark:focus:border-[#4A7FA5] rounded-lg px-3 py-2 text-[13px] text-[#374151] dark:text-[#9CA3AF] placeholder:text-[#9CA3AF] outline-none transition-colors"
                    style={{ minHeight: '40px', maxHeight: '120px' }}
                  />
                  <button
                    onClick={handleReply}
                    disabled={replySending || !replyBody.trim()}
                    className="bg-brand dark:bg-brand-btn text-white text-[12px] font-medium rounded-md h-9 px-4 transition-opacity disabled:opacity-50 disabled:cursor-not-allowed hover:opacity-90 flex-shrink-0"
                  >
                    {replySending ? 'Sending...' : 'Send'}
                  </button>
                </div>
              </div>
            </>
          ) : null}
        </div>
      </div>

      {showCompose && (
        <ComposeModal provider={provider} onClose={() => setShowCompose(false)} />
      )}
  </>)
}

export default function InboxPage() {
  return (
    <Suspense fallback={<div />}>
      <InboxContent />
    </Suspense>
  )
}

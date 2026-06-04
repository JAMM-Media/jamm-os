// frontend/src/components/concierge/ConciergePanel.tsx
'use client'

import { useState, useRef, useEffect, useCallback } from 'react'
import { useRouter, usePathname } from 'next/navigation'
import { X, Send, Zap } from 'lucide-react'
import ReactMarkdown from 'react-markdown'
import { useAuth } from '@/lib/hooks/useAuth'
import api from '@/lib/api'
import {
  emitConciergeAction,
  type ConciergeAction,
} from '@/lib/events/conciergeEvents'

interface Message {
  role: 'user' | 'concierge'
  content: string
  actionConfirm?: string
}

interface Notification {
  id: string
  trigger_type: string
  message: string
  created_at: string
}

interface ConciergePanelProps {
  isOpen: boolean
  onClose: () => void
}

const PAGE_LABELS: Record<string, string> = {
  '/clients': 'Clients',
  '/settings/team': 'Settings',
  '/settings/integrations': 'Settings',
  '/settings/billing': 'Settings',
  '/engagements/templates': 'Templates',
}

const MODAL_LABELS: Record<string, string> = {
  'new-client': 'New Client form',
  'new-engagement': 'New Engagement form',
  'invite-staff': 'Invite Team Member form',
  'portal-magic-link': 'Send Magic-Link',
  'new-template': 'New Template form',
  'quickbooks-scroll': 'QuickBooks connection',
  'stripe-scroll': 'Stripe connection',
}

function buildActionConfirm(action: ConciergeAction): string {
  const page =
    action.route
      ? PAGE_LABELS[action.route] ??
        (action.route.startsWith('/clients/') ? 'Client' : action.route)
      : ''
  const form = action.modal ? MODAL_LABELS[action.modal] ?? action.modal : ''
  if (page && form) return `Navigating to ${page} and opening the ${form}.`
  return ''
}

export function ConciergePanel({ isOpen, onClose }: ConciergePanelProps) {
  const router = useRouter()
  const pathname = usePathname()
  const PAGE_LABELS: Record<string, string> = {
    '/dashboard': 'Dashboard',
    '/clients': 'Clients',
    '/engagements': 'Engagements',
    '/tasks': 'Tasks',
    '/documents': 'Documents',
    '/billing': 'Billing',
    '/settings': 'Settings',
    '/firm-chat': 'Firm Chat',
  }
  const currentPage = Object.entries(PAGE_LABELS).find(([k]) => pathname.startsWith(k))?.[1] ?? 'JAMM PX'
  const { user } = useAuth()
  const logoUrl = user ? `/api/backend/firms/logo/${user.firm_id}` : null
  const initials =
    user?.full_name?.split(' ').map((n) => n[0]).join('').slice(0, 2).toUpperCase() ?? '?'

  const [messages, setMessages] = useState<Message[]>(() => {
    if (typeof window !== 'undefined') {
      try {
        const stored = sessionStorage.getItem('jamm_concierge_messages')
        if (stored) return JSON.parse(stored) as Message[]
      } catch {
        // ignore parse errors
      }
    }
    return []
  })
  const [notifications, setNotifications] = useState<Notification[]>([])
  const [input, setInput] = useState('')
  const [streaming, setStreaming] = useState(false)
  const [autopilotOn, setAutopilotOn] = useState(() => {
    if (typeof window !== 'undefined') {
      return sessionStorage.getItem('jamm_concierge_autopilot') === 'true'
    }
    return false
  })
  const [suggestions, setSuggestions] = useState<string[]>([])
  const [formDirty, setFormDirtyState] = useState(false)
  const [statusMessage, setStatusMessage] = useState('')

  // Keep a ref so the async sendMessages callback always reads current value.
  const autopilotRef = useRef(false)
  useEffect(() => { autopilotRef.current = autopilotOn }, [autopilotOn])
  useEffect(() => {
    const pending = sessionStorage.getItem('jamm_concierge_status')
    if (pending) {
      sessionStorage.removeItem('jamm_concierge_status')
      setStatusMessage(pending)
    }
  }, [])
  const pendingActionRef = useRef<ConciergeAction | null>(null)

  const messagesEndRef = useRef<HTMLDivElement>(null)
  const textareaRef = useRef<HTMLTextAreaElement>(null)
  const hasInitialized = useRef(false)

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])
  useEffect(() => {
    if (typeof window !== 'undefined') {
      try {
        sessionStorage.setItem('jamm_concierge_messages', JSON.stringify(messages))
      } catch {
        // ignore storage errors
      }
    }
  }, [messages])

  // Reset autopilot when panel closes (session-only per spec).
  useEffect(() => {
    if (!isOpen) {
      setAutopilotOn(false)
      autopilotRef.current = false
      sessionStorage.removeItem('jamm_concierge_autopilot')
      sessionStorage.removeItem('jamm_concierge_messages')
      setMessages([])
    }
  }, [isOpen])

  useEffect(() => {
    const handler = (e: Event) => {
      setFormDirtyState((e as CustomEvent<{ dirty: boolean }>).detail.dirty)
    }
    window.addEventListener('jamm:form-dirty', handler)
    return () => window.removeEventListener('jamm:form-dirty', handler)
  }, [])

  // Auto-clear status message after 2 seconds.
  useEffect(() => {
    if (!statusMessage) return
    const timer = setTimeout(() => setStatusMessage(''), 2000)
    return () => clearTimeout(timer)
  }, [statusMessage])

  const fetchNotifications = useCallback(async () => {
    try {
      const res = await api.get('/concierge/notifications')
      setNotifications((prev) => {
        const existing = new Set(prev.map((n) => n.id))
        const incoming = (res.data.items ?? []) as Notification[]
        const fresh = incoming.filter((n) => !existing.has(n.id))
        return fresh.length > 0 ? [...prev, ...fresh] : prev
      })
    } catch {
      // non-fatal
    }
  }, [])

  const dismissNotification = useCallback(async (id: string) => {
    setNotifications((prev) => prev.filter((n) => n.id !== id))
    try {
      await api.patch(`/concierge/notifications/${id}/read`)
    } catch {
      // already removed from UI
    }
  }, [])

  const sendMessages = useCallback(
    async (thread: Message[]) => {
      setStreaming(true)
      setMessages((prev) => [...prev, { role: 'concierge', content: '' }])

      const token = localStorage.getItem('access_token')
      const headers: Record<string, string> = { 'Content-Type': 'application/json' }
      if (token) headers['Authorization'] = `Bearer ${token}`

      const apiMessages = thread.map((m) => ({
        role: m.role === 'concierge' ? 'assistant' : 'user',
        content: m.content,
      }))

      let assembled = ''

      try {
        const res = await fetch('/api/backend/concierge/chat', {
          method: 'POST',
          headers,
          body: JSON.stringify({
            messages: apiMessages,
            autopilot_enabled: autopilotRef.current,
          }),
        })

        if (!res.ok || !res.body) {
          setMessages((prev) => {
            const updated = [...prev]
            updated[updated.length - 1] = {
              role: 'concierge',
              content: 'Something went wrong. Please try again.',
            }
            return updated
          })
          return
        }

        const reader = res.body.getReader()
        const decoder = new TextDecoder()
        let buffer = ''

        while (true) {
          const { done, value } = await reader.read()
          if (done) {
            buffer += decoder.decode()
            if (buffer.startsWith('data: ')) {
              const chunk = buffer.slice(6)
              if (chunk) {
                assembled += chunk + '\n'
              }
            }
            break
          }
          buffer += decoder.decode(value, { stream: true })
          const lines = buffer.split('\n')
          buffer = lines.pop() ?? ''
          for (const line of lines) {
            if (line.startsWith('data:')) {
              const chunk = line.replace(/^data:\s*/, '')
              assembled += chunk + '\n'
            }
          }
        }

        const cleanContent = handleConciergeAction(assembled)
        setMessages((prev) => {
          const updated = [...prev]
          const last = updated[updated.length - 1]
          if (last.role === 'concierge') {
            updated[updated.length - 1] = {
              role: 'concierge',
              content: cleanContent,
            }
          }
          return updated
        })
        if (pendingActionRef.current) {
          const action = pendingActionRef.current
          pendingActionRef.current = null
          void executeAction(action)
        }
        const lower = assembled.toLowerCase()
        const chips: string[] = []
        if (lower.includes('client') || lower.includes('import')) {
          chips.push('Go to Clients', 'Import clients')
        } else if (lower.includes('engagement')) {
          chips.push('Go to Engagements', 'New engagement')
        } else if (lower.includes('settings') || lower.includes('team') || lower.includes('staff')) {
          chips.push('Go to Settings')
        } else if (lower.includes('billing') || lower.includes('invoice') || lower.includes('stripe')) {
          chips.push('Go to Billing')
        } else if (lower.includes('document')) {
          chips.push('Go to Documents')
        } else {
          chips.push('Go to Dashboard')
        }
        setSuggestions(chips.slice(0, 3))
      } catch {
        setMessages((prev) => {
          const updated = [...prev]
          updated[updated.length - 1] = {
            role: 'concierge',
            content: 'Something went wrong. Please try again.',
          }
          return updated
        })
      } finally {
        setStreaming(false)
      }
    },
    [router],
  )

  useEffect(() => {
    if (isOpen && !hasInitialized.current) {
      hasInitialized.current = true
      if (messages.length === 0) {
        if (!user?.firm_type) {
          setMessages([{
            role: 'concierge',
            content: 'Welcome to JAMM Concierge. Before we start -- what does your firm do most? This lets me point you to the right setup path.\n\n1. Tax prep and returns\n2. Bookkeeping and monthly close\n3. Advisory and planning',
          }])
        } else {
          sendMessages([{ role: 'user', content: '__OPEN__' }])
        }
      }
    }
    if (isOpen) {
      setTimeout(() => textareaRef.current?.focus(), 250)
      api.post('/concierge/trigger-check').then(() => fetchNotifications()).catch(() => fetchNotifications())
    }
  }, [isOpen, sendMessages, fetchNotifications, user])

  async function handleSend(text?: string) {
    const msg = (text ?? input).trim()
    if (!msg || streaming) return
    setInput('')
    setSuggestions([])
    const userMsg: Message = { role: 'user', content: msg }
    const newThread = [...messages, userMsg]
    setMessages(newThread)
    await sendMessages(newThread)
  }

  function handleSuggestion(label: string) {
    const routes: Record<string, string> = {
      'Go to Clients': '/clients',
      'Go to Engagements': '/engagements',
      'Go to Settings': '/settings',
      'Go to Billing': '/billing',
      'Go to Documents': '/documents',
      'Go to Dashboard': '/dashboard',
      'Import clients': '/clients',
      'New engagement': '/engagements',
    }
    const route = routes[label]
    if (route) setTimeout(() => router.push(route), 0)
  }

  function handleConciergeAction(raw: string): string {
    const ACTION_MARKER = 'CONCIERGE_ACTION:'
    const actionIndex = raw.indexOf(ACTION_MARKER)
    if (actionIndex === -1) return raw

    const beforeAction = raw.slice(0, actionIndex).trim()
    const afterMarker = raw.slice(actionIndex + ACTION_MARKER.length)
    const braceStart = afterMarker.indexOf('{')
    const braceEnd = afterMarker.lastIndexOf('}')
    if (braceStart === -1 || braceEnd === -1) return beforeAction
    const actionLine = afterMarker.slice(braceStart, braceEnd + 1).replace(/\s+/g, ' ').trim()

    if (!autopilotRef.current) {
      return beforeAction || 'To navigate, turn on Autopilot using the toggle above.'
    }

    try {
      const action: ConciergeAction = JSON.parse(actionLine)
      pendingActionRef.current = action
    } catch {}

    return beforeAction || ''
  }

  async function executeAction(action: ConciergeAction) {
    if (action.type === 'set_firm_type' && action.firm_type) {
      try {
        await api.patch('/firms/me/concierge', { firm_type: action.firm_type })
        setStatusMessage('Practice type saved')
      } catch {
        // non-fatal -- firm_type will be set on next reload
      }
      return
    }
    const normalizedType = (action.type as string) === 'open_modal' ? 'open-modal' :
      (action.type as string) === 'navigate_and_open' ? 'navigate-and-open' : action.type
    const normalizedRoute = (action.route === '/settings/team' ? '/settings' : action.route) as string
    const routeToLabel: Record<string, string> = {
      '/clients': 'Navigated to Clients',
      '/settings/team': 'Navigated to Team Settings',
      '/engagements/templates': 'Navigated to Engagement Templates',
      '/settings/integrations': 'Navigated to Integrations',
      '/settings/billing': 'Navigated to Billing',
    }

    if (action.route) {
      const clientMatch = normalizedRoute.match(/^\/clients\/([^/?]+)(\?.*)?$/)
      if (clientMatch) {
        const queryString = clientMatch[2] ?? ''
        const name = decodeURIComponent(clientMatch[1]).replace(/-/g, ' ').replace(/\s+/g, ' ').trim()
        const isUUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(name)
        if (!isUUID) {
          const token = localStorage.getItem('access_token')
          const fetchHeaders: Record<string, string> = {}
          if (token) fetchHeaders['Authorization'] = `Bearer ${token}`
          try {
            const res = await fetch(
              `/api/backend/concierge/clients/resolve?name=${encodeURIComponent(name)}`,
              { headers: fetchHeaders }
            )
            if (!res.ok) {
              setStatusMessage('Could not find client')
              return
            }
            const data = await res.json() as { id?: string; name?: string }
            if (!data.id) {
              setStatusMessage('Could not find client')
              return
            }
            const capitalized = (data.name ?? name).replace(/\b\w/g, c => c.toUpperCase())
            const resolvedRoute = `/clients/${data.id}${queryString}`
            if (formDirty) {
              const ok = window.confirm('You have unsaved changes. Navigate away?')
              if (!ok) return
            }
            sessionStorage.setItem('jamm_concierge_status', `Navigated to ${capitalized}`)
            sessionStorage.setItem('jamm_concierge_pending', JSON.stringify({ ...action, route: resolvedRoute, _ts: Date.now() }))
            router.push(resolvedRoute)
            setStatusMessage(`Navigated to ${capitalized}`)
          } catch {
            setStatusMessage('Could not find client')
          }
          return
        }
      }

      const navLabel = routeToLabel[normalizedRoute] ?? `Navigated to ${normalizedRoute}`
      if (formDirty) {
        const ok = window.confirm('You have unsaved changes. Navigate away?')
        if (!ok) return
      }
      sessionStorage.setItem('jamm_concierge_status', navLabel)
      router.push(normalizedRoute)
      setStatusMessage(navLabel)
    }

    const modalLabel: Record<string, string> = {
      'new-client': 'Opened New Client drawer',
      'new-engagement': 'Opened New Engagement drawer',
      'invite-staff': 'Opened Invite Staff modal',
      'new-template': 'Opened New Template drawer',
    }
    if (action.modal && action.route) {
      const alreadyOnRoute = pathname.startsWith(normalizedRoute)
      if (alreadyOnRoute) {
        emitConciergeAction(action)
      } else {
        sessionStorage.setItem('jamm_concierge_pending', JSON.stringify({ ...action, route: normalizedRoute, _ts: Date.now() }))
      }
      setStatusMessage(modalLabel[action.modal ?? ''] ?? 'Opened modal')
    } else if (action.modal) {
      emitConciergeAction(action)
      setStatusMessage(modalLabel[action.modal ?? ''] ?? 'Opened modal')
    } else if (action.route) {
      emitConciergeAction(action)
    }
  }

  function handleKeyDown(e: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }

  function handleInput(e: React.FormEvent<HTMLTextAreaElement>) {
    const el = e.currentTarget
    el.style.height = 'auto'
    el.style.height = Math.min(el.scrollHeight, 96) + 'px'
  }

  return (
    <>
      {isOpen && (
        <div
          onClick={onClose}
          style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.25)', zIndex: 39 }}
        />
      )}

      <div
        style={{
          position: 'fixed',
          right: 0,
          top: 0,
          width: 400,
          height: '100vh',
          zIndex: 40,
          transform: isOpen ? 'translateX(0)' : 'translateX(100%)',
          transition: 'transform 200ms ease-out',
          display: 'flex',
          flexDirection: 'column',
        }}
        className="bg-[#EDEEF0] dark:bg-[#383838] border-l border-[0.5px] border-[#C8CDD6] dark:border-[#484848]"
      >
        {/* Header */}
        <div
          className="flex items-center justify-between px-4 border-b border-[0.5px] border-[#C8CDD6] dark:border-[#484848] flex-shrink-0"
          style={{ height: 48 }}
        >
          <div className="flex items-center gap-2">
            {logoUrl ? (
              <img
                src={logoUrl}
                alt="Firm logo"
                className="h-6 w-auto object-contain rounded-sm"
                onError={(e) => { e.currentTarget.style.display = 'none' }}
              />
            ) : (
              <div className="h-6 w-6 rounded-sm bg-[#3A6A94] flex items-center justify-center flex-shrink-0">
                <span className="text-[10px] font-medium text-white">{initials}</span>
              </div>
            )}
            <span className="text-[14px] font-medium text-[#1F3148] dark:text-[#EDEEF0]">
              JAMM Concierge
            </span>
          </div>

          <div className="flex items-center gap-2">
            {/* Autopilot toggle */}
            <div className="relative group">
              <button
                onClick={() => {
                  const next = !autopilotOn
                  setAutopilotOn(next)
                  sessionStorage.setItem('jamm_concierge_autopilot', String(next))
                  autopilotRef.current = next
                }}
                className={`flex items-center gap-1 text-[11px] font-medium px-2 py-1 rounded-[4px] border border-[0.5px] transition-all duration-150 ${
                  autopilotOn
                    ? 'border-[#1F3148] bg-[#1F3148] text-white dark:border-[#4A7FA5] dark:bg-[#4A7FA5]'
                    : 'border-[#C8CDD6] dark:border-[#484848] bg-transparent text-[#6B7280] dark:text-[#9CA3AF] hover:border-[#1F3148] hover:text-[#1F3148] dark:hover:border-[#4A7FA5] dark:hover:text-[#4A7FA5]'
                }`}
              >
                <Zap className={`h-3 w-3 transition-all ${autopilotOn ? 'fill-white stroke-white' : 'fill-none'}`} />
                Autopilot
              </button>
            </div>

            <button
              onClick={onClose}
              aria-label="Close concierge panel"
              className="text-[#6B7280] hover:text-[#1F3148] dark:hover:text-[#EDEEF0] transition-colors"
            >
              <X className="h-4 w-4" />
            </button>
          </div>
        </div>

        {autopilotOn && (
          <div className="px-4 py-1 bg-[#EBF4FB] dark:bg-[#1a3a52] border-b border-[0.5px] border-[#C8CDD6] dark:border-[#484848]">
            <p className="text-[11px] text-[#4A7FA5] dark:text-[#7ab8d8]">Autopilot on. I'll navigate for you.</p>
          </div>
        )}

        {/* Notification cards */}
        {notifications.length > 0 && (
          <div className="flex flex-col gap-2 px-4 pt-3 flex-shrink-0">
            {notifications.map((n) => (
              <div
                key={n.id}
                className="flex items-start gap-2 bg-white dark:bg-[#2D2D2D] border border-[0.5px] border-[#C8CDD6] dark:border-[#484848] rounded-[8px] px-3 py-2.5 cursor-pointer hover:bg-[#E4E6EA] dark:hover:bg-[#333333] transition-colors"
                onClick={() => { dismissNotification(n.id); handleSend(n.message) }}
              >
                <p className="flex-1 text-[12px] leading-[1.5] text-[#1F3148] dark:text-[#EDEEF0]">
                  {n.message}
                </p>
                <button
                  onClick={(e) => { e.stopPropagation(); dismissNotification(n.id) }}
                  aria-label="Dismiss notification"
                  className="flex-shrink-0 text-[#6B7280] hover:text-[#1F3148] dark:hover:text-[#EDEEF0] transition-colors mt-0.5"
                >
                  <X className="h-3.5 w-3.5" />
                </button>
              </div>
            ))}
          </div>
        )}

        {/* Message feed */}
        <div className="flex-1 overflow-y-auto p-4 flex flex-col gap-3">

          {/* Opening message fires automatically via __OPEN__ sentinel on first open */}

          {messages.map((msg, i) => (
            <div key={i}>
            <div className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'} items-start gap-2`}>
              {msg.role === 'concierge' && (
                <div className="flex-shrink-0 w-6 h-6 rounded-full bg-[#1F3148] flex items-center justify-center mt-1">
                  <span className="text-[9px] font-medium text-white">JC</span>
                </div>
              )}
              <div
                className={`text-[13px] leading-[1.6] px-3 py-2 rounded-[12px] max-w-[75%] ${msg.role === 'user' ? 'text-white' : ''}`}
                style={
                  msg.role === 'user'
                    ? { background: '#1F3148', color: '#FFFFFF' }
                    : { background: '#E4E6EA', color: '#1F3148' }
                }
              >
                {msg.content ? (
                  <div className={`prose prose-sm max-w-none text-[13px] ${msg.role === 'user' ? 'text-white' : 'text-[#374151] dark:text-[#9CA3AF]'}`}>
                    <ReactMarkdown
                      components={{
                        ul: ({node, ...props}) => <ul className="list-disc list-outside ml-4 my-1 space-y-0.5" {...props} />,
                        ol: ({node, ...props}) => <ol className="list-decimal list-outside ml-4 my-1 space-y-0.5" {...props} />,
                        li: ({node, ...props}) => <li className="leading-snug" {...props} />,
                        p: ({node, ...props}) => <p className="mb-1 last:mb-0" {...props} />,
                        strong: ({node, ...props}) => <strong className="font-medium text-[#1F3148] dark:text-[#EDEEF0]" {...props} />,
                      }}
                    >
                      {msg.content}
                    </ReactMarkdown>
                  </div>
                ) : streaming && i === messages.length - 1 ? (
                  <span className="text-[13px] text-[#6B7280] animate-pulse">Thinking...</span>
                ) : null}
                {msg.actionConfirm && (
                  <p className="text-[11px] text-[#6B7280] mt-1 italic">{msg.actionConfirm}</p>
                )}
              </div>
            </div>
            {!autopilotOn && suggestions.length > 0 && i === messages.length - 1 && msg.role === 'concierge' && (
              <div className="flex flex-wrap gap-2 mt-2 ml-8">
                {suggestions.map((s) => (
                  <button
                    key={s}
                    onClick={() => handleSuggestion(s)}
                    className="text-[11px] font-medium px-3 py-1.5 rounded-full border border-[#C8CDD6] dark:border-[#484848] text-[#1F3148] dark:text-[#EDEEF0] bg-white dark:bg-[#2D2D2D] hover:border-[#4A7FA5] hover:text-[#4A7FA5] transition-colors"
                  >
                    {s}
                  </button>
                ))}
              </div>
            )}
            </div>
          ))}
          <p
            className={`text-[11px] text-[#6B7280] text-center transition-opacity duration-500 ${statusMessage ? 'opacity-100' : 'opacity-0'}`}
            style={{ minHeight: 16 }}
          >
            {statusMessage}
          </p>
          <div ref={messagesEndRef} />
        </div>

        {currentPage && (
          <div className="px-3 pt-2 pb-0">
            <span className="inline-flex items-center gap-1 text-[10px] font-medium text-[#6B7280] dark:text-[#9CA3AF]">
              <span className="w-1.5 h-1.5 rounded-full bg-[#4A7FA5]" />
              You are on: {currentPage}
            </span>
          </div>
        )}
        {/* Input area */}
        <div className="p-4 border-t border-[0.5px] border-[#C8CDD6] dark:border-[#484848] flex-shrink-0">
          <div className="flex items-end gap-2">
            <textarea
              ref={textareaRef}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              onInput={handleInput}
              placeholder="Ask anything about JAMM PX..."
              rows={1}
              disabled={streaming}
              className="flex-1 rounded-[6px] border border-[0.5px] border-[#C8CDD6] focus:border-[#4A7FA5] focus:outline-none bg-[#F7F7F8] dark:bg-[#2D2D2D] text-[13px] text-[#374151] dark:text-[#9CA3AF] placeholder:text-[#9CA3AF] p-2.5 resize-none transition-colors disabled:opacity-60"
              style={{ minHeight: 36, maxHeight: 96, overflowY: 'auto' }}
            />
            <button
              onClick={() => handleSend()}
              disabled={!input.trim() || streaming}
              aria-label="Send message"
              className="h-9 w-9 rounded-[6px] bg-[#1F3148] flex items-center justify-center transition-opacity disabled:opacity-40 disabled:cursor-not-allowed flex-shrink-0"
            >
              <Send className="h-4 w-4 text-white" />
            </button>
          </div>
        </div>
      </div>
    </>
  )
}

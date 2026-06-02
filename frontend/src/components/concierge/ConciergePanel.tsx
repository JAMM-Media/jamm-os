// frontend/src/components/concierge/ConciergePanel.tsx
'use client'

import { useState, useRef, useEffect, useCallback } from 'react'
import { useRouter } from 'next/navigation'
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

const STARTER_PROMPTS = [
  'What should I set up first after signing up?',
  'How do I import my existing clients?',
  'How does the client portal work?',
]

const STARTER_PROMPT_INSTRUCTIONS: Record<string, string> = {
  'How do I import my existing clients?': 'Answer using a numbered markdown list. Each step on its own numbered line.',
  'How does the client portal work?': 'Answer using a numbered markdown list. Each step on its own numbered line.',
}

const HARDCODED_RESPONSES: Record<string, string> = {
  'What should I set up first after signing up?': `Here's the recommended setup order:

1. **Firm profile.** Go to Settings > Firm Profile. Add your firm name, logo, and contact details. This appears on engagement letters and all client-facing documents.

2. **Invite staff.** Go to Settings > Team. Add each staff member by email and assign their role. They receive a magic-link to set their password.

3. **Connect QuickBooks (if applicable).** Go to Settings > Integrations > QuickBooks and complete the OAuth flow. Use the Import Preview before committing.

4. **Import clients.** QuickBooks: use the Import Preview. CSV: go to Clients > Import. Required column: name. Recommended: email, entity_type.

5. **Create engagement templates.** Go to Engagements > Templates > New Template. Build templates for your most common work types with pre-set task lists.

6. **Create engagements.** Go to Clients > [Client Name] > Engagements > New Engagement. Use a template if available.

7. **Enable automation presets.** Go to Settings > Automations. Start with deadline alerts and document upload confirmations.

8. **Send portal magic-links.** New clients: send immediately. Existing clients: convert in batches of 10 to 15 per week.

9. **Send first document request.** Go to the engagement > Document Requests > New Request.

10. **Connect Stripe.** Go to Settings > Billing > Connect Stripe. Required before sending invoices for payment.`,
  'How do I import my existing clients?': `Two ways to import clients into JAMM PX:

**Option A: QuickBooks import**

1. Go to Settings > Integrations > QuickBooks and complete the OAuth connection.
2. Open the Import Preview to see which clients will come over before committing.
3. Select the clients you want and confirm the import.
4. Common skip reasons: no email on the QuickBooks record, duplicate email, inactive customer, sub-customer record.

**Option B: CSV import**

1. Export a CSV from your current platform.
2. Make sure the file has a name column. Recommended columns: email, entity_type, phone, company_name.
3. Entity type values: individual, business, trust, estate.
4. Go to Clients > Import and upload the file.
5. Review the result summary. Skipped rows are listed with the reason. Fix and re-import only the skipped rows.

Note: invoices, payment history, and documents do not transfer. Only client records come over.`,
  'How does the client portal work?': `The client portal is a secure space where clients upload documents, pay invoices, and communicate with your firm.

**Sending access**

1. Go to Clients > [Client Name] > Portal tab > Send Magic-Link.
2. New clients: send immediately when creating their first engagement.
3. Existing clients: convert in batches of 10 to 15 per week. Never send to all clients at once.
4. Magic-links expire after 72 hours. Clients can set a password if they prefer.

**What clients see**

5. Engagements with any notes you mark as client-visible.
6. Document requests with a checklist they can upload files against.
7. Invoices they can pay online once Stripe is connected.
8. A messages tab for secure back-and-forth with your firm.

Note: internal engagement notes are never visible to clients. Only notes_client_visible fields appear in the portal.`,
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
  const { user } = useAuth()
  const logoUrl = user ? `/api/backend/firms/logo/${user.firm_id}` : null
  const initials =
    user?.full_name?.split(' ').map((n) => n[0]).join('').slice(0, 2).toUpperCase() ?? '?'

  const [messages, setMessages] = useState<Message[]>([])
  const [notifications, setNotifications] = useState<Notification[]>([])
  const [input, setInput] = useState('')
  const [streaming, setStreaming] = useState(false)
  const [showStarters, setShowStarters] = useState(true)
  const [autopilotOn,setAutopilotOn] = useState(false)
  const [suggestions, setSuggestions] = useState<string[]>([])
  const [formDirty, setFormDirtyState] = useState(false)
  const [statusMessage, setStatusMessage] = useState(() => {
    if (typeof window !== 'undefined') {
      const pending = sessionStorage.getItem('jamm_concierge_status')
      if (pending) {
        sessionStorage.removeItem('jamm_concierge_status')
        return pending
      }
    }
    return ''
  })

  // Keep a ref so the async sendMessages callback always reads current value.
  const autopilotRef = useRef(false)
  useEffect(() => { autopilotRef.current = autopilotOn }, [autopilotOn])

  const messagesEndRef = useRef<HTMLDivElement>(null)
  const textareaRef = useRef<HTMLTextAreaElement>(null)
  const hasInitialized = useRef(false)

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  // Reset autopilot when panel closes (session-only per spec).
  useEffect(() => {
    if (!isOpen) setAutopilotOn(false)
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
      setNotifications(res.data.items ?? [])
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
      setShowStarters(false)
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

        setMessages((prev) => {
          const updated = [...prev]
          const last = updated[updated.length - 1]
          if (last.role === 'concierge') {
            updated[updated.length - 1] = {
              role: 'concierge',
              content: handleConciergeAction(assembled),
            }
          }
          return updated
        })
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
    }
    if (isOpen) {
      setTimeout(() => textareaRef.current?.focus(), 250)
      fetchNotifications()
    }
  }, [isOpen, sendMessages, fetchNotifications])

  async function handleSend(text?: string) {
    const msg = (text ?? input).trim()
    if (!msg || streaming) return
    setInput('')
    setSuggestions([])
    const hardcoded = text ? HARDCODED_RESPONSES[text] : undefined
    if (hardcoded) {
      const userMsg: Message = { role: 'user', content: msg }
      setMessages((prev) => [...prev, userMsg, { role: 'concierge', content: '' }])
      setStreaming(true)
      await new Promise((resolve) => setTimeout(resolve, 1400))
      setStreaming(false)
      setMessages((prev) => {
        const updated = [...prev]
        updated[updated.length - 1] = { role: 'concierge', content: hardcoded }
        return updated
      })
      return
    }
    const instruction = text ? STARTER_PROMPT_INSTRUCTIONS[text] : undefined
    const apiContent = instruction ? `${msg}\n\n[Format instruction: ${instruction}]` : msg
    const userMsg: Message = { role: 'user', content: msg }
    const apiMsg: Message = { role: 'user', content: apiContent }
    const newThread = [...messages, userMsg]
    const apiThread = [...messages, apiMsg]
    setMessages(newThread)
    await sendMessages(apiThread)
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
    const actionLine = raw.slice(actionIndex + ACTION_MARKER.length).split('\n')[0].trim()

    if (!autopilotRef.current) {
      return 'To use autopilot navigation, turn on Autopilot using the toggle above.'
    }

    try {
      const action: ConciergeAction = JSON.parse(actionLine)
      void executeAction(action)
    } catch {}

    return beforeAction || ''
  }

  async function executeAction(action: ConciergeAction) {
    const routeToLabel: Record<string, string> = {
      '/clients': 'Navigated to Clients',
      '/settings/team': 'Navigated to Team Settings',
      '/engagements/templates': 'Navigated to Engagement Templates',
      '/settings/integrations': 'Navigated to Integrations',
      '/settings/billing': 'Navigated to Billing',
    }

    if (action.route) {
      const clientMatch = action.route.match(/^\/clients\/([^/]+)$/)
      if (clientMatch) {
        const name = decodeURIComponent(clientMatch[1]).replace(/-/g, ' ')
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
            const resolvedRoute = `/clients/${data.id}`
            if (formDirty) {
              const ok = window.confirm('You have unsaved changes. Navigate away?')
              if (!ok) return
            }
            sessionStorage.setItem('jamm_concierge_status', `Navigated to ${capitalized}`)
            router.push(resolvedRoute)
            setStatusMessage(`Navigated to ${capitalized}`)
            setTimeout(() => emitConciergeAction({ ...action, route: resolvedRoute }), 500)
          } catch {
            setStatusMessage('Could not find client')
          }
          return
        }
      }

      const navLabel = routeToLabel[action.route] ?? `Navigated to ${action.route}`
      if (formDirty) {
        const ok = window.confirm('You have unsaved changes. Navigate away?')
        if (!ok) return
      }
      sessionStorage.setItem('jamm_concierge_status', navLabel)
      router.push(action.route)
      setStatusMessage(navLabel)
    }

    if (action.modal) {
      const modalLabel: Record<string, string> = {
        'new-client': 'Opened New Client drawer',
        'new-engagement': 'Opened New Engagement drawer',
        'invite-staff': 'Opened Invite Staff modal',
        'new-template': 'Opened New Template drawer',
      }
      setTimeout(() => {
        emitConciergeAction(action)
        setStatusMessage(modalLabel[action.modal ?? ''] ?? 'Opened modal')
      }, 500)
    } else if (action.route) {
      setTimeout(() => emitConciergeAction(action), 500)
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
                onClick={() => setAutopilotOn((v) => !v)}
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
                className="flex items-start gap-2 bg-white dark:bg-[#2D2D2D] border border-[0.5px] border-[#C8CDD6] dark:border-[#484848] rounded-[8px] px-3 py-2.5"
              >
                <p className="flex-1 text-[12px] leading-[1.5] text-[#1F3148] dark:text-[#EDEEF0]">
                  {n.message}
                </p>
                <button
                  onClick={() => dismissNotification(n.id)}
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

          {showStarters && messages.length === 0 && (
            <div className="flex flex-col gap-3">
              <p className="text-[12px] text-[#6B7280] leading-[1.5]">
                Ask me anything about JAMM PX. Here are a few places to start:
              </p>
              {STARTER_PROMPTS.map((prompt, i) => (
                <button
                  key={i}
                  onClick={() => handleSend(prompt)}
                  className="text-left text-[13px] text-[#1F3148] dark:text-[#EDEEF0] bg-white dark:bg-[#2D2D2D] border border-[0.5px] border-[#C8CDD6] dark:border-[#484848] rounded-[8px] px-3 py-2.5 hover:border-[#4A7FA5] hover:bg-[#F0F4F8] dark:hover:bg-[#333333] transition-colors leading-[1.5]"
                >
                  {prompt}
                </button>
              ))}
            </div>
          )}

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

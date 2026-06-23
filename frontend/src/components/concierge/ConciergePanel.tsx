// frontend/src/components/concierge/ConciergePanel.tsx
'use client'

import { useState, useRef, useEffect, useCallback } from 'react'
import { useRouter, usePathname } from 'next/navigation'
import { X, Send, Zap, Download } from 'lucide-react'
import ReactMarkdown from 'react-markdown'
import jsPDF from 'jspdf'
import { useAuth } from '@/lib/hooks/useAuth'
import { useConciergeContext } from '@/lib/hooks/useConciergeContext'
import api from '@/lib/api'
import {
  emitConciergeAction,
  type ConciergeAction,
} from '@/lib/events/conciergeEvents'
import { assembleSSELines } from '@/lib/concierge/assembleSSEStream'

interface Message {
  role: 'user' | 'concierge'
  content: string
  actionConfirm?: string
  isBriefing?: boolean
  draft?: { type: string; content: string; source: string | null } | null
}

interface Notification {
  id: string
  trigger_type: string
  message: string
  created_at: string
  metadata?: Record<string, unknown> | null
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
  const { user } = useAuth()
  const uiContext = useConciergeContext()
  const currentPage = uiContext.entity_name
    ? uiContext.entity_name
    : Object.entries(PAGE_LABELS).find(([k]) => pathname.startsWith(k))?.[1] ?? 'JAMM PX'
  const logoUrl = user ? `/api/backend/firms/logo/${user.firm_id}` : null
  const initials =
    user?.full_name?.split(' ').map((n) => n[0]).join('').slice(0, 2).toUpperCase() ?? '?'

  const [messages, setMessages] = useState<Message[]>([])
  const [notifications, setNotifications] = useState<Notification[]>([])
  const [input, setInput] = useState('')
  const [streaming, setStreaming] = useState(false)
  const [hasMounted, setHasMounted] = useState(false)
  useEffect(() => {
    setHasMounted(true)
  }, [])
  const [autopilotOn, setAutopilotOn] = useState(() => {
    if (typeof window !== 'undefined') {
      return sessionStorage.getItem('jamm_concierge_autopilot') === 'true'
    }
    return false
  })
  const [suggestions, setSuggestions] = useState<string[]>([])
  const [formDirty, setFormDirtyState] = useState(false)
  const [statusMessage, setStatusMessage] = useState('')
  const [pasteFormOpen, setPasteFormOpen] = useState(false)
  const [briefingLoading, setBriefingLoading] = useState(false)
  const [isDownloading, setIsDownloading] = useState(false)
  const [copiedId, setCopiedId] = useState<string | null>(null)
  const [editingDraftContent, setEditingDraftContent] = useState<Record<number, string>>({})
  const [detailBriefing, setDetailBriefing] = useState<string | null>(null)
  const [detailReady, setDetailReady] = useState(false)
  const [pasteForm, setPasteForm] = useState({
    name: '',
    email: '',
    phone: '',
    entity_type: '',
  })

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
    try {
      const stored = sessionStorage.getItem('jamm_concierge_messages')
      if (stored) setMessages(JSON.parse(stored) as Message[])
    } catch {
      // ignore parse errors
    }
  }, [])
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
            page_context: uiContext,
          }),
        })

        if (!res.ok || !res.body) {
          let errorContent = 'Something went wrong. Please try again.'
          if (res.status === 400) {
            errorContent = 'I am not able to help with that request.'
          } else if (res.status === 429) {
            errorContent = 'Too many requests. Please wait a moment before trying again.'
          } else if (res.status === 403) {
            errorContent = 'Access denied.'
          }
          setMessages((prev) => {
            const updated = [...prev]
            updated[updated.length - 1] = {
              role: 'concierge',
              content: errorContent,
            }
            return updated
          })
          return
        }

        const reader = res.body.getReader()
        const decoder = new TextDecoder()
        let buffer = ''
        const allRawLines: string[] = []

        while (true) {
          const { done, value } = await reader.read()
          if (done) {
            buffer += decoder.decode()
            if (buffer) allRawLines.push(buffer)
            break
          }
          buffer += decoder.decode(value, { stream: true })
          const lines = buffer.split('\n')
          buffer = lines.pop() ?? ''
          allRawLines.push(...lines)
        }

        assembled = assembleSSELines(allRawLines)

        console.log('[CONCIERGE RAW]', assembled)
        const filteredAssembled = filterOutput(assembled.replace(/\[TOPIC:\w+\]\s*$/, '').trimEnd())
        const parsedDraft = parseDraftFromResponse(filteredAssembled)
        const textForAction = parsedDraft ? parsedDraft.cleanedResponse : filteredAssembled
        const cleanContent = handleConciergeAction(textForAction)
        setMessages((prev) => {
          const updated = [...prev]
          const last = updated[updated.length - 1]
          if (last.role === 'concierge') {
            updated[updated.length - 1] = {
              role: 'concierge',
              content: cleanContent,
              draft: parsedDraft ? { type: parsedDraft.type, content: parsedDraft.content, source: parsedDraft.source } : null,
            }
          }
          return updated
        })
        if (pendingActionRef.current) {
          const action = pendingActionRef.current
          pendingActionRef.current = null
          void executeAction(action)
        }
        const topicMatch = assembled.match(/\[TOPIC:(\w+)\]/)
        const topic = topicMatch ? topicMatch[1] : 'general'

        const TOPIC_CHIPS: Record<string, string[]> = {
          clients: ['Go to Clients', 'Import clients'],
          engagements: ['Go to Engagements', 'New engagement'],
          tasks: ['Go to Tasks'],
          document_requests: ['Go to Documents'],
          portal: ['Go to Clients'],
          billing: ['Go to Billing'],
          time_tracking: ['Go to Billing'],
          automations: ['Go to Settings'],
          irs_authorizations: ['Go to Clients'],
          staff: ['Go to Settings'],
          settings: ['Go to Settings'],
          operational_data: ['Go to Dashboard'],
          general: [],
        }

        setSuggestions((TOPIC_CHIPS[topic] ?? []).slice(0, 3))
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
    [router, uiContext],
  )

  useEffect(() => {
    if (isOpen && !hasInitialized.current) {
      hasInitialized.current = true
      if (messages.length === 0) {
        const _open = async () => {
          if (!uiContext.ready) {
            let waited = 0
            while (!uiContext.ready && waited < 1500) {
              await new Promise((resolve) => setTimeout(resolve, 100))
              waited += 100
            }
          }
          if (pathname.startsWith('/dashboard')) {
            setBriefingLoading(true)
            try {
              const res = await api.post('/concierge/morning-briefing')
              if (res.status === 200 && res.data?.briefing) {
                setMessages([{ role: 'concierge', content: res.data.briefing, isBriefing: true }])
                api.post('/concierge/morning-briefing/detail')
                  .then((r) => { if (r.data?.briefing) { setDetailBriefing(r.data.briefing); setDetailReady(true) } })
                  .catch(() => {})
                hasInitialized.current = true
                setBriefingLoading(false)
                return
              }
            } catch {
              // fall through to standard opening
            } finally {
              setBriefingLoading(false)
            }
          }
          if (!user?.firm_type) {
            setMessages([{
              role: 'concierge',
              content: 'Here for anything you need. Before we start, what does your firm do most? This lets me point you to the right setup path.\n\n1. Tax prep and returns\n2. Bookkeeping and monthly close\n3. Advisory and planning',
            }])
          } else {
            sendMessages([{ role: 'user', content: '__OPEN__' }])
          }
        }
        _open()
      }
    }
    if (isOpen) {
      setTimeout(() => textareaRef.current?.focus(), 250)
      api.post('/concierge/trigger-check').then(() => fetchNotifications()).catch(() => fetchNotifications())
    }
  }, [isOpen, sendMessages, fetchNotifications, user])

  // 60-second context refresh -- polls trigger check while panel is open
  useEffect(() => {
    if (!isOpen) return
    const interval = setInterval(() => {
      api.post('/concierge/trigger-check')
        .then(() => fetchNotifications())
        .catch(() => {})
    }, 60_000)
    return () => clearInterval(interval)
  }, [isOpen, fetchNotifications])

  async function handleSend(text?: string) {
    const msg = (text ?? input).trim()
    if (!msg || streaming) return

    // If the user is on a route that resolves to an entity (client or engagement
    // detail page) but the entity context has not finished loading yet, wait
    // briefly so the question is answered with the correct scoped context rather
    // than firing before entity_name is populated.
    if (!uiContext.ready) {
      let waited = 0
      while (!uiContext.ready && waited < 1500) {
        await new Promise((resolve) => setTimeout(resolve, 100))
        waited += 100
      }
    }

    setInput('')
    setSuggestions([])
    const userMsg: Message = { role: 'user', content: msg }
    const newThread = [...messages, userMsg]
    setMessages(newThread)
    await sendMessages(newThread)
  }

  function handlePasteFormSubmit() {
    if (!pasteForm.name.trim()) return
    setPasteFormOpen(false)
    const summary = [
      pasteForm.name.trim(),
      pasteForm.email.trim(),
      pasteForm.phone.trim(),
      pasteForm.entity_type,
    ].filter(Boolean).join(', ')
    const userMsg: Message = {
      role: 'user',
      content: `Add client: ${summary}`,
    }
    setMessages((prev) => [...prev, userMsg])
    const confirmMsg: Message = {
      role: 'concierge',
      content: `Got it. Here is what I have:\n\n${pasteForm.name.trim()}${pasteForm.email ? '\nEmail: ' + pasteForm.email.trim() : ''}${pasteForm.phone ? '\nPhone: ' + pasteForm.phone.trim() : ''}${pasteForm.entity_type ? '\nType: ' + pasteForm.entity_type : ''}\n\nTurn on Autopilot and I will open the New Client form with these fields pre-filled. Or navigate to Clients and select New Client to enter them manually.`,
    }
    if (autopilotRef.current) {
      const action: ConciergeAction = {
        type: 'navigate-and-open',
        route: '/clients',
        modal: 'new-client',
        prefill: {
          name: pasteForm.name.trim(),
          email: pasteForm.email.trim(),
          phone: pasteForm.phone.trim(),
          entityType: pasteForm.entity_type,
        },
      }
      setMessages((prev) => [...prev, { role: 'concierge', content: '' }])
      void executeAction(action)
      setStatusMessage('Opening New Client form')
    } else {
      setMessages((prev) => [...prev, confirmMsg])
    }
    setPasteForm({ name: '', email: '', phone: '', entity_type: '' })
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

  function getStarterPrompts(): string[] {
    if (uiContext.entity_type === 'client' && uiContext.entity_name) {
      return [
        `What's the status of ${uiContext.entity_name}?`,
        `What's overdue for ${uiContext.entity_name}?`,
        `What documents are still missing?`,
      ]
    }
    if (uiContext.entity_type === 'engagement' && uiContext.entity_name) {
      return [
        `What needs to happen next on this engagement?`,
        `Who is assigned to this?`,
        `What's the current status?`,
      ]
    }
    if (currentPage === 'Billing') {
      return [
        `Which invoices are past due?`,
        `What work haven't I invoiced yet?`,
        `Draft a payment reminder for the oldest overdue invoice.`,
      ]
    }
    if (currentPage === 'Dashboard') {
      return [
        `What needs my attention today?`,
        `Who owes me money?`,
        `What's overdue?`,
      ]
    }
    return [
      `What needs my attention today?`,
      `What's overdue?`,
      `Who owes me money?`,
    ]
  }

  function parseDraftFromResponse(text: string): {
    type: string
    content: string
    source: string | null
    cleanedResponse: string
  } | null {
    const startMarker = '---DRAFT:'
    const endMarker = '---END DRAFT---'
    const startIdx = text.indexOf(startMarker)
    const endIdx = text.indexOf(endMarker)
    if (startIdx === -1 || endIdx === -1 || endIdx <= startIdx) return null

    const typeEnd = text.indexOf('---', startIdx + startMarker.length)
    if (typeEnd === -1) return null

    const type = text.slice(startIdx + startMarker.length, typeEnd).trim()
    let rawBlock = text.slice(typeEnd + 3, endIdx).trim()

    let source: string | null = null
    const sourceMatch = rawBlock.match(/SOURCE:\s*([\s\S]+?)(?:\n\s*\n|$)/)
    if (sourceMatch) {
      source = sourceMatch[1].replace(/\s+/g, ' ').trim()
      rawBlock = rawBlock.slice(0, sourceMatch.index).trim()
    }

    const cleanedResponse = text.slice(0, startIdx).trimEnd()

    if (!type || !rawBlock) return null
    return { type, content: rawBlock, source, cleanedResponse }
  }

  function filterOutput(text: string): string {
    const SSN_PATTERN = /\b\d{3}-\d{2}-\d{4}\b/g
    const EIN_PATTERN = /\b\d{2}-\d{7}\b/g
    const LEAK_PHRASES = [
      'my instructions are',
      'my system prompt',
      'i was instructed to',
      'i am instructed to',
      'the system prompt says',
      'my prompt says',
      'i have been told to',
      'i have been configured',
      'as per my instructions',
      'according to my instructions',
    ]

    if (SSN_PATTERN.test(text) || EIN_PATTERN.test(text)) {
      console.error('[SECURITY] PII pattern detected in model output -- redacting')
      text = text.replace(SSN_PATTERN, '[REDACTED]')
      text = text.replace(EIN_PATTERN, '[REDACTED]')
    }

    const lower = text.toLowerCase()
    for (const phrase of LEAK_PHRASES) {
      if (lower.includes(phrase)) {
        console.error(`[SECURITY] System prompt leak phrase detected in output: ${phrase}`)
        return 'I am JAMM Concierge. I am here to help you use JAMM PX.'
      }
    }

    return text
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

    try {
      const action: ConciergeAction = JSON.parse(actionLine)
      if (action.type === 'set_firm_type') {
        pendingActionRef.current = action
        return beforeAction || ''
      }
    } catch {}

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
      {hasMounted && isOpen && (
        <div
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
          transform: hasMounted && isOpen ? 'translateX(0)' : 'translateX(100%)',
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
                title="When ON, I'll navigate the app and open forms for you automatically. When OFF, I'll just tell you where to go."
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
              <div className="absolute right-0 top-full mt-1 w-56 px-2.5 py-1.5 rounded-[6px] bg-[#1F3148] text-white text-[11px] leading-snug opacity-0 group-hover:opacity-100 transition-opacity duration-150 pointer-events-none z-50 shadow-lg">
                When ON, I&apos;ll navigate the app and open forms for you automatically. When OFF, I&apos;ll just tell you where to go.
              </div>
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
            <div className="flex items-center gap-1.5 px-0.5">
              <span className="w-1.5 h-1.5 rounded-full bg-[#D97706]" />
              <span className="text-[10px] font-semibold uppercase tracking-wide text-[#92400E] dark:text-[#D97706]">
                {notifications.length} {notifications.length === 1 ? 'Alert' : 'Alerts'}
              </span>
            </div>
            {notifications.map((n) => {
              const draft = n.metadata?.draft as string | undefined
              return (
                <div
                  key={n.id}
                  className="flex flex-col gap-2 bg-white dark:bg-[#2D2D2D] border border-[0.5px] border-[#C8CDD6] dark:border-[#484848] border-l-[3px] border-l-[#D97706] rounded-[8px] px-3 py-2.5"
                >
                  <div className="flex items-start gap-2">
                    <p
                      className="flex-1 text-[12px] leading-[1.5] text-[#1F3148] dark:text-[#EDEEF0] cursor-pointer"
                      onClick={() => { dismissNotification(n.id); handleSend(n.message) }}
                    >
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
                  {draft && (
                    <div className="mt-1 rounded-[6px] bg-[#F0F4F8] dark:bg-[#1a2a3a] border border-[0.5px] border-[#C8CDD6] dark:border-[#3a4a5a] px-2.5 py-2">
                      <p className="text-[11px] text-[#6B7280] dark:text-[#9CA3AF] mb-1.5 font-medium uppercase tracking-wide">Draft</p>
                      <p className="text-[12px] leading-[1.5] text-[#374151] dark:text-[#D1D5DB] whitespace-pre-wrap">{draft}</p>
                      <div className="flex gap-2 mt-2">
                        <button
                          onClick={() => {
                            navigator.clipboard.writeText(draft).then(() => {
                              setCopiedId(n.id)
                              setTimeout(() => setCopiedId(null), 2000)
                            }).catch(() => {})
                          }}
                          className="text-[11px] font-medium px-2.5 py-1 rounded-[4px] border border-[0.5px] border-[#C8CDD6] dark:border-[#484848] text-[#6B7280] dark:text-[#9CA3AF] hover:border-[#4A7FA5] hover:text-[#4A7FA5] transition-colors"
                        >
                          {copiedId === n.id ? 'Copied' : 'Copy'}
                        </button>
                        <button
                          onClick={() => {
                            const targetClientId = uiContext.entity_type === 'client' ? uiContext.entity_id : null
                            if (!targetClientId) {
                              window.alert('Open the specific client record first, then I can pre-fill this message for you to send.')
                              return
                            }
                            const confirmed = window.confirm(
                              `Open ${uiContext.entity_name ?? 'this client'}'s Messages tab with this draft ready to send?\n\nMessage:\n${draft}\n\nYou will have a final chance to review before sending.`
                            )
                            if (!confirmed) return
                            dismissNotification(n.id)
                            const alreadyOnClientPage = pathname.startsWith(`/clients/${targetClientId}`)
                            if (alreadyOnClientPage) {
                              emitConciergeAction({ type: 'prefill-message', prefillMessage: draft })
                            } else {
                              sessionStorage.setItem(
                                'jamm_concierge_pending',
                                JSON.stringify({
                                  clientId: targetClientId,
                                  prefillMessage: draft,
                                  _ts: Date.now(),
                                }),
                              )
                            }
                            router.push(`/clients/${targetClientId}?tab=messages`)
                          }}
                          className="text-[11px] font-medium px-2.5 py-1 rounded-[4px] bg-[#1F3148] text-white hover:bg-[#2a4060] transition-colors"
                        >
                          Open to send
                        </button>
                      </div>
                    </div>
                  )}
                </div>
              )
            })}
          </div>
        )}

        {/* Message feed */}
        <div className="flex-1 min-h-0 overflow-y-auto p-4 flex flex-col gap-3">

          {/* Opening message fires automatically via __OPEN__ sentinel on first open */}

          {briefingLoading && messages.length === 0 && (
            <div className="flex gap-2.5 px-3 py-2">
              <div className="w-7 h-7 rounded-full bg-[#1F3148] flex items-center justify-center flex-shrink-0">
                <span className="text-white text-[10px] font-medium">JC</span>
              </div>
              <div className="flex flex-col gap-2 flex-1 pt-1">
                <div className="h-3 w-24 bg-[#D5D8DE] dark:bg-[#444444] animate-pulse rounded" />
                <div className="h-2 w-full bg-[#D5D8DE] dark:bg-[#444444] animate-pulse rounded" />
                <div className="h-2 w-4/5 bg-[#D5D8DE] dark:bg-[#444444] animate-pulse rounded" />
                <div className="h-2 w-16 bg-[#D5D8DE] dark:bg-[#444444] animate-pulse rounded mt-1" />
                <div className="h-2 w-full bg-[#D5D8DE] dark:bg-[#444444] animate-pulse rounded" />
                <div className="h-2 w-3/4 bg-[#D5D8DE] dark:bg-[#444444] animate-pulse rounded" />
                <div className="h-2 w-16 bg-[#D5D8DE] dark:bg-[#444444] animate-pulse rounded mt-1" />
                <div className="h-2 w-full bg-[#D5D8DE] dark:bg-[#444444] animate-pulse rounded" />
                <div className="h-2 w-2/3 bg-[#D5D8DE] dark:bg-[#444444] animate-pulse rounded" />
              </div>
            </div>
          )}

          {messages.length === 0 && !briefingLoading && !streaming && (
            <div className="flex flex-col gap-2 px-1 py-1">
              <p className="text-[11px] text-[#9CA3AF] px-2">Try asking</p>
              <div className="flex flex-wrap gap-1.5 px-1">
                {getStarterPrompts().map((prompt) => (
                  <button
                    key={prompt}
                    onClick={() => handleSend(prompt)}
                    className="text-[11px] font-medium px-3 py-1.5 rounded-full border border-[#C8CDD6] dark:border-[#484848] text-[#1F3148] dark:text-[#EDEEF0] bg-white dark:bg-[#2D2D2D] hover:border-[#4A7FA5] hover:text-[#4A7FA5] transition-colors"
                  >
                    {prompt}
                  </button>
                ))}
              </div>
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
                        h2: ({node, ...props}) => <h2 className="text-[13px] font-semibold text-[#1F3148] dark:text-[#EDEEF0] mt-3 mb-1 first:mt-0" {...props} />,
                        h3: ({node, ...props}) => <h3 className="text-[12px] font-semibold text-[#4A7FA5] uppercase tracking-wide mt-2.5 mb-1" {...props} />,
                        hr: ({node, ...props}) => <hr className="border-t border-[#C8CDD6] dark:border-[#484848] my-2" />,
                        ul: ({node, ...props}) => <ul className="list-disc list-outside ml-4 my-1 space-y-0.5" {...props} />,
                        ol: ({node, ...props}) => <ol className="list-decimal list-outside ml-4 my-1 space-y-0.5" {...props} />,
                        li: ({node, ...props}) => <li className="leading-snug" {...props} />,
                        p: ({node, ...props}) => <p className="mb-1 last:mb-0" {...props} />,
                        strong: ({node, ...props}) => <strong className="font-medium text-[#1F3148] dark:text-[#EDEEF0]" {...props} />,
                        em: ({node, ...props}) => <em className="not-italic text-[11px] text-[#6B7280]" {...props} />,
                      }}
                    >
                      {msg.content}
                    </ReactMarkdown>
                  </div>
                ) : streaming && i === messages.length - 1 ? (
                  <span className="text-[13px] text-[#6B7280] animate-pulse">Thinking...</span>
                ) : null}
                {msg.isBriefing && (
                  <div className="mt-2">
                    <button
                      disabled={!detailReady || isDownloading}
                      onClick={async () => {
                        setIsDownloading(true)
                        try {
                          let briefingText = detailBriefing
                          if (!briefingText) {
                            const res = await api.post('/concierge/morning-briefing/detail')
                            if (res.status === 200 && res.data?.briefing) {
                              briefingText = res.data.briefing
                              setDetailBriefing(res.data.briefing)
                            }
                          }
                          if (briefingText) {
                            const doc = new jsPDF({ format: 'a4' })
                            const dateStr = new Date().toLocaleDateString('en-US', { weekday: 'long', year: 'numeric', month: 'long', day: 'numeric' })
                            let pageNum = 1

                            // BUG 1: strip leading lines the AI echoes back (title, date, firm name)
                            const monthNames = ['January','February','March','April','May','June','July','August','September','October','November','December']
                            const strippedLines = briefingText.split('\n')
                            let stripIdx = 0
                            while (stripIdx < strippedLines.length && stripIdx < 6) {
                              const l = strippedLines[stripIdx].trim()
                              if (
                                l === '' ||
                                l.includes('JAMM PX Morning Briefing') ||
                                monthNames.some((m) => l.includes(m)) ||
                                l.includes('2026') || l.includes('2025') ||
                                l.includes('Tax') || l.includes('Bookkeeping') || l.includes('Accounting') || l.includes('Firm')
                              ) {
                                stripIdx++
                              } else {
                                break
                              }
                            }
                            const cleanedText = strippedLines
                              .slice(stripIdx)
                              .filter((l) =>
                                !l.includes('{firm name}') &&
                                !l.includes('{firm_name}') &&
                                l.trim() !== 'JAMM PX' &&
                                !l.match(/^JAMM PX Morning Briefing/)
                              )
                              .join('\n')

                            // BUG 5: first-page header with full branding; subsequent pages get minimal gray header only
                            const addPageHeader = (isFirst: boolean) => {
                              if (isFirst) {
                                doc.setFillColor(31, 49, 72)
                                doc.rect(0, 0, 210, 26, 'F')
                                doc.setFont('helvetica', 'bold')
                                doc.setFontSize(15)
                                doc.setTextColor(255, 255, 255)
                                doc.text('JAMM', 20, 13)
                                const jammWidth = doc.getTextWidth('JAMM')
                                doc.setTextColor(211, 165, 97)
                                doc.text(' PX', 20 + jammWidth, 13)
                                doc.setTextColor(255, 255, 255)
                                doc.setFont('helvetica', 'bold')
                                doc.setFontSize(9)
                                doc.text('Morning Briefing', 20, 19)
                                doc.setFont('helvetica', 'normal')
                                doc.setFontSize(9)
                                doc.setTextColor(255, 255, 255)
                                doc.text(dateStr, 190, 19, { align: 'right' })
                              } else {
                                doc.setFont('helvetica', 'normal')
                                doc.setFontSize(8)
                                doc.setTextColor(156, 163, 175)
                                doc.text('JAMM PX Morning Briefing (continued)', 20, 10)
                              }
                              doc.setDrawColor(74, 127, 165)
                              doc.setLineWidth(0.3)
                            }

                            const addPageNumber = () => {
                              doc.setFont('helvetica', 'normal')
                              doc.setFontSize(8)
                              doc.setTextColor(156, 163, 175)
                              doc.text(`Page ${pageNum}`, 190, 285, { align: 'right' })
                            }

                            addPageHeader(true)

                            let y = 28

                            const sections = cleanedText.split('---')
                            const knownHeaders = ['FIRM OVERVIEW', 'NEEDS ATTENTION', 'THIS WEEK', 'ALL ACTIVE ENGAGEMENTS', 'RECENT ACTIVITY', 'STAFF & PORTAL SUMMARY']

                            for (const section of sections) {
                              const rawLines = section.trim().split('\n')
                              if (rawLines.length === 0) continue
                              const firstLine = rawLines[0].trim()
                              if (!firstLine) continue
                              const isHeader = (firstLine === firstLine.toUpperCase() && firstLine.length > 2) || knownHeaders.some((h) => firstLine.includes(h))

                              if (isHeader) {
                                // FIX 2: skip sections whose only content is "None." or "None"
                                const nonEmptyBody = rawLines.slice(1).map((l) => l.trim()).filter((l) => l.length > 0)
                                if (nonEmptyBody.length === 1 && (nonEmptyBody[0] === 'None.' || nonEmptyBody[0] === 'None')) continue
                                if (y > 260) {
                                  addPageNumber()
                                  doc.addPage()
                                  pageNum++
                                  addPageHeader(false)
                                  y = 30
                                }
                                y += 4
                                doc.setFont('helvetica', 'bold')
                                doc.setFontSize(11)
                                doc.setTextColor(74, 127, 165)
                                doc.text(firstLine, 20, y)
                                doc.setDrawColor(74, 127, 165)
                                doc.setLineWidth(0.3)
                                doc.line(20, y + 1, 190, y + 1)
                                y += 7
                                doc.setFont('helvetica', 'normal')
                                doc.setFontSize(9)
                                doc.setTextColor(55, 65, 81)
                                const bodyLines = rawLines.slice(1)
                                for (const bl of bodyLines) {
                                  const trimmed = bl.trim()
                                  if (!trimmed) continue
                                  const wrapped = doc.splitTextToSize(trimmed, 165)
                                  for (const wl of wrapped) {
                                    if (y > 272) {
                                      addPageNumber()
                                      doc.addPage()
                                      pageNum++
                                      addPageHeader(false)
                                      y = 30
                                      doc.setFont('helvetica', 'normal')
                                      doc.setFontSize(9)
                                      doc.setTextColor(55, 65, 81)
                                    }
                                    doc.text(wl, 25, y)
                                    y += 5
                                  }
                                }
                              } else {
                                for (const bl of rawLines) {
                                  const trimmed = bl.trim()
                                  if (!trimmed) continue
                                  const wrapped = doc.splitTextToSize(trimmed, 165)
                                  for (const wl of wrapped) {
                                    if (y > 272) {
                                      addPageNumber()
                                      doc.addPage()
                                      pageNum++
                                      addPageHeader(false)
                                      y = 30
                                      doc.setFont('helvetica', 'normal')
                                      doc.setFontSize(9)
                                      doc.setTextColor(55, 65, 81)
                                    }
                                    doc.setFont('helvetica', 'normal')
                                    doc.setFontSize(9)
                                    doc.setTextColor(55, 65, 81)
                                    doc.text(wl, 25, y)
                                    y += 5
                                  }
                                }
                              }
                            }

                            addPageNumber()
                            const finalY = Math.min(y + 10, 282)
                            doc.setFont('helvetica', 'normal')
                            doc.setFontSize(8)
                            doc.setTextColor(200, 205, 214)
                            doc.text('Generated by JAMM PX', 105, finalY, { align: 'center' })
                            doc.save(`jamm-briefing-${new Date().toISOString().slice(0, 10)}.pdf`)
                          } else {
                            setStatusMessage('Could not generate report. Try again.')
                          }
                        } catch {
                          setStatusMessage('Could not generate report. Try again.')
                        } finally {
                          setIsDownloading(false)
                        }
                      }}
                      className="flex items-center gap-1.5 text-[11px] text-[#6B7280] hover:text-brand transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                    >
                      {!detailReady ? (
                        <span className="animate-pulse">Preparing report...</span>
                      ) : isDownloading ? (
                        <span>Generating PDF...</span>
                      ) : (
                        <>
                          <Download className="h-3 w-3" />
                          Download briefing
                        </>
                      )}
                    </button>
                  </div>
                )}
                {msg.actionConfirm && (
                  <p className="text-[11px] text-[#6B7280] mt-1 italic">{msg.actionConfirm}</p>
                )}
              </div>
            </div>
            {msg.draft && (
              <div className="ml-8 mt-2 rounded-[8px] bg-[#F0F4F8] dark:bg-[#1a2a3a] border border-[0.5px] border-[#C8CDD6] dark:border-[#3a4a5a] px-3 py-2.5">
                <p className="text-[10px] text-[#6B7280] dark:text-[#9CA3AF] mb-1.5 font-medium uppercase tracking-wide">
                  {msg.draft.type === 'CLIENT_EMAIL' ? 'Draft email' :
                   msg.draft.type === 'INVOICE_ITEMS' ? 'Draft invoice' :
                   msg.draft.type === 'STAFF_REASSIGN' ? 'Suggested reassignment' :
                   msg.draft.type === 'IRS_RENEWAL' ? 'Draft renewal request' :
                   'Draft'}
                </p>
                <textarea
                  value={editingDraftContent[i] ?? msg.draft.content}
                  onChange={(e) => setEditingDraftContent((prev) => ({ ...prev, [i]: e.target.value }))}
                  rows={Math.min(8, Math.max(3, (editingDraftContent[i] ?? msg.draft.content).split('\n').length + 1))}
                  className="w-full text-[12px] leading-[1.5] text-[#374151] dark:text-[#D1D5DB] bg-white dark:bg-[#2D2D2D] border border-[0.5px] border-[#C8CDD6] dark:border-[#484848] rounded-[6px] px-2 py-1.5 resize-none focus:outline-none focus:border-[#4A7FA5]"
                />
                {msg.draft.source && (
                  <p className="text-[10px] text-[#9CA3AF] mt-1.5 italic">
                    Based on: {msg.draft.source}
                  </p>
                )}
                <div className="flex gap-2 mt-2">
                  <button
                    onClick={() => {
                      const currentContent = editingDraftContent[i] ?? msg.draft!.content
                      navigator.clipboard.writeText(currentContent).then(() => {
                        setCopiedId(`msg-${i}`)
                        setTimeout(() => setCopiedId(null), 2000)
                      }).catch(() => {})
                    }}
                    className="text-[11px] font-medium px-2.5 py-1 rounded-[4px] border border-[0.5px] border-[#C8CDD6] dark:border-[#484848] text-[#6B7280] dark:text-[#9CA3AF] hover:border-[#4A7FA5] hover:text-[#4A7FA5] transition-colors"
                  >
                    {copiedId === `msg-${i}` ? 'Copied' : 'Copy'}
                  </button>
                  <button
                    onClick={() => {
                      const currentContent = editingDraftContent[i] ?? msg.draft!.content

                      if (msg.draft!.type === 'STAFF_REASSIGN') {
                        const confirmed = window.confirm('Open the engagement to apply this reassignment?')
                        if (confirmed) router.push('/engagements')
                        return
                      }

                      if (msg.draft!.type === 'INVOICE_ITEMS') {
                        const confirmed = window.confirm('Open billing to create this invoice?')
                        if (confirmed) router.push('/billing')
                        return
                      }

                      // CLIENT_EMAIL and IRS_RENEWAL: there is no mechanism for
                      // the AI to send a message directly. Navigate to the
                      // client's real Messages tab with the draft pre-filled,
                      // so the user sends it through the actual working send
                      // feature, after one final look.
                      const targetClientId = uiContext.entity_type === 'client' ? uiContext.entity_id : null
                      if (!targetClientId) {
                        window.alert('Open the specific client record first, then I can pre-fill this message for you to send.')
                        return
                      }
                      const confirmed = window.confirm(
                        `Open ${uiContext.entity_name ?? 'this client'}'s Messages tab with this draft ready to send?\n\nMessage:\n${currentContent}\n\nYou will have a final chance to review before sending.`
                      )
                      if (!confirmed) return

                      const alreadyOnClientPage = pathname.startsWith(`/clients/${targetClientId}`)
                      if (alreadyOnClientPage) {
                        emitConciergeAction({ type: 'prefill-message', prefillMessage: currentContent })
                      } else {
                        sessionStorage.setItem(
                          'jamm_concierge_pending',
                          JSON.stringify({
                            clientId: targetClientId,
                            prefillMessage: currentContent,
                            _ts: Date.now(),
                          }),
                        )
                      }
                      router.push(`/clients/${targetClientId}?tab=messages`)
                    }}
                    className="text-[11px] font-medium px-2.5 py-1 rounded-[4px] bg-[#1F3148] text-white hover:bg-[#2a4060] transition-colors"
                  >
                    {msg.draft.type === 'STAFF_REASSIGN' ? 'Open engagement' :
                     msg.draft.type === 'INVOICE_ITEMS' ? 'Open billing' :
                     'Open to send'}
                  </button>
                </div>
              </div>
            )}
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
        {/* Smart Paste form -- slides in above input when clipboard icon is clicked */}
        {pasteFormOpen && (
          <div className="px-4 pb-3 border-t border-[0.5px] border-[#C8CDD6] dark:border-[#484848] pt-3 flex-shrink-0 bg-white dark:bg-[#2D2D2D]">
            <div className="flex items-center justify-between mb-2">
              <span className="text-[11px] font-medium text-[#4A7FA5]">Add a client</span>
              <button
                onClick={() => {
                  setPasteFormOpen(false)
                  setPasteForm({ name: '', email: '', phone: '', entity_type: '' })
                }}
                className="text-[#6B7280] hover:text-[#1F3148] dark:hover:text-[#EDEEF0] transition-colors"
              >
                <X className="h-3.5 w-3.5" />
              </button>
            </div>
            <div className="flex flex-col gap-2">
              <input
                type="text"
                placeholder="Full name (required)"
                value={pasteForm.name}
                onChange={(e) => setPasteForm((prev) => ({ ...prev, name: e.target.value }))}
                className="w-full rounded-[6px] border border-[0.5px] border-[#C8CDD6] dark:border-[#484848] bg-[#F7F7F8] dark:bg-[#2D2D2D] text-[12px] text-[#374151] dark:text-[#9CA3AF] placeholder:text-[#9CA3AF] px-2.5 py-1.5 focus:outline-none focus:border-[#4A7FA5]"
              />
              <input
                type="email"
                placeholder="Email address"
                value={pasteForm.email}
                onChange={(e) => setPasteForm((prev) => ({ ...prev, email: e.target.value }))}
                className="w-full rounded-[6px] border border-[0.5px] border-[#C8CDD6] dark:border-[#484848] bg-[#F7F7F8] dark:bg-[#2D2D2D] text-[12px] text-[#374151] dark:text-[#9CA3AF] placeholder:text-[#9CA3AF] px-2.5 py-1.5 focus:outline-none focus:border-[#4A7FA5]"
              />
              <input
                type="tel"
                placeholder="Phone number"
                value={pasteForm.phone}
                onChange={(e) => setPasteForm((prev) => ({ ...prev, phone: e.target.value }))}
                className="w-full rounded-[6px] border border-[0.5px] border-[#C8CDD6] dark:border-[#484848] bg-[#F7F7F8] dark:bg-[#2D2D2D] text-[12px] text-[#374151] dark:text-[#9CA3AF] placeholder:text-[#9CA3AF] px-2.5 py-1.5 focus:outline-none focus:border-[#4A7FA5]"
              />
              <select
                value={pasteForm.entity_type}
                onChange={(e) => setPasteForm((prev) => ({ ...prev, entity_type: e.target.value }))}
                className="w-full rounded-[6px] border border-[0.5px] border-[#C8CDD6] dark:border-[#484848] bg-[#F7F7F8] dark:bg-[#2D2D2D] text-[12px] text-[#374151] dark:text-[#9CA3AF] px-2.5 py-1.5 focus:outline-none focus:border-[#4A7FA5]"
              >
                <option value="">Entity type (optional)</option>
                <option value="individual">Individual</option>
                <option value="business">Business</option>
                <option value="trust">Trust</option>
                <option value="estate">Estate</option>
              </select>
              <button
                onClick={handlePasteFormSubmit}
                disabled={!pasteForm.name.trim()}
                className="w-full rounded-[6px] bg-[#1F3148] text-white text-[12px] font-medium py-1.5 disabled:opacity-40 disabled:cursor-not-allowed hover:bg-[#2a4060] transition-colors"
              >
                Add Client
              </button>
            </div>
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
              onClick={() => setPasteFormOpen((prev) => !prev)}
              aria-label="Add client"
              title="Add a client"
              className="h-9 w-9 rounded-[6px] border border-[0.5px] border-[#C8CDD6] dark:border-[#484848] flex items-center justify-center transition-all flex-shrink-0 bg-white dark:bg-[#2D2D2D] hover:border-[#4A7FA5] text-[#6B7280] hover:text-[#4A7FA5]"
              style={pasteFormOpen ? { borderColor: '#4A7FA5', color: '#4A7FA5' } : {}}
            >
              <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M16 4h2a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2h2"/>
                <rect x="8" y="2" width="8" height="4" rx="1" ry="1"/>
              </svg>
            </button>
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

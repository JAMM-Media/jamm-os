// frontend/src/components/concierge/ConciergePanel.tsx
'use client'

import { useState, useRef, useEffect, useCallback } from 'react'
import { useRouter, usePathname } from 'next/navigation'
import { X, Send, Zap, Download, ChevronDown, Trash2 } from 'lucide-react'
import ReactMarkdown from 'react-markdown'
import jsPDF from 'jspdf'
import { useAuth } from '@/lib/hooks/useAuth'
import { useConfirm } from '@/lib/hooks/useConfirm'
import { useAlert } from '@/lib/hooks/useAlert'
import { useConciergeContext } from '@/lib/hooks/useConciergeContext'
import api from '@/lib/api'
import {
  emitConciergeAction,
  onConciergeAction,
  type ConciergeAction,
} from '@/lib/events/conciergeEvents'
import { assembleSSELines } from '@/lib/concierge/assembleSSEStream'

interface Message {
  role: 'user' | 'concierge'
  content: string
  actionConfirm?: string
  isBriefing?: boolean
  skipReveal?: boolean
  drafts?: Array<{ type: string; content: string; source: string | null; clientName: string | null }> | null
  options?: string[]
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

function sanitizeRevealSlice(text: string): string {
  const asteriskCount = (text.match(/\*\*/g) || []).length
  if (asteriskCount % 2 !== 0) {
    const lastIndex = text.lastIndexOf('**')
    return text.slice(0, lastIndex)
  }
  return text
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
  const { user, isLoading } = useAuth()
  const { confirm, ConfirmDialog } = useConfirm()
  const { alert, AlertDialog } = useAlert()
  const uiContext = useConciergeContext()
  const currentPage = uiContext.entity_name
    ? uiContext.entity_name
    : Object.entries(PAGE_LABELS).find(([k]) => pathname.startsWith(k))?.[1] ?? 'JAMM PX'
  const logoUrl = user ? `/api/backend/firms/logo/${user.firm_id}` : null
  const initials =
    user?.full_name?.split(' ').map((n) => n[0]).join('').slice(0, 2).toUpperCase() ?? '?'

  const [messages, setMessages] = useState<Message[]>([])
  const [notifications, setNotifications] = useState<Notification[]>([])
  const [notificationsExpanded, setNotificationsExpanded] = useState(false)
  const [input, setInput] = useState('')
  const [streaming, setStreaming] = useState(false)
  const [revealedWordCount, setRevealedWordCount] = useState(0)
  const [revealSession, setRevealSession] = useState(0)
  const revealSessionRef = useRef(0)
  const revealTimerRef = useRef<number | null>(null)
  const revealActiveRef = useRef(false)
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
  const [briefingLoading, setBriefingLoading] = useState(false)
  const [isDownloading, setIsDownloading] = useState(false)
  const [copiedId, setCopiedId] = useState<string | null>(null)
  const [editingDraftContent, setEditingDraftContent] = useState<Record<string, string>>({})
  const [detailBriefing, setDetailBriefing] = useState<string | null>(null)
  const [detailReady, setDetailReady] = useState(false)
  const [detailFailed, setDetailFailed] = useState(false)
  const detailTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null)
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
  const isLoadingAuthRef = useRef(true)
  useEffect(() => {
    isLoadingAuthRef.current = isLoading
  }, [isLoading])

  useEffect(() => {
    if (detailReady) {
      if (detailTimeoutRef.current) clearTimeout(detailTimeoutRef.current)
      detailTimeoutRef.current = null
      setDetailFailed(false)
    }
  }, [detailReady])

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  const targetWordCountRef = useRef(0)
  useEffect(() => {
    const lastMsg = messages[messages.length - 1]
    if (lastMsg && lastMsg.role === 'concierge') {
      targetWordCountRef.current = lastMsg.content.split(/\s+/).filter(Boolean).length
    }
  }, [messages])

  useEffect(() => {
    if (revealSession === 0) return
    const effectSession = revealSession
    let count = 0
    function tick() {
      // If a newer session has started since this loop instance was created,
      // bail immediately without touching any shared refs or state.
      // rAF callbacks are not bound to React's synchronous effect cleanup timing,
      // so a stale frame can fire after cleanup has already run for this session.
      if (revealSessionRef.current !== effectSession) return
      const target = targetWordCountRef.current
      // Only truly stop once the session is finalized AND count has caught up.
      // Never stop purely because target happens to be 0 or equal to count on
      // this frame -- the target may still grow as streaming content arrives.
      if (!revealActiveRef.current && count >= target) {
        revealTimerRef.current = null
        return
      }
      if (count < target) {
        count += 1
        setRevealedWordCount(count)
      }
      revealTimerRef.current = requestAnimationFrame(tick)
    }
    revealTimerRef.current = requestAnimationFrame(tick)
    return () => {
      if (revealTimerRef.current) {
        cancelAnimationFrame(revealTimerRef.current)
        revealTimerRef.current = null
      }
    }
  }, [revealSession])
  useEffect(() => {
    try {
      const stored = sessionStorage.getItem('jamm_concierge_messages')
      if (stored) {
        const parsed = JSON.parse(stored) as Message[]
        setMessages(parsed.map((m) => ({ ...m, skipReveal: true })))
        if (parsed.some((m) => m.isBriefing)) {
          if (detailTimeoutRef.current) clearTimeout(detailTimeoutRef.current)
          detailTimeoutRef.current = setTimeout(() => setDetailFailed(true), 15000)
          api.post('/concierge/morning-briefing/detail')
            .then((r) => { if (r.data?.briefing) { setDetailBriefing(r.data.briefing); setDetailReady(true) } })
            .catch(() => {})
        }
      }
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
      hasInitialized.current = false
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

  useEffect(() => {
    return onConciergeAction((action) => {
      if (action.type === 'open-panel' && action.expandNotifications) {
        setNotificationsExpanded(true)
      }
    })
  }, [])

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

  function stripTrailingMarkers(text: string, partial = false): string {
    let result = text
    let changed = true
    while (changed) {
      const before = result
      if (partial) {
        result = result.replace(/\[OPTIONS:[\s\S]*$/, '').trimEnd()
        result = result.replace(/---DRAFT:[\s\S]*$/, '').trimEnd()
      } else {
        result = result.replace(/\[OPTIONS:\[[\s\S]*?\]\]\s*$/, '').trimEnd()
      }
      result = result.replace(/\[TOPIC:\w+\]\s*$/, '').trimEnd()
      changed = result !== before
    }
    return result
  }

  const sendMessages = useCallback(
    async (thread: Message[]) => {
      revealSessionRef.current += 1
      setRevealSession(revealSessionRef.current)
      setRevealedWordCount(0)
      revealActiveRef.current = true
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
              skipReveal: true,
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

          const partial = stripTrailingMarkers(assembleSSELines(allRawLines), true)
          if (partial) {
            setMessages((prev) => {
              const updated = [...prev]
              const last = updated[updated.length - 1]
              if (last && last.role === 'concierge') {
                updated[updated.length - 1] = { ...last, content: partial }
              }
              return updated
            })
          }
        }

        assembled = assembleSSELines(allRawLines)

        console.log('[CONCIERGE RAW]', assembled)

        // Extract [OPTIONS:[...]] before stripping markers from display text
        const optionsMatch = assembled.match(/\[OPTIONS:(\[[\s\S]*?\])\]/)
        let parsedOptions: string[] = []
        if (optionsMatch) {
          try {
            const parsed = JSON.parse(optionsMatch[1])
            if (Array.isArray(parsed)) {
              parsedOptions = parsed.filter((o): o is string => typeof o === 'string')
            }
          } catch {
            console.warn('[CONCIERGE] Failed to parse OPTIONS marker:', optionsMatch[1])
          }
        }

        const filteredAssembled = filterOutput(stripTrailingMarkers(assembled))
        const parsedResult = parseDraftFromResponse(filteredAssembled)
        const textForAction = parsedResult ? parsedResult.cleanedResponse : filteredAssembled
        const cleanContent = handleConciergeAction(textForAction)
        // Set the true final word count synchronously here, before revealActiveRef
        // is set to false in the finally block. The [messages]-keyed effect that
        // normally updates this ref runs asynchronously after a re-render, which
        // means there is a race where the tick loop's stopping condition can be
        // satisfied against a stale zero target if the effect has not yet run.
        // This direct assignment closes that race completely.
        targetWordCountRef.current = cleanContent.split(/\s+/).filter(Boolean).length
        setMessages((prev) => {
          const updated = [...prev]
          const last = updated[updated.length - 1]
          if (last.role === 'concierge') {
            updated[updated.length - 1] = {
              role: 'concierge',
              content: cleanContent,
              drafts: parsedResult ? parsedResult.drafts : null,
              options: parsedOptions.length > 0 ? parsedOptions : undefined,
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
          calendar: ['Go to Calendar'],
          document_requests: ['Go to Documents'],
          portal: ['Go to Clients'],
          billing: ['Go to Billing'],
          time_tracking: ['Go to Timesheets'],
          automations: ['Go to Settings'],
          irs_authorizations: ['Go to Clients'],
          staff: ['Go to Dashboard'],
          settings: ['Go to Settings'],
          operational_data: ['Go to Dashboard'],
          qc_checklists: ['Go to Engagements'],
          signature_envelopes: ['Go to Engagements'],
          general: [],
        }

        setSuggestions(parsedResult || parsedOptions.length > 0 ? [] : (TOPIC_CHIPS[topic] ?? []).slice(0, 3))
      } catch {
        setMessages((prev) => {
          const updated = [...prev]
          updated[updated.length - 1] = {
            role: 'concierge',
            content: 'Something went wrong. Please try again.',
            skipReveal: true,
          }
          return updated
        })
      } finally {
        revealActiveRef.current = false
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
          if (isLoadingAuthRef.current) {
            let waited = 0
            while (isLoadingAuthRef.current && waited < 1500) {
              await new Promise((resolve) => setTimeout(resolve, 100))
              waited += 100
            }
          }
          if (pathname.startsWith('/dashboard')) {
            setBriefingLoading(true)
            try {
              const res = await api.post('/concierge/morning-briefing')
              if (res.status === 200 && res.data?.briefing) {
                setMessages([{ role: 'concierge', content: res.data.briefing, isBriefing: true, skipReveal: true }])
                if (detailTimeoutRef.current) clearTimeout(detailTimeoutRef.current)
                detailTimeoutRef.current = setTimeout(() => setDetailFailed(true), 15000)
                api.post('/concierge/morning-briefing/detail')
                  .then((r) => { if (r.data?.briefing) { setDetailBriefing(r.data.briefing); setDetailReady(true) } })
                  .catch(() => {})
                hasInitialized.current = true
                setBriefingLoading(false)
                return
              }
              if (res.status === 200 && res.data?.cooldown) {
                setMessages([{ role: 'concierge', content: "You're all caught up for today. I can pull up your briefing again anytime if you need it. What else is on your mind?", skipReveal: true }])
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
              skipReveal: true,
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

  async function handleClearConversation() {
    const confirmed = await confirm({ message: 'Clear this conversation? This cannot be undone.', confirmLabel: 'Clear', destructive: true })
    if (!confirmed) return
    setMessages([])
    sessionStorage.removeItem('jamm_concierge_messages')
    setSuggestions([])
  }

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

  function handleSuggestion(label: string) {
    const routes: Record<string, string> = {
      'Go to Clients': '/clients',
      'Go to Engagements': '/engagements',
      'Go to Settings': '/settings',
      'Go to Billing': '/billing',
      'Go to Documents': '/documents',
      'Go to Dashboard': '/dashboard',
      'Go to Tasks': '/tasks',
      'Go to Calendar': '/calendar',
      'Import clients': '/clients',
      'Go to Timesheets': '/timesheets',
      'Go to Staff': '/staff',
    }
    if (label === 'New engagement') {
      void executeAction({ type: 'navigate-and-open', route: '/engagements', modal: 'new-engagement' })
      return
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
    drafts: Array<{ type: string; content: string; source: string | null; clientName: string | null }>
    cleanedResponse: string
  } | null {
    const startMarker = '---DRAFT:'
    const endMarker = '---END DRAFT---'
    const firstStartIdx = text.indexOf(startMarker)
    if (firstStartIdx === -1) return null
    const cleanedResponse = text.slice(0, firstStartIdx).trimEnd()
    const drafts: Array<{ type: string; content: string; source: string | null; clientName: string | null }> = []
    let searchFrom = 0
    while (true) {
      const startIdx = text.indexOf(startMarker, searchFrom)
      if (startIdx === -1) break
      const endIdx = text.indexOf(endMarker, startIdx)
      if (endIdx === -1) break
      const typeEnd = text.indexOf('---', startIdx + startMarker.length)
      if (typeEnd === -1) break
      const type = text.slice(startIdx + startMarker.length, typeEnd).trim()
      let rawBlock = text.slice(typeEnd + 3, endIdx).trim()
      let source: string | null = null
      const sourceMatch = rawBlock.match(/SOURCE:\s*([\s\S]+?)(?:\n\s*\n|$)/)
      if (sourceMatch) {
        source = sourceMatch[1].replace(/\s+/g, ' ').trim()
        rawBlock = rawBlock.slice(0, sourceMatch.index).trim()
      }
      let clientName: string | null = null
      const clientMatch = rawBlock.match(/CLIENT:\s*(.+?)(?:\n|$)/)
      if (clientMatch) {
        clientName = clientMatch[1].trim() || null
        rawBlock = rawBlock.slice(0, clientMatch.index).trim()
      }
      if (type && rawBlock) {
        drafts.push({ type, content: rawBlock, source, clientName })
      }
      searchFrom = endIdx + endMarker.length
    }
    if (drafts.length === 0) return null
    return { drafts, cleanedResponse }
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
      if (action.type === 'show_briefing_again') {
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
    if (action.type === 'show_briefing_again') {
      setDetailFailed(false)
      if (detailTimeoutRef.current) clearTimeout(detailTimeoutRef.current)
      detailTimeoutRef.current = setTimeout(() => setDetailFailed(true), 15000)
      try {
        const res = await api.post('/concierge/morning-briefing/detail')
        if (res.status === 200 && res.data?.briefing) {
          setDetailBriefing(res.data.briefing)
          setDetailReady(true)
          setMessages((prev) => {
            const updated = [...prev]
            const last = updated[updated.length - 1]
            if (last && last.role === 'concierge') {
              updated[updated.length - 1] = { ...last, isBriefing: true }
            }
            return updated
          })
        }
      } catch {
        // non-fatal -- message text already shown, download button simply will not appear
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
              const ok = await confirm('You have unsaved changes. Navigate away?')
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
        const ok = await confirm('You have unsaved changes. Navigate away?')
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
      {ConfirmDialog}
      {AlertDialog}
      {hasMounted && isOpen && (
        <div
          style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.25)', zIndex: 39, pointerEvents: 'none' }}
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
        className="bg-surface-card dark:bg-dark-card border-l-2 border-concierge shadow-xl"
      >
        {/* Header */}
        <div
          className="flex items-center justify-between px-4 border-b border-[0.5px] border-surface-border dark:border-dark-border flex-shrink-0"
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
              <div className="h-6 w-6 rounded-sm bg-brand-btn flex items-center justify-center flex-shrink-0">
                <span className="text-[10px] font-medium text-white">{initials}</span>
              </div>
            )}
            <div className="flex items-center gap-1.5">
              <span className="w-1.5 h-1.5 rounded-full bg-concierge flex-shrink-0" />
              <span className="text-[14px] font-medium font-display text-brand dark:text-foreground">
                JAMM Concierge
              </span>
            </div>
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
                    ? 'border-brand bg-brand text-white dark:border-brand-light dark:bg-brand-light'
                    : 'border-surface-border dark:border-dark-border bg-transparent text-muted-foreground hover:border-brand hover:text-brand dark:hover:border-brand-light dark:hover:text-brand-light'
                }`}
              >
                <Zap className={`h-3 w-3 transition-all ${autopilotOn ? 'fill-white stroke-white' : 'fill-none'}`} />
                Autopilot
              </button>
              <div className="absolute right-0 top-full mt-1.5 w-60 px-3 py-2 rounded-[6px] bg-surface-card dark:bg-dark-card border border-[0.5px] border-surface-border dark:border-dark-border text-foreground text-[11px] leading-relaxed opacity-0 group-hover:opacity-100 transition-opacity duration-150 pointer-events-none z-50 shadow-lg">
                When ON, I&apos;ll navigate the app and open forms for you automatically. When OFF, I&apos;ll just tell you where to go.
              </div>
            </div>

            {messages.length > 1 && (
              <button
                onClick={handleClearConversation}
                aria-label="Clear conversation"
                className="text-[#DC2626]/40 dark:text-[#F87171]/30 hover:text-[#DC2626] dark:hover:text-[#F87171] transition-colors"
              >
                <Trash2 className="h-4 w-4" />
              </button>
            )}

            <button
              onClick={onClose}
              aria-label="Close concierge panel"
              className="text-muted-foreground hover:text-brand dark:hover:text-foreground transition-colors"
            >
              <X className="h-4 w-4" />
            </button>
          </div>
        </div>

        {autopilotOn && (
          <div className="px-4 py-1 bg-brand-light/10 dark:bg-brand-dark border-b border-[0.5px] border-surface-border dark:border-dark-border">
            <p className="text-[11px] text-brand-light dark:text-brand-muted">Autopilot on. I'll navigate for you.</p>
          </div>
        )}

        {/* Notification cards */}
        {notifications.length > 0 && (
          <div className="flex flex-col gap-2 px-4 pt-3 flex-shrink-0">
            <div className="flex items-center justify-between px-0.5">
              <button
                onClick={() => setNotificationsExpanded((prev) => !prev)}
                className="flex items-center gap-1.5"
              >
                <span className="w-1.5 h-1.5 rounded-full bg-[#D97706]" />
                <span className="text-[10px] font-semibold uppercase tracking-wide text-status-amber-text dark:text-[#D97706]">
                  {notifications.length} {notifications.length === 1 ? 'Alert' : 'Alerts'}
                </span>
                <ChevronDown
                  className={`h-3 w-3 text-status-amber-text dark:text-[#D97706] transition-transform ${notificationsExpanded ? 'rotate-180' : ''}`}
                />
              </button>
              {notificationsExpanded && (
                <button
                  onClick={() => notifications.forEach((n) => dismissNotification(n.id))}
                  className="text-[10px] font-medium text-muted-foreground hover:text-brand dark:hover:text-foreground transition-colors"
                >
                  Dismiss all
                </button>
              )}
            </div>
            {notificationsExpanded && (
              <div className="flex flex-col gap-2 overflow-y-auto max-h-64">
                {notifications.map((n) => {
              const draft = n.metadata?.draft as string | undefined
              return (
                <div
                  key={n.id}
                  className="flex flex-col gap-2 bg-white dark:bg-dark-page border border-[0.5px] border-surface-border dark:border-dark-border border-l-[3px] border-l-[#D97706] rounded-[8px] px-3 py-2.5"
                >
                  <div className="flex items-start gap-2">
                    <p
                      className="flex-1 text-[12px] leading-[1.5] text-brand dark:text-foreground cursor-pointer"
                      onClick={() => { dismissNotification(n.id); handleSend(n.message) }}
                    >
                      {n.message}
                    </p>
                    <button
                      onClick={(e) => { e.stopPropagation(); dismissNotification(n.id) }}
                      aria-label="Dismiss notification"
                      className="flex-shrink-0 text-muted-foreground hover:text-brand dark:hover:text-foreground transition-colors mt-0.5"
                    >
                      <X className="h-3.5 w-3.5" />
                    </button>
                  </div>
                  {draft && (
                    <div className="mt-1 rounded-[6px] bg-surface-card dark:bg-dark-card border border-[0.5px] border-surface-border dark:border-dark-border px-2.5 py-2">
                      <p className="text-[11px] text-muted-foreground mb-1.5 font-medium uppercase tracking-wide">Draft</p>
                      <p className="text-[12px] leading-[1.5] text-foreground whitespace-pre-wrap">{draft}</p>
                      <div className="flex gap-2 mt-2">
                        <button
                          onClick={() => {
                            navigator.clipboard.writeText(draft).then(() => {
                              setCopiedId(n.id)
                              setTimeout(() => setCopiedId(null), 2000)
                            }).catch(() => {})
                          }}
                          className="text-[11px] font-medium px-2.5 py-1 rounded-[4px] border border-[0.5px] border-surface-border dark:border-dark-border text-muted-foreground hover:border-brand-light hover:text-brand-light transition-colors"
                        >
                          {copiedId === n.id ? 'Copied' : 'Copy'}
                        </button>
                        <button
                          onClick={async () => {
                            const notifClientId = typeof n.metadata?.client_id === 'string' ? n.metadata.client_id : null
                            const targetClientId = notifClientId ?? (uiContext.entity_type === 'client' ? uiContext.entity_id : null)
                            if (!targetClientId) {
                              alert('No client record could be identified for this draft. Open the client directly and use the Messages tab to send it.')
                              return
                            }
                            const confirmed = await confirm(
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
                          className="text-[11px] font-medium px-2.5 py-1 rounded-[4px] bg-brand text-white hover:opacity-90 transition-colors"
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
          </div>
        )}

        {/* Message feed */}
        <div className="flex-1 min-h-0 overflow-y-auto p-4 flex flex-col gap-3">

          {/* Opening message fires automatically via __OPEN__ sentinel on first open */}

          {briefingLoading && messages.length === 0 && (
            <div className="flex gap-2.5 px-3 py-2">
              <div className="w-7 h-7 rounded-full bg-concierge flex items-center justify-center flex-shrink-0">
                <span className="text-white text-[10px] font-medium">JC</span>
              </div>
              <div className="flex flex-col gap-2 flex-1 pt-1">
                <div className="h-3 w-32 bg-surface-border dark:bg-dark-border animate-pulse rounded" />
                <div className="flex flex-col gap-1.5 ml-3 mt-0.5">
                  <div className="h-2 w-full bg-surface-border dark:bg-dark-border animate-pulse rounded" />
                  <div className="h-2 w-4/5 bg-surface-border dark:bg-dark-border animate-pulse rounded" />
                </div>
                <div className="h-3 w-28 bg-surface-border dark:bg-dark-border animate-pulse rounded mt-2" />
                <div className="flex flex-col gap-1.5 ml-3 mt-0.5">
                  <div className="h-2 w-full bg-surface-border dark:bg-dark-border animate-pulse rounded" />
                  <div className="h-2 w-3/4 bg-surface-border dark:bg-dark-border animate-pulse rounded" />
                  <div className="h-2 w-2/3 bg-surface-border dark:bg-dark-border animate-pulse rounded" />
                </div>
                <div className="h-px w-full bg-surface-border dark:bg-dark-border mt-2" />
                <div className="h-2 w-36 bg-surface-border dark:bg-dark-border animate-pulse rounded mt-2" />
                <div className="h-2 w-20 bg-surface-border dark:bg-dark-border animate-pulse rounded mt-1" />
              </div>
            </div>
          )}

          {messages.length === 0 && !briefingLoading && !streaming && (
            <div className="flex flex-col gap-2 px-1 py-1">
              <p className="text-[11px] text-muted-foreground px-2">Try asking</p>
              <div className="flex flex-wrap gap-1.5 px-1">
                {getStarterPrompts().map((prompt) => (
                  <button
                    key={prompt}
                    onClick={() => handleSend(prompt)}
                    className="text-[11px] font-medium px-3 py-1.5 rounded-full border border-surface-border dark:border-dark-border text-brand dark:text-foreground bg-white dark:bg-dark-page hover:border-brand-light hover:text-brand-light transition-colors"
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
                <div className="flex-shrink-0 w-6 h-6 rounded-full bg-concierge flex items-center justify-center mt-1">
                  <span className="text-[9px] font-medium text-white">JC</span>
                </div>
              )}
              <div
                className={`text-[13px] leading-[1.6] px-3 py-2 rounded-[12px] max-w-[75%] ${msg.role === 'user' ? 'text-white' : 'bg-surface-page dark:bg-dark-page text-brand dark:text-foreground'}`}
                style={msg.role === 'user' ? { background: '#1F3148', color: '#FFFFFF' } : undefined}
              >
                {msg.content ? (
                  <div className={`prose prose-sm max-w-none text-[13px] ${msg.role === 'user' ? 'text-white' : 'text-foreground'}`}>
                    <ReactMarkdown
                      components={{
                        h2: ({node, ...props}) => <h2 className="text-[13px] font-semibold font-display text-brand dark:text-foreground mt-3 mb-1 first:mt-0" {...props} />,
                        h3: ({node, ...props}) => <h3 className="text-[12px] font-semibold text-brand-light uppercase tracking-wide mt-2.5 mb-1" {...props} />,
                        hr: ({node, ...props}) => <hr className="border-t border-surface-border dark:border-dark-border my-2" />,
                        ul: ({node, ...props}) => <ul className="list-disc list-outside ml-4 my-1 space-y-0.5" {...props} />,
                        ol: ({node, ...props}) => <ol className="list-decimal list-outside ml-4 my-1 space-y-0.5" {...props} />,
                        li: ({node, ...props}) => <li className="leading-snug" {...props} />,
                        p: ({node, ...props}) => <p className="mb-1 last:mb-0" {...props} />,
                        strong: ({node, children, ...props}) => {
                          const text = Array.isArray(children)
                            ? children.map(c => (typeof c === 'string' ? c : '')).join('')
                            : typeof children === 'string' ? children : ''
                          const isOption = !!(text && msg.options?.includes(text))
                          return (
                            <strong
                              {...props}
                              className={`font-display font-medium text-brand dark:text-foreground${isOption ? ' cursor-pointer underline decoration-dotted underline-offset-2 hover:text-brand-light dark:hover:text-brand-light transition-colors' : ''}`}
                              onClick={isOption ? () => void handleSend(text) : undefined}
                            >
                              {children}
                            </strong>
                          )
                        },
                        em: ({node, ...props}) => <em className="not-italic text-[11px] text-muted-foreground" {...props} />,
                      }}
                    >
                      {!msg.skipReveal && i === messages.length - 1 && revealedWordCount < msg.content.split(/\s+/).filter(Boolean).length
                        ? sanitizeRevealSlice(msg.content.split(/\s+/).filter(Boolean).slice(0, revealedWordCount).join(' '))
                        : msg.content}
                    </ReactMarkdown>
                  </div>
                ) : (streaming && i === messages.length - 1) ? (
                  <span className="text-[13px] text-concierge animate-pulse">Thinking...</span>
                ) : null}
                {msg.isBriefing && (
                  <div className="mt-2">
                    <button
                      disabled={(!detailReady && !detailFailed) || isDownloading}
                      onClick={async () => {
                        setDetailFailed(false)
                        setIsDownloading(true)
                        try {
                          let briefingText = detailBriefing
                          if (!briefingText) {
                            const res = await api.post('/concierge/morning-briefing/detail')
                            if (res.status === 200 && res.data?.briefing) {
                              briefingText = res.data.briefing
                              setDetailBriefing(res.data.briefing)
                              setDetailReady(true)
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
                      className="flex items-center gap-1.5 text-[11px] text-muted-foreground hover:text-brand transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                    >
                      {isDownloading ? (
                        <span>Generating PDF...</span>
                      ) : !detailReady && detailFailed ? (
                        <span>Could not load report - tap to retry</span>
                      ) : !detailReady ? (
                        <span className="animate-pulse">Preparing report...</span>
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
                  <p className="text-[11px] text-muted-foreground mt-1 italic">{msg.actionConfirm}</p>
                )}
              </div>
            </div>
            {(msg.drafts ?? []).map((draft, draftIdx) => {
              const draftKey = `${i}-${draftIdx}`
              const currentContent = editingDraftContent[draftKey] ?? draft.content
              const isBatch = (msg.drafts?.length ?? 0) > 1
              return (
                <div key={draftIdx} className="ml-8 mt-2 rounded-[8px] bg-surface-card dark:bg-dark-card border border-[0.5px] border-surface-border dark:border-dark-border px-3 py-2.5">
                  <p className="text-[10px] text-muted-foreground mb-1.5 font-medium uppercase tracking-wide">
                    {draft.type === 'CLIENT_EMAIL' ? 'Draft email' :
                     draft.type === 'INVOICE_ITEMS' ? 'Draft invoice' :
                     draft.type === 'STAFF_REASSIGN' ? 'Suggested reassignment' :
                     draft.type === 'IRS_RENEWAL' ? 'Draft renewal request' :
                     'Draft'}
                    {isBatch && draft.clientName ? ` — ${draft.clientName}` : ''}
                  </p>
                  <textarea
                    value={currentContent}
                    onChange={(e) => setEditingDraftContent((prev) => ({ ...prev, [draftKey]: e.target.value }))}
                    rows={Math.min(8, Math.max(3, currentContent.split('\n').length + 1))}
                    className="w-full text-[12px] leading-[1.5] text-foreground bg-white dark:bg-dark-page border border-[0.5px] border-surface-border dark:border-dark-border rounded-[6px] px-2 py-1.5 resize-none focus:outline-none focus:border-brand-light"
                  />
                  {draft.source && (
                    <p className="text-[10px] text-muted-foreground mt-1.5 italic">
                      Based on: {draft.source}
                    </p>
                  )}
                  <div className="flex gap-2 mt-2">
                    <button
                      onClick={async () => {
                        navigator.clipboard.writeText(currentContent).then(() => {
                          setCopiedId(`msg-${draftKey}`)
                          setTimeout(() => setCopiedId(null), 2000)
                        }).catch(() => {})
                      }}
                      className="text-[11px] font-medium px-2.5 py-1 rounded-[4px] border border-[0.5px] border-surface-border dark:border-dark-border text-muted-foreground hover:border-brand-light hover:text-brand-light transition-colors"
                    >
                      {copiedId === `msg-${draftKey}` ? 'Copied' : 'Copy'}
                    </button>
                    <button
                      onClick={async () => {
                        if (draft.type === 'STAFF_REASSIGN') {
                          const confirmed = await confirm('Open the engagement to apply this reassignment?')
                          if (confirmed) router.push('/engagements')
                          return
                        }

                        if (draft.type === 'INVOICE_ITEMS') {
                          const confirmed = await confirm('Open billing to create this invoice?')
                          if (confirmed) router.push('/billing')
                          return
                        }

                        // CLIENT_EMAIL and IRS_RENEWAL: navigate to the client's
                        // Messages tab with the draft pre-filled so the firm owner
                        // sends it through the actual send feature after a final look.
                        const navigateToClient = (clientId: string, clientDisplayName: string) => {
                          confirm(
                            `Open ${clientDisplayName}'s Messages tab with this draft ready to send?\n\nMessage:\n${currentContent}\n\nYou will have a final chance to review before sending.`
                          ).then((confirmed) => {
                            if (!confirmed) return
                            const alreadyOnClientPage = pathname.startsWith(`/clients/${clientId}`)
                            if (alreadyOnClientPage) {
                              emitConciergeAction({ type: 'prefill-message', prefillMessage: currentContent })
                            } else {
                              sessionStorage.setItem(
                                'jamm_concierge_pending',
                                JSON.stringify({ clientId, prefillMessage: currentContent, _ts: Date.now() }),
                              )
                            }
                            router.push(`/clients/${clientId}?tab=messages`)
                          }).catch(() => {})
                        }

                        const contextClientId = uiContext.entity_type === 'client' ? uiContext.entity_id : null
                        if (contextClientId && !isBatch) {
                          navigateToClient(contextClientId, uiContext.entity_name ?? 'this client')
                          return
                        }

                        const draftClientName = draft.clientName
                        if (draftClientName) {
                          try {
                            const result = await api.get('/clients/', { params: { q: draftClientName, limit: 5 } })
                            const clients: Array<{ id: string; name: string }> = result.data.items ?? []
                            const exactMatch = clients.find((c) => c.name.toLowerCase() === draftClientName.toLowerCase())
                            const match = exactMatch ?? (clients.length === 1 ? clients[0] : null)
                            if (match) {
                              navigateToClient(match.id, match.name)
                              return
                            }
                          } catch {
                            // fall through to fallback
                          }
                          alert(`Could not find a client named "${draftClientName}" to open directly. Search for them in Clients and use the Messages tab to send this draft.`)
                          return
                        }

                        alert('No specific client was identified for this draft. Open the client record directly and use the Messages tab to send it.')
                      }}
                      className="text-[11px] font-medium px-2.5 py-1 rounded-[4px] bg-brand text-white hover:opacity-90 transition-colors"
                    >
                      {draft.type === 'STAFF_REASSIGN' ? 'Open engagement' :
                       draft.type === 'INVOICE_ITEMS' ? 'Open billing' :
                       'Open to send'}
                    </button>
                  </div>
                </div>
              )
            })}
            {!autopilotOn && suggestions.length > 0 && i === messages.length - 1 && msg.role === 'concierge' && revealedWordCount >= msg.content.split(/\s+/).filter(Boolean).length && (
              <div className="flex flex-wrap gap-2 mt-2 ml-8">
                {suggestions.map((s) => (
                  <button
                    key={s}
                    onClick={() => handleSuggestion(s)}
                    className="text-[11px] font-medium px-3 py-1.5 rounded-full border border-surface-border dark:border-dark-border text-brand dark:text-foreground bg-white dark:bg-dark-page hover:border-brand-light hover:text-brand-light transition-colors"
                  >
                    {s}
                  </button>
                ))}
              </div>
            )}
            {msg.options && msg.options.length > 0 && i === messages.length - 1 && msg.role === 'concierge' && revealedWordCount >= msg.content.split(/\s+/).filter(Boolean).length && (
              <div className="flex flex-wrap gap-2 mt-3 ml-8">
                {msg.options.map((opt) => (
                  <button
                    key={opt}
                    onClick={() => void handleSend(opt)}
                    className="text-[11px] font-medium px-3 py-1.5 rounded-[6px] border border-brand-light text-brand-light bg-white dark:bg-dark-page hover:bg-brand-light hover:text-white transition-colors"
                  >
                    {opt}
                  </button>
                ))}
              </div>
            )}
            </div>
          ))}
          <p
            className={`text-[11px] text-muted-foreground text-center transition-opacity duration-500 ${statusMessage ? 'opacity-100' : 'opacity-0'}`}
            style={{ minHeight: 16 }}
          >
            {statusMessage}
          </p>
          <div ref={messagesEndRef} />
        </div>

        {currentPage && (
          <div className="px-3 pt-2 pb-0">
            <span className="inline-flex items-center gap-1 text-[10px] font-medium text-muted-foreground">
              <span className="w-1.5 h-1.5 rounded-full bg-concierge" />
              You are on: {currentPage}
            </span>
          </div>
        )}
        {/* Input area */}
        <div className="p-4 border-t border-[0.5px] border-surface-border dark:border-dark-border flex-shrink-0">
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
              className="flex-1 rounded-[6px] border border-[0.5px] border-surface-border focus:border-brand-light focus:outline-none bg-surface-input dark:bg-dark-page text-[13px] text-foreground dark:text-muted-foreground placeholder:text-muted-foreground p-2.5 resize-none transition-colors disabled:opacity-60"
              style={{ minHeight: 36, maxHeight: 96, overflowY: 'auto' }}
            />
            <button
              onClick={() => handleSend()}
              disabled={!input.trim() || streaming}
              aria-label="Send message"
              className="h-9 w-9 rounded-[6px] bg-brand flex items-center justify-center transition-opacity disabled:opacity-40 disabled:cursor-not-allowed flex-shrink-0"
            >
              <Send className="h-4 w-4 text-white" />
            </button>
          </div>
        </div>
      </div>
    </>
  )
}

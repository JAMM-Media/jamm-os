// frontend/src/components/concierge/ConciergePanel.tsx
'use client'

import { useState, useRef, useEffect, useCallback } from 'react'
import { X, Send } from 'lucide-react'
import ReactMarkdown from 'react-markdown'
import { useAuth } from '@/lib/hooks/useAuth'
import api from '@/lib/api'

interface Message {
  role: 'user' | 'concierge'
  content: string
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

export function ConciergePanel({ isOpen, onClose }: ConciergePanelProps) {
  const { user } = useAuth()
  const logoUrl = user ? `/api/backend/firms/logo/${user.firm_id}` : null
  const initials = user?.full_name?.split(' ').map((n) => n[0]).join('').slice(0, 2).toUpperCase() ?? '?'
  const [messages, setMessages] = useState<Message[]>([])
  const [input, setInput] = useState('')
  const [streaming, setStreaming] = useState(false)
  const [showStarters, setShowStarters] = useState(true)
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const textareaRef = useRef<HTMLTextAreaElement>(null)
  const hasInitialized = useRef(false)

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  const sendMessages = useCallback(async (thread: Message[]) => {
    setStreaming(true)
    setShowStarters(false)
    setMessages((prev) => [...prev, { role: 'concierge', content: '' }])

    const authHeader = api.defaults.headers.common['Authorization']
    const headers: Record<string, string> = { 'Content-Type': 'application/json' }
    if (authHeader) headers['Authorization'] = String(authHeader)

    const apiMessages = thread.map((m) => ({
      role: m.role === 'concierge' ? 'assistant' : 'user',
      content: m.content,
    }))

    try {
      const res = await fetch('/api/backend/concierge/chat', {
        method: 'POST',
        headers,
        body: JSON.stringify({ messages: apiMessages }),
      })

      if (!res.ok || !res.body) {
        setMessages((prev) => {
          const updated = [...prev]
          updated[updated.length - 1] = { role: 'concierge', content: 'Something went wrong. Please try again.' }
          return updated
        })
        return
      }

      const reader = res.body.getReader()
      const decoder = new TextDecoder()
      let buffer = ''

      while (true) {
        const { done, value } = await reader.read()
        if (done) break
        buffer += decoder.decode(value, { stream: true })
        const lines = buffer.split('\n')
        buffer = lines.pop() ?? ''
        for (const line of lines) {
          if (line.startsWith('data: ')) {
            const chunk = line.slice(6)
            setMessages((prev) => {
              const updated = [...prev]
              updated[updated.length - 1] = {
                role: 'concierge',
                content: updated[updated.length - 1].content + chunk,
              }
              return updated
            })
          }
        }
      }
    } catch {
      setMessages((prev) => {
        const updated = [...prev]
        updated[updated.length - 1] = { role: 'concierge', content: 'Something went wrong. Please try again.' }
        return updated
      })
    } finally {
      setStreaming(false)
    }
  }, [])

  useEffect(() => {
    if (isOpen && !hasInitialized.current) {
      hasInitialized.current = true
    }
    if (isOpen) {
      setTimeout(() => textareaRef.current?.focus(), 250)
    }
  }, [isOpen, sendMessages])

  async function handleSend(text?: string) {
    const msg = (text ?? input).trim()
    if (!msg || streaming) return
    setInput('')
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
          <button
            onClick={onClose}
            aria-label="Close concierge panel"
            className="text-[#6B7280] hover:text-[#1F3148] dark:hover:text-[#EDEEF0] transition-colors"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        {/* Message feed */}
        <div className="flex-1 overflow-y-auto p-4 flex flex-col gap-3">

          {/* Empty state with starter prompts */}
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
            <div key={i} className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
              <div
                className="text-[13px] leading-[1.6] px-3 py-2 rounded-[12px] max-w-[75%] whitespace-pre-wrap"
                style={
                  msg.role === 'user'
                    ? { background: '#1F3148', color: '#FFFFFF' }
                    : { background: '#E4E6EA', color: '#1F3148' }
                }
              >
                {msg.content && (!streaming || i < messages.length - 1) ? (
                  <ReactMarkdown
                    components={{
                      p: ({ children }) => <p className="mb-2 last:mb-0">{children}</p>,
                      ol: ({ children }) => <ol className="list-decimal pl-4 space-y-1">{children}</ol>,
                      ul: ({ children }) => <ul className="list-disc pl-4 space-y-1">{children}</ul>,
                      li: ({ children }) => <li>{children}</li>,
                      strong: ({ children }) => <strong className="font-medium">{children}</strong>,
                    }}
                  >
                    {msg.content}
                  </ReactMarkdown>
                ) : msg.content && streaming && i === messages.length - 1 ? (
                  <span className="text-[13px] text-[#6B7280]">Thinking...</span>
                ) : (
                  streaming && i === messages.length - 1 ? (
                    <span className="text-[13px] text-[#6B7280] animate-pulse">Thinking...</span>
                  ) : (
                    ''
                  )
                )}
              </div>
            </div>
          ))}
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

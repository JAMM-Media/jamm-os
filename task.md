\STANDING RULES:
- Never use passlib. Use bcrypt directly.
- Background tasks must create their own SessionLocal() in try/finally.

TASK: Build client messages tab — replace placeholder with working UI

FILE TO EDIT: frontend/src/app/(dashboard)/clients/[id]/page.tsx

PROBLEM: The messages tab currently shows a static empty state with no
ability to send or view messages. The backend is fully built.

Endpoints:
- GET /clients/{client_id}/messages → list of messages
- POST /clients/{client_id}/messages → send message, body: { body: string }

Message shape from server:
  id, body, sender_name, sender_role, created_at

sender_role is either "staff" or "client" — use this to align messages
(staff on right, client on left, like iMessage).

REPLACE the entire messages tab content block:

Find:
  {activeTab === 'messages' && (
    <div className="flex flex-col items-center justify-center py-24 gap-[10px]">
      <div className="flex items-center justify-center w-10 h-10 rounded-lg bg-surface-card dark:bg-dark-card border border-[0.5px] border-surface-border dark:border-dark-border">
        <span className="text-[18px]">💬</span>
      </div>
      <p className="text-[13px] font-medium text-brand dark:text-[#EDEEF0]">
        No messages yet
      </p>
      <p className="text-[12px] text-[#6B7280]">
        Messages with this client will appear here.
      </p>
    </div>
  )}

Replace with a full messaging UI. Add the following state at the top
of the component (near other useState declarations):

  const [clientMessages, setClientMessages] = useState<Array<{
    id: string
    body: string
    senderName: string | null
    senderRole: string
    createdAt: string
  }>>([])
  const [messagesLoading, setMessagesLoading] = useState(false)
  const [messageCompose, setMessageCompose] = useState('')
  const [messageSending, setMessageSending] = useState(false)

Add a useEffect to fetch messages when the messages tab is active:

  useEffect(() => {
    if (activeTab !== 'messages' || !clientId) return
    setMessagesLoading(true)
    api.get(`/clients/${clientId}/messages`)
      .then((res) => {
        const items = Array.isArray(res.data) ? res.data : (res.data.items ?? [])
        setClientMessages(items.map((m: Record<string, unknown>) => ({
          id: String(m.id),
          body: String(m.body ?? ''),
          senderName: m.sender_name ? String(m.sender_name) : null,
          senderRole: String(m.sender_role ?? 'staff'),
          createdAt: String(m.created_at ?? ''),
        })))
      })
      .catch(() => {})
      .finally(() => setMessagesLoading(false))
  }, [activeTab, clientId])

Add a handleSendMessage function:

  const handleSendMessage = async () => {
    if (!messageCompose.trim() || messageSending) return
    setMessageSending(true)
    try {
      const res = await api.post(`/clients/${clientId}/messages`, {
        body: messageCompose.trim()
      })
      const m = res.data
      setClientMessages((prev) => [...prev, {
        id: String(m.id),
        body: String(m.body ?? ''),
        senderName: m.sender_name ? String(m.sender_name) : null,
        senderRole: String(m.sender_role ?? 'staff'),
        createdAt: String(m.created_at ?? ''),
      }])
      setMessageCompose('')
    } catch {
      toast.error('Failed to send message')
    } finally {
      setMessageSending(false)
    }
  }

Replace the placeholder with this UI:

  {activeTab === 'messages' && (
    <div className="flex flex-col h-[500px]">
      {/* Messages list */}
      <div className="flex-1 overflow-y-auto px-4 py-4 space-y-3">
        {messagesLoading ? (
          <div className="flex items-center justify-center py-8">
            <Loader2 className="h-5 w-5 animate-spin text-[#6B7280]" />
          </div>
        ) : clientMessages.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-16 gap-2">
            <div className="flex items-center justify-center w-10 h-10 rounded-lg bg-surface-card dark:bg-dark-card border border-[0.5px] border-surface-border dark:border-dark-border">
              <span className="text-[18px]">💬</span>
            </div>
            <p className="text-[13px] font-medium text-brand dark:text-[#EDEEF0]">No messages yet</p>
            <p className="text-[12px] text-[#6B7280]">Send the first message below.</p>
          </div>
        ) : (
          clientMessages.map((msg) => {
            const isStaff = msg.senderRole === 'staff'
            return (
              <div key={msg.id} className={`flex flex-col gap-1 ${isStaff ? 'items-end' : 'items-start'}`}>
                <div
                  className={`max-w-[70%] px-3 py-2 rounded-xl text-[13px] leading-relaxed ${
                    isStaff
                      ? 'bg-[#1F3148] text-white rounded-br-sm'
                      : 'bg-surface-card dark:bg-dark-card text-[#374151] dark:text-[#EDEEF0] rounded-bl-sm border border-[#C8CDD6] dark:border-[#484848]'
                  }`}
                >
                  {msg.body}
                </div>
                <div className="flex items-center gap-1.5">
                  <span className="text-[11px] text-[#6B7280]">
                    {msg.senderName ?? (isStaff ? 'You' : 'Client')}
                  </span>
                  <span className="text-[11px] text-[#9CA3AF]">
                    {new Date(msg.createdAt).toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit' })}
                  </span>
                </div>
              </div>
            )
          })
        )}
      </div>

      {/* Compose box */}
      <div className="flex-shrink-0 border-t border-[#C8CDD6] dark:border-[#484848] px-4 py-3 flex gap-2 items-end">
        <textarea
          value={messageCompose}
          onChange={(e) => setMessageCompose(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
              e.preventDefault()
              handleSendMessage()
            }
          }}
          placeholder="Send a message to this client..."
          rows={1}
          className="flex-1 resize-none bg-surface-input dark:bg-dark-page border border-[#C8CDD6] dark:border-[#484848] focus:border-[#4A7FA5] dark:focus:border-[#4A7FA5] rounded-lg px-3 py-2 text-[13px] text-[#374151] dark:text-[#9CA3AF] placeholder:text-[#9CA3AF] outline-none transition-colors"
          style={{ minHeight: 36, maxHeight: 120 }}
        />
        <button
          onClick={handleSendMessage}
          disabled={!messageCompose.trim() || messageSending}
          className="flex-shrink-0 h-9 w-9 flex items-center justify-center rounded-lg bg-[#1F3148] text-white hover:bg-[#3A6A94] disabled:opacity-40 transition-colors"
        >
          {messageSending ? (
            <Loader2 className="h-4 w-4 animate-spin" />
          ) : (
            <Send className="h-4 w-4" />
          )}
        </button>
      </div>
    </div>
  )}

Make sure Send and Loader2 are imported from lucide-react — they
likely already are. If not, add them to the existing lucide-react import.

After making changes show:
1. The new state declarations
2. The useEffect
3. Confirm Send and Loader2 are imported
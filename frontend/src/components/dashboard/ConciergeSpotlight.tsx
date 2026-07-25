// frontend/src/components/dashboard/ConciergeSpotlight.tsx
'use client'

import { useState, useEffect, useCallback } from 'react'
import { useRouter, usePathname } from 'next/navigation'
import { ChevronDown, ChevronUp } from 'lucide-react'
import api from '@/lib/api'
import { useConfirm } from '@/lib/hooks/useConfirm'
import { useAlert } from '@/lib/hooks/useAlert'
import { emitConciergeAction } from '@/lib/events/conciergeEvents'

interface Notification {
  id: string
  trigger_type: string
  message: string
  created_at: string
  metadata?: Record<string, unknown> | null
}

const MINIMIZED_KEY = 'jamm_concierge_spotlight_minimized'

export function ConciergeSpotlight() {
  const router = useRouter()
  const pathname = usePathname()
  const { confirm, ConfirmDialog } = useConfirm()
  const { alert, AlertDialog } = useAlert()
  const [featured, setFeatured] = useState<Notification | null | undefined>(undefined)
  const [copiedId, setCopiedId] = useState<string | null>(null)
  const [minimized, setMinimized] = useState(false)

  useEffect(() => {
    const saved = sessionStorage.getItem(MINIMIZED_KEY) === 'true'
    if (saved) setMinimized(true)
  }, [])

  const dismissNotification = useCallback(async (id: string) => {
    setFeatured(null)
    try {
      await api.patch(`/concierge/notifications/${id}/read`)
    } catch {
      // already removed from UI
    }
  }, [])

  useEffect(() => {
    api
      .get('/concierge/notifications')
      .then((res) => {
        const items = (res.data.items ?? []) as Notification[]
        if (items.length === 0) {
          setFeatured(null)
          return
        }
        const withDraft = items.find((n) => typeof n.metadata?.draft === 'string')
        setFeatured(withDraft ?? items[0])
      })
      .catch(() => {
        setFeatured(null)
      })
  }, [])

  if (featured === undefined || featured === null) return null

  const draft = featured.metadata?.draft as string | undefined

  function toggleMinimized(e: React.MouseEvent) {
    e.stopPropagation()
    setMinimized((prev) => {
      const next = !prev
      sessionStorage.setItem(MINIMIZED_KEY, String(next))
      return next
    })
  }

  function handleContainerClick() {
    emitConciergeAction({ type: 'open-panel', expandNotifications: true })
  }

  return (
    <>
      {ConfirmDialog}
      {AlertDialog}
      <div
        onClick={handleContainerClick}
        className="flex flex-col border border-[0.5px] border-surface-border dark:border-dark-border border-l-[3px] border-l-[#BF9640] rounded-[8px] bg-surface-card dark:bg-dark-card shadow-sm overflow-hidden cursor-pointer hover:shadow-md transition-shadow"
      >
        {/* Header row */}
        <div className="px-3 py-2 border-b border-surface-border dark:border-dark-border flex items-center gap-1.5">
          <span className="w-1.5 h-1.5 rounded-full bg-[#BF9640] flex-shrink-0" />
          <span className="text-[10px] font-semibold uppercase tracking-wide text-[#BF9640] flex-1">
            JAMM Concierge
          </span>
          {minimized && (
            <p className="text-[12px] text-brand dark:text-foreground truncate max-w-[60%]">
              {featured.message}
            </p>
          )}
          <button
            onClick={toggleMinimized}
            aria-label={minimized ? 'Expand concierge spotlight' : 'Minimize concierge spotlight'}
            className="flex-shrink-0 text-muted-foreground hover:text-brand dark:hover:text-foreground transition-colors ml-1"
          >
            {minimized
              ? <ChevronDown className="h-3.5 w-3.5" />
              : <ChevronUp className="h-3.5 w-3.5" />
            }
          </button>
        </div>

        {/* Content -- hidden when minimized */}
        {!minimized && (
          <div className="px-3 py-2.5 flex flex-col gap-2">
            <p className="text-[13px] leading-[1.5] text-brand dark:text-foreground">
              {featured.message}
            </p>
            {draft && (
              <div className="rounded-[6px] bg-surface-input dark:bg-dark-page border border-[0.5px] border-surface-border dark:border-dark-border px-2.5 py-2">
                <p className="text-[11px] text-muted-foreground mb-1.5 font-medium uppercase tracking-wide">Draft</p>
                <p className="text-[12px] leading-[1.5] text-foreground whitespace-pre-wrap">{draft}</p>
                <div className="flex gap-2 mt-2">
                  <button
                    onClick={(e) => {
                      e.stopPropagation()
                      navigator.clipboard.writeText(draft).then(() => {
                        setCopiedId(featured.id)
                        setTimeout(() => setCopiedId(null), 2000)
                      }).catch(() => {})
                    }}
                    className="text-[11px] font-medium px-2.5 py-1 rounded-[4px] border border-[0.5px] border-surface-border dark:border-dark-border text-muted-foreground hover:border-brand-light hover:text-brand-light transition-colors"
                  >
                    {copiedId === featured.id ? 'Copied' : 'Copy'}
                  </button>
                  <button
                    onClick={async (e) => {
                      e.stopPropagation()
                      const notifClientId = typeof featured.metadata?.client_id === 'string' ? featured.metadata.client_id : null
                      const targetClientId = notifClientId ?? null
                      if (!targetClientId) {
                        alert('No client record could be identified for this draft. Open the client directly and use the Messages tab to send it.')
                        return
                      }
                      const confirmed = await confirm(
                        `Open this client's Messages tab with this draft ready to send?\n\nMessage:\n${draft}\n\nYou will have a final chance to review before sending.`
                      )
                      if (!confirmed) return
                      dismissNotification(featured.id)
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
        )}
      </div>
    </>
  )
}

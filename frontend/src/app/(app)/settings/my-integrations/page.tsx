// frontend/src/app/settings/my-integrations/page.tsx
'use client'

import { useEffect, useState, Suspense } from 'react'
import { useSearchParams } from 'next/navigation'
import { toast } from 'sonner'
import { Plug, CheckCircle2, XCircle } from 'lucide-react'
import api from '@/lib/api'
import { settingsApi, type FirmDetails } from '@/lib/api/settingsApi'
import { cn } from '@/lib/utils'

interface Integration {
  id: string
  provider: string
  status: string
  external_account_id: string | null
}

function MyIntegrationsContent() {
  const searchParams = useSearchParams()
  const [integrations, setIntegrations] = useState<Integration[]>([])
  const [firmSettings, setFirmSettings] = useState<Record<string, unknown>>({})
  const [loading, setLoading] = useState(true)
  const [connecting, setConnecting] = useState<string | null>(null)
  const [disconnecting, setDisconnecting] = useState<string | null>(null)

  async function fetchData() {
    try {
      const [intResp, firmResp] = await Promise.all([
        api.get('/api/v1/integrations/staff/me'),
        settingsApi.getMyFirm(),
      ])
      setIntegrations(intResp.data ?? [])
      setFirmSettings((firmResp.data as FirmDetails)?.settings ?? {})
    } catch {
      toast.error('Failed to load integrations.')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchData()
  }, [])

  useEffect(() => {
    const connected = searchParams.get('connected')
    const error = searchParams.get('error')
    if (connected === 'gmail') toast.success('Gmail connected successfully.')
    if (connected === 'outlook') toast.success('Outlook connected successfully.')
    if (error === 'gmail_failed') toast.error('Gmail connection failed. Please try again.')
    if (error === 'outlook_failed') toast.error('Outlook connection failed. Please try again.')
  }, [searchParams])

  async function handleConnect(provider: 'gmail' | 'outlook') {
    setConnecting(provider)
    try {
      const resp = await api.get(`/api/v1/integrations/staff/${provider}/connect`)
      window.location.href = resp.data.authorization_url
    } catch {
      toast.error(`Failed to start ${provider} connection.`)
      setConnecting(null)
    }
  }

  async function handleDisconnect(provider: string) {
    setDisconnecting(provider)
    try {
      await api.delete(`/api/v1/integrations/staff/${provider}`)
      toast.success(`${provider.charAt(0).toUpperCase() + provider.slice(1)} disconnected.`)
      await fetchData()
    } catch {
      toast.error('Failed to disconnect. Please try again.')
    } finally {
      setDisconnecting(null)
    }
  }

  function getIntegration(provider: string): Integration | undefined {
    return integrations.find((i) => i.provider === provider)
  }

  const emailSyncEnabled = firmSettings.email_sync_enabled !== false

  const providers: { key: 'gmail' | 'outlook'; label: string }[] = [
    { key: 'gmail', label: 'Gmail' },
    { key: 'outlook', label: 'Outlook' },
  ]

  return (
      <div className="p-6 flex flex-col gap-6">
        <div>
          <h1 className="text-2xl font-medium text-brand dark:text-[#EDEEF0]">My Integrations</h1>
          <p className="text-[12px] text-[#6B7280] mt-0.5">
            Connect your email and calendar to JAMM PX. Your emails and calendar are private to you -- only you can see them.
          </p>
        </div>

        {loading ? (
          <div className="flex flex-col gap-3 max-w-lg">
            {[1, 2].map((i) => (
              <div key={i} className="bg-surface-card dark:bg-dark-card rounded-[10px] p-4 h-[88px] animate-pulse" />
            ))}
          </div>
        ) : (
          <div className="flex flex-col gap-3 max-w-lg">
            {providers.map(({ key, label }) => {
              const integration = getIntegration(key)
              const connected = integration?.status === 'connected'

              if (!emailSyncEnabled) {
                return (
                  <div
                    key={key}
                    className="bg-surface-card dark:bg-dark-card rounded-[10px] p-4 flex items-center gap-4 border border-surface-border dark:border-dark-border"
                    style={{ borderWidth: '0.5px' }}
                  >
                    <div className="flex items-center justify-center w-9 h-9 rounded-lg bg-[#F3F4F6] dark:bg-[#333333] flex-shrink-0">
                      <Plug className="h-4 w-4 text-[#9CA3AF]" />
                    </div>
                    <div className="flex-1">
                      <p className="text-[13px] font-medium text-brand dark:text-[#EDEEF0]">{label}</p>
                      <p className="text-[11px] text-[#9CA3AF] mt-0.5">
                        Email sync is disabled by your firm owner.
                      </p>
                    </div>
                  </div>
                )
              }

              return (
                <div
                  key={key}
                  className="bg-surface-card dark:bg-dark-card rounded-[10px] p-4 flex items-center gap-4 border border-surface-border dark:border-dark-border"
                  style={{ borderWidth: '0.5px' }}
                >
                  <div
                    className={cn(
                      'flex items-center justify-center w-9 h-9 rounded-lg flex-shrink-0',
                      connected ? 'bg-[#D1FAE5] dark:bg-[#064E3B]/30' : 'bg-[#F3F4F6] dark:bg-[#333333]',
                    )}
                  >
                    {connected ? (
                      <CheckCircle2 className="h-4 w-4 text-[#059669]" />
                    ) : (
                      <Plug className="h-4 w-4 text-[#6B7280]" />
                    )}
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <p className="text-[13px] font-medium text-brand dark:text-[#EDEEF0]">{label}</p>
                      {connected && (
                        <span className="text-[10px] font-medium px-1.5 py-0.5 rounded-full bg-[#D1FAE5] text-[#065F46]">
                          Connected
                        </span>
                      )}
                    </div>
                    {connected && integration?.external_account_id && (
                      <p className="text-[11px] text-[#6B7280] mt-0.5 truncate">
                        {integration.external_account_id}
                      </p>
                    )}
                    {!connected && (
                      <p className="text-[11px] text-[#9CA3AF] mt-0.5">Not connected</p>
                    )}
                  </div>
                  <div className="flex-shrink-0">
                    {connected ? (
                      <button
                        onClick={() => handleDisconnect(key)}
                        disabled={disconnecting === key}
                        className="h-7 px-3 text-[12px] font-medium rounded-[6px] border border-[#E5E7EB] dark:border-dark-border text-[#6B7280] hover:text-[#DC2626] hover:border-[#DC2626] transition-colors disabled:opacity-60"
                      >
                        {disconnecting === key ? 'Disconnecting...' : 'Disconnect'}
                      </button>
                    ) : (
                      <button
                        onClick={() => handleConnect(key)}
                        disabled={connecting === key}
                        className="h-7 px-3 text-[12px] font-medium rounded-[6px] bg-brand text-white hover:bg-brand/90 transition-colors disabled:opacity-60"
                      >
                        {connecting === key ? 'Redirecting...' : `Connect ${label}`}
                      </button>
                    )}
                  </div>
                </div>
              )
            })}
          </div>
        )}
      </div>
  )
}

export default function MyIntegrationsPage() {
  return (
    <Suspense fallback={<div />}>
      <MyIntegrationsContent />
    </Suspense>
  )
}

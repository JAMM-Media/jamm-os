// frontend/src/app/portal/page.tsx
'use client'

import { useState, useEffect } from 'react'
import { useRouter, useSearchParams } from 'next/navigation'
import { loadStripe } from '@stripe/stripe-js'
import { Elements } from '@stripe/react-stripe-js'
import { PortalShell } from '@/components/portal/PortalShell'
import { PortalTodo } from '@/components/portal/PortalTodo'
import { PortalDocuments } from '@/components/portal/PortalDocuments'
import { PortalInvoices } from '@/components/portal/PortalInvoices'
import { PortalMessages } from '@/components/portal/PortalMessages'
import PortalOrganizer from '@/components/portal/PortalOrganizer'
import { PortalBillingDetail } from '@/components/portal/PortalBillingDetail'

let _stripePromise: ReturnType<typeof loadStripe> | null = null
function getStripePromise() {
  if (!_stripePromise) {
    _stripePromise = loadStripe(process.env.NEXT_PUBLIC_STRIPE_PUBLISHABLE_KEY!)
  }
  return _stripePromise
}

interface PortalMe {
  client_id: string
  client_name: string
  firm_name: string
  portal_display_name: string
  portal_logo_url: string | null
  portal_mode: 'light' | 'dark'
  portal_top_bar_color: string
  portal_page_color: string
  portal_tab_bar_color: string
  portal_accent_color: string
  portal_avatar_color: string
  portal_subtitle_color: string
  portal_card_color: string
  portal_text_primary: string
  portal_text_muted: string
}

export default function PortalPage() {
  const router = useRouter()
  const searchParams = useSearchParams()
  const [activeTab, setActiveTab] = useState(searchParams.get('tab') ?? 'todo')
  const [deepLinkOrganizerId, setDeepLinkOrganizerId] = useState<string | null>(
    searchParams.get('organizer_id')
  )
  const [me, setMe] = useState<PortalMe | null>(null)

  // Sync activeTab and deepLinkOrganizerId whenever the URL search params change.
  // The lazy useState initializer only runs on the initial mount; useSearchParams
  // returns a live object that updates on every client-side navigation, so this
  // useEffect is what actually catches router.push('/portal?tab=documents') calls
  // from other pages in the same session.
  useEffect(() => {
    setActiveTab(searchParams.get('tab') ?? 'todo')
  }, [searchParams])

  useEffect(() => {
    setDeepLinkOrganizerId(searchParams.get('organizer_id'))
  }, [searchParams])

  useEffect(() => {
    const token = localStorage.getItem('portal_access_token')
    fetch('/api/backend/portal/me', {
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    })
      .then(async (res) => {
        if (res.status === 401 || res.status === 403) {
          router.replace('/portal/login')
          return
        }
        if (!res.ok) return
        const data: PortalMe = await res.json()
        setMe(data)
      })
      .catch(() => {
        router.replace('/portal/login')
      })
  }, [router])

  function handleTabChange(tab: string) {
    setActiveTab(tab)
    router.replace('/portal?tab=' + tab, { scroll: false })
  }

  if (!me) {
    return (
      <div className="min-h-screen bg-[#2D2D2D] flex flex-col">
        <div className="h-12 bg-[#1F3148] flex-shrink-0 animate-pulse" />
        <div className="h-10 bg-[#252525] border-b border-[#383838] flex-shrink-0 animate-pulse" />
        <div className="flex-1 p-5 flex flex-col gap-3 max-w-2xl mx-auto w-full">
          {[1, 2, 3].map((i) => (
            <div key={i} className="flex items-center justify-between gap-4 rounded-[8px] px-5 py-4" style={{ backgroundColor: '#383838' }}>
              <div className="flex items-start gap-3">
                <div className="h-5 w-5 rounded flex-shrink-0 mt-0.5 animate-pulse" style={{ backgroundColor: 'rgba(255,255,255,0.12)' }} />
                <div className="flex flex-col gap-1.5">
                  <div className="h-3 w-40 rounded animate-pulse" style={{ backgroundColor: 'rgba(255,255,255,0.12)' }} />
                  <div className="h-3 w-56 rounded animate-pulse" style={{ backgroundColor: 'rgba(255,255,255,0.12)' }} />
                </div>
              </div>
              <div className="h-5 w-5 rounded-full flex-shrink-0 animate-pulse" style={{ backgroundColor: 'rgba(255,255,255,0.12)' }} />
            </div>
          ))}
        </div>
      </div>
    )
  }

  const firstName = me.client_name.split(' ')[0]
  const logoImgSrc = me.portal_logo_url
    ? `https://api.jammpx.com${me.portal_logo_url}`
    : undefined

  return (
    <PortalShell
      firmName={me.portal_display_name || me.firm_name}
      logoUrl={logoImgSrc}
      brandColor={me.portal_top_bar_color}
      pageColor={me.portal_page_color}
      tabBarColor={me.portal_tab_bar_color}
      accentColor={me.portal_accent_color}
      avatarColor={me.portal_avatar_color}
      subtitleColor={me.portal_subtitle_color}
      portalMode={me.portal_mode}
      clientName={me.client_name}
      activeTab={activeTab}
      onTabChange={handleTabChange}
    >
      {activeTab === 'todo' && <PortalTodo clientFirstName={firstName} accentColor={me.portal_accent_color} cardColor={me.portal_card_color} portalMode={me.portal_mode} textPrimary={me.portal_text_primary} textMuted={me.portal_text_muted} />}
      {activeTab === 'documents' && <PortalDocuments firmName={me.portal_display_name || me.firm_name} accentColor={me.portal_accent_color} cardColor={me.portal_card_color} portalMode={me.portal_mode} textPrimary={me.portal_text_primary} textMuted={me.portal_text_muted} />}
      {activeTab === 'invoices' && (
        <Elements stripe={getStripePromise()}>
          <PortalInvoices accentColor={me.portal_accent_color} cardColor={me.portal_card_color} portalMode={me.portal_mode} textPrimary={me.portal_text_primary} textMuted={me.portal_text_muted} />
        </Elements>
      )}
      {activeTab === 'messages' && (
        <PortalMessages clientId={me.client_id} firmName={me.firm_name} cardColor={me.portal_card_color} accentColor={me.portal_accent_color} portalMode={me.portal_mode} textPrimary={me.portal_text_primary} textMuted={me.portal_text_muted} />
      )}
      {activeTab === 'organizer' && (
        <PortalOrganizer clientId={me.client_id} initialOrganizerId={deepLinkOrganizerId} cardColor={me.portal_card_color} portalMode={me.portal_mode} textPrimary={me.portal_text_primary} textMuted={me.portal_text_muted} />
      )}
      {activeTab === 'billing-detail' && <PortalBillingDetail cardColor={me.portal_card_color} accentColor={me.portal_accent_color} portalMode={me.portal_mode} textPrimary={me.portal_text_primary} textMuted={me.portal_text_muted} />}
    </PortalShell>
  )
}

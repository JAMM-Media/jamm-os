// frontend/src/app/portal/page.tsx
'use client'

import { useState, useEffect } from 'react'
import { useRouter } from 'next/navigation'
import { loadStripe } from '@stripe/stripe-js'
import { Elements } from '@stripe/react-stripe-js'
import { PortalShell } from '@/components/portal/PortalShell'
import { PortalTodo } from '@/components/portal/PortalTodo'
import { PortalDocuments } from '@/components/portal/PortalDocuments'
import { PortalInvoices } from '@/components/portal/PortalInvoices'
import { PortalMessages } from '@/components/portal/PortalMessages'
import PortalOrganizer from '@/components/portal/PortalOrganizer'

const stripePromise = loadStripe(process.env.NEXT_PUBLIC_STRIPE_PUBLISHABLE_KEY!)

interface PortalMe {
  client_id: string
  client_name: string
  firm_name: string
  portal_display_name: string
  portal_logo_url: string | null
  portal_brand_color: string
}

export default function PortalPage() {
  const router = useRouter()
  const [activeTab, setActiveTab] = useState('todo')
  const [me, setMe] = useState<PortalMe | null>(null)

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

  if (!me) {
    return (
      <div className="min-h-screen bg-[#2D2D2D] flex flex-col">
        <div className="h-12 bg-[#1F3148] flex-shrink-0 animate-pulse" />
        <div className="h-10 bg-[#252525] border-b border-[#383838] flex-shrink-0 animate-pulse" />
        <div className="flex-1 p-5 flex flex-col gap-3 max-w-2xl mx-auto w-full">
          {[1, 2, 3].map((i) => (
            <div key={i} className="h-16 rounded-[8px] bg-[#383838] animate-pulse" />
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
      brandColor={me.portal_brand_color || '#1F3148'}
      clientName={me.client_name}
      activeTab={activeTab}
      onTabChange={setActiveTab}
    >
      {activeTab === 'todo' && <PortalTodo clientFirstName={firstName} />}
      {activeTab === 'documents' && <PortalDocuments firmName={me.firm_name} />}
      {activeTab === 'invoices' && (
        <Elements stripe={stripePromise}>
          <PortalInvoices />
        </Elements>
      )}
      {activeTab === 'messages' && (
        <PortalMessages clientId={me.client_id} firmName={me.firm_name} />
      )}
      {activeTab === 'organizer' && (
        <PortalOrganizer clientId={me.client_id} />
      )}
    </PortalShell>
  )
}

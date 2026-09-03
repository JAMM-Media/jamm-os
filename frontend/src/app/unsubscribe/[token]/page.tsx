// path: frontend/src/app/unsubscribe/[token]/page.tsx
'use client'

import { Suspense, useState } from 'react'
import { useParams } from 'next/navigation'
import Link from 'next/link'
import { Loader2, Lock, Mail, X } from 'lucide-react'

type PageState = 'confirm' | 'loading' | 'success' | 'invalid' | 'error'

const leftPanel = (
  <div className="relative hidden md:flex w-1/2 bg-brand flex-col p-10 overflow-hidden">
    <div className="flex items-center gap-2.5">
      <img src="/jamm-logo-mark-light.svg" alt="" className="flex-shrink-0 h-8 w-auto" />
      <span className="text-white text-3xl font-medium">
        JAMM <span style={{ color: '#B07D3A' }}>PX</span>
      </span>
    </div>
    <div className="flex flex-1 items-center">
      <div className="flex flex-col">
        <div className="h-[2px] mb-3" style={{ backgroundColor: '#B07D3A', width: '48px' }} />
        <h2 className="text-white text-7xl font-bold leading-tight">
          Trusted guidance.<br />
          <span style={{ color: '#B07D3A' }}>Real partnership.</span>
        </h2>
        <p className="mt-4 text-[15px] leading-relaxed" style={{ color: 'rgba(255,255,255,0.65)' }}>
          We're here to help you succeed every step of the way.
        </p>
      </div>
    </div>
    <svg
      viewBox="0 0 500 160"
      xmlns="http://www.w3.org/2000/svg"
      className="absolute bottom-0 left-0 w-full"
      style={{ opacity: 0.09 }}
      aria-hidden="true"
    >
      <path d="M0,80 C80,40 160,120 250,80 C340,40 420,120 500,80 L500,160 L0,160 Z" fill="white" />
      <path d="M0,110 C80,70 160,150 250,110 C340,70 420,150 500,110 L500,160 L0,160 Z" fill="white" />
      <path d="M0,50 C100,20 200,90 300,50 C400,10 450,70 500,50" fill="none" stroke="white" strokeWidth="1.5" />
    </svg>
  </div>
)

function UnsubscribeContent() {
  const params = useParams()
  const token = typeof params?.token === 'string' ? params.token : undefined

  const [state, setState] = useState<PageState>('confirm')
  const [backendMessage, setBackendMessage] = useState('')

  if (!token) {
    return (
      <div className="min-h-screen flex">
        {leftPanel}
        <div className="flex flex-1 items-center justify-center bg-surface-page dark:bg-dark-page">
          <div className="w-[460px] bg-surface-card dark:bg-dark-card rounded-[10px] border border-surface-border p-10 flex flex-col gap-4">
            <h1 className="text-4xl font-bold text-brand dark:text-[#EDEEF0]">Invalid link</h1>
            <p className="text-[14px] text-[#6B7280] leading-relaxed">
              This unsubscribe link is missing a token and cannot be used.
            </p>
          </div>
        </div>
      </div>
    )
  }

  async function handleUnsubscribe() {
    setState('loading')
    try {
      const res = await fetch(`/api/backend/unsubscribe/${token}`)
      const data = await res.json().catch(() => ({}))
      if (data.status === 'unsubscribed') {
        setBackendMessage(data.message ?? '')
        setState('success')
      } else if (data.status === 'invalid') {
        setBackendMessage(data.message ?? '')
        setState('invalid')
      } else {
        setState('error')
      }
    } catch {
      setState('error')
    }
  }

  if (state === 'success') {
    return (
      <div className="min-h-screen flex">
        {leftPanel}
        <div className="flex flex-1 items-center justify-center bg-surface-page dark:bg-dark-page">
          <div className="w-[460px] bg-surface-card dark:bg-dark-card rounded-[10px] border border-surface-border p-10 flex flex-col gap-4">
            <h1 className="text-4xl font-bold text-brand dark:text-[#EDEEF0]">Unsubscribed</h1>
            <p className="text-[14px] text-[#6B7280] leading-relaxed">{backendMessage}</p>
            <Link
              href="/"
              className="text-[13px] text-brand dark:text-[#4A7FA5] underline hover:opacity-80"
            >
              Return to homepage
            </Link>
          </div>
        </div>
      </div>
    )
  }

  if (state === 'invalid') {
    return (
      <div className="min-h-screen flex">
        {leftPanel}
        <div className="flex flex-1 items-center justify-center bg-surface-page dark:bg-dark-page">
          <div className="w-[460px] bg-surface-card dark:bg-dark-card rounded-[10px] border border-surface-border p-10 flex flex-col gap-4">
            <h1 className="text-4xl font-bold text-brand dark:text-[#EDEEF0]">Link not valid</h1>
            <p className="text-[14px] text-[#6B7280] leading-relaxed">{backendMessage}</p>
          </div>
        </div>
      </div>
    )
  }

  if (state === 'error') {
    return (
      <div className="min-h-screen flex">
        {leftPanel}
        <div className="flex flex-1 items-center justify-center bg-surface-page dark:bg-dark-page">
          <div className="w-[460px] bg-surface-card dark:bg-dark-card rounded-[10px] border border-surface-border p-10 flex flex-col gap-4">
            <h1 className="text-4xl font-bold text-brand dark:text-[#EDEEF0]">Something went wrong</h1>
            <p className="text-[14px] text-[#6B7280] leading-relaxed">
              We could not process your request. Please try again.
            </p>
            <button
              onClick={handleUnsubscribe}
              className="w-full h-11 mt-2 rounded-md text-sm font-medium text-white bg-brand dark:bg-brand-btn flex items-center justify-center"
            >
              Try again
            </button>
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="min-h-screen flex">
      {leftPanel}
      <div className="flex flex-1 flex-col items-center justify-center bg-surface-page dark:bg-dark-page">
        <div className="w-[460px] bg-surface-card dark:bg-dark-card rounded-[10px] border border-surface-border p-10 flex flex-col gap-5">
          <div className="relative w-[72px] h-[72px]">
            <div
              className="w-[72px] h-[72px] rounded-full flex items-center justify-center"
              style={{ backgroundColor: '#F5EFE7' }}
            >
              <Mail className="w-9 h-9" style={{ color: '#6B5744' }} />
            </div>
            <div
              className="absolute bottom-0 right-0 w-[22px] h-[22px] rounded-full flex items-center justify-center"
              style={{ backgroundColor: '#B07D3A' }}
            >
              <X className="w-3 h-3 text-white" strokeWidth={3} />
            </div>
          </div>
          <div className="flex flex-col gap-2">
            <h1 className="text-4xl font-bold text-brand dark:text-[#EDEEF0]">Unsubscribe from these emails?</h1>
            <p className="text-[14px] text-[#6B7280] leading-relaxed">
              Clicking the button below will stop all marketing emails from this firm.
            </p>
          </div>
          <button
            onClick={handleUnsubscribe}
            disabled={state === 'loading'}
            className="w-full h-11 rounded-md text-sm font-medium text-white bg-brand dark:bg-brand-btn disabled:opacity-60 flex items-center justify-center gap-2"
          >
            {state === 'loading' ? (
              <>
                <Loader2 className="w-3.5 h-3.5 animate-spin" />
                Unsubscribing...
              </>
            ) : (
              'Yes, unsubscribe me'
            )}
          </button>
        </div>
        <div className="w-[460px] flex items-start gap-2 mt-4 px-1">
          <Lock className="w-3.5 h-3.5 mt-0.5 flex-shrink-0" style={{ color: '#9CA3AF' }} />
          <p className="text-[12px] leading-relaxed" style={{ color: '#9CA3AF' }}>
            We respect your privacy. We will process your request immediately and you will no longer receive marketing emails.
          </p>
        </div>
      </div>
    </div>
  )
}

export default function UnsubscribePage() {
  return (
    <Suspense fallback={
      <div className="min-h-screen flex items-center justify-center">
        <Loader2 className="h-6 w-6 animate-spin text-brand" />
      </div>
    }>
      <UnsubscribeContent />
    </Suspense>
  )
}

// path: frontend/src/app/intake-resume/[token]/page.tsx
'use client'

import { Suspense, useEffect, useState } from 'react'
import { useParams } from 'next/navigation'
import { Loader2, CheckCircle, AlertCircle, ClipboardList } from 'lucide-react'

type PageState = 'loading' | 'valid' | 'invalid' | 'error' | 'missing'

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
          Your accounting team is ready to help you succeed.
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

function IntakeResumeContent() {
  const params = useParams()
  const token = typeof params?.token === 'string' ? params.token : undefined

  const [state, setState] = useState<PageState>(token ? 'loading' : 'missing')

  useEffect(() => {
    if (!token) return

    let cancelled = false
    async function validate() {
      try {
        const res = await fetch(`/api/backend/intake-token/validate/${token}`)
        if (cancelled) return
        if (!res.ok) {
          setState('error')
          return
        }
        const data = await res.json().catch(() => ({}))
        if (data.status === 'valid') {
          setState('valid')
        } else {
          setState('invalid')
        }
      } catch {
        if (!cancelled) setState('error')
      }
    }
    validate()
    return () => { cancelled = true }
  }, [token])

  if (state === 'missing') {
    return (
      <div className="min-h-screen flex">
        {leftPanel}
        <div className="flex flex-1 items-center justify-center bg-surface-page dark:bg-dark-page">
          <div className="w-[460px] bg-surface-card dark:bg-dark-card rounded-[10px] border border-surface-border p-10 flex flex-col gap-4">
            <AlertCircle className="w-10 h-10 text-[#9CA3AF]" />
            <h1 className="text-4xl font-bold text-brand dark:text-[#EDEEF0]">Invalid link</h1>
            <p className="text-[14px] text-[#6B7280] leading-relaxed">
              This link is missing a session token. Please use the link from your email exactly as received.
            </p>
          </div>
        </div>
      </div>
    )
  }

  if (state === 'loading') {
    return (
      <div className="min-h-screen flex">
        {leftPanel}
        <div className="flex flex-1 items-center justify-center bg-surface-page dark:bg-dark-page">
          <div className="w-[460px] bg-surface-card dark:bg-dark-card rounded-[10px] border border-surface-border p-10 flex flex-col items-center gap-4">
            <Loader2 className="w-8 h-8 animate-spin text-brand" />
            <p className="text-[14px] text-[#6B7280]">Verifying your link...</p>
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
            <AlertCircle className="w-10 h-10 text-[#9CA3AF]" />
            <h1 className="text-4xl font-bold text-brand dark:text-[#EDEEF0]">Link expired</h1>
            <p className="text-[14px] text-[#6B7280] leading-relaxed">
              This intake session link has expired or is no longer valid. Please contact your accounting firm to receive a new link.
            </p>
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
            <AlertCircle className="w-10 h-10 text-[#9CA3AF]" />
            <h1 className="text-4xl font-bold text-brand dark:text-[#EDEEF0]">Something went wrong</h1>
            <p className="text-[14px] text-[#6B7280] leading-relaxed">
              We could not verify your link right now. Please try again in a few moments.
            </p>
            <button
              onClick={() => { setState('loading') }}
              className="w-full h-11 mt-2 rounded-md text-sm font-medium text-white bg-brand dark:bg-brand-btn flex items-center justify-center"
            >
              Try again
            </button>
          </div>
        </div>
      </div>
    )
  }

  // state === 'valid'
  return (
    <div className="min-h-screen flex">
      {leftPanel}
      <div className="flex flex-1 flex-col items-center justify-center bg-surface-page dark:bg-dark-page">
        <div className="w-[460px] bg-surface-card dark:bg-dark-card rounded-[10px] border border-surface-border p-10 flex flex-col gap-5">
          <div
            className="w-[72px] h-[72px] rounded-full flex items-center justify-center"
            style={{ backgroundColor: '#ECFDF5' }}
          >
            <ClipboardList className="w-9 h-9" style={{ color: '#059669' }} />
          </div>
          <div className="flex flex-col gap-2">
            <h1 className="text-4xl font-bold text-brand dark:text-[#EDEEF0]">Welcome back</h1>
            <p className="text-[14px] text-[#6B7280] leading-relaxed">
              Your intake session is active. Your accounting team has received your information and will be in touch shortly.
            </p>
          </div>
          <div className="flex items-start gap-2.5 p-3 rounded-[8px] bg-surface-page dark:bg-dark-page border border-surface-border">
            <CheckCircle className="w-4 h-4 mt-0.5 flex-shrink-0" style={{ color: '#059669' }} />
            <p className="text-[13px] text-[#374151] dark:text-[#EDEEF0]">
              Your session link is valid and will remain active for up to 30 days.
            </p>
          </div>
        </div>
      </div>
    </div>
  )
}

export default function IntakeResumePage() {
  return (
    <Suspense fallback={
      <div className="min-h-screen flex items-center justify-center">
        <Loader2 className="h-6 w-6 animate-spin text-brand" />
      </div>
    }>
      <IntakeResumeContent />
    </Suspense>
  )
}

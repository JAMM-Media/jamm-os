// path: frontend/src/app/(auth)/login/magic/page.tsx
'use client'

import { Suspense, useEffect, useState } from 'react'
import { useRouter, useSearchParams } from 'next/navigation'
import { Loader2 } from 'lucide-react'
import Link from 'next/link'

function MagicLinkContent() {
  const searchParams = useSearchParams()
  const router = useRouter()
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    const token = searchParams.get('token')
    if (!token) {
      setError('This link is invalid. Please request a new one.')
      return
    }

    fetch(`/api/auth/magic?token=${encodeURIComponent(token)}`)
      .then(async (res) => {
        if (!res.ok) {
          setError('This link has expired or already been used. Request a new one.')
          return
        }
        router.replace('/dashboard')
      })
      .catch(() => {
        setError('This link has expired or already been used. Request a new one.')
      })
  }, [searchParams, router])

  if (error) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-surface-page dark:bg-dark-page">
        <div className="w-[380px] bg-surface-card dark:bg-dark-card rounded-[10px] border border-surface-border p-8 text-center flex flex-col gap-3">
          <p className="text-[13px] font-medium text-[#991B1B]">Link unavailable</p>
          <p className="text-[12px] text-[#6B7280]">{error}</p>
          <Link
            href="/login"
            className="text-[12px] text-brand dark:text-[#4A7FA5] underline hover:opacity-80"
          >
            Back to sign in
          </Link>
        </div>
      </div>
    )
  }

  return (
    <div className="min-h-screen flex flex-col items-center justify-center gap-3 bg-surface-page dark:bg-dark-page">
      <Loader2 className="h-6 w-6 animate-spin text-brand" />
      <p className="text-[13px] text-[#6B7280]">Signing you in...</p>
    </div>
  )
}

export default function MagicLinkPage() {
  return (
    <Suspense fallback={
      <div className="min-h-screen flex items-center justify-center">
        <Loader2 className="h-6 w-6 animate-spin text-brand" />
      </div>
    }>
      <MagicLinkContent />
    </Suspense>
  )
}

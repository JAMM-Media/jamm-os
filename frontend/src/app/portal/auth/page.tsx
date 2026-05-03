// path: frontend/src/app/portal/auth/page.tsx
'use client'

import { useEffect, useState } from 'react'
import { useRouter, useSearchParams } from 'next/navigation'
import { Loader2 } from 'lucide-react'

export default function PortalAuthPage() {
  const searchParams = useSearchParams()
  const router = useRouter()
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    const token = searchParams.get('token')

    if (!token) {
      setError('This link is invalid. Please contact your firm for a new portal link.')
      return
    }

    fetch(`/api/backend/portal/auth?token=${encodeURIComponent(token)}`)
      .then(async (res) => {
        if (!res.ok) {
          setError('This link has expired or has already been used. Please contact your firm for a new link.')
          return
        }
        const data = await res.json()
        localStorage.setItem('portal_access_token', data.access_token)
        router.replace('/portal')
      })
      .catch(() => {
        setError('This link has expired or has already been used. Please contact your firm for a new link.')
      })
  }, [searchParams, router])

  if (error) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-surface-page dark:bg-dark-page">
        <div className="w-[380px] bg-surface-card dark:bg-dark-card rounded-[10px] border border-surface-border p-8 text-center">
          <p className="text-[13px] font-medium text-[#991B1B] mb-2">Link unavailable</p>
          <p className="text-[12px] text-[#6B7280]">{error}</p>
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

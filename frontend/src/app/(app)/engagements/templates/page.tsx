// frontend/src/app/engagements/templates/page.tsx
'use client'

import { useEffect } from 'react'
import { useRouter } from 'next/navigation'

export default function EngagementsTemplatesRedirect() {
  const router = useRouter()
  useEffect(() => {
    router.replace('/templates')
  }, [router])
  return null
}

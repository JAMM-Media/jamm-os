// path: frontend/src/app/portal-preview/layout.tsx
import type { Metadata, Viewport } from 'next'

export const dynamic = 'force-dynamic'

export const viewport: Viewport = {
  width: 'device-width',
  initialScale: 1,
  maximumScale: 1,
}

export const metadata: Metadata = {
  title: 'Portal Preview (Staff)',
  robots: 'noindex,nofollow',
}

export default function PortalPreviewLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return <>{children}</>
}

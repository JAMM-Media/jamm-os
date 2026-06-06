// path: frontend/src/app/portal/layout.tsx
import type { Metadata, Viewport } from 'next'

export const dynamic = 'force-dynamic'

export const viewport: Viewport = {
  themeColor: '#1F3148',
  width: 'device-width',
  initialScale: 1,
  maximumScale: 1,
  userScalable: false,
}

export const metadata: Metadata = {
  title: 'Client Portal',
  description: 'Your secure client portal',
  manifest: '/portal-manifest.json',
  appleWebApp: {
    capable: true,
    statusBarStyle: 'black-translucent',
    title: 'Client Portal',
  },
}

export default function PortalLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <>
      <script
        dangerouslySetInnerHTML={{
          __html: `
            if ('serviceWorker' in navigator) {
              window.addEventListener('load', function() {
                navigator.serviceWorker.register('/portal-sw.js')
              })
            }
          `,
        }}
      />
      {children}
    </>
  )
}

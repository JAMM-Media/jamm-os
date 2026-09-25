// frontend/src/app/layout.tsx
import type { Metadata } from 'next'
import { Lora, Plus_Jakarta_Sans, Playfair_Display } from 'next/font/google'
import './globals.css'
import 'react-grid-layout/css/styles.css'
import 'react-resizable/css/styles.css'
import { ThemeProvider } from '@/providers/theme-provider'
import { AuthProvider } from '@/lib/hooks/useAuth'
import { QueryProvider } from '@/providers/QueryProvider'
import { Toaster } from '@/components/ui/sonner'

const lora = Lora({
  subsets: ['latin'],
  weight: ['400', '500', '600', '700'],
  style: ['normal', 'italic'],
  variable: '--font-lora',
})

const plusJakartaSans = Plus_Jakarta_Sans({
  subsets: ['latin'],
  weight: ['300', '400', '500', '600', '700'],
  variable: '--font-plus-jakarta-sans',
})

const playfairDisplay = Playfair_Display({
  subsets: ['latin'],
  weight: ['500'],
  style: ['normal'],
  variable: '--font-playfair',
})

export const metadata: Metadata = {
  title: 'JAMM PX',
  description: 'Practice experience for accounting firms',
  icons: {
    icon: '/favicon.ico',
    apple: '/logo.png',
  },
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body className={`${lora.variable} ${plusJakartaSans.variable} ${playfairDisplay.variable} font-sans`} suppressHydrationWarning>
        <QueryProvider>
          <AuthProvider>
            <ThemeProvider
              attribute="class"
              defaultTheme="light"
              enableSystem={false}
              disableTransitionOnChange
            >
              {children}
              <Toaster />
            </ThemeProvider>
          </AuthProvider>
        </QueryProvider>
      </body>
    </html>
  )
}

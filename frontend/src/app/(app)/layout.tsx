// path: frontend/src/app/(app)/layout.tsx
import { AppShell } from '@/components/layout/AppShell'

export default function AppGroupLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return <AppShell>{children}</AppShell>
}

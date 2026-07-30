// path: frontend/src/lib/hooks/useAuth.tsx
'use client'

import { createContext, useContext, useState, useEffect, useCallback } from 'react'
import { useRouter } from 'next/navigation'

export interface AuthUser {
  id: string
  email: string
  full_name: string
  role: 'firm_owner' | 'manager' | 'staff' | 'client_portal_user' | 'system_admin'
  firm_id: string
  totp_enabled?: boolean
  firm_type?: string | null
  concierge_active?: boolean
  concierge_entry_mode?: string | null
  concierge_suggestions_enabled?: boolean | null
}

interface AuthContextType {
  user: AuthUser | null
  isLoading: boolean
  isAuthenticated: boolean
  login: (
    email: string,
    password: string,
    totp_code?: string,
    backup_code?: string
  ) => Promise<{ success: boolean; requires_2fa?: boolean; message?: string }>
  logout: () => Promise<void>
  refreshUser: () => Promise<void>
}

const AuthContext = createContext<AuthContextType | null>(null)

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const router = useRouter()

  const refreshUser = useCallback(async () => {
    try {
      const res = await fetch('/api/auth/me')
      const data = await res.json()
      setUser(data.user ?? null)
    } catch {
      // non-fatal: called on initial mount and after settings changes
    }
  }, [])

  useEffect(() => {
    refreshUser().finally(() => setIsLoading(false))
  }, [refreshUser])

  const login = useCallback(
    async (
      email: string,
      password: string,
      totp_code?: string,
      backup_code?: string
    ): Promise<{ success: boolean; requires_2fa?: boolean; message?: string }> => {
      const res = await fetch('/api/auth/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email, password, totp_code, backup_code }),
      })
      const data = await res.json()
      if (data.requires_2fa) {
        return { success: false, requires_2fa: true }
      }
      if (data.success) {
        if (data.access_token) localStorage.setItem('access_token', data.access_token)
        const meRes = await fetch('/api/auth/me')
        const meData = await meRes.json()
        setUser(meData.user ?? null)
        return { success: true }
      }
      return { success: false, message: data.message }
    },
    []
  )

  const logout = useCallback(async () => {
    await fetch('/api/auth/logout', { method: 'POST' })
    setUser(null)
    router.push('/login')
  }, [router])

  const isAuthenticated = user !== null && !isLoading

  return (
    <AuthContext.Provider value={{ user, isLoading, isAuthenticated, login, logout, refreshUser }}>
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth() {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used within AuthProvider')
  return ctx
}

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
}

interface AuthContextType {
  user: AuthUser | null
  isLoading: boolean
  isAuthenticated: boolean
  login: (
    email: string,
    password: string,
    totp_code?: string
  ) => Promise<{ success: boolean; message?: string }>
  logout: () => Promise<void>
}

const AuthContext = createContext<AuthContextType | null>(null)

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const router = useRouter()

  useEffect(() => {
    fetch('/api/auth/me')
      .then((res) => res.json())
      .then((data) => {
        setUser(data.user ?? null)
        setIsLoading(false)
      })
      .catch(() => {
        setIsLoading(false)
      })
  }, [])

  const login = useCallback(
    async (
      email: string,
      password: string,
      totp_code?: string
    ): Promise<{ success: boolean; message?: string }> => {
      const res = await fetch('/api/auth/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email, password, totp_code }),
      })
      const data = await res.json()
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
    <AuthContext.Provider value={{ user, isLoading, isAuthenticated, login, logout }}>
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth() {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used within AuthProvider')
  return ctx
}

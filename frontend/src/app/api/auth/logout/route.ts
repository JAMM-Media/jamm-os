// path: frontend/src/app/api/auth/logout/route.ts
import { NextResponse } from 'next/server'
import { cookies } from 'next/headers'

const BACKEND_URL = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000'

export async function POST() {
  const cookieStore = await cookies()
  const accessToken = cookieStore.get('jamm_token')?.value

  // Revoke the refresh token server-side — always succeeds from the client's perspective
  try {
    await fetch(`${BACKEND_URL}/auth/logout`, {
      method: 'POST',
      headers: accessToken ? { Authorization: `Bearer ${accessToken}` } : {},
    })
  } catch {
    // Backend unreachable — still clear cookies locally
  }

  // Clear jamm_token locally as a fallback
  cookieStore.set('jamm_token', '', { maxAge: 0, path: '/' })
  return NextResponse.json({ success: true })
}

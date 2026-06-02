// path: frontend/src/app/api/auth/me/route.ts
import { NextRequest, NextResponse } from 'next/server'
import { cookies } from 'next/headers'

export async function GET(request: NextRequest) {
  try {
    const cookieStore = await cookies()
    const cookieToken = cookieStore.get('jamm_token')?.value

    // Fallback: read from Authorization header if cookie is missing
    const authHeader = request.headers.get('authorization')
    const headerToken =
      authHeader?.startsWith('Bearer ') ? authHeader.slice(7) : undefined

    const token = cookieToken ?? headerToken

    if (!token) {
      return NextResponse.json({ user: null })
    }

    const backendUrl = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000'
    const res = await fetch(`${backendUrl}/users/me`, {
      headers: { Authorization: `Bearer ${token}` },
      cache: 'no-store',
    })

    if (res.ok) {
      const user = await res.json()
      return NextResponse.json({ user })
    }

    if (res.status === 401) {
      const response = NextResponse.json({ user: null })
      response.cookies.set('jamm_token', '', { maxAge: 0, path: '/' })
      return response
    }

    return NextResponse.json({ user: null })
  } catch {
    return NextResponse.json({ user: null })
  }
}

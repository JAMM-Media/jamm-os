// path: frontend/src/app/api/backend/auth/refresh/route.ts
import { NextResponse } from 'next/server'
import { cookies } from 'next/headers'

const BACKEND_URL = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000'

export async function POST() {
  const cookieStore = await cookies()
  const refreshToken = cookieStore.get('jamm_refresh_token')?.value

  if (!refreshToken) {
    return NextResponse.json({ detail: 'No refresh token' }, { status: 401 })
  }

  try {
    const res = await fetch(`${BACKEND_URL}/auth/refresh`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Cookie: `jamm_refresh_token=${refreshToken}`,
      },
    })

    if (!res.ok) {
      return NextResponse.json({ detail: 'Refresh failed' }, { status: 401 })
    }

    const data = await res.json()
    const response = NextResponse.json({ access_token: data.access_token })

    // Forward the new jamm_refresh_token Set-Cookie from the backend (token rotation)
    const backendSetCookie = res.headers.get('set-cookie')
    if (backendSetCookie) {
      response.headers.append('Set-Cookie', backendSetCookie)
    }

    // Update the jamm_token HttpOnly cookie so the server-side proxy stays in sync
    response.cookies.set('jamm_token', data.access_token, {
      httpOnly: true,
      secure: process.env.NODE_ENV === 'production',
      sameSite: 'lax',
      path: '/',
      maxAge: 60 * 60,
    })

    return response
  } catch {
    return NextResponse.json({ detail: 'Refresh failed' }, { status: 401 })
  }
}

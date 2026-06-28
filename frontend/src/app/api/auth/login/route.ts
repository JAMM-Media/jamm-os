// path: frontend/src/app/api/auth/login/route.ts
import { NextRequest, NextResponse } from 'next/server'

export async function POST(request: NextRequest) {
  try {
    const { email, password, totp_code, backup_code } = await request.json()

    const backendUrl = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000'
    const res = await fetch(`${backendUrl}/auth/token`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        username: email,
        password,
        totp_code: totp_code ?? null,
        backup_code: backup_code ?? null,
      }),
    })

    if (res.ok) {
      const data = await res.json()
      if (data.requires_2fa === true) {
        return NextResponse.json({ requires_2fa: true }, { status: 200 })
      }
      const response = NextResponse.json({ success: true, access_token: data.access_token })
      response.cookies.set('jamm_token', data.access_token, {
        httpOnly: true,
        secure: process.env.NODE_ENV === 'production',
        sameSite: 'lax',
        path: '/',
        maxAge: 60 * 60 * 8,  // 8 hours — matches ACCESS_TOKEN_EXPIRE_MINUTES in config
      })
      // Forward the refresh token cookie set by the backend
      const backendSetCookie = res.headers.get('set-cookie')
      if (backendSetCookie) {
        response.headers.append('Set-Cookie', backendSetCookie)
      }
      return response
    }

    if (res.status === 401 || res.status === 422) {
      let message = 'Invalid email or password.'
      try {
        const errData = await res.json()
        if (typeof errData.detail === 'string') message = errData.detail
      } catch { /* ignore */ }
      return NextResponse.json({ success: false, message }, { status: 401 })
    }

    return NextResponse.json(
      { success: false, message: 'Unable to reach server. Please try again.' },
      { status: 503 }
    )
  } catch {
    return NextResponse.json(
      { success: false, message: 'Unable to reach server. Please try again.' },
      { status: 503 }
    )
  }
}

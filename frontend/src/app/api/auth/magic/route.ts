import { type NextRequest, NextResponse } from 'next/server'

export async function GET(request: NextRequest): Promise<NextResponse> {
  const token = request.nextUrl.searchParams.get('token')
  if (!token) {
    return NextResponse.json({ error: 'Missing token' }, { status: 400 })
  }

  const backendUrl = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000'

  try {
    const res = await fetch(
      `${backendUrl}/auth/verify-magic-link?token=${encodeURIComponent(token)}`,
      { method: 'GET', headers: { 'Content-Type': 'application/json' } }
    )

    if (!res.ok) {
      return NextResponse.json({ error: 'Link invalid or expired' }, { status: 401 })
    }

    const data = await res.json()
    if (!data.access_token) {
      return NextResponse.json({ error: 'Invalid response' }, { status: 500 })
    }

    const response = NextResponse.json({ success: true })
    response.cookies.set('jamm_token', data.access_token, {
      httpOnly: true,
      secure: process.env.NODE_ENV === 'production',
      sameSite: 'lax',
      path: '/',
      maxAge: 60 * 60 * 8,
    })

    if (data.refresh_token) {
      response.cookies.set('jamm_refresh_token', data.refresh_token, {
        httpOnly: true,
        secure: process.env.NODE_ENV === 'production',
        sameSite: 'lax',
        path: '/',
        maxAge: 60 * 60 * 24 * 30,
      })
    }

    return response
  } catch {
    return NextResponse.json({ error: 'Server error' }, { status: 500 })
  }
}

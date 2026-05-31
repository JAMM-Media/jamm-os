// path: frontend/src/app/api/backend/[...path]/route.ts
import { type NextRequest, NextResponse } from 'next/server'
import { cookies } from 'next/headers'

const BACKEND_URL = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000'

async function attemptRefresh(): Promise<string | null> {
  /**
   * Calls /auth/refresh on the backend using the jamm_refresh_token cookie.
   * Returns the new access token string on success, null on failure.
   * Also updates the jamm_token and jamm_refresh_token cookies in the
   * response if successful — but since we are in a server action we
   * handle cookie updates in the proxy response below.
   */
  const cookieStore = await cookies()
  const refreshToken = cookieStore.get('jamm_refresh_token')?.value
  if (!refreshToken) return null

  try {
    const res = await fetch(`${BACKEND_URL}/auth/refresh`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Cookie': `jamm_refresh_token=${refreshToken}`,
      },
    })
    if (!res.ok) return null
    const data = await res.json()
    return data.access_token ?? null
  } catch {
    return null
  }
}

async function proxyRequest(
  request: NextRequest,
  params: { path: string[] }
): Promise<NextResponse> {
  const cookieStore = await cookies()
  const incomingAuth = request.headers.get('Authorization')
  const cookieToken = cookieStore.get('jamm_token')?.value

  const path = params.path.join('/')
  const search = request.nextUrl.search ?? ''
  const targetUrl = `${BACKEND_URL}/${path}${search}`

  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
  }
  // Portal routes send their own JWT via Authorization header.
  // Always prefer the incoming Authorization header when present.
  // Fall back to the staff cookie token for staff-side requests.
  if (incomingAuth) {
    headers['Authorization'] = incomingAuth
  } else if (cookieToken) {
    headers['Authorization'] = `Bearer ${cookieToken}`
  }

  const init: RequestInit = {
    method: request.method,
    headers,
  }

  if (!['GET', 'HEAD'].includes(request.method)) {
    const body = await request.text()
    if (body) init.body = body
  }

  try {
    const res = await fetch(targetUrl, init)

    // If 401, attempt silent refresh then retry once
    if (res.status === 401) {
      const newAccessToken = await attemptRefresh()
      if (newAccessToken) {
        // Retry the original request with the new token
        const retryHeaders = { ...headers, Authorization: `Bearer ${newAccessToken}` }
        const retryInit: RequestInit = { ...init, headers: retryHeaders }
        const retryRes = await fetch(targetUrl, retryInit)
        const retryData = await retryRes.text()

        const response = new NextResponse(retryData, {
          status: retryRes.status,
          headers: {
            'Content-Type': retryRes.headers.get('Content-Type') ?? 'application/json',
          },
        })
        // Update the jamm_token cookie with the new access token
        response.cookies.set('jamm_token', newAccessToken, {
          httpOnly: true,
          secure: process.env.NODE_ENV === 'production',
          sameSite: 'lax',
          path: '/',
          maxAge: 60 * 30,
        })
        return response
      }
      // Refresh failed — return 401 to trigger login redirect
      return NextResponse.json(
        { detail: 'Session expired. Please log in again.' },
        { status: 401 }
      )
    }

    // Pass streaming responses (SSE) through without buffering.
    const contentType = res.headers.get('Content-Type') ?? ''
    if (contentType.includes('text/event-stream') && res.body) {
      const reader = res.body.getReader()
      const stream = new ReadableStream({
        start(controller) {
          function pump() {
            reader.read().then(({ done, value }) => {
              if (done) { controller.close(); return }
              controller.enqueue(value)
              pump()
            }).catch(() => { controller.close() })
          }
          pump()
        },
        cancel() { reader.cancel().catch(() => {}) },
      })
      return new NextResponse(stream, {
        status: res.status,
        headers: {
          'Content-Type': 'text/event-stream',
          'Cache-Control': 'no-cache',
          'X-Accel-Buffering': 'no',
        },
      })
    }

    const data = await res.text()
    return new NextResponse(data, {
      status: res.status,
      headers: {
        'Content-Type': contentType || 'application/json',
      },
    })
  } catch {
    return NextResponse.json(
      { detail: 'Backend unreachable' },
      { status: 503 }
    )
  }
}

export async function GET(
  request: NextRequest,
  { params }: { params: Promise<{ path: string[] }> }
) {
  return proxyRequest(request, await params)
}

export async function POST(
  request: NextRequest,
  { params }: { params: Promise<{ path: string[] }> }
) {
  return proxyRequest(request, await params)
}

export async function PATCH(
  request: NextRequest,
  { params }: { params: Promise<{ path: string[] }> }
) {
  return proxyRequest(request, await params)
}

export async function PUT(
  request: NextRequest,
  { params }: { params: Promise<{ path: string[] }> }
) {
  return proxyRequest(request, await params)
}

export async function DELETE(
  request: NextRequest,
  { params }: { params: Promise<{ path: string[] }> }
) {
  return proxyRequest(request, await params)
}

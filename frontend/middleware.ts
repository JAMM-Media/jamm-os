// path: frontend/middleware.ts
import { type NextRequest, NextResponse } from 'next/server'

const PUBLIC_PATHS = [
  '/login',
  '/api/auth/login',
  '/api/auth/logout',
  '/api/auth/me',
  '/portal',
  '/_next',
  '/favicon.ico',
  '/favicon.svg',
  '/logo.svg',
]

export function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl

  // Allow all public paths
  const isPublic = PUBLIC_PATHS.some((path) => pathname.startsWith(path))
  if (isPublic) {
    return NextResponse.next()
  }

  // Check for auth cookie
  const token = request.cookies.get('jamm_token')?.value

  if (!token) {
    const loginUrl = request.nextUrl.clone()
    loginUrl.pathname = '/login'
    return NextResponse.redirect(loginUrl)
  }

  return NextResponse.next()
}

export const config = {
  matcher: [
    /*
     * Match all request paths EXCEPT:
     * - _next/static (static files)
     * - _next/image (image optimization)
     * - favicon.ico
     */
    '/((?!_next/static|_next/image|favicon\\.ico|favicon\\.svg|logo\\.svg).*)',
  ],
}

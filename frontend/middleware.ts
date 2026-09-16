// path: frontend/middleware.ts
import { type NextRequest, NextResponse } from 'next/server'

const PUBLIC_PATHS = [
  '/login',
  '/api/auth/login',
  '/api/auth/logout',
  '/api/auth/me',
  '/api/auth/magic',
  '/api/backend/auth/request-magic-link',
  '/api/backend/auth/verify-magic-link',
  '/api/backend/auth/refresh',
  '/api/backend/portal',
  '/portal',
  '/review',
  '/_next',
]

// Static image files are served without auth regardless of filename.
// Matches only a real file extension at the end of the path, so a route
// like /clients.svg-shaped (no dot-separated extension suffix) is not excluded.
const STATIC_EXTENSIONS = /\.(?:svg|png|ico|jpg|jpeg|webp)$/

export function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl

  // Allow static image files and all public paths
  const isPublic =
    STATIC_EXTENSIONS.test(pathname) ||
    PUBLIC_PATHS.some((path) => pathname.startsWith(path))
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
     * - any path whose final segment is a static image file (.svg, .png, .ico,
     *   .jpg, .jpeg, .webp). The extension must be at the very end of the path
     *   so that routes like /clients.svg-shaped are not excluded.
     */
    '/((?!_next/static|_next/image)(?!.*\\.(?:svg|png|ico|jpg|jpeg|webp)$).*)',
  ],
}

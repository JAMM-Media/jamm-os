// path: frontend/src/lib/api.ts
import axios from 'axios'

/**
 * Axios instance for all FastAPI calls.
 * Routes through /api/backend/* (Next.js rewrite → FastAPI).
 * Auth token is read from the jamm_token HttpOnly cookie server-side
 * by the Next.js middleware — client components call /api/backend/* and
 * the browser automatically sends the cookie to the Next.js server.
 *
 * For server components or route handlers that need to forward the token,
 * use the getServerApi() helper below instead.
 */
const api = axios.create({
  baseURL: '/api/backend',
  headers: { 'Content-Type': 'application/json' },
  withCredentials: true,
})

export default api

/**
 * For use in Next.js Route Handlers only (server-side).
 * Pass the token string read from cookies().
 */
export function getServerApi(token: string) {
  return axios.create({
    baseURL: process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000',
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${token}`,
    },
  })
}

// API module re-exports — allows `import { clientsApi } from '@/lib/api'`
export { clientsApi } from './api/clients'
export { engagementsApi } from './api/engagements'
export type { CalendarItem } from './api/engagements'
export { tasksApi } from './api/tasks'
export { documentsApi } from './api/documents'
export { invoicesApi } from './api/invoices'
export { dashboardApi } from './api/dashboard'
export type { Client, ClientDetail, PaginatedResponse } from './api/clients'
export type { Engagement } from './api/engagements'
export type { Task } from './api/tasks'
export type { Document } from './api/documents'
export type { Invoice } from './api/invoices'
export type { DashboardItem, DashboardStats } from './api/dashboard'
export { reportsApi } from './api/reports'
export type { WIPSummary, WIPEngagement } from './api/reports'

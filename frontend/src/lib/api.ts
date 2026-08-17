// path: frontend/src/lib/api.ts
import axios from 'axios'

const api = axios.create({
  baseURL: '/api/backend',
  headers: { 'Content-Type': 'application/json' },
  withCredentials: true,
})

// Attach access_token from localStorage on every request if present
api.interceptors.request.use((config) => {
  if (typeof window !== 'undefined') {
    const token = localStorage.getItem('access_token')
    if (token) {
      config.headers['Authorization'] = `Bearer ${token}`
    }
  }
  return config
})

let isRefreshing = false
let failedQueue: Array<{ resolve: (token: string) => void; reject: (reason: unknown) => void }> = []

function processQueue(error: unknown, token: string | null) {
  failedQueue.forEach((p) => (error ? p.reject(error) : p.resolve(token!)))
  failedQueue = []
}

// Handle 401s with silent refresh; redirect to /login only when refresh itself fails
api.interceptors.response.use(
  (response) => response,
  async (error) => {
    const originalRequest = error.config

    if (error.response?.status !== 401) {
      return Promise.reject(error)
    }

    // A 401 from the refresh endpoint itself means the session is truly expired
    if (originalRequest.url?.includes('/auth/refresh')) {
      if (typeof window !== 'undefined') {
        localStorage.clear()
        window.location.href = '/login'
      }
      return Promise.reject(error)
    }

    // Already retried once — do not loop
    if (originalRequest._retry) {
      if (typeof window !== 'undefined') {
        localStorage.clear()
        window.location.href = '/login'
      }
      return Promise.reject(error)
    }

    // Queue any concurrent 401s while a refresh is already in flight
    if (isRefreshing) {
      return new Promise<string>((resolve, reject) => {
        failedQueue.push({ resolve, reject })
      }).then((token) => {
        originalRequest.headers['Authorization'] = `Bearer ${token}`
        return api(originalRequest)
      })
    }

    originalRequest._retry = true
    isRefreshing = true

    try {
      const { data } = await axios.post<{ access_token: string }>(
        '/api/backend/auth/refresh',
        {},
        { withCredentials: true }
      )
      const newToken = data.access_token
      if (typeof window !== 'undefined') {
        localStorage.setItem('access_token', newToken)
      }
      api.defaults.headers.common['Authorization'] = `Bearer ${newToken}`
      originalRequest.headers['Authorization'] = `Bearer ${newToken}`
      processQueue(null, newToken)
      return api(originalRequest)
    } catch (refreshError) {
      processQueue(refreshError, null)
      if (typeof window !== 'undefined') {
        localStorage.clear()
        window.location.href = '/login'
      }
      return Promise.reject(refreshError)
    } finally {
      isRefreshing = false
    }
  }
)

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
export { leadsApi } from './api/leads'
export type { Lead, LeadActivityItem } from './api/leads'

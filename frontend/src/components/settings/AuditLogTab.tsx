'use client'

import { useState, useEffect, useCallback } from 'react'
import api from '@/lib/api'

interface AuditEntry {
  id: string
  action: string
  actor_name: string
  actor_type: string
  entity_type: string | null
  entity_id: string | null
  ip_address: string | null
  metadata: Record<string, unknown> | null
  created_at: string
}

const ACTION_LABELS: Record<string, string> = {
  'document.uploaded': 'Document uploaded',
  'document.downloaded': 'Document downloaded',
  'document.deleted': 'Document deleted',
  'user.login_success': 'Staff login',
  'user.login_failed': 'Failed login attempt',
  'user.invited': 'Staff invited',
  'user.role_changed': 'Staff role changed',
  'user.deactivated': 'Staff deactivated',
  'engagement.status_changed': 'Engagement status changed',
  'engagement.completed': 'Engagement completed',
  'invoice.sent': 'Invoice sent',
  'invoice.paid': 'Invoice paid',
  'tax_organizer.submitted': 'Tax organizer submitted',
  'totp.enabled': '2FA enabled',
  'totp.disabled': '2FA disabled',
  'firm.data_exported': 'Firm data exported',
  'portal.client_login': 'Client portal login',
  'irs_auth.sent': 'IRS authorization sent',
  'quickbooks.connected': 'QuickBooks connected',
  'quickbooks.disconnected': 'QuickBooks disconnected',
}

function formatAction(action: string): string {
  return ACTION_LABELS[action] ?? action.replace(/\./g, ' ').replace(/_/g, ' ')
}

function formatDate(iso: string): string {
  const d = new Date(iso)
  return d.toLocaleDateString('en-US', {
    month: 'short', day: 'numeric', year: 'numeric',
    hour: '2-digit', minute: '2-digit',
  })
}

export default function AuditLogTab() {
  const [entries, setEntries] = useState<AuditEntry[]>([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(true)
  const [skip, setSkip] = useState(0)
  const [actionFilter, setActionFilter] = useState('')
  const [entityFilter, setEntityFilter] = useState('')
  const LIMIT = 50

  const fetchEntries = useCallback(async () => {
    setLoading(true)
    try {
      const params: Record<string, string | number> = { skip, limit: LIMIT }
      if (actionFilter) params.action = actionFilter
      if (entityFilter) params.entity_type = entityFilter
      const res = await api.get('/audit-log/', { params })
      setEntries(res.data.items ?? [])
      setTotal(res.data.total ?? 0)
    } catch {
      setEntries([])
    } finally {
      setLoading(false)
    }
  }, [skip, actionFilter, entityFilter])

  useEffect(() => { fetchEntries() }, [fetchEntries])

  function handleFilterChange() {
    setSkip(0)
    fetchEntries()
  }

  return (
    <div className="space-y-4">
      <div>
        <h2 className="text-[15px] font-semibold text-[#1F3148] dark:text-[#EDEEF0]">
          Audit Log
        </h2>
        <p className="text-[13px] text-[#6B7280] mt-1">
          A complete record of actions taken in your firm. Append-only and cannot be modified.
        </p>
      </div>

      {/* Filters */}
      <div className="flex gap-3 flex-wrap">
        <input
          type="text"
          placeholder="Filter by action..."
          value={actionFilter}
          onChange={(e) => setActionFilter(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && handleFilterChange()}
          className="rounded-[6px] border border-[0.5px] border-[#C8CDD6] dark:border-[#484848] bg-white dark:bg-[#2D2D2D] text-[13px] text-[#374151] dark:text-[#9CA3AF] px-3 py-1.5 focus:outline-none focus:border-[#4A7FA5] w-48"
        />
        <select
          value={entityFilter}
          onChange={(e) => { setEntityFilter(e.target.value); setSkip(0) }}
          className="rounded-[6px] border border-[0.5px] border-[#C8CDD6] dark:border-[#484848] bg-white dark:bg-[#2D2D2D] text-[13px] text-[#374151] dark:text-[#9CA3AF] px-3 py-1.5 focus:outline-none focus:border-[#4A7FA5]"
        >
          <option value="">All entity types</option>
          <option value="document">Document</option>
          <option value="user">Staff</option>
          <option value="engagement">Engagement</option>
          <option value="invoice">Invoice</option>
          <option value="client">Client</option>
          <option value="irs_authorization">IRS Authorization</option>
          <option value="tax_organizer">Tax Organizer</option>
          <option value="firm">Firm</option>
        </select>
        <button
          onClick={handleFilterChange}
          className="rounded-[6px] bg-[#1F3148] text-white text-[13px] font-medium px-4 py-1.5 hover:bg-[#2a4060] transition-colors"
        >
          Filter
        </button>
      </div>

      {/* Table */}
      <div className="border border-[0.5px] border-[#C8CDD6] dark:border-[#484848] rounded-[8px] overflow-hidden">
        <table className="w-full text-[13px]">
          <thead>
            <tr className="bg-[#EDEEF0] dark:bg-[#2D2D2D] border-b border-[#C8CDD6] dark:border-[#484848]">
              <th className="text-left px-4 py-2.5 font-medium text-[#1F3148] dark:text-[#EDEEF0]">
                Date
              </th>
              <th className="text-left px-4 py-2.5 font-medium text-[#1F3148] dark:text-[#EDEEF0]">
                Action
              </th>
              <th className="text-left px-4 py-2.5 font-medium text-[#1F3148] dark:text-[#EDEEF0]">
                Actor
              </th>
              <th className="text-left px-4 py-2.5 font-medium text-[#1F3148] dark:text-[#EDEEF0]">
                Entity
              </th>
              <th className="text-left px-4 py-2.5 font-medium text-[#1F3148] dark:text-[#EDEEF0]">
                IP Address
              </th>
            </tr>
          </thead>
          <tbody>
            {loading && (
              <tr>
                <td colSpan={5} className="px-4 py-8 text-center text-[#6B7280]">
                  Loading...
                </td>
              </tr>
            )}
            {!loading && entries.length === 0 && (
              <tr>
                <td colSpan={5} className="px-4 py-8 text-center text-[#6B7280]">
                  No audit log entries found.
                </td>
              </tr>
            )}
            {!loading && entries.map((entry, i) => (
              <tr
                key={entry.id}
                className={`border-b border-[#C8CDD6] dark:border-[#484848] last:border-0 ${
                  i % 2 === 0 ? 'bg-white dark:bg-[#1E1E1E]' : 'bg-[#F7F7F8] dark:bg-[#252525]'
                }`}
              >
                <td className="px-4 py-2.5 text-[#6B7280] whitespace-nowrap">
                  {formatDate(entry.created_at)}
                </td>
                <td className="px-4 py-2.5 text-[#1F3148] dark:text-[#EDEEF0] font-medium">
                  {formatAction(entry.action)}
                </td>
                <td className="px-4 py-2.5 text-[#374151] dark:text-[#9CA3AF]">
                  {entry.actor_name}
                </td>
                <td className="px-4 py-2.5 text-[#374151] dark:text-[#9CA3AF]">
                  {entry.entity_type ?? ''}
                </td>
                <td className="px-4 py-2.5 text-[#6B7280] font-mono text-[11px]">
                  {entry.ip_address ?? ''}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Pagination */}
      {total > LIMIT && (
        <div className="flex items-center justify-between text-[13px] text-[#6B7280]">
          <span>
            Showing {skip + 1} to {Math.min(skip + LIMIT, total)} of {total} entries
          </span>
          <div className="flex gap-2">
            <button
              onClick={() => setSkip(Math.max(0, skip - LIMIT))}
              disabled={skip === 0}
              className="px-3 py-1.5 rounded-[6px] border border-[#C8CDD6] dark:border-[#484848] disabled:opacity-40 hover:border-[#4A7FA5] transition-colors"
            >
              Previous
            </button>
            <button
              onClick={() => setSkip(skip + LIMIT)}
              disabled={skip + LIMIT >= total}
              className="px-3 py-1.5 rounded-[6px] border border-[#C8CDD6] dark:border-[#484848] disabled:opacity-40 hover:border-[#4A7FA5] transition-colors"
            >
              Next
            </button>
          </div>
        </div>
      )}
    </div>
  )
}

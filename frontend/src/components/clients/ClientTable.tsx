// frontend/src/components/clients/ClientTable.tsx
'use client'

import { useRouter } from 'next/navigation'
import { type Client } from '@/lib/api'
import { StatusBadge } from '@/components/ui/StatusBadge'
import { HealthDot } from '@/components/clients/HealthDot'
import { formatEntityType, formatEntitySubtype } from '@/lib/utils'

interface ClientTableProps {
  clients: Client[]
}

export function ClientTable({ clients }: ClientTableProps) {
  const router = useRouter()

  return (
    <div className="rounded-modal border border-[0.5px] border-surface-border dark:border-dark-border overflow-auto">
      <table className="w-full border-collapse">
        <thead>
          <tr className="bg-surface-card dark:bg-[#252525]">
            {['Client', 'Email', 'Phone', 'Entity Type', 'Status', ''].map((col) => (
              <th
                key={col}
                className="px-4 py-2.5 text-left text-[11px] font-medium text-[#6B7280] uppercase tracking-[0.05em] whitespace-nowrap"
              >
                {col}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {clients.map((client, i) => (
            <tr
              key={client.id}
              onClick={() => router.push(`/clients/${client.id}`)}
              className={[
                'group cursor-pointer transition-colors',
                'bg-surface-page dark:bg-dark-page',
                'hover:bg-[#DDDFE3] dark:hover:bg-[#323232]',
                i !== clients.length - 1
                  ? 'border-b border-[0.5px] border-[#D5D8DE] dark:border-dark-card'
                  : '',
              ].join(' ')}
            >
              <td className="px-4 py-3">
                <div className="flex items-center gap-2">
                  <HealthDot clientId={client.id} />
                  <span className="text-[12px] font-medium text-brand dark:text-[#EDEEF0]">
                    {client.name}
                  </span>
                </div>
              </td>
              <td className="px-4 py-3">
                <span className="text-[12px] text-[#374151] dark:text-[#9CA3AF]">
                  {client.email ?? '—'}
                </span>
              </td>
              <td className="px-4 py-3">
                <span className="text-[12px] text-[#374151] dark:text-[#9CA3AF]">
                  {client.phone ?? '—'}
                </span>
              </td>
              <td className="px-4 py-3">
                <span className="text-[12px] text-[#374151] dark:text-[#9CA3AF]">
                  {formatEntityType(client.entityType)
                    ? `${formatEntityType(client.entityType)}${client.entitySubtype ? ` -- ${formatEntitySubtype(client.entitySubtype)}` : ''}`
                    : '—'}
                </span>
              </td>
              <td className="px-4 py-3">
                <StatusBadge variant={client.isActive ? 'active' : 'inactive'} />
              </td>
              <td className="px-4 py-3 text-right">
                <span className="text-[12px] text-[#6B7280] opacity-0 group-hover:opacity-100 transition-opacity">
                  View →
                </span>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

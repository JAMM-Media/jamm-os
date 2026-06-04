// path: frontend/src/components/settings/AutomationsTab.tsx
'use client'

import { useState, useEffect, useCallback } from 'react'
import { Loader2 } from 'lucide-react'
import { toast } from 'sonner'
import api from '@/lib/api'
import { cn } from '@/lib/utils'
import { useAuth } from '@/lib/hooks/useAuth'
import AutomationEditModal from './AutomationEditModal'

type Action = {
  type: string
  config: Record<string, unknown>
  order: number
}

interface AutomationRule {
  id: string
  name: string
  description: string
  is_enabled: boolean
  execution_count: number
  last_executed_at: string | null
  actions: Action[]
  default_actions: Action[]
}

const DEFAULT_ON_PRESETS = new Set([
  "Document Request Reminder (3-day)",
  "E-Signature Reminder (2-day)",
  "Overdue Task Alert to Staff",
  "New Client Welcome Email",
  "Invoice Overdue Reminder",
  "Extension Filed Auto-Notify",
  "IRS Authorization Expiry Warning",
  "Invoice Overdue Escalating Sequence",
  "Engagement Deadline Approaching — 14-day Alert",
])

function ToggleSwitch({
  checked,
  disabled,
  loading,
  onChange,
}: {
  checked: boolean
  disabled: boolean
  loading: boolean
  onChange: () => void
}) {
  if (loading) {
    return <Loader2 className="w-3.5 h-3.5 animate-spin text-[#6B7280]" />
  }
  return (
    <button
      role="switch"
      aria-checked={checked}
      disabled={disabled}
      onClick={onChange}
      className={cn(
        'relative inline-flex h-5 w-9 shrink-0 items-center rounded-full transition-colors focus:outline-none disabled:opacity-50',
        checked ? 'bg-brand dark:bg-[#3A6A94]' : 'bg-gray-300 dark:bg-gray-600',
      )}
    >
      <span
        className={cn(
          'inline-block h-3.5 w-3.5 transform rounded-full bg-white transition-transform',
          checked ? 'translate-x-4' : 'translate-x-0.5',
        )}
      />
    </button>
  )
}

function SkeletonRow() {
  return (
    <div className="bg-card dark:bg-dark-card rounded-lg border border-subtle px-4 py-3 flex items-center gap-4 mb-2">
      <div className="flex-1 flex flex-col gap-2">
        <div className="h-4 rounded bg-gray-200 dark:bg-gray-700 w-[45%] animate-pulse" />
        <div className="h-3 rounded bg-gray-200 dark:bg-gray-700 w-[70%] animate-pulse" />
        <div className="h-3 rounded bg-gray-200 dark:bg-gray-700 w-[25%] animate-pulse" />
      </div>
      <div className="h-6 w-10 rounded-full bg-gray-200 dark:bg-gray-700 animate-pulse" />
    </div>
  )
}

function RuleCard({
  rule,
  section,
  isPending,
  canEdit,
  onToggle,
  onEdit,
}: {
  rule: AutomationRule
  section: 'active' | 'available'
  isPending: boolean
  canEdit: boolean
  onToggle: (rule: AutomationRule) => void
  onEdit: (rule: AutomationRule) => void
}) {
  const [expanded, setExpanded] = useState(false)
  const showBadge =
    section === 'active' && rule.is_enabled && DEFAULT_ON_PRESETS.has(rule.name)
  const needsTruncation = rule.description.length > 80
  const truncated = needsTruncation && !expanded
    ? rule.description.slice(0, 80) + '…'
    : rule.description
  const lastRun = rule.last_executed_at
    ? 'Last run: ' +
      new Date(rule.last_executed_at).toLocaleDateString('en-US', {
        month: 'short',
        day: 'numeric',
      })
    : 'Never used'

  return (
    <div className="bg-card dark:bg-dark-card rounded-lg border border-subtle px-4 py-3 flex items-center gap-4 mb-2">
      <div className="flex-1 flex flex-col gap-1">
        <div className="flex items-center gap-2">
          <span
            className={cn(
              'rounded-full w-1.5 h-1.5 shrink-0',
              rule.is_enabled ? 'bg-green-500' : 'bg-gray-300',
            )}
          />
          <span className="text-[13px] font-medium text-brand dark:text-[#EDEEF0]">
            {rule.name}
          </span>
          {showBadge && (
            <span className="text-[10px] font-medium bg-brand text-white px-2 py-0.5 rounded-full shrink-0">
              Default on
            </span>
          )}
        </div>
        <span className="text-[12px] text-[#6B7280] dark:text-[#9CA3AF]">
          {truncated}
          {needsTruncation && (
            <button
              onClick={() => setExpanded((e) => !e)}
              className="ml-1 text-[11px] text-brand-light hover:underline focus:outline-none"
            >
              {expanded ? 'Show less' : 'Show more'}
            </button>
          )}
        </span>
        <span className="text-[11px] text-[#6B7280] dark:text-[#9CA3AF]">{lastRun}</span>
      </div>
      <div className="flex items-center gap-3 shrink-0">
        {canEdit && (
          <button
            onClick={() => onEdit(rule)}
            className="text-[12px] text-brand dark:text-[#4A7FA5] hover:underline focus:outline-none"
          >
            Edit
          </button>
        )}
        <ToggleSwitch
          checked={rule.is_enabled}
          disabled={isPending}
          loading={isPending}
          onChange={() => onToggle(rule)}
        />
      </div>
    </div>
  )
}

const sectionLabelClass =
  'text-[12px] uppercase tracking-wide text-[#6B7280] mb-3 font-medium'
const emptyStateClass = 'text-[12px] text-[#6B7280] text-center py-6'

export default function AutomationsTab() {
  const { user } = useAuth()
  const canEdit = user?.role === 'firm_owner' || user?.role === 'manager'

  const [rules, setRules] = useState<AutomationRule[]>([])
  const [loading, setLoading] = useState(true)
  const [fetchError, setFetchError] = useState(false)
  const [pendingIds, setPendingIds] = useState<Set<string>>(new Set())
  const [editingRule, setEditingRule] = useState<AutomationRule | null>(null)

  const fetchRules = useCallback(() => {
    setLoading(true)
    setFetchError(false)
    api
      .get('/automation-rules/?limit=50')
      .then((r) => {
        const items: AutomationRule[] = r.data?.items ?? r.data
        setRules(items)
      })
      .catch(() => setFetchError(true))
      .finally(() => setLoading(false))
  }, [])

  useEffect(() => {
    fetchRules()
  }, [fetchRules])

  const handleToggle = useCallback(
    (rule: AutomationRule) => {
      const newEnabled = !rule.is_enabled
      setPendingIds((prev) => new Set(prev).add(rule.id))
      setRules((prev) =>
        prev.map((r) => (r.id === rule.id ? { ...r, is_enabled: newEnabled } : r)),
      )
      api
        .post(`/automation-rules/${rule.id}/toggle?enabled=${newEnabled}`)
        .then(() => {
          toast.success(newEnabled ? 'Automation enabled' : 'Automation disabled', {
            description: rule.name,
          })
        })
        .catch(() => {
          setRules((prev) =>
            prev.map((r) =>
              r.id === rule.id ? { ...r, is_enabled: rule.is_enabled } : r,
            ),
          )
          toast.error('Could not update automation', { description: 'Please try again.' })
        })
        .finally(() => {
          setPendingIds((prev) => {
            const next = new Set(prev)
            next.delete(rule.id)
            return next
          })
        })
    },
    [],
  )

  if (loading) {
    return (
      <div>
        {Array.from({ length: 4 }).map((_, i) => (
          <SkeletonRow key={i} />
        ))}
      </div>
    )
  }

  if (fetchError) {
    return (
      <div className="flex flex-col items-center justify-center py-12 gap-3">
        <p className="text-[13px] text-[#6B7280]">Could not load automations.</p>
        <button
          onClick={fetchRules}
          className="h-8 px-3 text-[13px] font-medium rounded-[6px] bg-brand text-white hover:bg-brand/90 transition-colors"
        >
          Retry
        </button>
      </div>
    )
  }

  const enabled = rules.filter((r) => r.is_enabled)
  const disabled = rules.filter((r) => !r.is_enabled)

  return (
    <div>
      <p className={sectionLabelClass}>Active Automations</p>
      {enabled.length === 0 ? (
        <p className={emptyStateClass}>
          No automations enabled yet. Turn on your first one below.
        </p>
      ) : (
        enabled.map((rule) => (
          <RuleCard
            key={rule.id}
            rule={rule}
            section="active"
            isPending={pendingIds.has(rule.id)}
            canEdit={canEdit}
            onToggle={handleToggle}
            onEdit={setEditingRule}
          />
        ))
      )}

      <p className={cn(sectionLabelClass, 'mt-6')}>Available Automations</p>
      {disabled.length === 0 ? (
        <p className={emptyStateClass}>All automations are active.</p>
      ) : (
        disabled.map((rule) => (
          <RuleCard
            key={rule.id}
            rule={rule}
            section="available"
            isPending={pendingIds.has(rule.id)}
            canEdit={canEdit}
            onToggle={handleToggle}
            onEdit={setEditingRule}
          />
        ))
      )}

      {editingRule && (
        <AutomationEditModal
          rule={editingRule}
          onClose={() => setEditingRule(null)}
          onSaved={() => {
            setEditingRule(null)
            fetchRules()
          }}
        />
      )}
    </div>
  )
}

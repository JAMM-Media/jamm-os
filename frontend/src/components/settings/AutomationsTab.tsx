// path: frontend/src/components/settings/AutomationsTab.tsx
'use client'

import { useState, useEffect, useCallback } from 'react'
import { Loader2, FlaskConical, CheckCircle2, XCircle, AlertTriangle } from 'lucide-react'
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
  trigger_event: string
  trigger_conditions: unknown[]
  is_enabled: boolean
  execution_count: number
  last_executed_at: string | null
  actions: Action[]
  default_actions: Action[]
}

const PAYLOAD_FIELDS: Record<string, Array<{ key: string; label: string; placeholder: string }>> = {
  'engagement.created':                    [{ key: 'engagement_type',    label: 'Engagement Type',    placeholder: 'e.g. tax_return_1040' }],
  'engagement.status_changed':             [{ key: 'new_status',         label: 'New Status',         placeholder: 'e.g. completed' }],
  'engagement.completed':                  [{ key: 'engagement_type',    label: 'Engagement Type',    placeholder: 'e.g. tax_return_1040' }],
  'engagement.deadline_approaching':       [{ key: 'days_until_deadline', label: 'Days Until Deadline', placeholder: 'e.g. 7' }],
  'document_request.completed':            [],
  'document_request.created':              [],
  'invoice.created':                       [{ key: 'total_amount',       label: 'Invoice Amount',     placeholder: 'e.g. 850' }],
  'invoice.overdue':                       [{ key: 'days_overdue',       label: 'Days Overdue',       placeholder: 'e.g. 7' }],
  'invoice.paid':                          [{ key: 'total_amount',       label: 'Invoice Amount',     placeholder: 'e.g. 850' }],
  'client.created':                        [],
  'extension.filed':                       [],
  'irs_authorization.expiry_approaching':  [{ key: 'days_until_expiry',  label: 'Days Until Expiry',  placeholder: 'e.g. 30' }],
  'task.overdue':                          [{ key: 'days_overdue',       label: 'Days Overdue',       placeholder: 'e.g. 3' }],
}

interface SimulateResult {
  would_trigger: boolean
  conditions_evaluated: number
  conditions_passed: boolean
  trigger_event: string
  actions_that_would_execute: Array<{ type: string; order: number }>
  rule_is_enabled: boolean
}

function SimulateModal({ rule, onClose }: { rule: AutomationRule; onClose: () => void }) {
  const [values, setValues] = useState<Record<string, string>>({})
  const [result, setResult] = useState<SimulateResult | null>(null)
  const [running, setRunning] = useState(false)

  useEffect(() => {
    function handleKeyDown(e: KeyboardEvent) {
      if (e.key === 'Escape') onClose()
    }
    document.addEventListener('keydown', handleKeyDown)
    return () => document.removeEventListener('keydown', handleKeyDown)
  }, [onClose])

  const fields = PAYLOAD_FIELDS[rule.trigger_event] ?? [{ key: 'event_data', label: 'Event Data (JSON)', placeholder: '{}' }]
  const truncatedName = rule.name.length > 35 ? rule.name.slice(0, 35) + '…' : rule.name

  async function handleRun() {
    setRunning(true)
    setResult(null)
    try {
      const payload: Record<string, unknown> = {}
      fields.forEach(f => {
        if (values[f.key]) payload[f.key] = values[f.key]
      })
      const { data } = await api.post(`/automation-rules/${rule.id}/simulate`, payload)
      setResult(data)
    } catch {
      toast.error('Simulation failed — check your payload and try again.')
    } finally {
      setRunning(false)
    }
  }

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/35"
      onClick={onClose}
    >
      <div
        className="bg-[#EDEEF0] dark:bg-[#383838] rounded-[10px] border border-[#C8CDD6] dark:border-[#484848] w-full max-w-md mx-4 shadow-lg"
        onClick={e => e.stopPropagation()}
      >
        {/* Header */}
        <div
          className="flex items-center justify-between px-4 border-b border-[#C8CDD6] dark:border-[#484848]"
          style={{ height: 48 }}
        >
          <div className="flex items-center gap-2">
            <FlaskConical className="w-3.5 h-3.5 text-[#6B7280]" />
            <span className="text-[13px] font-medium text-brand dark:text-[#EDEEF0]">
              {truncatedName}
            </span>
          </div>
          <button onClick={onClose} className="text-[#6B7280] hover:text-brand focus:outline-none">
            <XCircle className="w-4 h-4" />
          </button>
        </div>

        {/* Body */}
        <div className="p-4 flex flex-col gap-4">
          {/* Rule info strip */}
          <div className="flex items-center gap-3">
            <span className="text-[11px] bg-[#E5E7EB] dark:bg-[#484848] text-[#374151] dark:text-[#9CA3AF] px-2 py-0.5 rounded-full">
              {rule.trigger_event}
            </span>
            <div className="flex items-center gap-1.5">
              <span
                className={cn(
                  'w-1.5 h-1.5 rounded-full',
                  rule.is_enabled ? 'bg-green-500' : 'bg-gray-300',
                )}
              />
              <span className="text-[11px] text-[#6B7280] dark:text-[#9CA3AF]">
                {rule.is_enabled ? 'Enabled' : 'Disabled'}
              </span>
            </div>
          </div>

          {/* Payload fields */}
          <div>
            <p className="text-[11px] uppercase tracking-wide text-[#6B7280] dark:text-[#9CA3AF] mb-2 font-medium">
              Test payload
            </p>
            {fields.length === 0 ? (
              <p className="text-[12px] italic text-[#6B7280]">
                No payload required — this rule triggers on the event alone.
              </p>
            ) : (
              <div className="flex flex-col gap-3">
                {fields.map(f => (
                  <div key={f.key}>
                    <label className="block text-[11px] font-medium text-brand dark:text-[#4A7FA5] mb-1">
                      {f.label}
                    </label>
                    <input
                      type="text"
                      placeholder={f.placeholder}
                      value={values[f.key] ?? ''}
                      onChange={e => setValues(prev => ({ ...prev, [f.key]: e.target.value }))}
                      className="h-9 px-3 rounded-md border border-[#C8CDD6] dark:border-[#484848] bg-[#F7F7F8] dark:bg-[#2D2D2D] text-[13px] text-brand dark:text-[#EDEEF0] focus:border-[#4A7FA5] focus:outline-none w-full"
                    />
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Result area */}
          {result && (
            <div
              className={cn(
                'rounded-[8px] border p-4',
                result.would_trigger
                  ? 'border-[#D1FAE5] bg-[#D1FAE5]/30 dark:bg-[#065F46]/10'
                  : 'border-[#FEE2E2] bg-[#FEE2E2]/30 dark:bg-[#991B1B]/10',
              )}
            >
              <div className="flex items-center gap-2 mb-2">
                {result.would_trigger ? (
                  <CheckCircle2 className="w-4 h-4 text-[#065F46]" />
                ) : (
                  <XCircle className="w-4 h-4 text-[#991B1B]" />
                )}
                <span
                  className={cn(
                    'text-[13px] font-medium',
                    result.would_trigger ? 'text-[#065F46]' : 'text-[#991B1B]',
                  )}
                >
                  {result.would_trigger ? 'Would trigger' : 'Would not trigger'}
                </span>
              </div>

              {result.would_trigger ? (
                <ul className="flex flex-col gap-1 mb-2">
                  {result.actions_that_would_execute.map((action, i) => (
                    <li key={i} className="flex items-center gap-2 text-[12px] text-[#374151] dark:text-[#9CA3AF]">
                      <span className="w-1 h-1 rounded-full bg-gray-400 shrink-0" />
                      {action.type.replace(/_/g, ' ').replace(/^./, c => c.toUpperCase())}
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="text-[12px] text-[#6B7280] dark:text-[#9CA3AF] mb-2">
                  Conditions not met for this payload.
                </p>
              )}

              {!result.rule_is_enabled && (
                <div className="flex items-start gap-2 mt-2">
                  <AlertTriangle className="w-3.5 h-3.5 text-[#92400E] shrink-0 mt-0.5" />
                  <p className="text-[12px] text-[#92400E]">
                    This rule is currently disabled. It would not fire even if conditions are met.
                  </p>
                </div>
              )}

              <p className="text-[11px] text-[#6B7280] dark:text-[#9CA3AF] mt-2">
                {result.conditions_evaluated} condition{result.conditions_evaluated !== 1 ? 's' : ''} evaluated
              </p>
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="flex items-center justify-between px-4 py-3 border-t border-[#C8CDD6] dark:border-[#484848]">
          <p className="text-[12px] text-[#6B7280] dark:text-[#9CA3AF]">
            Results are a preview only. No emails or tasks are created.
          </p>
          <div className="flex items-center gap-2">
            <button
              onClick={onClose}
              className="border border-brand text-brand text-[12px] h-8 px-3 rounded-[6px] hover:bg-brand/5 focus:outline-none transition-colors"
            >
              Cancel
            </button>
            <button
              onClick={handleRun}
              disabled={running}
              className="bg-brand dark:bg-brand-btn text-white text-[12px] font-medium h-8 px-3 rounded-[6px] hover:bg-brand/90 focus:outline-none transition-colors disabled:opacity-50"
            >
              {running ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : 'Run Test'}
            </button>
          </div>
        </div>
      </div>
    </div>
  )
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
  onTest,
}: {
  rule: AutomationRule
  section: 'active' | 'available'
  isPending: boolean
  canEdit: boolean
  onToggle: (rule: AutomationRule) => void
  onEdit: (rule: AutomationRule) => void
  onTest: (rule: AutomationRule) => void
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
        {canEdit && (
          <button
            onClick={() => onTest(rule)}
            className="text-[12px] text-[#6B7280] hover:text-brand dark:hover:text-[#4A7FA5] hover:underline focus:outline-none transition-colors"
          >
            Test
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
  const [testingRule, setTestingRule] = useState<AutomationRule | null>(null)

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
            onTest={setTestingRule}
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
            onTest={setTestingRule}
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

      {testingRule && (
        <SimulateModal rule={testingRule} onClose={() => setTestingRule(null)} />
      )}
    </div>
  )
}

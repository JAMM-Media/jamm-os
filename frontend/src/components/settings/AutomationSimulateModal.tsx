// path: frontend/src/components/settings/AutomationSimulateModal.tsx
'use client'

import { useState } from 'react'
import { X, Loader2, CheckCircle } from 'lucide-react'
import api from '@/lib/api'

type SimulateRule = {
  id: string
  name: string
  trigger_event: string
  is_enabled: boolean
}

type ActionSummary = {
  type: string
  order: number
}

type SimulateResult = {
  would_trigger: boolean
  conditions_evaluated: number
  conditions_passed: boolean
  trigger_event: string
  actions_that_would_execute: ActionSummary[]
  rule_is_enabled: boolean
}

type FieldDef = { key: string; label: string; defaultValue: string }

function getFields(trigger_event: string): FieldDef[] {
  if (trigger_event.includes('engagement')) {
    return [
      { key: 'status', label: 'Status', defaultValue: 'completed' },
      { key: 'engagement_type', label: 'Engagement Type', defaultValue: 'tax_return_1040' },
    ]
  }
  if (trigger_event.includes('invoice')) {
    return [
      { key: 'status', label: 'Status', defaultValue: 'overdue' },
      { key: 'amount', label: 'Amount', defaultValue: '500' },
    ]
  }
  if (trigger_event.includes('document')) {
    return [
      { key: 'status', label: 'Status', defaultValue: 'completed' },
      { key: 'item_count', label: 'Item Count', defaultValue: '3' },
    ]
  }
  if (trigger_event.includes('client')) {
    return [
      { key: 'entity_type', label: 'Entity Type', defaultValue: 'individual' },
    ]
  }
  return [
    { key: 'event_type', label: 'Event Type', defaultValue: trigger_event },
  ]
}

const inputClass =
  'w-full h-9 px-3 rounded-[6px] text-[13px] bg-[#F7F7F8] dark:bg-[#2D2D2D] ' +
  'border border-[0.5px] border-[#C8CDD6] focus:border-[#4A7FA5] focus:outline-none transition-colors'
const labelClass =
  'block text-[11px] font-[500] text-[#1F3148] dark:text-[#EDEEF0] mb-1'

interface Props {
  rule: SimulateRule
  onClose: () => void
}

export default function AutomationSimulateModal({ rule, onClose }: Props) {
  const fields = getFields(rule.trigger_event)
  const [formValues, setFormValues] = useState<Record<string, string>>(
    Object.fromEntries(fields.map((f) => [f.key, f.defaultValue])),
  )
  const [result, setResult] = useState<SimulateResult | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const handleTest = async () => {
    setLoading(true)
    setError(null)
    try {
      const res = await api.post(`/automation-rules/${rule.id}/simulate`, {
        mock_payload: formValues,
      })
      setResult(res.data)
    } catch {
      setError('Simulation failed. Please try again.')
    } finally {
      setLoading(false)
    }
  }

  const handleReset = () => {
    setResult(null)
    setError(null)
  }

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center"
      style={{ backgroundColor: 'rgba(0,0,0,0.35)' }}
      onMouseDown={(e) => { if (e.target === e.currentTarget) onClose() }}
    >
      <div
        className="w-[480px] max-w-[95vw] flex flex-col rounded-[10px] bg-[#EDEEF0] dark:bg-[#383838]"
        style={{ border: '0.5px solid #C8CDD6' }}
      >
        {/* Header */}
        <div
          className="flex items-center justify-between px-4 py-3"
          style={{ borderBottom: '0.5px solid #C8CDD6' }}
        >
          <span className="text-[13px] font-[500] text-[#1F3148] dark:text-[#EDEEF0]">
            {rule.name}
          </span>
          <button
            onClick={onClose}
            className="text-[#6B7280] hover:text-[#1F3148] dark:hover:text-[#EDEEF0] transition-colors"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Body */}
        <div className="px-4 py-3.5">
          {result === null ? (
            <div className="flex flex-col gap-3">
              <p className="text-[12px] text-[#6B7280] dark:text-[#9CA3AF]">
                Enter mock values to test whether this rule would trigger.
              </p>
              {fields.map((f) => (
                <div key={f.key}>
                  <label className={labelClass}>{f.label}</label>
                  <input
                    type="text"
                    value={formValues[f.key] ?? ''}
                    onChange={(e) =>
                      setFormValues((prev) => ({ ...prev, [f.key]: e.target.value }))
                    }
                    className={inputClass}
                  />
                </div>
              ))}
              {error && (
                <p className="text-[12px] text-[#991B1B]">{error}</p>
              )}
            </div>
          ) : (
            <div className="flex flex-col gap-3">
              {result.would_trigger ? (
                <div className="flex items-center gap-2">
                  <CheckCircle className="w-6 h-6 text-green-500 shrink-0" />
                  <span className="text-[15px] font-[600] text-green-600 dark:text-green-400">
                    Would trigger
                  </span>
                </div>
              ) : (
                <div className="flex items-center gap-2">
                  <span className="text-[22px] leading-none text-amber-500">&#x2717;</span>
                  <span className="text-[15px] font-[600] text-amber-600 dark:text-amber-400">
                    Would not trigger
                  </span>
                </div>
              )}
              <p className="text-[11px] text-[#6B7280] dark:text-[#9CA3AF]">
                Rule is currently {result.rule_is_enabled ? 'enabled' : 'disabled'}
              </p>
              {result.would_trigger && result.actions_that_would_execute.length > 0 && (
                <div>
                  <p className="text-[11px] font-[500] text-[#1F3148] dark:text-[#EDEEF0] mb-2">
                    Actions that would execute:
                  </p>
                  <div className="flex flex-wrap gap-2">
                    {result.actions_that_would_execute.map((a) => (
                      <span
                        key={a.order}
                        className="text-[11px] font-[500] bg-[#1F3148] text-white dark:bg-[#4A7FA5] px-2 py-0.5 rounded-full"
                      >
                        {a.type}
                      </span>
                    ))}
                  </div>
                </div>
              )}
              {!result.would_trigger && !result.rule_is_enabled && (
                <p className="text-[12px] text-[#6B7280] dark:text-[#9CA3AF] italic">
                  This rule is currently disabled
                </p>
              )}
            </div>
          )}
        </div>

        {/* Footer */}
        <div
          className="flex items-center justify-between px-4 py-3"
          style={{ borderTop: '0.5px solid #C8CDD6' }}
        >
          <button
            onClick={onClose}
            className="h-8 px-3 text-[12px] rounded-[6px] text-[#6B7280] hover:text-[#1F3148] dark:hover:text-[#EDEEF0] transition-colors"
          >
            Cancel
          </button>
          {result === null ? (
            <button
              onClick={handleTest}
              disabled={loading}
              className="h-8 px-4 text-[12px] font-[500] rounded-[6px] bg-[#1F3148] text-white hover:bg-[#2a4060] disabled:opacity-50 transition-colors flex items-center gap-1"
            >
              {loading && <Loader2 className="w-3 h-3 animate-spin" />}
              Test Rule
            </button>
          ) : (
            <button
              onClick={handleReset}
              className="h-8 px-4 text-[12px] font-[500] rounded-[6px] bg-[#1F3148] text-white hover:bg-[#2a4060] transition-colors"
            >
              Test again
            </button>
          )}
        </div>
      </div>
    </div>
  )
}

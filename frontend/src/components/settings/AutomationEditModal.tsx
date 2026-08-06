// path: frontend/src/components/settings/AutomationEditModal.tsx
'use client'

import { useState, useEffect } from 'react'
import { X, Trash2, Plus, Loader2 } from 'lucide-react'
import { toast } from 'sonner'
import api from '@/lib/api'

type Action = {
  type: string
  config: Record<string, unknown>
  order: number
}

export type AutomationRuleForEdit = {
  id: string
  name: string
  actions: Action[]
  default_actions: Action[]
}

interface Props {
  rule: AutomationRuleForEdit
  onClose: () => void
  onSaved: () => void
}

const labelClass =
  'block text-[11px] font-[500] text-[#1F3148] dark:text-[#EDEEF0] mb-1'
const inputClass =
  'w-full h-9 px-3 rounded-[6px] text-[13px] bg-[#F7F7F8] dark:bg-[#2D2D2D] ' +
  'border border-[0.5px] border-[#C8CDD6] focus:border-[#4A7FA5] focus:outline-none transition-colors'
const helperClass = 'text-[11px] text-[#6B7280] mt-1'
const dividerClass = 'border-t border-[0.5px] border-[#C8CDD6] my-3'

export default function AutomationEditModal({ rule, onClose, onSaved }: Props) {
  const [localActions, setLocalActions] = useState<Action[]>([])
  const [saving, setSaving] = useState(false)
  const [resetting, setResetting] = useState(false)

  useEffect(() => {
    setLocalActions(JSON.parse(JSON.stringify(rule.actions)))
  }, [rule])

  // ── Mutators ──────────────────────────────────────────────────────────────

  const updateConfig = (idx: number, key: string, value: unknown) => {
    setLocalActions((prev) =>
      prev.map((a, i) =>
        i === idx ? { ...a, config: { ...a.config, [key]: value } } : a,
      ),
    )
  }

  const updateLineItem = (idx: number, field: string, value: unknown) => {
    setLocalActions((prev) =>
      prev.map((a, i) => {
        if (i !== idx) return a
        const items = Array.isArray(a.config.line_items)
          ? [...(a.config.line_items as Record<string, unknown>[])]
          : [{}]
        items[0] = { ...items[0], [field]: value }
        return { ...a, config: { ...a.config, line_items: items } }
      }),
    )
  }

  const removeTaskAction = (idx: number) => {
    setLocalActions((prev) => {
      const next = prev.filter((_, i) => i !== idx)
      return next.map((a, i) => ({ ...a, order: i }))
    })
  }

  const addTaskAction = () => {
    setLocalActions((prev) => [
      ...prev,
      { type: 'create_task', config: { title: '' }, order: prev.length },
    ])
  }

  // ── API calls ─────────────────────────────────────────────────────────────

  const handleSave = async () => {
    setSaving(true)
    try {
      await api.patch(`/automation-rules/${rule.id}`, { actions: localActions })
      toast.success('Automation updated')
      onSaved()
    } catch {
      toast.error('Could not save — please try again')
    } finally {
      setSaving(false)
    }
  }

  const handleReset = async () => {
    setResetting(true)
    try {
      await api.post(`/automation-rules/${rule.id}/reset-to-default`)
      toast.success('Reset to default settings')
      onSaved()
    } catch {
      toast.error('Could not reset — please try again')
    } finally {
      setResetting(false)
    }
  }

  // ── Categorise actions for rendering ──────────────────────────────────────

  const withIdx = localActions.map((a, i) => ({ a, i }))

  const delayActions = withIdx.filter(({ a }) => a.config.delay_days !== undefined)
  const subjectActions = withIdx.filter(({ a }) => a.config.subject !== undefined)
  const bodyActions = withIdx.filter(({ a }) => a.type === 'send_email')
  const messageActions = withIdx.filter(({ a }) => a.config.message !== undefined)
  const taskActions = withIdx.filter(({ a }) => a.type === 'create_task')
  const invoiceActions = withIdx.filter(
    ({ a }) => a.type === 'create_invoice' && Array.isArray(a.config.line_items),
  )
  const ackActions = withIdx.filter(({ a }) => a.config.acknowledgment_days !== undefined)

  const showDelay = delayActions.length > 0
  const showSubject = subjectActions.length > 0
  const showBody = bodyActions.length > 0
  const showMessage = messageActions.length > 0
  const showTasks = taskActions.length > 0
  const showInvoice = invoiceActions.length > 0
  const showAck = ackActions.length > 0

  const hasAny =
    showDelay || showSubject || showBody || showMessage ||
    showTasks || showInvoice || showAck

  // Preceding sections rendered (for divider logic)
  const prevOf = (...flags: boolean[]) => flags.some(Boolean)

  // Delay label — Preset 12 style when 3+ actions have delay_days
  const getDelayLabel = (actionIdx: number, actionType: string): string => {
    if (delayActions.length >= 3) {
      const pos = delayActions.findIndex(({ i }) => i === actionIdx)
      if (pos === 0) return 'First reminder (days)'
      if (pos === 1) return 'Follow-up reminder (days)'
      return 'Owner escalation (days)'
    }
    return actionType === 'send_email' ? 'Reminder delay (days)' : 'Escalation delay (days)'
  }

  // ── Render ─────────────────────────────────────────────────────────────────

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center"
      style={{ backgroundColor: 'rgba(0,0,0,0.35)' }}
      onMouseDown={(e) => { if (e.target === e.currentTarget) onClose() }}
    >
      <div
        className="w-[520px] max-w-[95vw] flex flex-col rounded-[10px] bg-[#EDEEF0] dark:bg-[#383838] overflow-hidden"
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
        <div
          className="overflow-y-auto px-4 py-3.5"
          style={{ maxHeight: '60vh' }}
        >
          {!hasAny && (
            <p className="text-[12px] text-[#6B7280] text-center py-4">
              This automation has no configurable fields.
            </p>
          )}

          {/* 1. Delay days */}
          {showDelay && (
            <div>
              {delayActions.map(({ a, i }, pos) => (
                <div key={i} className={pos > 0 ? 'mt-3' : ''}>
                  <label className={labelClass}>{getDelayLabel(i, a.type)}</label>
                  <input
                    type="number"
                    min={1}
                    max={90}
                    value={(a.config.delay_days as number) ?? ''}
                    onChange={(e) =>
                      updateConfig(i, 'delay_days', Math.max(1, parseInt(e.target.value) || 1))
                    }
                    className={inputClass}
                  />
                </div>
              ))}
            </div>
          )}

          {/* 2. Email subject */}
          {showSubject && prevOf(showDelay) && <div className={dividerClass} />}
          {showSubject && (
            <div>
              {subjectActions.map(({ a, i }, pos) => (
                <div key={i} className={pos > 0 ? 'mt-3' : ''}>
                  <label className={labelClass}>Email subject</label>
                  <input
                    type="text"
                    maxLength={150}
                    value={(a.config.subject as string) ?? ''}
                    onChange={(e) => updateConfig(i, 'subject', e.target.value)}
                    className={inputClass}
                  />
                </div>
              ))}
            </div>
          )}

          {/* 3. Email body / template override */}
          {showBody && prevOf(showDelay, showSubject) && <div className={dividerClass} />}
          {showBody && (
            <div>
              {bodyActions.map(({ a, i }, pos) => {
                const hasTemplate = a.config.template !== undefined
                const hasBody = a.config.body !== undefined
                const isOverride = hasTemplate && !hasBody
                return (
                  <div key={i} className={pos > 0 ? 'mt-3' : ''}>
                    <label className={labelClass}>
                      {isOverride
                        ? 'Custom email message (overrides default template)'
                        : 'Email message'}
                    </label>
                    <textarea
                      rows={4}
                      maxLength={1000}
                      value={(a.config.body as string) ?? ''}
                      onChange={(e) => updateConfig(i, 'body', e.target.value)}
                      className={`${inputClass} h-auto py-2 resize-none`}
                    />
                    {isOverride && (
                      <p className={helperClass}>Leave blank to use the default template</p>
                    )}
                  </div>
                )
              })}
            </div>
          )}

          {/* 4. Notification message */}
          {showMessage && prevOf(showDelay, showSubject, showBody) && (
            <div className={dividerClass} />
          )}
          {showMessage && (
            <div>
              {messageActions.map(({ a, i }, pos) => (
                <div key={i} className={pos > 0 ? 'mt-3' : ''}>
                  <label className={labelClass}>Notification message</label>
                  <input
                    type="text"
                    maxLength={300}
                    value={(a.config.message as string) ?? ''}
                    onChange={(e) => updateConfig(i, 'message', e.target.value)}
                    className={inputClass}
                  />
                </div>
              ))}
            </div>
          )}

          {/* 5. Task titles */}
          {showTasks && prevOf(showDelay, showSubject, showBody, showMessage) && (
            <div className={dividerClass} />
          )}
          {showTasks && (
            <div>
              <label className={labelClass}>Auto-created tasks</label>
              <div className="flex flex-col gap-2">
                {taskActions.map(({ a, i }) => (
                  <div key={i} className="flex items-center gap-2">
                    <input
                      type="text"
                      value={(a.config.title as string) ?? ''}
                      onChange={(e) => updateConfig(i, 'title', e.target.value)}
                      className={`${inputClass} flex-1`}
                      placeholder="Task title"
                    />
                    <button
                      onClick={() => removeTaskAction(i)}
                      disabled={taskActions.length <= 1}
                      className="text-[#991B1B] hover:text-[#7F1D1D] disabled:opacity-30 transition-colors flex-shrink-0"
                    >
                      <Trash2 className="w-4 h-4" />
                    </button>
                  </div>
                ))}
              </div>
              <button
                onClick={addTaskAction}
                className="mt-2 flex items-center gap-1 text-[12px] text-brand dark:text-[#4A7FA5] hover:underline focus:outline-none"
              >
                <Plus className="w-3.5 h-3.5" />
                Add task
              </button>
            </div>
          )}

          {/* 6. Invoice defaults */}
          {showInvoice &&
            prevOf(showDelay, showSubject, showBody, showMessage, showTasks) && (
              <div className={dividerClass} />
            )}
          {showInvoice && (
            <div>
              {invoiceActions.map(({ a, i }, pos) => {
                const items = a.config.line_items as Record<string, unknown>[]
                const item = items?.[0] ?? {}
                return (
                  <div key={i} className={pos > 0 ? 'mt-4' : ''}>
                    <div className="mb-3">
                      <label className={labelClass}>Default line item description</label>
                      <input
                        type="text"
                        maxLength={200}
                        value={(item.description as string) ?? ''}
                        onChange={(e) => updateLineItem(i, 'description', e.target.value)}
                        className={inputClass}
                      />
                    </div>
                    <div className="mb-3">
                      <label className={labelClass}>Default unit price ($)</label>
                      <input
                        type="number"
                        min={0}
                        step={0.01}
                        value={(item.unit_price as number) ?? ''}
                        onChange={(e) =>
                          updateLineItem(i, 'unit_price', parseFloat(e.target.value) || 0)
                        }
                        className={inputClass}
                      />
                    </div>
                    <div>
                      <label className={labelClass}>Days until invoice due</label>
                      <input
                        type="number"
                        min={1}
                        max={365}
                        value={(a.config.due_days_from_now as number) ?? ''}
                        onChange={(e) =>
                          updateConfig(
                            i,
                            'due_days_from_now',
                            Math.max(1, parseInt(e.target.value) || 1),
                          )
                        }
                        className={inputClass}
                      />
                    </div>
                  </div>
                )
              })}
            </div>
          )}

          {/* 7. Acknowledgment window */}
          {showAck &&
            prevOf(showDelay, showSubject, showBody, showMessage, showTasks, showInvoice) && (
              <div className={dividerClass} />
            )}
          {showAck && (
            <div>
              {ackActions.map(({ a, i }, pos) => (
                <div key={i} className={pos > 0 ? 'mt-3' : ''}>
                  <label className={labelClass}>Acknowledgment window (days)</label>
                  <input
                    type="number"
                    min={1}
                    max={30}
                    value={(a.config.acknowledgment_days as number) ?? ''}
                    onChange={(e) =>
                      updateConfig(
                        i,
                        'acknowledgment_days',
                        Math.max(1, parseInt(e.target.value) || 1),
                      )
                    }
                    className={inputClass}
                  />
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Footer */}
        <div
          className="flex items-center justify-between px-4 py-3"
          style={{ borderTop: '0.5px solid #C8CDD6' }}
        >
          {/* Left — Reset to default */}
          <button
            onClick={handleReset}
            disabled={resetting || saving}
            className="text-[12px] text-[#991B1B] hover:text-[#7F1D1D] disabled:opacity-50 transition-colors flex items-center gap-1"
          >
            {resetting && <Loader2 className="w-3 h-3 animate-spin" />}
            Reset to default
          </button>

          {/* Right — Cancel + Save */}
          <div className="flex items-center gap-2">
            <button
              onClick={onClose}
              disabled={saving || resetting}
              className="h-8 px-3 text-[12px] rounded-[6px] text-[#6B7280] hover:text-[#1F3148] dark:hover:text-[#EDEEF0] disabled:opacity-50 transition-colors"
            >
              Cancel
            </button>
            <button
              onClick={handleSave}
              disabled={saving || resetting}
              className="h-8 px-4 text-[12px] font-[500] rounded-[6px] bg-[#1F3148] text-white hover:bg-[#2a4060] disabled:opacity-50 transition-colors flex items-center gap-1"
            >
              {saving && <Loader2 className="w-3 h-3 animate-spin" />}
              Save
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}

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

const LEGACY_TO_ROLE: Record<string, string> = {
  assigned_staff: 'assigned_staff',
  firm_owner: 'firm_owner',
  manager: 'manager',
  client: 'client',
  staff: 'assigned_staff',
}

export default function AutomationEditModal({ rule, onClose, onSaved }: Props) {
  const [localActions, setLocalActions] = useState<Action[]>([])
  const [saving, setSaving] = useState(false)
  const [resetting, setResetting] = useState(false)

  useEffect(() => {
    const parsed: Action[] = JSON.parse(JSON.stringify(rule.actions))
    const normalized = parsed.map((action) => {
      if (action.type !== 'send_notification') return action
      const c = action.config
      if (c.recipient_role !== undefined) return action
      const { to, message, notification_type: _nt, ...rest } = c
      return {
        ...action,
        config: {
          ...rest,
          recipient_role: LEGACY_TO_ROLE[(to as string) ?? ''] ?? 'assigned_staff',
          tier: 'quiet',
          // Legacy "message" maps to title: a one-sentence notification reads
          // as a headline, not body copy, and the backend skips when title is empty.
          title: ((message as string) ?? '').trim() || rule.name,
          body: '',
        },
      }
    })
    setLocalActions(normalized)
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
  const messageActions = withIdx.filter(({ a }) => a.config.message !== undefined && a.type !== 'send_notification')
  const taskActions = withIdx.filter(({ a }) => a.type === 'create_task')
  const invoiceActions = withIdx.filter(
    ({ a }) => a.type === 'create_invoice' && Array.isArray(a.config.line_items),
  )
  const ackActions = withIdx.filter(({ a }) => a.config.acknowledgment_days !== undefined)
  const notifActions = withIdx.filter(({ a }) => a.type === 'send_notification')

  const showDelay = delayActions.length > 0
  const showSubject = subjectActions.length > 0
  const showBody = bodyActions.length > 0
  const showMessage = messageActions.length > 0
  const showTasks = taskActions.length > 0
  const showInvoice = invoiceActions.length > 0
  const showAck = ackActions.length > 0
  const showNotif = notifActions.length > 0

  const hasAny =
    showDelay || showSubject || showBody || showMessage ||
    showTasks || showInvoice || showAck || showNotif

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

  const MERGE_EXAMPLES: Record<string, string> = {
    client_name: 'Riverside Tax',
    engagement_type: '1040 return',
    firm_name: 'Riverside Tax & Advisory',
    days_until_due: '3',
  }

  function resolveMergeFields(text: string): string {
    return text.replace(/\{\{\s*([a-zA-Z0-9_]+)\s*\}\}/g, (_, key) =>
      Object.prototype.hasOwnProperty.call(MERGE_EXAMPLES, key) ? MERGE_EXAMPLES[key] : 'Example value'
    )
  }

    // ── Render ─────────────────────────────────────────────────────────────────

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center"
      style={{ backgroundColor: 'rgba(0,0,0,0.35)' }}
      onMouseDown={(e) => { if (e.target === e.currentTarget) onClose() }}
    >
      <div
        className="w-[620px] max-w-[95vw] flex flex-col rounded-[10px] bg-[#EDEEF0] dark:bg-[#383838] overflow-hidden"
        style={{ border: '0.5px solid #C8CDD6', maxHeight: 'min(90vh, 720px)' }}
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
          className="flex-1 overflow-y-auto px-4 py-3.5"
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

          {/* 8. Send Notification config */}
          {showNotif && prevOf(showDelay, showSubject, showBody, showMessage, showTasks, showInvoice, showAck) && (
            <div className={dividerClass} />
          )}
          {showNotif && (
            <div>
              {notifActions.map(({ a, i }) => {
                const recipientRole = (a.config.recipient_role as string) ?? 'firm_owner'
                const tier = (a.config.tier as string) ?? 'loud'
                const notifTitle = (a.config.title as string) ?? ''
                const notifBody = (a.config.body as string) ?? ''
                const previewTitle = resolveMergeFields(notifTitle || 'Engagement deadline approaching')
                const previewBody = resolveMergeFields(notifBody || "{{client_name}}'s {{engagement_type}} is due in 3 days.")
                return (
                  <div key={i}>
                    {/* Recipient role */}
                    <div className="mb-[17px]">
                      <label className={labelClass}>Who should be notified?</label>
                      <select
                        value={recipientRole}
                        onChange={(e) => updateConfig(i, 'recipient_role', e.target.value)}
                        className={inputClass}
                        style={{
                          appearance: 'none',
                          backgroundImage: 'linear-gradient(45deg,transparent 50%,#1F3148 50%),linear-gradient(135deg,#1F3148 50%,transparent 50%)',
                          backgroundPosition: 'calc(100% - 15px) 50%, calc(100% - 11px) 50%',
                          backgroundSize: '4px 4px, 4px 4px',
                          backgroundRepeat: 'no-repeat',
                          paddingRight: '30px',
                        }}
                      >
                        <option value="firm_owner">Firm Owner</option>
                        <option value="manager">Manager</option>
                        <option value="assigned_staff">Assigned Staff</option>
                        <option value="client">Client</option>
                      </select>
                      <p className={helperClass}>Assigned Staff means whoever the triggering item is assigned to.</p>
                    </div>

                    {/* Urgency segmented toggle */}
                    <div className="mb-[17px]">
                      <label className={labelClass}>How urgent is this?</label>
                      <div
                        role="group"
                        aria-label="Notification urgency"
                        className="grid gap-[3px] p-[3px] rounded-[7px] bg-white dark:bg-[#252525]"
                        style={{ gridTemplateColumns: '1fr 1fr', border: '0.5px solid #C8CDD6' }}
                      >
                        {(['loud', 'quiet'] as const).map((t) => (
                          <button
                            key={t}
                            type="button"
                            aria-pressed={tier === t}
                            onClick={() => updateConfig(i, 'tier', t)}
                            className={[
                              'min-h-[34px] px-[9px] py-[6px] rounded-[5px] text-[11px] font-[600] transition-colors',
                              tier === t
                                ? 'bg-[#1F3148] text-white'
                                : 'bg-transparent text-[#1F3148] dark:text-[#EDEEF0]',
                            ].join(' ')}
                          >
                            {t === 'loud' ? 'Notify right away' : 'Save to list'}
                          </button>
                        ))}
                      </div>

                      {/* Live preview */}
                      <div
                        className="mt-[10px] p-[11px] rounded-[7px] bg-[#FAFAFB] dark:bg-[#2D2D2D]"
                        style={{ border: '0.5px solid #C8CDD6' }}
                      >
                        <p className="mb-[8px] text-[10px] font-[650] uppercase tracking-[0.04em] text-[#6B7280] dark:text-[#AEB4BE]">Live preview</p>
                        <div
                          className="relative min-h-[164px] rounded-[6px] bg-white dark:bg-[#252525] overflow-hidden"
                          style={{ border: '0.5px solid #C8CDD6' }}
                        >
                          <div
                            className="h-[26px] flex items-center gap-[5px] px-[9px]"
                            style={{ borderBottom: '0.5px solid #C8CDD6', background: '#F7F7F8' }}
                            aria-hidden="true"
                          >
                            {(['#D56A63','#D7A64A','#6E9E73'] as const).map((bg, idx) => (
                              <span key={idx} className="w-[7px] h-[7px] rounded-full flex-shrink-0" style={{ background: bg }} />
                            ))}
                          </div>
                          {tier === 'loud' ? (
                            <>
                              <div className="p-[12px]">
                                {[82,62,38].map((w,idx) => (
                                  <div key={idx} className="h-[6px] rounded-[5px] bg-[#E7E9ED] mb-[8px]" style={{ width: `${w}%` }} />
                                ))}
                              </div>
                              <div
                                className="absolute right-[10px] bottom-[10px] p-[9px_10px_10px] rounded-[7px] bg-white dark:bg-[#2D2D2D]"
                                style={{ width: 'min(260px,calc(100% - 20px))', border: '0.5px solid #C8CDD6', borderLeft: '3px solid #B07D3A', boxShadow: '0 8px 22px rgba(31,49,72,.12)' }}
                              >
                                <p className="mb-[6px] text-[10px] text-[#6B7280]">Just now</p>
                                <div className="flex items-start gap-[8px]">
                                  <div className="w-[24px] h-[24px] flex items-center justify-center rounded-[6px] bg-[#F7F7F8] dark:bg-[#252525] flex-shrink-0">
                                    <svg viewBox="0 0 24 24" fill="none" stroke="#B07D3A" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" className="w-[14px] h-[14px]" aria-hidden="true"><path d="M18 8a6 6 0 0 0-12 0c0 7-3 7-3 9h18c0-2-3-2-3-9"/><path d="M13.7 21a2 2 0 0 1-3.4 0"/></svg>
                                  </div>
                                  <div className="min-w-0">
                                    <p className="text-[12px] font-[700] leading-[1.3] text-[#1F3148] dark:text-[#EDEEF0] break-words">{previewTitle}</p>
                                    <p className="text-[11px] leading-[1.4] text-[#6B7280] dark:text-[#AEB4BE] break-words">{previewBody}</p>
                                  </div>
                                </div>
                              </div>
                            </>
                          ) : (
                            <>
                              <div className="flex justify-end px-[12px] pt-[12px]">
                                <div className="relative w-[30px] h-[30px] flex items-center justify-center rounded-full bg-white dark:bg-[#2D2D2D]" style={{ border: '0.5px solid #C8CDD6' }}>
                                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" className="w-[15px] h-[15px] text-[#1F3148] dark:text-[#EDEEF0]" aria-hidden="true"><path d="M18 8a6 6 0 0 0-12 0c0 7-3 7-3 9h18c0-2-3-2-3-9"/><path d="M13.7 21a2 2 0 0 1-3.4 0"/></svg>
                                  <span className="absolute -top-[4px] -right-[3px] min-w-[15px] h-[15px] px-[4px] flex items-center justify-center rounded-full bg-[#B07D3A] text-white text-[9px] font-[700]" style={{ border: '2px solid white' }}>1</span>
                                </div>
                              </div>
                              <div className="mx-[12px] mb-[12px] rounded-[7px] bg-white dark:bg-[#2D2D2D] overflow-hidden" style={{ border: '0.5px solid #C8CDD6', boxShadow: '0 8px 22px rgba(31,49,72,.10)' }}>
                                <div className="px-[11px] py-[9px] text-[11px] font-[700] text-[#1F3148] dark:text-[#EDEEF0]" style={{ borderBottom: '0.5px solid #C8CDD6' }}>Notifications</div>
                                <div className="flex gap-[9px] items-start px-[11px] py-[10px]">
                                  <div className="w-[24px] h-[24px] flex items-center justify-center rounded-[6px] bg-[#F7F7F8] dark:bg-[#252525] flex-shrink-0">
                                    <svg viewBox="0 0 24 24" fill="none" stroke="#B07D3A" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" className="w-[14px] h-[14px]" aria-hidden="true"><path d="M18 8a6 6 0 0 0-12 0c0 7-3 7-3 9h18c0-2-3-2-3-9"/><path d="M13.7 21a2 2 0 0 1-3.4 0"/></svg>
                                  </div>
                                  <div className="min-w-0">
                                    <p className="text-[12px] font-[700] leading-[1.3] text-[#1F3148] dark:text-[#EDEEF0] break-words">{previewTitle}</p>
                                    <p className="text-[11px] leading-[1.4] text-[#6B7280] dark:text-[#AEB4BE] break-words">{previewBody}</p>
                                  </div>
                                </div>
                              </div>
                            </>
                          )}
                        </div>
                        <p className="mt-[8px] text-[11px] leading-[1.45] text-[#6B7280] dark:text-[#AEB4BE]">
                          {tier === 'loud'
                            ? "This will pop up immediately, interrupting whatever they're doing."
                            : "This will appear in their notification list to check when they're ready. No interruption."}
                        </p>
                      </div>
                    </div>

                    {/* Notification title */}
                    <div className="mb-[17px]">
                      <label className={labelClass}>Notification title</label>
                      <input
                        type="text"
                        maxLength={200}
                        placeholder="e.g. Engagement deadline approaching"
                        value={notifTitle}
                        onChange={(e) => updateConfig(i, 'title', e.target.value)}
                        className={inputClass}
                      />
                    </div>

                    {/* Notification message */}
                    <div>
                      <label className={labelClass}>Notification message</label>
                      <textarea
                        rows={4}
                        maxLength={1000}
                        placeholder="e.g. {{client_name}}'s {{engagement_type}} is due in 3 days."
                        value={notifBody}
                        onChange={(e) => updateConfig(i, 'body', e.target.value)}
                        className={`${inputClass} h-auto py-2 resize-none`}
                      />
                      <p className={helperClass}>You can use merge fields like client name and engagement type. They'll be filled in automatically when this fires.</p>
                    </div>
                  </div>
                )
              })}
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

// frontend/src/lib/events/conciergeEvents.ts

const CONCIERGE_ACTION_EVENT = 'jamm:concierge-action'

export interface ConciergeAction {
  type: 'navigate' | 'open-modal' | 'navigate-and-open' | 'set_firm_type' | 'prefill-message' | 'show_briefing_again'
  route?: string
  modal?: string
  prefill?: Record<string, string>
  firm_type?: string
  prefillMessage?: string
}

export function emitConciergeAction(action: ConciergeAction) {
  window.dispatchEvent(new CustomEvent(CONCIERGE_ACTION_EVENT, { detail: action }))
}

export function onConciergeAction(handler: (action: ConciergeAction) => void): () => void {
  const listener = (e: Event) => handler((e as CustomEvent<ConciergeAction>).detail)
  window.addEventListener(CONCIERGE_ACTION_EVENT, listener)
  return () => window.removeEventListener(CONCIERGE_ACTION_EVENT, listener)
}

export function setFormDirty(dirty: boolean) {
  window.dispatchEvent(new CustomEvent('jamm:form-dirty', { detail: { dirty } }))
}

// frontend/src/lib/events/conciergeEvents.ts

const CONCIERGE_ACTION_EVENT = 'jamm:concierge-action'

export interface ConciergeAction {
  type: 'navigate' | 'open-modal' | 'navigate-and-open'
  route?: string
  modal?: string
  prefill?: Record<string, string>
}

export function emitConciergeAction(action: ConciergeAction) {
  window.dispatchEvent(new CustomEvent(CONCIERGE_ACTION_EVENT, { detail: action }))
}

export function onConciergeAction(handler: (action: ConciergeAction) => void): () => void {
  const listener = (e: Event) => handler((e as CustomEvent<ConciergeAction>).detail)
  window.addEventListener(CONCIERGE_ACTION_EVENT, listener)
  return () => window.removeEventListener(CONCIERGE_ACTION_EVENT, listener)
}

// Module-level dirty-form flag. Form components call setFormDirty(true) when
// they have unsaved input and setFormDirty(false) on save or reset.
let _formDirty = false

export function setFormDirty(dirty: boolean) {
  _formDirty = dirty
  window.dispatchEvent(new CustomEvent('jamm:form-dirty', { detail: { dirty } }))
}

export function isFormDirty(): boolean {
  return _formDirty
}

// frontend/src/lib/events/conciergeEvents.ts

export interface ConciergeAction {
  type: 'navigate' | 'open_modal' | 'prefill'
  route?: string
  modal?: string
  fields?: Record<string, string>
}

const EVENT_NAME = 'concierge:action'

// Module-level dirty-form flag. Form components can call setFormDirty(true)
// when they have unsaved input and setFormDirty(false) on save or reset.
let _formDirty = false

export function setFormDirty(dirty: boolean): void {
  _formDirty = dirty
}

export function isFormDirty(): boolean {
  return _formDirty
}

export function emitConciergeAction(action: ConciergeAction): void {
  if (typeof window === 'undefined') return
  window.dispatchEvent(new CustomEvent(EVENT_NAME, { detail: action }))
}

/** Register a handler and return the cleanup function. */
export function onConciergeAction(
  handler: (action: ConciergeAction) => void,
): () => void {
  const listener = (e: Event) => {
    handler((e as CustomEvent<ConciergeAction>).detail)
  }
  window.addEventListener(EVENT_NAME, listener)
  return () => window.removeEventListener(EVENT_NAME, listener)
}

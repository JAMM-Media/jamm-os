# TASK — Two small fixes: portal engagement badge colors + text color pickers

## FIX 1 — EngagementBadge in PortalTodo
FILE: frontend/src/components/portal/PortalTodo.tsx

Find the EngagementBadge function and replace the entire getStyle switch with:

```tsx
  const getStyle = (): React.CSSProperties => {
    switch (status) {
      case 'active':
        return { backgroundColor: accentColor + '33', color: accentColor, border: `1px solid ${accentColor}66` }
      case 'in_progress':
        return { backgroundColor: accentColor + '33', color: accentColor, border: `1px solid ${accentColor}66` }
      case 'in_review':
        return { backgroundColor: '#DBEAFE', color: '#1E40AF' }
      case 'completed':
        return { backgroundColor: '#D1FAE5', color: '#065F46' }
      case 'overdue':
      case 'blocked':
        return { backgroundColor: '#FEE2E2', color: '#991B1B' }
      case 'awaiting_docs':
        return { backgroundColor: '#FEF3C7', color: '#92400E' }
      case 'planning':
      case 'draft':
      case 'archived':
      case 'cancelled':
      case 'not_started':
      default:
        return { backgroundColor: '#E5E7EB', color: '#1F3148', border: '0.5px solid #1F3148' }
    }
  }
```

---

## FIX 2 — Add text color pickers to portal branding
FILE: frontend/src/components/settings/PortalBrandingTab.tsx

### 2A — Add text_primary and text_muted to ColorSet interface:
```tsx
  text_primary: string
  text_muted: string
```

### 2B — Add to DARK_DEFAULTS:
```tsx
  text_primary: '#EDEEF0',
  text_muted: '#9CA3AF',
```

### 2C — Add to LIGHT_DEFAULTS:
```tsx
  text_primary: '#1F3148',
  text_muted: '#6B7280',
```

### 2D — Add to COLOR_LABELS after card:
```tsx
  { key: 'text_primary', label: 'Primary text' },
  { key: 'text_muted', label: 'Secondary text' },
```

---

## FIX 3 — Add text colors to portal_me backend
FILE: app/api/portal.py

In dark_defaults add:
```python
        "text_primary": "#EDEEF0",
        "text_muted": "#9CA3AF",
```

In light_defaults add:
```python
        "text_primary": "#1F3148",
        "text_muted": "#6B7280",
```

In the return dict add after portal_card_color:
```python
        "portal_text_primary": colors["text_primary"],
        "portal_text_muted": colors["text_muted"],
```

---

## FIX 4 — Pass text colors through portal page and components
FILE: frontend/src/app/portal/page.tsx

Add to PortalMe interface:
```tsx
  portal_text_primary: string
  portal_text_muted: string
```

Pass to all five tab components:
```tsx
textPrimary={me.portal_text_primary}
textMuted={me.portal_text_muted}
```

---

## FIX 5 — Consume textPrimary and textMuted in each portal component

For each of the five components (PortalTodo, PortalDocuments, PortalInvoices, PortalMessages, PortalOrganizer):

Add `textPrimary?: string` and `textMuted?: string` to the props interface.

Add to destructuring with defaults matching the dark mode values:
- `textPrimary = '#EDEEF0'`
- `textMuted = '#9CA3AF'`

Replace the derived variables at the top of each function body:
```tsx
  const primaryText = textPrimary
  const mutedText = textMuted
```

This replaces the current `portalMode === 'light' ? ... : ...` derivation — the component no longer needs to calculate text colors itself, it just uses what it receives. The `portalMode` prop can stay for other purposes (like the PaymentForm isDark check in PortalInvoices) but text color derivation moves to the parent.

Do NOT remove the portalMode prop from any component — it's still used for isDark in PortalInvoices and getInputClass in PortalOrganizer.

## VERIFICATION
1. Planning/Archived/Draft badges show grey with border
2. Active badge shows semi-transparent accent color
3. In Review badge shows blue (#DBEAFE / #1E40AF) — fixed semantic color
4. Completed badge stays green
5. Overdue/Blocked badge stays red
6. Settings → Portal shows text_primary and text_muted color pickers in both dark and light sections
7. Text colors in portal components come from props, not derived from portalMode
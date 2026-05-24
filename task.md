# TASK — Three small fixes

## FIX 1 — Light mode primary text default to black
FILE: frontend/src/components/settings/PortalBrandingTab.tsx

Find LIGHT_DEFAULTS and change:
```
  text_primary: '#1F3148',
```
To:
```
  text_primary: '#111111',
```

FILE: app/api/portal.py

Find light_defaults and change:
```python
        "text_primary": "#1F3148",
```
To:
```python
        "text_primary": "#111111",
```

---

## FIX 2 — Status badge colors in EngagementBadge
FILE: frontend/src/components/portal/PortalTodo.tsx

Find the getStyle switch in EngagementBadge. Replace the entire switch body with:

```tsx
    switch (status) {
      case 'active':
        return { backgroundColor: accentColor, color: '#FFFFFF' }
      case 'in_progress':
        return { backgroundColor: accentColor, color: '#FFFFFF' }
      case 'in_review':
        return { backgroundColor: '#FEF3C7', color: '#92400E' }
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
```

No other changes.
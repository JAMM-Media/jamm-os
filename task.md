# JAMM PX — Task Batch

Read every instruction in this file before writing a single line of code. Execute in the order listed. Do not skip steps or reorder them.

---

## STANDING RULES

- Backend: FastAPI, PostgreSQL, SQLAlchemy ORM 2.0, Pydantic v2. Never deviate from existing patterns.
- Frontend: Next.js 14 App Router, TypeScript always, Tailwind CSS, shadcn/ui.
- Every file must begin with its path comment.
- Never touch files not listed in a task's scope.
- Never add new npm or pip packages unless explicitly instructed.

---

## TASK 1 — Fix invoice ResponseValidationError: make LineItemSchema.total optional with fallback

**File to edit:** `app/schemas/invoice.py`

**Problem:** Some line items stored in the database JSON column were saved without a `total` field — they have `description`, `quantity`, `unit_price`, and `amount` but no `total`. When the `InvoiceOut` schema tries to serialize them, `LineItemSchema` requires `total: Decimal` and throws a `ResponseValidationError`.

**Fix:** Make `total` optional in `LineItemSchema` and add a validator that computes it from `quantity * unit_price` if missing, or falls back to `amount` if present:

Find `LineItemSchema` and replace it with:

```python
class LineItemSchema(BaseModel):
    description: str
    quantity: Decimal
    unit_price: Decimal
    amount: Optional[Decimal] = None
    total: Optional[Decimal] = None

    @field_validator('total', mode='before')
    @classmethod
    def coerce_total(cls, v, info):
        if v is not None:
            return v
        # Try to compute from quantity * unit_price
        data = info.data
        qty = data.get('quantity')
        price = data.get('unit_price')
        if qty is not None and price is not None:
            return qty * price
        # Fall back to amount field
        amt = data.get('amount')
        if amt is not None:
            return amt
        return Decimal('0')
```

Make sure `Optional` is imported from `typing` at the top of the file — check the existing imports before adding it.

No migration required. No frontend changes required.

---

## TASK 2 — @mention rendering: display name only, drop the @ symbol

**Problem:** `match[0]` captures the full `@Name` string including the `@`. Industry standard (Slack, Teams, Discord) is to display just the name in bold, no `@` symbol in the rendered output. The `@` stays in the stored body text — it just doesn't render visually.

The fix is changing `{match[0]}` to `{match[1]}` in the rendered span. `match[1]` is the first capture group — the name part without the `@`.

### 2A — Firm chat renderBody

**File to edit:** `frontend/src/app/(dashboard)/firm-chat/page.tsx`

In the `renderBody` function there are two branches that render a mention span. Both currently have:
```tsx
<span key={match.index} className="font-semibold text-[#1F3148] dark:text-[#EDEEF0]">
  {match[0]}
</span>
```

Change both to:
```tsx
<span key={match.index} className="font-semibold text-[#1F3148] dark:text-[#EDEEF0]">
  {match[1]}
</span>
```

The first branch uses regex `/@(\S+)/g` (fallback when no staffMap). The second branch uses the named-staff pattern. Both use `match[1]` after this change. No other changes to this function.

### 2B — Notes renderNoteBody

**File to edit:** `frontend/src/components/notes/NotesPanel.tsx`

In the `renderNoteBody` function, the mention span currently has:
```tsx
<span key={match.index} className="font-semibold text-[#1F3148] dark:text-[#EDEEF0]">
  {match[0]}
</span>
```

Change it to:
```tsx
<span key={match.index} className="font-semibold text-[#1F3148] dark:text-[#EDEEF0]">
  {match[1]}
</span>
```

The regex in `renderNoteBody` is `/@(\S+(?:\s\S+)?)/g` — `match[1]` is the name without the `@`. No other changes to this function.

---

## EXECUTION ORDER

1. Task 1 — backend: app/schemas/invoice.py
2. Task 2A — frontend: firm-chat/page.tsx
3. Task 2B — frontend: notes/NotesPanel.tsx

After all tasks: report every file modified and confirm no TypeScript errors.

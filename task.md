# TASK — Portal light mode text colors, status badges, and message compose

## OVERVIEW
Five fixes:
1. Add portalMode prop to all portal components so text adapts light/dark
2. Fix hardcoded dark text colors in PortalTodo, PortalDocuments, PortalInvoices, PortalMessages, PortalOrganizer
3. Fix status badge colors so they work in both modes
4. Fix message compose box to use cardColor and accentColor
5. Pass portalMode from portal/page.tsx to all components

---

## PART 1 — Pass portalMode from portal/page.tsx
FILE: frontend/src/app/portal/page.tsx

Add `portal_mode: 'light' | 'dark'` to PortalMe interface if not already there.

Update every tab component to also receive portalMode:
- `<PortalTodo ... portalMode={me.portal_mode} />`
- `<PortalDocuments ... portalMode={me.portal_mode} />`
- `<PortalInvoices ... portalMode={me.portal_mode} />`
- `<PortalMessages ... portalMode={me.portal_mode} />`
- `<PortalOrganizer ... portalMode={me.portal_mode} />`

---

## PART 2 — Update PortalTodo
FILE: frontend/src/components/portal/PortalTodo.tsx

### 2A — Add portalMode prop
Add `portalMode?: 'light' | 'dark'` to PortalTodoProps.
Add `portalMode = 'dark'` to destructuring.

### 2B — Derive text color variables at the top of PortalTodo function body:
```tsx
  const primaryText = portalMode === 'light' ? '#1F3148' : '#EDEEF0'
  const mutedText = portalMode === 'light' ? '#6B7280' : '#9CA3AF'
  const iconColor = portalMode === 'light' ? '#6B7280' : '#9CA3AF'
```

### 2C — Pass primaryText, mutedText, iconColor to ActionCard:
Update ActionCard signature:
```tsx
function ActionCard({ item, accentColor, cardColor, primaryText, mutedText, iconColor }: {
  item: ActionItem
  accentColor: string
  cardColor: string
  primaryText: string
  mutedText: string
  iconColor: string
}) {
```

Update all ActionCard usages to pass these three new props.

### 2D — Update ActionCard text colors:
Replace:
```tsx
          <p className="text-[14px] font-medium text-[#EDEEF0] leading-tight">{item.title}</p>
          <p className="text-[13px] text-[#9CA3AF] mt-0.5 leading-snug">{item.description}</p>
```
With:
```tsx
          <p className="text-[14px] font-medium leading-tight" style={{ color: primaryText }}>{item.title}</p>
          <p className="text-[13px] mt-0.5 leading-snug" style={{ color: mutedText }}>{item.description}</p>
```

Replace the due date line:
```tsx
            <p className="text-[13px] text-[#9CA3AF] mt-1">Due {item.dueDate}</p>
```
With:
```tsx
            <p className="text-[13px] mt-1" style={{ color: mutedText }}>Due {item.dueDate}</p>
```

Update getIcon to accept and use iconColor:
```tsx
function getIcon(type: ActionItem['type'], iconColor: string) {
  if (type === 'document-request') return <FileUp className="h-5 w-5" style={{ color: iconColor }} />
  if (type === 'signature') return <PenLine className="h-5 w-5" style={{ color: iconColor }} />
  return <CreditCard className="h-5 w-5" style={{ color: iconColor }} />
}
```
Update the getIcon call in ActionCard to pass iconColor.

### 2E — Fix status badge colors
Replace the entire STATUS_COLORS constant and EngagementBadge function with:

```tsx
function EngagementBadge({ status, accentColor }: { status: string; accentColor: string }) {
  // Semantic color mapping — works in both light and dark modes
  const getStyle = (): React.CSSProperties => {
    switch (status) {
      case 'active':
      case 'in_progress':
        return { backgroundColor: accentColor + '33', color: accentColor, border: `1px solid ${accentColor}66` }
      case 'completed':
        return { backgroundColor: '#D1FAE5', color: '#065F46' }
      case 'overdue':
      case 'blocked':
        return { backgroundColor: '#FEE2E2', color: '#991B1B' }
      case 'planning':
      case 'draft':
      case 'pending':
      default:
        return { backgroundColor: accentColor + '22', color: accentColor, border: `1px solid ${accentColor}44` }
    }
  }
  return (
    <span
      className="text-[10px] font-medium px-1.5 py-0.5 rounded-[4px] capitalize"
      style={getStyle()}
    >
      {status.replace(/_/g, ' ')}
    </span>
  )
}
```

Update EngagementBadge usage to pass accentColor:
```tsx
<EngagementBadge status={eng.status} accentColor={accentColor} />
```

Also update engagement name text color. Find:
```tsx
                  <p className="text-[14px] font-medium text-[#EDEEF0]">{eng.name}</p>
```
Replace with:
```tsx
                  <p className="text-[14px] font-medium" style={{ color: primaryText }}>{eng.name}</p>
```

Also fix the greeting and count text. Find:
```tsx
        <p className="text-[18px] font-medium text-[#EDEEF0]">Hello, {clientFirstName}</p>
        <p className="text-[14px] text-[#9CA3AF] mt-0.5">
```
Replace with:
```tsx
        <p className="text-[18px] font-medium" style={{ color: primaryText }}>Hello, {clientFirstName}</p>
        <p className="text-[14px] mt-0.5" style={{ color: mutedText }}>
```

Fix the section labels. Find:
```tsx
          <p className="text-[12px] font-medium text-[#9CA3AF] uppercase tracking-[0.05em] mb-2">
            Action needed
          </p>
```
Replace with:
```tsx
          <p className="text-[12px] font-medium uppercase tracking-[0.05em] mb-2" style={{ color: mutedText }}>
            Action needed
          </p>
```
Do the same for the "Active engagements" section label.

---

## PART 3 — Update PortalDocuments
FILE: frontend/src/components/portal/PortalDocuments.tsx

Add `portalMode?: 'light' | 'dark'` to PortalDocumentsProps with default `'dark'`.

At top of function body add:
```tsx
  const primaryText = portalMode === 'light' ? '#1F3148' : '#EDEEF0'
  const mutedText = portalMode === 'light' ? '#6B7280' : '#9CA3AF'
```

Replace hardcoded text colors in document rows:
- `text-[#EDEEF0]` → `style={{ color: primaryText }}`
- `text-[#9CA3AF]` → `style={{ color: mutedText }}`

Also find the "Documents (N)" section label and update its text color to mutedText.

---

## PART 4 — Update PortalMessages
FILE: frontend/src/components/portal/PortalMessages.tsx

Add `portalMode?: 'light' | 'dark'` to PortalMessagesProps with default `'dark'`.

At top of function body add:
```tsx
  const primaryText = portalMode === 'light' ? '#1F3148' : '#EDEEF0'
  const mutedText = portalMode === 'light' ? '#6B7280' : '#9CA3AF'
  const borderColor = portalMode === 'light' ? '#C8CDD6' : '#383838'
  const inputBorder = portalMode === 'light' ? '#C8CDD6' : '#484848'
  const inputFocusBorder = portalMode === 'light' ? '#1F3148' : '#3A6A94'
```

Fix message text. Find:
```tsx
                <p className="text-[13px] text-[#EDEEF0] leading-relaxed">{msg.body}</p>
```
Replace with:
```tsx
                <p className="text-[13px] leading-relaxed" style={{ color: primaryText }}>{msg.body}</p>
```

Fix timestamp text from `text-[#9CA3AF]` to inline style with mutedText.

Fix "No messages yet" text from `text-[#9CA3AF]` to mutedText.

Fix compose box — find the border-t div and the textarea and send button:

Find:
```tsx
      <div className="border-t border-[#383838] p-4 max-w-2xl mx-auto w-full">
        <div className="flex items-end gap-2">
          <textarea
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Message your accountant..."
            rows={2}
            className="flex-1 bg-[#383838] border border-[#484848] rounded-[6px] px-3 py-2 text-[13px] text-[#EDEEF0] placeholder:text-[#6B7280] resize-none focus:outline-none focus:border-[#3A6A94]"
          />
          <button
            onClick={handleSend}
            disabled={!draft.trim() || sending}
            className="h-9 w-9 rounded-[6px] bg-[#3A6A94] text-[#EDEEF0] flex items-center justify-center disabled:opacity-40 hover:opacity-90 transition-opacity flex-shrink-0"
          >
```

Replace with:
```tsx
      <div className="border-t p-4 max-w-2xl mx-auto w-full" style={{ borderColor }}>
        <div className="flex items-end gap-2">
          <textarea
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Message your accountant..."
            rows={2}
            className="flex-1 rounded-[6px] px-3 py-2 text-[13px] resize-none focus:outline-none"
            style={{
              backgroundColor: cardColor,
              border: `1px solid ${inputBorder}`,
              color: primaryText,
              outlineColor: inputFocusBorder,
            }}
          />
          <button
            onClick={handleSend}
            disabled={!draft.trim() || sending}
            className="h-9 w-9 rounded-[6px] flex items-center justify-center disabled:opacity-40 hover:opacity-90 transition-opacity flex-shrink-0"
            style={{ backgroundColor: accentColor, color: '#FFFFFF' }}
          >
```

---

## PART 5 — Update PortalOrganizer
FILE: frontend/src/components/portal/PortalOrganizer.tsx

Add `portalMode?: 'light' | 'dark'` to PortalOrganizerProps with default `'dark'`.

At top of function body add:
```tsx
  const primaryText = portalMode === 'light' ? '#1F3148' : '#EDEEF0'
  const mutedText = portalMode === 'light' ? '#6B7280' : '#9CA3AF'
```

Replace hardcoded `text-[#EDEEF0]` with `style={{ color: primaryText }}` and `text-[#9CA3AF]` with `style={{ color: mutedText }}` throughout the component.

Also update the hardcoded input field class. Find:
```tsx
  'w-full rounded-[6px] border border-[#484848] bg-[#2D2D2D] focus:border-[#4A7FA5] text-[#EDEEF0] text-[13px] px-3 py-2 outline-none transition-colors'
```
This is a constant — it can't use dynamic values directly. Replace it with a function that takes portalMode:
```tsx
function getInputClass(portalMode: 'light' | 'dark') {
  return portalMode === 'light'
    ? 'w-full rounded-[6px] border border-[#C8CDD6] bg-white focus:border-[#1F3148] text-[#1F3148] text-[13px] px-3 py-2 outline-none transition-colors'
    : 'w-full rounded-[6px] border border-[#484848] bg-[#2D2D2D] focus:border-[#4A7FA5] text-[#EDEEF0] text-[13px] px-3 py-2 outline-none transition-colors'
}
```
Replace all uses of the old constant with `getInputClass(portalMode)`.

---

## PART 6 — Update PortalInvoices for text colors
FILE: frontend/src/components/portal/PortalInvoices.tsx

Add `portalMode?: 'light' | 'dark'` to the PortalInvoices props with default `'dark'`.

At top of PortalInvoices function body add:
```tsx
  const primaryText = portalMode === 'light' ? '#1F3148' : '#EDEEF0'
  const mutedText = portalMode === 'light' ? '#6B7280' : '#9CA3AF'
```

Replace hardcoded `text-[#EDEEF0]` and `text-[#9CA3AF]` in invoice rows with inline styles.

Pass portalMode to PaymentForm as well. Add `portalMode?: 'light' | 'dark'` to PaymentFormProps and update the `isDark` derivation:
```tsx
  const isDark = portalMode !== 'light'
```

---

## VERIFICATION
1. Light mode portal shows dark text (#1F3148) on all cards and content areas
2. Planning/draft/pending badges use accent color with semi-transparent background
3. Completed badge stays green
4. Overdue/blocked badge is red
5. Message compose textarea uses cardColor background and primaryText
6. Send button uses accentColor
7. No TypeScript errors
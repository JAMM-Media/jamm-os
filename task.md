# TASK — Portal button colors, subtitle color, and color input UX fixes

## OVERVIEW
Four things to fix:
1. Portal action buttons use accentColor instead of hardcoded #3A6A94
2. "Client Portal" subtitle text uses a customizable color
3. Color hex text inputs in PortalBrandingTab don't re-render on every keystroke (fix cursor jump + auto-scroll)
4. Add portal_subtitle_color to both color sets in branding

---

## PART 1 — Add subtitle color to backend and branding

### 1A — Add portal_subtitle_color to portal_me defaults
FILE: app/api/portal.py

Find the dark_defaults and light_defaults dicts in portal_me. Add subtitle to each:

In dark_defaults add:
```python
        "subtitle": "#7DA3C4",
```

In light_defaults add:
```python
        "subtitle": "#7DA3C4",
```

In the return dict, add after portal_avatar_color:
```python
        "portal_subtitle_color": colors["subtitle"],
```

### 1B — Add subtitle to ColorSet interface and defaults
FILE: frontend/src/components/settings/PortalBrandingTab.tsx

Find the ColorSet interface and add:
```tsx
  subtitle: string
```

Find DARK_DEFAULTS and add:
```tsx
  subtitle: '#7DA3C4',
```

Find LIGHT_DEFAULTS and add:
```tsx
  subtitle: '#7DA3C4',
```

Find the COLOR_LABELS array and add after avatar:
```tsx
  { key: 'subtitle', label: 'Subtitle text ("Client Portal")' },
```

### 1C — Fix color hex inputs to use local state (prevents cursor jump and auto-scroll)
FILE: frontend/src/components/settings/PortalBrandingTab.tsx

The color text inputs currently call setColor on every onChange, causing re-renders that jump the cursor and auto-scroll. Fix by using onBlur instead of onChange for the text input, keeping a local display value.

Find the ColorSection function. Inside it, replace the color picker + text input pair mapping with:

```tsx
        {COLOR_LABELS.map(({ key, label }) => {
          const value = colors[key]
          return (
            <div key={key} className="flex items-center gap-3">
              <input
                type="color"
                value={VALID_HEX.test(value) ? value : '#1F3148'}
                onChange={(e) => setColor(mode, key, e.target.value)}
                className="w-8 h-8 rounded cursor-pointer border border-surface-border dark:border-dark-border p-0.5 flex-shrink-0"
              />
              <input
                type="text"
                defaultValue={value}
                key={`${mode}-${key}-${value}`}
                onBlur={(e) => {
                  const v = e.target.value.trim()
                  if (VALID_HEX.test(v)) setColor(mode, key, v)
                  else e.target.value = value
                }}
                maxLength={7}
                placeholder="#000000"
                className="w-28 rounded-[6px] border border-surface-border dark:border-dark-border bg-surface-page dark:bg-dark-page text-[12px] text-brand dark:text-[#EDEEF0] px-2 py-1 focus:outline-none focus:ring-1 focus:ring-brand"
              />
              <span className="text-[12px] text-[#6B7280]">{label}</span>
            </div>
          )
        })}
```

The `key={`${mode}-${key}-${value}`}` forces a reset of the input only when the value changes from the color picker, not on every keystroke. The `onBlur` validates and commits on blur. This eliminates all cursor jump and auto-scroll issues.

---

## PART 2 — Pass accentColor and subtitleColor through the portal page
FILE: frontend/src/app/portal/page.tsx

### 2A — Add subtitle_color to PortalMe interface:
Find the PortalMe interface and add:
```tsx
  portal_subtitle_color: string
```

### 2B — Pass accentColor and subtitleColor to all portal tab components:

Find where PortalTodo, PortalDocuments, and PortalInvoices are rendered (inside the PortalShell children). Update each one to pass accentColor:

Find:
```tsx
          <PortalTodo clientFirstName={firstName} />
```
Replace with:
```tsx
          <PortalTodo clientFirstName={firstName} accentColor={me.portal_accent_color} />
```

Find:
```tsx
          <PortalDocuments firmName={me.portal_display_name || me.firm_name} />
```
Replace with:
```tsx
          <PortalDocuments firmName={me.portal_display_name || me.firm_name} accentColor={me.portal_accent_color} />
```

Find the PortalInvoices usage and add accentColor prop:
```tsx
          <PortalInvoices accentColor={me.portal_accent_color} />
```

### 2C — Pass subtitleColor to PortalShell:

Find the PortalShell usage and add:
```tsx
      subtitleColor={me.portal_subtitle_color}
```

---

## PART 3 — Update PortalShell to use subtitleColor
FILE: frontend/src/components/portal/PortalShell.tsx

### 3A — Add subtitleColor to interface:
```tsx
  subtitleColor?: string
```

### 3B — Add to destructuring with default:
```tsx
  subtitleColor = '#7DA3C4',
```

### 3C — Update the "Client Portal" span to use subtitleColor:
Find:
```tsx
          <span className="text-[10px]" style={{ color: '#7DA3C4' }}>Client Portal</span>
```
Replace with:
```tsx
          <span className="text-[10px]" style={{ color: subtitleColor }}>Client Portal</span>
```

---

## PART 4 — Update PortalTodo to use accentColor
FILE: frontend/src/components/portal/PortalTodo.tsx

### 4A — Add accentColor prop to PortalTodoProps:
Find:
```tsx
interface PortalTodoProps {
  clientFirstName: string
}
```
Replace with:
```tsx
interface PortalTodoProps {
  clientFirstName: string
  accentColor?: string
}
```

### 4B — Destructure accentColor:
Find:
```tsx
export function PortalTodo({ clientFirstName }: PortalTodoProps) {
```
Replace with:
```tsx
export function PortalTodo({ clientFirstName, accentColor = '#3A6A94' }: PortalTodoProps) {
```

### 4C — Pass accentColor to ActionCard:
Find the ActionCard function definition:
```tsx
function ActionCard({ item }: { item: ActionItem }) {
```
Replace with:
```tsx
function ActionCard({ item, accentColor }: { item: ActionItem; accentColor: string }) {
```

### 4D — Update the action button in ActionCard to use accentColor:
Find:
```tsx
        <button className="flex-shrink-0 h-10 px-4 rounded-[6px] bg-[#3A6A94] text-[#EDEEF0] text-[13px] font-medium hover:opacity-90 transition-opacity whitespace-nowrap">
```
Replace with:
```tsx
        <button
          className="flex-shrink-0 h-10 px-4 rounded-[6px] text-white text-[13px] font-medium hover:opacity-90 transition-opacity whitespace-nowrap"
          style={{ backgroundColor: accentColor }}
        >
```

### 4E — Pass accentColor to ActionCard in the map:
Find:
```tsx
            {active.map((item) => (
              <ActionCard key={item.id} item={item} />
            ))}
```
Replace with:
```tsx
            {active.map((item) => (
              <ActionCard key={item.id} item={item} accentColor={accentColor} />
            ))}
```

---

## PART 5 — Update PortalDocuments to use accentColor
FILE: frontend/src/components/portal/PortalDocuments.tsx

### 5A — Add accentColor to PortalDocumentsProps:
Find:
```tsx
interface PortalDocumentsProps {
  firmName: string
}
```
Replace with:
```tsx
interface PortalDocumentsProps {
  firmName: string
  accentColor?: string
}
```

### 5B — Destructure:
Find:
```tsx
export function PortalDocuments({ firmName }: PortalDocumentsProps) {
```
Replace with:
```tsx
export function PortalDocuments({ firmName, accentColor = '#3A6A94' }: PortalDocumentsProps) {
```

### 5C — Update all buttons with hardcoded bg-[#3A6A94]:

There are two buttons in PortalDocuments with `bg-[#3A6A94]` — the Upload button and the Retry button. For each one:

Find:
```tsx
            className="h-8 px-4 rounded-[6px] bg-[#3A6A94] text-[#EDEEF0] text-[12px] font-medium hover:opacity-90 transition-opacity"
```
Replace with:
```tsx
            className="h-8 px-4 rounded-[6px] text-white text-[12px] font-medium hover:opacity-90 transition-opacity"
            style={{ backgroundColor: accentColor }}
```

Find:
```tsx
          className="flex items-center gap-1.5 h-8 px-3 rounded-[6px] bg-[#3A6A94] text-[#EDEEF0] text-[12px] font-medium hover:opacity-90 transition-opacity"
```
Replace with:
```tsx
          className="flex items-center gap-1.5 h-8 px-3 rounded-[6px] text-white text-[12px] font-medium hover:opacity-90 transition-opacity"
          style={{ backgroundColor: accentColor }}
```

---

## PART 6 — Update PortalInvoices to use accentColor
FILE: frontend/src/components/portal/PortalInvoices.tsx

### 6A — Find the PortalInvoices props interface and add accentColor:
Find the interface or function signature for PortalInvoices. Add:
```tsx
  accentColor?: string
```
And destructure with default `'#3A6A94'`.

### 6B — Find confirmBg variable in PaymentForm:
```tsx
  const confirmBg = isDark ? '#3A6A94' : '#1F3148'
```

PaymentForm is a child component — it needs accentColor passed as a prop too. Add accentColor to PaymentFormProps:
```tsx
interface PaymentFormProps {
  clientSecret: string
  onSuccess: () => void
  onCancel: () => void
  accentColor?: string
}
```

Update PaymentForm destructuring to include `accentColor = '#3A6A94'`.

Replace:
```tsx
  const confirmBg = isDark ? '#3A6A94' : '#1F3148'
```
With:
```tsx
  const confirmBg = accentColor
```

### 6C — Pass accentColor from PortalInvoices down to PaymentForm wherever it is rendered:
Find where PaymentForm is used inside PortalInvoices and add:
```tsx
  accentColor={accentColor}
```

### 6D — Find the Pay Now button in PortalInvoices (not PaymentForm) — it likely has bg-[#3A6A94] or similar. Replace with inline style using accentColor.

---

## PART 7 — Add subtitle color to branding mini preview
FILE: frontend/src/components/settings/PortalBrandingTab.tsx

In the ColorSection function, find the "Client Portal" span in the mini preview:
```tsx
              <span className="text-[9px]" style={{ color: '#7DA3C4' }}>Client Portal</span>
```
Replace with:
```tsx
              <span className="text-[9px]" style={{ color: VALID_HEX.test(colors.subtitle) ? colors.subtitle : '#7DA3C4' }}>Client Portal</span>
```

---

## VERIFICATION
1. Typing in hex color fields is smooth — no cursor jump, no auto-scroll
2. Color picker onChange still updates the preview immediately
3. Hex text field commits on blur, reverts to previous value if invalid hex entered
4. "Review & Sign", "Upload", "Retry", "Pay Now" buttons all use accentColor
5. "Client Portal" subtitle text uses subtitleColor prop
6. subtitleColor is customizable in both dark and light sections of Settings → Portal
7. No TypeScript errors
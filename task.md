# TASK — Portal card background color customization

## OVERVIEW
Add a `card` color to the portal ColorSet. This controls the background of action item cards, document rows, invoice rows, message bubbles, and organizer cards — everywhere #383838 is currently hardcoded.

Default dark card: #383838
Default light card: #EDEEF0

---

## PART 1 — Add card color to backend and branding

### 1A — Add card to portal_me defaults
FILE: app/api/portal.py

In dark_defaults add:
```python
        "card": "#383838",
```

In light_defaults add:
```python
        "card": "#EDEEF0",
```

In the return dict add after portal_subtitle_color:
```python
        "portal_card_color": colors["card"],
```

### 1B — Add card to ColorSet and defaults
FILE: frontend/src/components/settings/PortalBrandingTab.tsx

Add `card: string` to ColorSet interface.

Add `card: '#383838'` to DARK_DEFAULTS.
Add `card: '#EDEEF0'` to LIGHT_DEFAULTS.

Add to COLOR_LABELS after subtitle:
```tsx
  { key: 'card', label: 'Card / item background' },
```

Add to the mini preview in ColorSection — find the page background swatch div and add a card preview row above it:
```tsx
          <div className="px-3 py-2" style={{ backgroundColor: previewPage }}>
            <div className="rounded-[4px] px-3 py-2" style={{ backgroundColor: VALID_HEX.test(colors.card) ? colors.card : (mode === 'dark' ? '#383838' : '#EDEEF0') }}>
              <span className="text-[10px]" style={{ color: mode === 'light' ? '#1F3148' : '#EDEEF0' }}>Card item</span>
            </div>
          </div>
```
Replace the existing page background swatch div with this (it already shows page color as the outer wrapper).

---

## PART 2 — Pass cardColor through portal page
FILE: frontend/src/app/portal/page.tsx

Add to PortalMe interface:
```tsx
  portal_card_color: string
```

Pass to each portal component:
- PortalTodo: add `cardColor={me.portal_card_color}`
- PortalDocuments: add `cardColor={me.portal_card_color}`
- PortalInvoices: add `cardColor={me.portal_card_color}`
- PortalMessages: add `cardColor={me.portal_card_color}` (find the PortalMessages usage)
- PortalOrganizer: add `cardColor={me.portal_card_color}` (find the PortalOrganizer usage)

---

## PART 3 — Update PortalTodo
FILE: frontend/src/components/portal/PortalTodo.tsx

Add `cardColor?: string` to PortalTodoProps.
Add `cardColor = '#383838'` to destructuring.
Add `cardColor: string` to ActionCard props.
Pass `cardColor={cardColor}` to all ActionCard usages.

In ActionCard, replace:
```tsx
      className="flex items-center justify-between gap-4 bg-[#383838] rounded-[8px] px-5 py-4"
```
With:
```tsx
      className="flex items-center justify-between gap-4 rounded-[8px] px-5 py-4"
      style={{ backgroundColor: cardColor, opacity: item.completed ? 0.7 : 1 }}
```
Note: move the opacity from the style prop on the outer div into the same style object.

Also find the loading skeleton div with `bg-[#383838]` and replace with:
```tsx
          <div key={i} className="h-16 rounded-[8px] animate-pulse" style={{ backgroundColor: cardColor }} />
```

Find the engagement rows with `bg-[#383838]` and replace with inline style.

---

## PART 4 — Update PortalDocuments
FILE: frontend/src/components/portal/PortalDocuments.tsx

Add `cardColor?: string` to PortalDocumentsProps.
Add `cardColor = '#383838'` to destructuring.

Replace all instances of `bg-[#383838]` with `style={{ backgroundColor: cardColor }}` (removing the className bg reference). There are three: the error state div, the skeleton divs, and the document row divs.

---

## PART 5 — Update PortalInvoices
FILE: frontend/src/components/portal/PortalInvoices.tsx

Add `cardColor?: string` to the PortalInvoices props.
Add `cardColor = '#383838'` to destructuring.

Replace the `wrapperBg` variable in PaymentForm — it currently uses:
```tsx
  const wrapperBg = isDark ? '#2A2A2A' : '#F0F1F3'
```
Pass cardColor to PaymentForm as a prop and use it instead. Add `cardColor?: string` to PaymentFormProps and pass it from PortalInvoices.

Replace all `bg-[#383838]` in PortalInvoices with inline style={{ backgroundColor: cardColor }}.

---

## PART 6 — Update PortalMessages
FILE: frontend/src/components/portal/PortalMessages.tsx

Read the file first to understand its structure.

Add `cardColor?: string` to its props interface with default `'#383838'`.

Replace hardcoded `bg-[#383838]` on message bubbles (firm-side messages) with inline style. Client message bubbles use accentColor — check if accentColor is already a prop; if not add it too with default `'#3A6A94'`.

---

## PART 7 — Update PortalOrganizer
FILE: frontend/src/components/portal/PortalOrganizer.tsx

Read the file first.

Add `cardColor?: string` prop with default `'#383838'`.
Replace `bg-[#383838]` instances with inline style={{ backgroundColor: cardColor }}.

---

## VERIFICATION
1. Light mode portal shows light card backgrounds (#EDEEF0) on all action items, docs, invoices
2. Dark mode portal unchanged — still #383838
3. Customizing card color in Settings → Portal updates all cards
4. No TypeScript errors
5. Loading skeletons also use cardColor so they match
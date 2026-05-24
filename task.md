# TASK — Fix PortalBrandingTab: revert to correct types, fix toast import

FILE: frontend/src/components/settings/PortalBrandingTab.tsx

Read the full file first. There are two problems to fix:

## Problem 1 — Wrong event type on handleFileChange
The function uses React.FormEvent but should use React.ChangeEvent. Fix the signature and all the type casts.

Find:
```
  async function handleFileChange(e: React.FormEvent<HTMLInputElement>) {
    const file = (e.target as HTMLInputElement).files?.[0]
```
Replace with:
```
  async function handleFileChange(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0]
```

Find every instance of:
```
(e.target as HTMLInputElement).value = ''
```
Replace each with:
```
e.target.value = ''
```

Keep onInput={handleFileChange} on the input elements — do not change that back to onChange.

## Problem 2 — toast import conflict
The error "No constituent of type 'string | number' is callable" on toast.error means there is a naming conflict — something in the file is shadowing the `toast` import from sonner.

Look at the imports at the top of the file. There is likely both:
```
import { toast } from 'sonner'
```
and somewhere a variable or prop also named `toast`. 

Check if there is a local variable, state, or destructured value named `toast` anywhere in the component. If there is, rename it to avoid the conflict. The import from sonner must be the one that wins.

If no local variable named toast exists, check if the `toast` import itself got corrupted — delete and re-add:
```
import { toast } from 'sonner'
```

## Verification
After fixes:
- handleFileChange accepts React.ChangeEvent<HTMLInputElement>
- e.target.files and e.target.value work without type casts
- toast.error and toast.success calls compile without errors
- onInput={handleFileChange} remains on both file inputs
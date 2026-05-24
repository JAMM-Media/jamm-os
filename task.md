# TASK — Fix logo upload: switch from onChange to onInput

FILE: frontend/src/components/settings/PortalBrandingTab.tsx

Read the file first.

The handleFileChange function signature currently accepts React.ChangeEvent<HTMLInputElement>.
Change it to accept React.FormEvent<HTMLInputElement> since we are switching from onChange to onInput:

Find:
```
  async function handleFileChange(e: React.ChangeEvent<HTMLInputElement>) {
```
Replace with:
```
  async function handleFileChange(e: React.FormEvent<HTMLInputElement>) {
```

Now find every instance of:
```
onChange={handleFileChange}
```
Replace each one with:
```
onInput={handleFileChange}
```

There are two instances — one in the drop zone (no logo state) and one in the Replace button (logo exists state). Replace both.

No other changes. Do not touch anything else in the file.
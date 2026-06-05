Open frontend/src/app/clients/[id]/page.tsx.

Find the QBO AR balance card section. It renders a card that shows outstanding balance and last payment date, and displays "Not connected" when qboAr.connected is false.

Below the QBO AR balance card, add a new small card for manual QuickBooks link. Only render this card if the current user role is firm_owner or manager.

The card should:
- Show a label "QuickBooks Customer ID" in the standard muted label style
- Show the current client.quickbooks_customer_id value if set, or a muted "Not linked" placeholder if null
- Have a small edit icon button (pencil, 14px) next to the value that toggles an inline edit mode
- In edit mode: show a text input pre-filled with the current value, a Save button, and a Cancel button
- On save: call PATCH /clients/{clientId} with { quickbooks_customer_id: value } using the existing api client. On success show toast.success("QuickBooks ID linked") and refresh the client data. On error show toast.error.
- If the value is cleared and saved (empty string), send null to the backend to unlink

Add a qboEditMode boolean state and qboEditValue string state to manage this.

Run npx tsc --noEmit in the frontend directory and confirm it passes.
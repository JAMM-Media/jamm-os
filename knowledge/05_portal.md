## Portal > Overview > What the Client Portal Is

The client portal is a separate secure interface that clients use to upload documents, pay invoices, sign documents, send messages, and view their engagement status. It is distinct from the staff application. Clients never log into the staff side of JAMM PX.

The portal is accessible from any web browser on any device. It is optimized for mobile and can be added to a phone's home screen as an app. Each client has their own portal linked to their client record.

---

## Portal > Firm Side > Enabling Portal Access for a Client

Portal access is disabled by default for new clients. Enable it from the client record.

Navigate to Clients in the left sidebar and open the client record. Locate the Portal Access section. Enable portal access. Once enabled, the client can receive a magic link to log in.

Enabling portal access alone does not notify the client. You must also send them a magic link or invite for them to know their portal exists.

---

## Portal > Firm Side > Sending a Magic Link

A magic link is a one-time login link sent to the client by email. Clicking it logs the client directly into their portal without requiring a password.

Navigate to the client record and open the Portal Access section. Click Send Magic Link. JAMM PX emails the link to the client's email address on file. The link expires after a set number of hours.

Send a magic link when a client is logging in for the first time, when their previous link has expired, or when they say they cannot log in.

Magic links can only be sent by firm owners and managers. Staff cannot send magic links.

---

## Portal > Firm Side > Previewing the Client Portal

Any staff member can preview exactly what a client sees in their portal without logging in as the client.

Navigate to the client record and locate the Portal Access section. Click Preview Portal. JAMM PX generates a temporary access link and opens the portal in a new tab showing the client's exact view.

Use portal preview to troubleshoot client questions, to verify what documents and invoices are visible, and to coach clients through the portal experience.

---

## Portal > Firm Side > Revoking Portal Access

Revoking portal access disables the client's ability to log in and immediately ends any active portal sessions.

Navigate to the client record and open the Portal Access section. Click Revoke Access. The client is logged out immediately and cannot log back in until access is re-enabled and a new magic link is sent.

Revoke access when a client relationship ends, when a client account is compromised, or when you need to reset access and start fresh.

---

## Portal > Firm Side > Portal Branding Settings

The portal displays your firm name and can display your firm logo in the top bar. The portal color scheme is configurable.

Navigate to Settings and open the Portal Settings section. Upload a logo, set the portal display name, and configure the color theme. Changes apply to the portal for all clients immediately.

The default portal mode is dark. Firm owners can enable light mode as the default from portal settings. Individual clients can also toggle between light and dark mode from within their portal.

---

## Portal > Firm Side > What Clients Can See in the Portal

Clients can see the following information in their portal. The portal never exposes internal firm data, internal notes, staff assignments, billing rates, or other clients.

Document requests sent to them appear on the To-do tab and prompt them to upload files. Documents shared by the firm appear on the Documents tab. Invoices sent to them appear on the Invoices tab. Tax organizers sent to them appear on the Tax Organizer tab. Messages between the client and the firm appear on the Messages tab.

Engagement names and client-visible notes appear in the portal. Internal engagement notes never appear in the portal.

---

## Portal > Client Side > How a Client Logs In

A client logs into the portal using a magic link or with an email and password if they have set one.

The most common login method is the magic link. The client receives an email from their firm containing a link. Clicking the link opens the portal and logs them in automatically. No password is required to use a magic link.

After using a magic link, the client can set a password in their portal account settings if they prefer to log in with a password instead of requesting a new link each time.

---

## Portal > Client Side > The To-do Tab

The To-do tab is the first tab the client sees after logging in. It shows all items that need the client's attention.

Document requests appear here as action cards with an Upload button. The card shows the request title and due date if one was set. Clicking Upload opens the file picker for the client to select a file from their device.

Signature requests appear here as action cards with a Review and Sign button. Invoice payment requests appear here with a Pay Now button.

Completed items move to a completed section at the bottom of the To-do tab. Active engagements are also listed on this tab so the client can see the status of their work.

---

## Portal > Client Side > The Documents Tab

The Documents tab shows files that the firm has shared with the client. These are documents uploaded by the firm side, not files the client has uploaded.

Each document shows the file name, type, size, upload date, and whether it was uploaded by the firm or the client.

Older versions of documents that have been superseded are shown in a collapsed archived section at the bottom of the tab.

---

## Portal > Client Side > The Invoices Tab

The Invoices tab shows all invoices sent to the client. Each invoice shows the amount, due date, and payment status.

Clients can pay invoices directly from the portal using a credit or debit card through Stripe. Clicking Pay Now on an invoice opens the payment form. After a successful payment the invoice status updates to paid automatically.

---

## Portal > Client Side > The Messages Tab

The Messages tab is a direct message thread between the client and the firm. Clients can send messages and attach files. Firm staff can reply from the staff application.

An unread message badge appears on the Messages tab when the firm has sent a new message the client has not yet read.

---

## Portal > Client Side > The Tax Organizer Tab

The Tax Organizer tab shows tax organizer questionnaires sent by the firm. The client answers questions and submits the organizer from this tab. The firm receives the completed organizer in the staff application.

---

## Portal > Client Side > Setting a Portal Password

After logging in with a magic link, a client can set a password so they can log in with email and password in the future.

The client navigates to their portal settings by clicking their avatar or initials in the top right corner. They enter a new password and save it. After setting a password, they can log in at the portal login page using their email address and password without needing a new magic link.

---

## Portal > Common Failure Scenarios > Client Cannot Log In With Their Magic Link

If a client says their magic link is not working, there are three common causes.

The link has expired. Magic links expire after a set number of hours. Send a new magic link from the client record. Navigate to the client record, open Portal Access, and click Send Magic Link.

The client's portal access is disabled. Navigate to the client record and confirm portal access is enabled. If it is disabled, enable it and send a new magic link.

The client is clicking an old link from a previous email. Magic links are single-use. Once a link has been used or a new link has been generated, the old link no longer works. Send a fresh magic link and direct the client to use the most recent email.

---

## Portal > Common Failure Scenarios > Client Says They Are Not Seeing Their Documents or Invoices

If a client says they cannot find documents or invoices that you believe are there, confirm the following.

Documents shared by the firm appear on the Documents tab, not the To-do tab. If the client is looking at the To-do tab they will not see firm-shared documents there.

Invoices appear on the Invoices tab. Confirm the invoice has been sent and not left in draft status. A draft invoice is not visible to the client. The invoice status must be sent or overdue for the client to see it.

Document requests appear on the To-do tab as upload action items, not on the Documents tab.

---

## Portal > Common Failure Scenarios > Client Cannot Upload Their Documents

If a client says they cannot upload a file, there are three common causes.

The file type is not supported. Accepted types are PDF, Word documents, Excel files, PNG, and JPG. Ask the client to convert the file to a supported format and try again.

The client is on the Documents tab instead of the To-do tab. Document uploads for document requests happen from the To-do tab by clicking the Upload button on the request card. The Documents tab shows firm-shared files and does not currently support client uploads.

The client is using an unsupported browser or an old mobile browser. Ask the client to try Chrome or Safari on a recent version. If the issue persists, the client can email the files and the firm can upload them manually from the staff application.

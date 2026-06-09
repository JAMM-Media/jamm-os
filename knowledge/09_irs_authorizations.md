## IRS Authorizations > Overview > What IRS Authorizations Are

IRS authorizations are signed forms that give a tax firm legal permission to act on behalf of a client with the IRS. JAMM PX tracks two types of IRS authorization forms.

Form 8821 is a Tax Information Authorization. It allows the firm to receive IRS transcripts and account information on behalf of the client. Most tax engagements require an active 8821 before the firm can pull transcripts.

Form 2848 is a Power of Attorney. It allows the firm to represent the client before the IRS in audits, appeals, collections, and other proceedings.

A client can have both a Form 8821 and a Form 2848 on file at the same time. Each is tracked separately in JAMM PX.

IRS authorization records are visible to firm owners and managers only. Staff cannot view or create them.

---

## IRS Authorizations > Overview > Authorization Statuses

Each authorization record has one of four statuses.

Pending signature means the authorization form has been sent to the client for signing but has not been signed yet.

Active means the client has signed the form and the authorization is currently valid. An active authorization means the firm has legal permission to act within the scope of that form.

Expired means the authorization has passed its valid until date. An expired authorization no longer grants the firm permission to act. A new authorization must be obtained.

Revoked means the authorization has been cancelled before its expiry date, either by the client or by the firm.

---

## IRS Authorizations > Overview > Authorization Records on a Client

Open a client record and navigate to the IRS Authorizations section. JAMM PX shows whether the client has an active Form 8821 and an active Form 2848 on file, along with the tax years covered, the valid from date, and the valid until date.

If no active authorization exists for a form type, the indicator shows none on file.

---

## IRS Authorizations > Creating an Authorization > How to Send an Authorization for Signature

Navigate to the client record and open the IRS Authorizations section. Click Send Authorization. Select the form type, either 8821 or 2848. Enter the tax years the authorization should cover. Set the valid from and valid until dates if applicable. An 8821 can be set as indefinite with no expiry date.

JAMM PX generates a pre-filled PDF of the selected form and sends it to the client for e-signature through the existing signature envelope system. The authorization status is set to pending signature until the client signs.

---

## IRS Authorizations > Creating an Authorization > Tax Years Covered

When creating an authorization, enter the tax years the authorization should cover as a list. For example, an 8821 covering the 2022, 2023, and 2024 tax years would list all three.

Entering specific tax years limits the authorization to those years. If you need an open-ended authorization, use a broad date range and set no expiry. Consult IRS guidance on Form 8821 and 2848 instructions for the scope requirements relevant to each engagement.

---

## IRS Authorizations > Managing Authorizations > When an Authorization Is Signed

When the client signs the authorization through the client portal, JAMM PX receives a webhook from Dropbox Sign confirming the signature. The authorization status changes from pending signature to active automatically. The signed PDF is attached to the authorization record and stored under the client's documents.

No manual action is required from the firm after the client signs.

---

## IRS Authorizations > Managing Authorizations > Expiry Tracking and Alerts

JAMM PX monitors active authorizations for approaching expiry. When an authorization is nearing its valid until date, the IRS Authorization Expiry Warning automation preset fires. This preset sends a notification to staff, creates a task to renew the form, and sends an expiry warning email to the client.

The expiry notification fires once per authorization and does not repeat. Keep the IRS Authorization Expiry Warning preset enabled to ensure expiring authorizations are caught before they lapse.

When an authorization passes its valid until date without renewal, the status changes to expired automatically.

---

## IRS Authorizations > Managing Authorizations > Renewing an Expired Authorization

An expired authorization cannot be reactivated. Create a new authorization record for the client with updated tax years and validity dates. Send the new form for signature following the same process as the original authorization.

The expired record remains in the client's authorization history for reference. The new record replaces it as the active authorization once signed.

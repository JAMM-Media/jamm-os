## QuickBooks > Overview > What the QuickBooks Integration Does

JAMM PX connects to QuickBooks Online at the firm level. Once connected, JAMM PX can import clients from QuickBooks, link existing clients to their QuickBooks records, and surface QuickBooks financial data directly on client records inside JAMM PX.

The QuickBooks integration also powers the Budget Variance Alert automation preset, which creates a task when a client's actual spending deviates significantly from their QBO budget.

The QuickBooks integration is for QuickBooks Online only. QuickBooks Desktop is not supported.

---

## QuickBooks > Connecting QuickBooks > How to Connect QuickBooks Online

Navigate to Settings in the left sidebar and select Integrations. Locate the QuickBooks Online section and click Connect. JAMM PX redirects to the Intuit OAuth authorization page. Log in with your QuickBooks Online credentials and authorize the connection.

After authorization, you are redirected back to JAMM PX and the connection status shows as connected. The integration is firm-wide. All firm owners and managers can use QBO features after the connection is established.

Only firm owners can connect or disconnect QuickBooks.

---

## QuickBooks > Connecting QuickBooks > Disconnecting QuickBooks

Navigate to Settings and select Integrations. Locate the QuickBooks Online section and click Disconnect. The connection is removed immediately.

Disconnecting QuickBooks does not delete any data already imported into JAMM PX. Client records and the QuickBooks Customer IDs linked to them remain. QBO financial data cards on client records will show as unavailable after disconnecting.

---

## QuickBooks > Importing Clients > How to Import Clients from QuickBooks

Navigate to Settings and select Integrations. In the QuickBooks Online section, click Import from QuickBooks. JAMM PX fetches the customer list from QuickBooks and shows a preview.

Review the list. Each customer shows their name and email address. Deselect any customers you do not want to import. Click Import Selected when ready.

JAMM PX creates a new client record for each imported customer and links them to their QuickBooks Customer ID automatically. Customers who already exist as clients in JAMM PX are skipped. The import result shows how many clients were created and how many were skipped.

---

## QuickBooks > Importing Clients > Linking an Existing Client to QuickBooks

If a client already exists in JAMM PX and was not imported from QuickBooks, you can link them manually by entering their QuickBooks Customer ID.

Open the client record. Navigate to the QuickBooks section of the client detail page. Click the edit icon next to the QuickBooks Customer ID field. Enter the customer's ID from QuickBooks and save.

Once linked, JAMM PX pulls financial data for that client from QuickBooks. Use the Open in QuickBooks link on the client record to jump directly to that customer in QBO.

---

## QuickBooks > Financial Data on Client Records > QuickBooks AR Balance

When a client is linked to a QuickBooks Customer ID, the client record shows a QuickBooks AR card. This card shows the outstanding accounts receivable balance for that client and the date of their last payment in QuickBooks.

If the outstanding balance is greater than zero, the balance appears in amber. A zero balance appears in green.

The AR balance reflects the live data from QuickBooks at the time the card was last loaded. It is not cached permanently and refreshes each time the client record is opened.

---

## QuickBooks > Financial Data on Client Records > Bookkeeping Health Score

For clients linked to QuickBooks, JAMM PX calculates a bookkeeping health score based on transaction categorization, reconciliation status, and account balance consistency. The score is displayed on the client record.

The health score helps bookkeeping firms quickly identify clients whose books need attention without opening QuickBooks for each one.

---

## QuickBooks > Financial Data on Client Records > Financial Trends

For clients linked to QuickBooks, JAMM PX surfaces P&L and balance sheet trends on the client record. These show revenue, expense, and balance patterns over recent periods.

The trends give the firm owner a quick financial picture of the client without leaving JAMM PX. Click Open in QuickBooks on the client record to go directly to that customer in QBO for a deeper review.

---

## QuickBooks > Budget Variance > How Budget Variance Alerts Work

JAMM PX checks QuickBooks budgets daily for clients who are linked to QuickBooks and have an active budget configured in QBO. When actual spending in any category deviates from the budget by more than 15%, the Budget Variance Alert automation preset fires.

The preset creates a task to review the variance, due within 3 days. The task is assigned to the firm owner.

For this preset to fire, three conditions must be met: the QuickBooks integration must be connected, the client must be linked to a QuickBooks Customer ID, and the client must have an active budget configured in QuickBooks Online. Clients without a QBO budget are not checked.

Enable the Budget Variance Alert preset from Settings and select Automations.

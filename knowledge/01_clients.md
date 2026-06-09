# Clients Knowledge Corpus

## Clients > Overview > What a Client Record Is

A client record in JAMM PX represents a single person, business, trust, or estate that the firm provides services for. Every piece of work in the system -- engagements, invoices, document requests, and portal access -- belongs to a client record. The client record is the top-level container that ties all firm activity together for a given taxpayer or entity.

Client records store contact information, entity type, tags, internal notes, and a link to the client portal. A client can have multiple contacts associated with it, which is useful for businesses where more than one person communicates with the firm. The primary contact is the one who receives portal magic-links and email communications by default.

Client records are visible to all staff members in the firm. Archiving a client removes it from the active client list without deleting any historical data.

## Clients > Creating a Client > How to Create a Client Manually

To create a client manually, go to Clients in the left navigation, then click New Client in the upper right corner of the client list. A drawer will open on the right side of the screen. Fill in the client name, entity type, email address, and any other fields relevant to your firm. Click Save to create the record.

The name field is required. The email field is strongly recommended because it is used for portal magic-links, invoice delivery, and document request notifications. If a client record is saved without an email address, the client will not be able to receive portal access until the email is added later.

After the client is saved, the record opens automatically so you can add tags, contacts, or notes. You can also create an engagement directly from the client record by clicking New Engagement on the Engagements tab.

## Clients > Creating a Client > Entity Types

JAMM PX supports four entity types for client records: individual, business, trust, and estate. The entity type you select affects how the client appears in reports, how engagement types are categorized, and which fields are shown on the client record.

Individual is used for personal tax clients, sole proprietors who file as individuals, and any person where the primary filing unit is a Form 1040 or equivalent. Business is used for corporations, partnerships, LLCs, and any entity that files a separate business return. Trust is used for revocable and irrevocable trusts that require separate trust returns. Estate is used for estates in administration that require Form 1041 or equivalent filings.

The entity type can be changed after the client record is created. Changing the entity type does not affect existing engagements but will update how the client appears in filtered views and reports going forward.

## Clients > Editing a Client > How to Edit Client Details

To edit a client record, go to Clients in the left navigation and click the client name to open the record. On the client detail page, click Edit in the upper right corner or click directly on any editable field. Make your changes and click Save.

Fields that can be edited include the client name, entity type, email address, phone number, company name, billing address, and internal notes. Tags can be added or removed from the Tags section of the client record without entering edit mode. Contacts can be managed from the Contacts tab.

Changes to client records are saved immediately when you click Save. There is no draft or approval step for client record edits. Staff members with any non-client role can edit client records.

## Clients > Client Health Indicator > What the Health Dot Means

The client health indicator is a colored dot that appears next to each client name in the client list. The dot gives a quick visual signal about the overall status of the client relationship based on engagement activity, open document requests, and portal engagement.

A green dot means the client has active engagements with recent activity and no overdue items. A yellow dot means there are one or more items that need attention, such as a document request that has been open for more than seven days or an engagement with no activity in the past fourteen days. A red dot means there are overdue items, expiring authorizations, or engagements that have been stalled for an extended period.

The health dot is calculated automatically by the system based on the current state of the client engagements and requests. It cannot be manually set. The color updates as the underlying conditions change.

## Clients > Client Health Indicator > How to Use the Health Dot

The health dot is intended to help staff prioritize client outreach during busy periods. When reviewing the client list, staff can filter by health status to surface clients who need immediate attention. Click the filter icon at the top of the client list and select the health status you want to display.

A yellow or red dot does not mean the client relationship is at risk. It means there is an open action item that should be addressed. Common reasons for a yellow dot include a document request waiting on the client, an engagement that has not been updated recently, or an upcoming filing deadline within the next fourteen days.

Resolving the underlying items -- sending a document request reminder, updating engagement status, or completing a task -- will update the health dot automatically. The dot refreshes each time the client list is loaded.

## Clients > QBO Sync > What QuickBooks Sync Does for Client Records

When a firm connects QuickBooks Online through Settings > Integrations > QuickBooks and completes an import, JAMM PX creates client records from the firm QuickBooks customer list. Each imported client record is linked to the corresponding QuickBooks customer by a sync ID stored on the client record.

After the initial import, changes made to customer records in QuickBooks are not automatically pushed to JAMM PX. The sync is a one-time import, not a continuous two-way connection. If a client name or email changes in QuickBooks after the import, you will need to update the JAMM PX client record manually.

The sync also brings over the customer name, email address, company name, phone number, and billing address where those fields exist in QuickBooks. Fields that do not exist in QuickBooks or that are blank in QuickBooks will be empty in the imported client record.

## Clients > QBO Sync > How to Identify a QBO-Synced Client

A client record that was imported from QuickBooks will show a QuickBooks badge on the client detail page near the client name. This badge indicates that the record originated from a QuickBooks import and that a QuickBooks customer ID is stored on the record.

The QuickBooks badge is informational only. It does not affect how the client record functions in JAMM PX. Staff can edit, archive, or delete a QBO-synced client record the same way they would any other client record.

To find all clients that were imported from QuickBooks, go to Clients and use the source filter to select QuickBooks. This will show only the clients whose records originated from the QuickBooks import.

## Clients > Tags > How to Tag a Client

To add a tag to a client record, open the client detail page and locate the Tags section. Click the Add Tag field and type the tag name you want to apply. If the tag already exists in the firm tag library, it will appear as a suggestion. Select it from the dropdown to apply it. If the tag does not exist yet, type the full tag name and press Enter to create it and apply it simultaneously.

Tags are firm-wide and shared across all staff. Creating a new tag from a client record makes it available for use on all other client records going forward. Tag names are case-insensitive and duplicates are prevented automatically.

A client can have any number of tags. Tags appear on the client list as colored chips and can be used to filter the client list. Common uses include service type labels such as Bookkeeping or Tax Only, status labels such as Onboarding, and source labels such as Referral.

## Clients > Tags > How to Remove a Tag

To remove a tag from a client record, open the client detail page and locate the Tags section. Find the tag you want to remove and click the X on the tag chip. The tag is removed from the client record immediately without a confirmation step.

Removing a tag from a client record does not delete the tag from the firm tag library. The tag remains available for use on other client records. To delete a tag from the firm entirely, go to Settings > Tags and delete it from the tag management page.

If a tag is deleted from Settings, it is automatically removed from all client records where it was applied. This action cannot be undone.

## Clients > Contacts > Adding Multiple Contacts to a Client

To add a contact to a client record, open the client detail page and click the Contacts tab. Click Add Contact. A form will appear asking for the contact name, email address, phone number, and role. Fill in the fields and click Save. The contact is added to the client record and appears in the contacts list on that tab.

Multiple contacts can be added to a single client record. This is useful for businesses where an owner, CFO, and bookkeeper each need to communicate with the firm separately. Each contact can have a different email address and phone number.

The primary contact is designated with a Primary badge in the contacts list. To change the primary contact, click the three-dot menu next to a contact and select Set as Primary. The primary contact receives portal magic-links and is the default recipient for invoices and document request notifications.

## Clients > Contacts > What Multi-Contact Handling Means for Portal Access

Each contact on a client record can be given separate portal access. Portal access is tied to an email address, not to the client record itself. This means two contacts at the same firm can both have portal access under their own email addresses and see the same client documents, engagements, and invoices.

Sending a portal magic-link to an additional contact follows the same process as sending one to the primary contact. Go to the client detail page, click the Portal tab, and use the Send Magic-Link action next to the contact you want to invite. Each contact receives their own magic-link.

If a contact email address changes, their portal access must be re-sent using the new email address. The old magic-link will no longer work after a new one is issued to the same contact. Portal access granted to one contact does not affect portal access for any other contact on the same client record.

## Clients > Archiving > How to Archive a Client

To archive a client, open the client detail page and click the three-dot menu in the upper right corner of the page. Select Archive Client from the menu. A confirmation dialog will appear. Click Confirm to complete the archive.

Archiving a client removes the client from the active client list and from all default list views. The client record and all associated data -- engagements, documents, invoices, and notes -- are preserved and can be accessed by switching to the archived client view. No data is deleted when a client is archived.

A client should be archived when the firm is no longer providing active services, the client has moved to another firm, or the client is inactive for the current period. Archiving keeps the system clean without losing historical records that may be needed for reference or audits.

## Clients > Archiving > How to Unarchive a Client

To unarchive a client, go to Clients in the left navigation and click the filter icon at the top of the list. Switch the view to show Archived clients. Find the client you want to restore and open the client detail page. Click the three-dot menu in the upper right corner and select Unarchive Client.

After unarchiving, the client returns to the active client list immediately. All previously archived data for the client -- engagements, invoices, documents, and contacts -- becomes active again and visible in normal list views.

Unarchiving a client does not change the status of any engagements that were active when the client was archived. Engagements that were in progress will return to their previous state. Engagements that were completed before the archive will remain completed.

## Clients > Search > How to Search for a Client

To search for a client, click the search bar at the top of the Clients page or use the global search bar in the main navigation. Type the client name, company name, or email address. Results appear as you type. Click a result to open the client record.

The client search matches against the client name, company name, email address, and tags. Partial matches are supported. Typing the first three letters of a name will return all clients whose name or company name begins with those letters.

The global search bar in the main navigation also returns client results alongside engagement and document results. If you are looking for a specific client, the Clients page search is faster. If you are not sure whether you are looking for a client or an engagement, use the global search bar.

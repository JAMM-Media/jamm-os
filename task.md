STANDING RULES:
- Never use passlib. Use bcrypt directly.
- Never use native_enum=True for enums with dots/special chars.
- Background tasks must create their own SessionLocal() in try/finally.
- All list endpoints use PaginatedResponse[T].
- Tenant isolation on every query via firm_id.

TASK: Fix billing page 500 — line_items null crash

The production invoices endpoint throws a ResponseValidationError because
existing invoices in the database have line_items = NULL, but the InvoiceOut
and PortalInvoiceOut Pydantic schemas declare line_items as list[LineItemSchema]
with no default, causing Pydantic to reject None.

FILE TO EDIT: app/schemas/invoice.py

CHANGE 1: In class InvoiceOut, add a line_items override that defaults to
an empty list:

    line_items: list[LineItemSchema] = []

This should go inside InvoiceOut before model_config.

CHANGE 2: In class PortalInvoiceOut, change:

    line_items: list[LineItemSchema]

to:

    line_items: list[LineItemSchema] = []

Also check class InvoiceBase — if line_items is declared there as
list[LineItemSchema] with no default, change it to:

    line_items: list[LineItemSchema] = []

Do not change any other files. Do not run migrations — this is a schema
(Pydantic) change only, not a database model change.

After making the changes, show the updated class definitions for
InvoiceBase, InvoiceOut, and PortalInvoiceOut so I can verify.
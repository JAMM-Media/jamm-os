STANDING RULES:
- Never use passlib. Use bcrypt directly.
- Background tasks must create their own SessionLocal() in try/finally.
- All list endpoints use PaginatedResponse[T].
- Tenant isolation on every query via firm_id.

TASK: Fix billing 500 — line_items None from database not coerced to []

The InvoiceOut schema has line_items: list[LineItemSchema] = []
but when Pydantic reads from SQLAlchemy attributes (from_attributes=True),
a NULL value in the database passes through as None, which still fails
validation because None is not a list.

The fix is to use a field_validator that coerces None to [].

FILE TO EDIT: app/schemas/invoice.py

CHANGE 1: In class InvoiceBase, change line_items to:
    line_items: list[LineItemSchema] = []

And add a field_validator directly in InvoiceBase:

    @field_validator('line_items', mode='before')
    @classmethod
    def coerce_line_items(cls, v):
        if v is None:
            return []
        return v

Make sure field_validator is imported from pydantic at the top of the file
— it likely already is, just verify.

CHANGE 2: In class InvoiceOut, keep:
    line_items: list[LineItemSchema] = []

The validator on InvoiceBase will be inherited so no separate validator
needed on InvoiceOut.

CHANGE 3: In class PortalInvoiceOut, add the same field_validator:

    @field_validator('line_items', mode='before')
    @classmethod
    def coerce_line_items(cls, v):
        if v is None:
            return []
        return v

After making changes, show the updated InvoiceBase and PortalInvoiceOut
class definitions so I can verify.
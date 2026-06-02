import app.models
from app.db.session import SessionLocal
from app.models.invoice import Invoice
import json

db = SessionLocal()
invoices = db.query(Invoice).all()
for inv in invoices:
    if inv.line_items is None:
        inv.line_items = []
        print(f'Fixed line_items: {inv.invoice_number}')
db.commit()
db.close()
print('Done')
import app.models
from app.db.session import SessionLocal
from app.models.task import Task
from app.models.invoice import Invoice

db = SessionLocal()

# Fix task statuses
STATUS_MAP = {
    'overdue': 'in_progress',
    'not_started': 'todo',
    'complete': 'done',
    'not-started': 'todo',
    'in-progress': 'in_progress',
}

tasks = db.query(Task).all()
for t in tasks:
    if t.status in STATUS_MAP:
        print(f'Fixed task: {t.title} ({t.status} -> {STATUS_MAP[t.status]})')
        t.status = STATUS_MAP[t.status]

# Fix invoice line_items
invoices = db.query(Invoice).all()
for inv in invoices:
    if inv.line_items is None:
        inv.line_items = []
        print(f'Fixed invoice: {inv.invoice_number}')

db.commit()
db.close()
print('Done')
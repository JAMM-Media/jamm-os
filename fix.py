import app.models
from app.db.session import SessionLocal
from app.models.client import Client

db = SessionLocal()
clients = db.query(Client).all()
for c in clients:
    if c.entity_type not in ['business', 'estate', 'individual', 'trust']:
        print(f'Fixed: {c.name} ({c.entity_type} -> business)')
        c.entity_type = 'business'
db.commit()
db.close()
print('Done')
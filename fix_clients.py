import app.models
from app.db.session import SessionLocal
from app.models.client import Client

db = SessionLocal()
clients = db.query(Client).all()

updates = {
    'Acme Corp': {
        'email': 'james@acmecorp.com',
        'phone': '(212) 555-0101',
        'address_line1': '123 Main Street',
        'city': 'New York',
        'state': 'NY',
        'postal_code': '10001',
    },
    'Bright Future LLC': {
        'email': 'naomi@brightfuture.com',
        'phone': '(212) 555-0102',
        'address_line1': '456 Oak Avenue',
        'city': 'Brooklyn',
        'state': 'NY',
        'postal_code': '11201',
    },
    'Goldstein & Partners': {
        'email': 'amos@goldsteinpartners.com',
        'phone': '(212) 555-0103',
        'address_line1': '789 Park Boulevard',
        'city': 'Manhattan',
        'state': 'NY',
        'postal_code': '10022',
    },
    'Ironclad Logistics': {
        'email': 'alex@ironclad.com',
        'phone': '(212) 555-0105',
        'address_line1': '55 Harbor Drive',
        'city': 'Queens',
        'state': 'NY',
        'postal_code': '11101',
    },
}

for client in clients:
    if client.name in updates:
        for field, value in updates[client.name].items():
            setattr(client, field, value)
        print(f'Updated: {client.name}')

db.commit()
db.close()
print('Done')
from dotenv import load_dotenv
load_dotenv()

from app.db.session import SessionLocal
from app.services.automation_presets import seed_firm_presets

db = SessionLocal()
try:
    row = db.execute(__import__("sqlalchemy").text("SELECT id FROM firms LIMIT 1")).fetchone()
    if row is None:
        print("No firm found — aborting.")
    else:
        firm_id = row[0]
        print(f"firm_id: {firm_id}")
        count = seed_firm_presets(firm_id, db)
        print(f"Rules seeded: {count}")
finally:
    db.close()

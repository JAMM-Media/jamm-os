from dotenv import load_dotenv
load_dotenv()

from sqlalchemy import text
from app.db.session import SessionLocal

FIRM_ID = "094716a4-279b-41ad-b671-5c750818e7ca"

DEFAULT_ON = [
    "Document Request Reminder (3-day)",
    "E-Signature Reminder (2-day)",
    "Overdue Task Alert to Staff",
    "New Client Welcome Email",
    "Invoice Overdue Reminder",
]

db = SessionLocal()
try:
    for name in DEFAULT_ON:
        db.execute(
            text(
                "UPDATE automation_rules SET is_enabled=:enabled "
                "WHERE firm_id=:firm_id AND name=:name"
            ),
            {"enabled": True, "firm_id": FIRM_ID, "name": name},
        )
        print(f"{name} — updated")
    db.commit()
finally:
    db.close()

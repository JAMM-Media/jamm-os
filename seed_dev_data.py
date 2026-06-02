import uuid
from datetime import date

from app.db.session import SessionLocal
from app.models.client import Client
from app.models.engagement import Engagement
from app.models.task import Task
from app.models.user import User
from app.services.automation_presets import seed_firm_presets

FIRM_ID = uuid.UUID("658f7117-2820-49e1-91ad-163ca87c3728")
FILING_DEADLINE = date(2026, 9, 15)

DEMO_CLIENTS = [
    {"name": "Acme Corporation", "entity_type": "business", "email": "acme@acmecorp.com"},
    {"name": "Sarah Johnson", "entity_type": "individual", "email": "sarah@gmail.com"},
    {"name": "Riverside Bakery LLC", "entity_type": "business", "email": "info@riversidebakery.com"},
    {"name": "Michael Chen", "entity_type": "individual", "email": "mchen@outlook.com"},
]

TASK_DEFS = [
    ("Review prior year return", "todo"),
    ("Request missing documents", "in_progress"),
]


def get_engagement_specs(entity_type: str) -> list[tuple[str, str]]:
    if entity_type == "business":
        return [("form_1120s", "in_progress"), ("form_1065", "awaiting_docs")]
    return [("form_1040", "in_progress"), ("form_1040", "awaiting_docs")]


def main() -> None:
    db = SessionLocal()
    try:
        preset_count = seed_firm_presets(FIRM_ID, db)
        print(f"Automation presets seeded: {preset_count}")

        owner = db.query(User).filter(User.email == "owner@jamm.com").first()
        if owner is None:
            print("WARNING: owner@jamm.com not found — tasks will have no assignee.")
            owner_id = None
        else:
            owner_id = owner.id

        clients_created = engagements_created = tasks_created = 0

        for cd in DEMO_CLIENTS:
            client = db.query(Client).filter(
                Client.firm_id == FIRM_ID,
                Client.email == cd["email"],
            ).first()

            if client is None:
                client = Client(
                    firm_id=FIRM_ID,
                    name=cd["name"],
                    entity_type=cd["entity_type"],
                    email=cd["email"],
                )
                db.add(client)
                db.flush()
                clients_created += 1
            else:
                print(f"Client '{cd['name']}' already exists, skipping.")

            for eng_type, eng_status in get_engagement_specs(cd["entity_type"]):
                eng = db.query(Engagement).filter(
                    Engagement.firm_id == FIRM_ID,
                    Engagement.client_id == client.id,
                    Engagement.engagement_type == eng_type,
                    Engagement.status == eng_status,
                ).first()

                if eng is None:
                    eng = Engagement(
                        firm_id=FIRM_ID,
                        client_id=client.id,
                        name=f"{client.name} — {eng_type.upper()}",
                        engagement_type=eng_type,
                        status=eng_status,
                        filing_deadline=FILING_DEADLINE,
                    )
                    db.add(eng)
                    db.flush()
                    engagements_created += 1
                else:
                    print(f"Engagement '{eng_type}' for '{client.name}' already exists, skipping.")

                for task_title, task_status in TASK_DEFS:
                    existing = db.query(Task).filter(
                        Task.engagement_id == eng.id,
                        Task.title == task_title,
                    ).first()

                    if existing is None:
                        db.add(Task(
                            firm_id=FIRM_ID,
                            client_id=client.id,
                            engagement_id=eng.id,
                            title=task_title,
                            status=task_status,
                            assigned_to=owner_id,
                        ))
                        db.flush()
                        tasks_created += 1
                    else:
                        print(f"Task '{task_title}' on engagement {eng.id} already exists, skipping.")

        db.commit()

        print("\n--- Seed Summary ---")
        print(f"Clients created:     {clients_created}")
        print(f"Engagements created: {engagements_created}")
        print(f"Tasks created:       {tasks_created}")
        print("All records created successfully.")

    finally:
        db.close()


if __name__ == "__main__":
    main()

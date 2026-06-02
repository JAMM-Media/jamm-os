from app.db.session import SessionLocal
from app.models.task import Task

db = SessionLocal()
try:
    tasks = db.query(Task).filter(Task.status == "not_started").all()
    for t in tasks:
        t.status = "todo"
    db.commit()
    print(f"Updated {len(tasks)} tasks from not_started to todo")
finally:
    db.close()

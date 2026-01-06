# app/main.py
from fastapi import FastAPI

from app.api.clients import router as clients_router
from app.api.projects import router as projects_router
from app.api.tasks import router as tasks_router
from app.api.auth import router as auth_router
from app.api.users import router as users_router

from app.db.session import engine
from app.db.base import Base

from app.api.users import router as users_router


app = FastAPI(title="JAMM OS")  # 👈 MUST COME FIRST

# --- Routers ---
app.include_router(auth_router, prefix="/auth", tags=["auth"])
app.include_router(users_router, tags=["users"])
app.include_router(clients_router, tags=["clients"])
app.include_router(projects_router, tags=["projects"])
app.include_router(tasks_router, tags=["tasks"])
app.include_router(users_router, tags=["users"])


@app.on_event("startup")
def on_startup():
    Base.metadata.create_all(bind=engine)


@app.get("/")
def root():
    return {"message": "JAMM OS is running"}

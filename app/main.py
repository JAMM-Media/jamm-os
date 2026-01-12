# app/main.py

from contextlib import asynccontextmanager
from fastapi import FastAPI

from app.api.clients import router as clients_router
from app.api.projects import router as projects_router
from app.api.tasks import router as tasks_router
from app.api.auth import router as auth_router
from app.api.users import router as users_router
from app.api.contacts import router as contacts_router
from app.api.health import router as health_router
from app.db.session import engine
from app.db.base import Base

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Run at startup
    Base.metadata.create_all(bind=engine)
    yield
    # Run at shutdown (if needed)

app = FastAPI(title="JAMM OS", lifespan=lifespan)

# --- Routers ---
app.include_router(auth_router, prefix="/auth", tags=["auth"])
app.include_router(users_router, tags=["users"])
app.include_router(clients_router, tags=["clients"])
app.include_router(projects_router, tags=["projects"])
app.include_router(tasks_router, tags=["tasks"])
app.include_router(contacts_router, tags=["contacts"])
app.include_router(health_router, prefix="/api")

# --- Routes ---
@app.get("/")
def root():
    return {"message": "JAMM OS is running"}

@app.get("/api/health")
def health_check():
    return {"status": "ok"}

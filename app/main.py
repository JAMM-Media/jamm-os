# app/main.py

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware

from app.api.clients import router as clients_router
from app.api.engagements import router as engagements_router
from app.api.tasks import router as tasks_router
from app.api.auth import router as auth_router
from app.api.users import router as users_router
from app.api.contacts import router as contacts_router
from app.api.firms import router as firms_router
from app.api.documents import router as documents_router

from app.db.base_class import Base
from app.core.config import get_settings
from app.core.middleware import SecurityHeadersMiddleware

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield


app = FastAPI(
    title=settings.app_name,
    debug=settings.debug,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.BACKEND_CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=[
        "localhost",
        "127.0.0.1",
        "testserver",
        "*.yourdomain.com",
    ],
)

app.add_middleware(SecurityHeadersMiddleware)

app.include_router(auth_router, prefix="/auth", tags=["auth"])
app.include_router(firms_router)
app.include_router(users_router)
app.include_router(clients_router)
app.include_router(engagements_router)
app.include_router(tasks_router)
app.include_router(contacts_router)
app.include_router(documents_router)


@app.get("/")
def root():
    return {"message": "JAMM OS is running"}


@app.get("/api/health")
def health_check():
    return {"status": "ok"}
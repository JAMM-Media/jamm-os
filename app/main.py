from fastapi import FastAPI
from .api.routes import router as api_router

def create_app() -> FastAPI:
    app = FastAPI(title="JAMM OS Backend", version="0.1.0")
    app.include_router(api_router, prefix="/api")

    @app.get("/")
    def root():
        return {"message": "JAMM OS is running"}

    return app

app = create_app()

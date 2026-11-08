from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from wialon_fleet_backend.config import get_settings

settings = get_settings()

app = FastAPI(title="Wialon Fleet Control API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}

"""Argus API — FastAPI backend."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .routers import ampel, chat, prices, research

app = FastAPI(title="Argus API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(ampel.router, prefix="/api/ampel", tags=["ampel"])
app.include_router(chat.router, prefix="/api/chat", tags=["chat"])
app.include_router(prices.router, prefix="/api/prices", tags=["prices"])
app.include_router(research.router, prefix="/api/research", tags=["research"])


@app.get("/api/health")
def health():
    return {"status": "ok"}

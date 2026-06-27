from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.main import *
from app.config import settings
import os


app = FastAPI(
    title="Travelara",
    description="Adaptive constraint-aware travel planning API powered by hierarchical graph optimization.",
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)


@app.get("/", tags=["Health"])
async def root():
    return {
        "service": "Travelara",
        "version": "0.1.0",
        "status": "ok",
        "docs": "/docs",
    }


@app.get("/health", tags=["Health"])
async def health():
    return {
        "status": "ok",
        "apis_configured": {
            "gemini": bool(settings.gemini_api_key),
            "geoapify": bool(settings.geoapify_api_key),
            "foursquare": bool(settings.foursquare_api_key),
        }
    }

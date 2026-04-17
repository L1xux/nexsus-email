from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.database import init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Import here to ensure env vars are loaded first
    from app.core.config import get_settings
    settings = get_settings()

    # Handle empty client_url gracefully
    if not settings.client_url:
        settings.client_url = "*"

    app.add_middleware(
        CORSMiddleware,
        allow_origins=[settings.client_url],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Initialize database, but don't fail if DB is not available
    try:
        await init_db()
    except Exception as e:
        print(f"Warning: Could not initialize database: {e}")

    yield


app = FastAPI(
    title="NexusMail API",
    description="AI-powered email management with Gmail integration",
    version="1.0.0",
    lifespan=lifespan,
)

# Routes are imported after app is created to avoid circular imports
from app.api.routes import auth, emails, categories, feedback, webhooks, threads

app.include_router(auth.router, prefix="/api/auth", tags=["auth"])
app.include_router(emails.router, prefix="/api/emails", tags=["emails"])
app.include_router(threads.router, prefix="/api/threads", tags=["threads"])
app.include_router(categories.router, prefix="/api/categories", tags=["categories"])
app.include_router(feedback.router, prefix="/api/feedback", tags=["feedback"])
app.include_router(webhooks.router, prefix="/api/webhooks", tags=["webhooks"])


@app.get("/api/health")
async def health_check():
    return {"status": "healthy", "app": "NexusMail"}
import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.database import init_db


def get_client_url() -> str:
    """Get client URL from environment or default."""
    url = os.getenv("CLIENT_URL", "")
    if not url or url == "http://localhost:5173":
        return "*"
    return url


@asynccontextmanager
async def lifespan(app: FastAPI):
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

# Add CORS middleware at startup
client_url = get_client_url()
app.add_middleware(
    CORSMiddleware,
    allow_origins=[client_url],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
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
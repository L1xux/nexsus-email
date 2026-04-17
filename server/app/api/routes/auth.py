from urllib.parse import urlencode
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from google.oauth2.credentials import Credentials

from app.core.database import get_db
from app.core.security import create_access_token, get_current_user
from app.core.google import get_google_oauth_flow, get_user_info
from app.core.config import get_settings
from app.models.user import User
from app.schemas.user import UserResponse, TokenResponse, GoogleAuthUrlResponse
from app.services.gmail_watch import watch_gmail_user, stop_gmail_watch

router = APIRouter()
settings = get_settings()


@router.get("/google", response_model=GoogleAuthUrlResponse)
async def get_google_auth_url():
    flow = get_google_oauth_flow()
    auth_url, _ = flow.authorization_url(
        prompt="consent",
        access_type="offline",
    )
    return GoogleAuthUrlResponse(url=auth_url)


@router.get("/callback")
async def google_callback(
    code: str = Query(...),
    db: AsyncSession = Depends(get_db)
):
    try:
        flow = get_google_oauth_flow()
        flow.fetch_token(code=code)
        credentials = flow.credentials

        user_info = await get_user_info(credentials)
        email = user_info.get("email")
        name = user_info.get("name")
        picture = user_info.get("picture")

        result = await db.execute(select(User).where(User.email == email))
        user = result.scalar_one_or_none()

        is_new_user = False
        if not user:
            user = User(
                email=email,
                name=name,
                picture=picture,
                google_access_token=credentials.token,
                google_refresh_token=credentials.refresh_token,
                google_token_expiry=credentials.expiry,
            )
            db.add(user)
            is_new_user = True
        else:
            user.google_access_token = credentials.token
            user.google_refresh_token = credentials.refresh_token
            user.google_token_expiry = credentials.expiry
            user.name = name
            user.picture = picture

        await db.commit()
        await db.refresh(user)

        access_token = create_access_token(data={"sub": str(user.id)})

        from fastapi import Response
        from urllib.parse import urlencode

        # Build redirect URL based on environment
        # In production, redirect to the client URL; in development, localhost
        if settings.app_env == "production" and settings.client_url:
            redirect_base = settings.client_url.rstrip('/')
        else:
            redirect_base = "http://localhost:5173"

        params = urlencode({
            "token": access_token,
            "user_id": str(user.id),
            "email": email,
            "name": name or "",
            "picture": picture or "",
        })

        return Response(
            content=f'<html><body><script>window.location.href="{redirect_base}/auth/callback?{params}";</script></body></html>',
            media_type="text/html",
        )
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Callback error: {str(e)}"
        )


@router.post("/logout")
async def logout(
    current_user: User = Depends(get_current_user),
):
    # Stop Gmail watch on logout
    if current_user.google_access_token:
        try:
            credentials = Credentials(
                token=current_user.google_access_token,
                refresh_token=current_user.google_refresh_token,
            )
            await stop_gmail_watch(credentials)
        except Exception as e:
            print(f"Failed to stop Gmail watch: {e}")
    
    return {"message": "Logged out successfully"}


@router.get("/me", response_model=UserResponse)
async def get_me(
    current_user: User = Depends(get_current_user),
):
    return current_user


@router.post("/setup-watch")
async def setup_watch(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Set up Gmail watch for the authenticated user."""
    if not current_user.google_access_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Google account not connected"
        )
    
    if not settings.gmail_pubsub_topic:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Gmail Pub/Sub topic not configured"
        )
    
    credentials = Credentials(
        token=current_user.google_access_token,
        refresh_token=current_user.google_refresh_token,
    )
    
    webhook_url = f"{settings.client_url}/api/webhooks/gmail"
    
    try:
        result = await watch_gmail_user(
            credentials,
            settings.gmail_pubsub_topic,
            webhook_url,
        )
        return {
            "status": "success",
            "history_id": result.get("history_id"),
            "expiration": result.get("expiration"),
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to set up watch: {str(e)}"
        )


@router.post("/stop-watch")
async def stop_watch(
    current_user: User = Depends(get_current_user),
):
    """Stop Gmail watch for the authenticated user."""
    if not current_user.google_access_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Google account not connected"
        )
    
    credentials = Credentials(
        token=current_user.google_access_token,
        refresh_token=current_user.google_refresh_token,
    )
    
    try:
        await stop_gmail_watch(credentials)
        return {"status": "success", "message": "Watch stopped"}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to stop watch: {str(e)}"
        )

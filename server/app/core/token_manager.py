"""
Google OAuth token management with automatic refresh.
"""
from datetime import datetime, timezone
from typing import Optional, Tuple
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import logging

from app.core.config import get_settings
from app.models.user import User

settings = get_settings()
logger = logging.getLogger(__name__)


async def refresh_token_if_needed(
    user: User,
    db: AsyncSession,
) -> Tuple[str, Optional[str]]:
    """
    Check if the user's Google access token is expired or about to expire,
    and refresh it if needed.

    Returns:
        Tuple of (access_token, refresh_token)

    Raises:
        Exception if refresh fails
    """
    if not user.google_access_token:
        raise ValueError("User has no Google access token")

    # Check if token needs refresh (expires within 5 minutes)
    needs_refresh = False
    if user.google_token_expiry:
        # Make expiry timezone-aware for comparison
        expiry = user.google_token_expiry
        if expiry.tzinfo is None:
            expiry = expiry.replace(tzinfo=timezone.utc)
        # Refresh if expiring within 5 minutes
        from datetime import timedelta
        if datetime.now(timezone.utc) >= expiry - timedelta(minutes=5):
            needs_refresh = True
    else:
        # No expiry stored, assume token might be expired
        needs_refresh = True

    if not needs_refresh:
        return user.google_access_token, user.google_refresh_token

    if not user.google_refresh_token:
        logger.warning(f"No refresh token available for user {user.id}")
        raise ValueError("No refresh token available. Please reconnect your Google account.")

    try:
        credentials = Credentials(
            token=user.google_access_token,
            refresh_token=user.google_refresh_token,
            token_uri="https://oauth2.googleapis.com/token",
            client_id=settings.google_client_id,
            client_secret=settings.google_client_secret,
        )

        # Refresh the token
        credentials.refresh(Request())

        # Update user with new tokens
        user.google_access_token = credentials.token
        if credentials.refresh_token:
            user.google_refresh_token = credentials.refresh_token
        if credentials.expiry:
            user.google_token_expiry = credentials.expiry

        await db.commit()
        logger.info(f"Refreshed Google token for user {user.id}")

        return credentials.token, credentials.refresh_token

    except Exception as e:
        logger.error(f"Failed to refresh token for user {user.id}: {e}")
        raise


def build_credentials(user: User) -> Credentials:
    """Build Google Credentials object from user."""
    return Credentials(
        token=user.google_access_token,
        refresh_token=user.google_refresh_token,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=settings.google_client_id,
        client_secret=settings.google_client_secret,
    )


async def build_credentials_with_refresh(
    user: User,
    db: AsyncSession,
) -> Credentials:
    """
    Build Google Credentials object, refreshing if needed.

    This is the recommended way to get credentials for making API calls.
    """
    token, _ = await refresh_token_if_needed(user, db)
    return Credentials(
        token=token,
        refresh_token=user.google_refresh_token,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=settings.google_client_id,
        client_secret=settings.google_client_secret,
    )

import base64
import json
from typing import Optional
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from app.core.config import get_settings
from app.core.gmail_parser import parse_gmail_message

settings = get_settings()


def get_gmail_service(credentials: Credentials):
    return build("gmail", "v1", credentials=credentials, cache_discovery=False)


async def watch_gmail_user(
    credentials: Credentials,
    topic_name: str,
    webhook_url: str,
) -> dict:
    """
    Register for Google Cloud Pub/Sub push notifications for new emails.
    
    Args:
        credentials: Google OAuth2 credentials
        topic_name: Pub/Sub topic name (projects/{project}/topics/{topic})
        webhook_url: The URL where webhook notifications will be sent
    
    Returns:
        dict with watch expiration info
    """
    service = get_gmail_service(credentials)
    
    watch_request = {
        "topicName": topic_name,
        "labelIds": ["INBOX"],
    }
    
    try:
        result = service.users().watch(userId="me", body=watch_request).execute()
        return {
            "history_id": result.get("historyId"),
            "expiration": result.get("expiration"),
        }
    except HttpError as e:
        print(f"Error setting up Gmail watch: {e}")
        raise


async def stop_gmail_watch(credentials: Credentials) -> dict:
    """
    Stop watching for Gmail notifications.
    """
    service = get_gmail_service(credentials)
    
    try:
        result = service.users().stop(userId="me").execute()
        return result
    except HttpError as e:
        print(f"Error stopping Gmail watch: {e}")
        raise


async def get_watch_status(credentials: Credentials) -> Optional[dict]:
    """
    Get current watch status for the user.
    """
    service = get_gmail_service(credentials)
    
    try:
        result = service.users().getProfile(userId="me").execute()
        return {
            "email_address": result.get("emailAddress"),
            "messages_total": result.get("messagesTotal"),
            "threads_total": result.get("threadsTotal"),
        }
    except HttpError as e:
        print(f"Error getting watch status: {e}")
        return None


async def get_history(
    credentials: Credentials,
    start_history_id: str,
    history_types: Optional[list[str]] = None,
) -> dict:
    """
    Get history of changes since a given historyId.
    
    Args:
        credentials: Google OAuth2 credentials
        start_history_id: The historyId to start from
        history_types: Types of history to fetch (e.g., ['messagesAdded', 'labelsChanged'])
    
    Returns:
        dict with history records
    """
    service = get_gmail_service(credentials)
    
    params = {
        "startHistoryId": start_history_id,
    }
    
    if history_types:
        params["historyTypes"] = history_types
    
    try:
        result = service.users().history().list(userId="me", **params).execute()
        return result
    except HttpError as e:
        print(f"Error fetching history: {e}")
        raise


async def list_new_messages(
    credentials: Credentials,
    start_history_id: str,
) -> list[dict]:
    """
    List only new messages since the given historyId.
    """
    history = await get_history(
        credentials,
        start_history_id,
        history_types=["messagesAdded"]
    )
    
    messages = []
    for record in history.get("history", []):
        for msg in record.get("messagesAdded", []):
            messages.append(msg)
    
    return messages


async def fetch_message_by_id(
    credentials: Credentials,
    message_id: str,
) -> dict:
    """
    Fetch a specific message by its ID.
    """
    service = get_gmail_service(credentials)
    
    try:
        message = service.users().messages().get(
            userId="me",
            id=message_id,
            format="full",
        ).execute()
        return message
    except HttpError as e:
        print(f"Error fetching message: {e}")
        raise


async def list_new_messages(

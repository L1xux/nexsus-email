import base64
import json
import re
from typing import Optional
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from app.core.config import get_settings

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


def parse_gmail_headers(headers: list[dict]) -> dict:
    """Convert list of headers to dict with lowercase keys."""
    return {h["name"].lower(): h["value"] for h in headers}


def parse_gmail_message(message: dict) -> dict:
    """Parse Gmail message payload into structured data."""
    payload = message.get("payload", {})
    headers = parse_gmail_headers(payload.get("headers", []))
    
    subject = headers.get("subject")
    sender = headers.get("from")
    sender_email = None
    if sender:
        match = re.search(r"<(.+?)>", sender)
        sender_email = match.group(1) if match else sender
    
    recipients = headers.get("to")
    
    snippet = message.get("snippet")
    
    body_text = None
    body_html = None
    
    # Try to get body from payload
    if payload.get("body", {}).get("data"):
        body_text = base64.urlsafe_b64decode(
            payload["body"]["data"]
        ).decode("utf-8")
    
    # Parse multipart message parts
    parts = payload.get("parts", [])
    for part in parts:
        mime_type = part.get("mimeType", "")
        if mime_type == "text/plain" and part.get("body", {}).get("data"):
            body_text = base64.urlsafe_b64decode(
                part["body"]["data"]
            ).decode("utf-8")
        elif mime_type == "text/html" and part.get("body", {}).get("data"):
            body_html = base64.urlsafe_b64decode(
                part["body"]["data"]
            ).decode("utf-8")
    
    label_ids = message.get("labelIds", [])
    
    internal_date = message.get("internalDate")
    received_at = None
    if internal_date:
        import time
        received_at = time.ctime(int(internal_date) / 1000)
    
    return {
        "gmail_message_id": message["id"],
        "history_id": message.get("historyId"),
        "thread_id": message.get("threadId"),
        "subject": subject,
        "sender": sender,
        "sender_email": sender_email,
        "recipients": recipients,
        "snippet": snippet,
        "body_text": body_text,
        "body_html": body_html,
        "label_ids": ",".join(label_ids),
        "received_at": received_at,
        "is_read": "UNREAD" not in label_ids,
        "is_starred": "STARRED" in label_ids,
    }


import time

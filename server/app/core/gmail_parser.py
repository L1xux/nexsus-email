"""
Shared Gmail message parsing utilities.
"""
import base64
import re
from typing import Optional


def parse_gmail_headers(headers: list[dict]) -> dict:
    """Convert list of headers to dict with lowercase keys."""
    return {h["name"].lower(): h["value"] for h in headers}


def parse_gmail_message(message: dict) -> dict:
    """
    Parse Gmail message payload into structured data.

    This is the canonical implementation used across all services.
    """
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

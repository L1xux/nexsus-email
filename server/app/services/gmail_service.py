from typing import Optional
from google.oauth2.credentials import Credentials

from app.core.google import get_gmail_service, list_emails, get_email as gmail_get_email


async def fetch_recent_emails(
    credentials: Credentials,
    max_results: int = 10,
) -> list[dict]:
    result = await list_emails(credentials, max_results=max_results)
    messages = result.get("messages", [])
    
    emails = []
    for msg in messages:
        email_data = await gmail_get_email(credentials, msg["id"])
        emails.append(email_data)
    
    return emails


def parse_gmail_message(message: dict) -> dict:
    headers = message.get("payload", {}).get("headers", [])
    header_dict = {h["name"].lower(): h["value"] for h in headers}
    
    subject = header_dict.get("subject")
    sender = header_dict.get("from")
    sender_email = None
    if sender:
        import re
        match = re.search(r"<(.+?)>", sender)
        sender_email = match.group(1) if match else sender
    
    recipients = header_dict.get("to")
    
    snippet = message.get("snippet")
    
    body_text = None
    body_html = None
    
    payload = message.get("payload", {})
    if payload.get("body", {}).get("data"):
        body_text = base64.urlsafe_b64decode(
            payload["body"]["data"]
        ).decode("utf-8")
    
    parts = payload.get("parts", [])
    for part in parts:
        if part.get("mimeType") == "text/plain" and part.get("body", {}).get("data"):
            body_text = base64.urlsafe_b64decode(
                part["body"]["data"]
            ).decode("utf-8")
        elif part.get("mimeType") == "text/html" and part.get("body", {}).get("data"):
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


import base64

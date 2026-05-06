import base64
import re
import time
from typing import Optional
from google.oauth2.credentials import Credentials

from app.core.google import get_gmail_service, list_emails, get_email as gmail_get_email
from app.core.gmail_parser import parse_gmail_message


async def fetch_recent_emails(
    credentials: Credentials,
    max_results: int = 10,
    query: str = "",
) -> list[dict]:
    result = await list_emails(credentials, max_results=max_results, query=query)
    messages = result.get("messages", [])

    emails = []
    for msg in messages:
        try:
            email_data = await gmail_get_email(credentials, msg["id"])
            emails.append(email_data)
        except Exception as e:
            print(f"Failed to fetch email {msg['id']}: {e}")
            continue

    return emails

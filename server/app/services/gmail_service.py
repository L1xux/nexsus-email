import asyncio
from typing import Optional
from google.oauth2.credentials import Credentials

from app.core.google import get_gmail_service, list_emails, get_email as gmail_get_email
from app.core.gmail_parser import parse_gmail_message

FETCH_BATCH_SIZE = 50   # concurrent Gmail API calls per batch
MAX_TOTAL_MESSAGES = 500  # hard cap to stay within Render's 30s timeout


async def _fetch_all_message_ids(
    credentials: Credentials,
    query: str,
    max_total: int,
) -> list[str]:
    """Collect message IDs across all nextPageToken pages up to max_total."""
    ids: list[str] = []
    page_token: Optional[str] = None

    while len(ids) < max_total:
        remaining = max_total - len(ids)
        page_size = min(500, remaining)  # Gmail API hard limit per page is 500
        result = await list_emails(
            credentials,
            max_results=page_size,
            query=query,
            page_token=page_token,
        )
        for msg in result.get("messages", []):
            ids.append(msg["id"])

        page_token = result.get("nextPageToken")
        if not page_token:
            break

    return ids


async def _fetch_single(credentials: Credentials, message_id: str) -> Optional[dict]:
    try:
        return await gmail_get_email(credentials, message_id)
    except Exception as e:
        print(f"Failed to fetch email {message_id}: {e}")
        return None


async def fetch_recent_emails(
    credentials: Credentials,
    max_results: int = 200,
    query: str = "",
) -> list[dict]:
    """
    Fetch full email data for all messages matching query.
    Uses nextPageToken pagination to collect all IDs, then fetches
    full content in parallel batches of FETCH_BATCH_SIZE.
    """
    message_ids = await _fetch_all_message_ids(
        credentials, query, min(max_results, MAX_TOTAL_MESSAGES)
    )

    emails: list[dict] = []
    for i in range(0, len(message_ids), FETCH_BATCH_SIZE):
        batch = message_ids[i:i + FETCH_BATCH_SIZE]
        results = await asyncio.gather(*[_fetch_single(credentials, mid) for mid in batch])
        emails.extend(r for r in results if r is not None)

    return emails

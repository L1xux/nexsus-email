from typing import Optional
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from app.core.config import get_settings

settings = get_settings()


def get_google_oauth_flow() -> Flow:
    return Flow.from_client_config(
        client_config={
            "web": {
                "client_id": settings.google_client_id,
                "client_secret": settings.google_client_secret,
                "redirect_uris": [settings.google_redirect_uri],
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
            }
        },
        scopes=[
            "openid",
            "https://www.googleapis.com/auth/userinfo.email",
            "https://www.googleapis.com/auth/userinfo.profile",
            "https://www.googleapis.com/auth/gmail.readonly",
            "https://www.googleapis.com/auth/gmail.modify",
        ],
        redirect_uri=settings.google_redirect_uri,
    )


def get_gmail_service(credentials: Credentials):
    return build("gmail", "v1", credentials=credentials, cache_discovery=False)


async def get_user_info(credentials: Credentials) -> dict:
    service = build("oauth2", "v2", credentials=credentials, cache_discovery=False)
    return service.userinfo().get().execute()


async def list_emails(
    credentials: Credentials,
    max_results: int = 10,
    query: str = "",
    page_token: Optional[str] = None
) -> dict:
    service = get_gmail_service(credentials)
    
    results = service.users().messages().list(
        userId="me",
        maxResults=max_results,
        q=query,
        pageToken=page_token,
    ).execute()
    
    return results


async def get_email(credentials: Credentials, message_id: str) -> dict:
    service = get_gmail_service(credentials)
    
    message = service.users().messages().get(
        userId="me",
        id=message_id,
        format="full",
    ).execute()
    
    return message


async def modify_email_labels(
    credentials: Credentials,
    message_id: str,
    add_label_ids: list[str] = None,
    remove_label_ids: list[str] = None
) -> dict:
    service = get_gmail_service(credentials)
    
    body = {}
    if add_label_ids:
        body["addLabelIds"] = add_label_ids
    if remove_label_ids:
        body["removeLabelIds"] = remove_label_ids
    
    message = service.users().messages().modify(
        userId="me",
        id=message_id,
        body=body,
    ).execute()
    
    return message


async def get_thread(credentials: Credentials, thread_id: str) -> dict:
    service = get_gmail_service(credentials)
    
    thread = service.users().threads().get(
        userId="me",
        id=thread_id,
        format="full",
    ).execute()
    
    return thread

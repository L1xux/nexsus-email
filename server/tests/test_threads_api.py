import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from httpx import AsyncClient

from app.models.thread import EmailThread, ThreadStatus
from app.models.email import Email


class TestThreadsAPI:
    @pytest.mark.asyncio
    async def test_list_threads_empty(self, client: AsyncClient):
        response = await client.get("/api/threads")
        
        assert response.status_code == 200
        data = response.json()
        assert "threads" in data
        assert data["total"] == 0

    @pytest.mark.asyncio
    async def test_list_threads_with_data(self, client: AsyncClient, db_session):
        thread = EmailThread(
            id=1,
            user_id=1,
            gmail_thread_id="test-thread-123",
            subject="Test Thread",
            status=ThreadStatus.TODO,
            message_count=2,
            snippet="Test snippet",
        )
        db_session.add(thread)
        await db_session.commit()

        response = await client.get("/api/threads")
        
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert len(data["threads"]) == 1
        assert data["threads"][0]["subject"] == "Test Thread"
        assert data["threads"][0]["status"] == "todo"

    @pytest.mark.asyncio
    async def test_list_threads_filter_by_status(self, client: AsyncClient, db_session):
        thread1 = EmailThread(
            user_id=1,
            gmail_thread_id="thread-1",
            subject="Thread 1",
            status=ThreadStatus.TODO,
        )
        thread2 = EmailThread(
            user_id=1,
            gmail_thread_id="thread-2",
            subject="Thread 2",
            status=ThreadStatus.DONE,
        )
        db_session.add_all([thread1, thread2])
        await db_session.commit()

        response = await client.get("/api/threads?status=todo")
        
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert data["threads"][0]["status"] == "todo"

    @pytest.mark.asyncio
    async def test_list_threads_pagination(self, client: AsyncClient, db_session):
        for i in range(25):
            thread = EmailThread(
                user_id=1,
                gmail_thread_id=f"thread-{i}",
                subject=f"Thread {i}",
                status=ThreadStatus.INBOX,
            )
            db_session.add(thread)
        await db_session.commit()

        response = await client.get("/api/threads?page=1&page_size=10")
        
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 25
        assert data["page"] == 1
        assert data["page_size"] == 10
        assert data["has_next"] == True
        assert len(data["threads"]) == 10

    @pytest.mark.asyncio
    async def test_get_thread_not_found(self, client: AsyncClient):
        response = await client.get("/api/threads/99999")
        
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_get_thread_with_emails(self, client: AsyncClient, db_session):
        thread = EmailThread(
            id=1,
            user_id=1,
            gmail_thread_id="thread-with-emails",
            subject="Thread with Emails",
            status=ThreadStatus.TODO,
        )
        db_session.add(thread)
        await db_session.flush()

        email = Email(
            id=1,
            user_id=1,
            gmail_message_id="msg-123",
            thread_id="thread-with-emails",
            email_thread_id=thread.id,
            subject="Email in Thread",
            sender="Sender <sender@test.com>",
            sender_email="sender@test.com",
        )
        db_session.add(email)
        await db_session.commit()

        response = await client.get(f"/api/threads/{thread.id}")
        
        assert response.status_code == 200
        data = response.json()
        assert data["subject"] == "Thread with Emails"
        assert len(data["emails"]) == 1
        assert data["emails"][0]["gmail_message_id"] == "msg-123"

    @pytest.mark.asyncio
    async def test_update_thread_status(self, client: AsyncClient, db_session):
        thread = EmailThread(
            id=1,
            user_id=1,
            gmail_thread_id="update-test",
            subject="Update Test",
            status=ThreadStatus.INBOX,
        )
        db_session.add(thread)
        await db_session.commit()

        response = await client.patch(
            f"/api/threads/{thread.id}",
            json={"status": "waiting"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "waiting"

    @pytest.mark.asyncio
    async def test_update_thread_mark_as_read(self, client: AsyncClient, db_session):
        thread = EmailThread(
            id=1,
            user_id=1,
            gmail_thread_id="read-test",
            subject="Read Test",
            is_read=False,
        )
        db_session.add(thread)
        await db_session.commit()

        response = await client.patch(
            f"/api/threads/{thread.id}",
            json={"is_read": True}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["is_read"] == True

    @pytest.mark.asyncio
    async def test_update_thread_starred(self, client: AsyncClient, db_session):
        thread = EmailThread(
            id=1,
            user_id=1,
            gmail_thread_id="star-test",
            subject="Star Test",
            is_starred=False,
        )
        db_session.add(thread)
        await db_session.commit()

        response = await client.patch(
            f"/api/threads/{thread.id}",
            json={"is_starred": True}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["is_starred"] == True


class TestThreadModel:
    def test_thread_status_enum(self):
        assert ThreadStatus.INBOX.value == "inbox"
        assert ThreadStatus.TODO.value == "todo"
        assert ThreadStatus.WAITING.value == "waiting"
        assert ThreadStatus.DONE.value == "done"

    @pytest.mark.asyncio
    async def test_thread_model_creation(self, db_session):
        thread = EmailThread(
            user_id=1,
            gmail_thread_id="gmail-123",
            subject="Test Subject",
            status=ThreadStatus.TODO,
            message_count=3,
            participant_count=2,
        )
        db_session.add(thread)
        await db_session.commit()
        await db_session.refresh(thread)
        
        assert thread.user_id == 1
        assert thread.gmail_thread_id == "gmail-123"
        assert thread.subject == "Test Subject"
        assert thread.status == ThreadStatus.TODO
        assert thread.message_count == 3
        assert thread.participant_count == 2
        assert thread.is_read == False
        assert thread.is_starred == False

    @pytest.mark.asyncio
    async def test_thread_model_default_values(self, db_session):
        thread = EmailThread(
            user_id=1,
            gmail_thread_id="test",
        )
        db_session.add(thread)
        await db_session.commit()
        await db_session.refresh(thread)
        
        assert thread.status == ThreadStatus.INBOX
        assert thread.message_count == 1
        assert thread.participant_count == 1
        assert thread.is_read == False
        assert thread.is_starred == False

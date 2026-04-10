import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from app.services.thread_classifier import (
    classify_thread,
    classify_thread_category,
    classify_thread_with_category,
    _extract_email_from_sender,
    _decode_body,
    _parse_message_headers,
    _build_conversation_context,
    ThreadClassificationResult,
)


class TestHelperFunctions:
    def test_extract_email_from_sender_with_brackets(self):
        sender = "John Doe <john@example.com>"
        result = _extract_email_from_sender(sender)
        assert result == "john@example.com"

    def test_extract_email_from_sender_without_brackets(self):
        sender = "john@example.com"
        result = _extract_email_from_sender(sender)
        assert result == "john@example.com"

    def test_extract_email_from_sender_empty(self):
        sender = ""
        result = _extract_email_from_sender(sender)
        assert result == ""

    def test_decode_body_with_data(self):
        import base64
        original = "Hello World"
        encoded = base64.urlsafe_b64encode(original.encode()).decode()
        body = {"data": encoded}
        result = _decode_body(body)
        assert result == original

    def test_decode_body_none(self):
        result = _decode_body(None)
        assert result is None

    def test_decode_body_no_data(self):
        result = _decode_body({})
        assert result is None

    def test_parse_message_headers(self):
        message = {
            "snippet": "Test snippet",
            "payload": {
                "headers": [
                    {"name": "Subject", "value": "Test Subject"},
                    {"name": "From", "value": "Sender <sender@example.com>"},
                ],
                "body": {},
                "parts": [],
            },
        }
        result = _parse_message_headers(message)
        
        assert result["subject"] == "Test Subject"
        assert result["sender"] == "Sender <sender@example.com>"
        assert result["sender_email"] == "sender@example.com"
        assert result["snippet"] == "Test snippet"

    def test_parse_message_headers_no_payload(self):
        message = {}
        result = _parse_message_headers(message)
        
        assert result["subject"] == ""
        assert result["sender"] == ""
        assert result["sender_email"] is None

    def test_build_conversation_context_single_message(self):
        messages = [
            {
                "snippet": "Hello",
                "payload": {
                    "headers": [
                        {"name": "Subject", "value": "Hi"},
                        {"name": "From", "value": "Bob <bob@test.com>"},
                    ],
                    "body": {"data": ""},
                    "parts": [],
                },
            }
        ]
        result = _build_conversation_context(messages)
        
        assert "Message 1:" in result
        assert "Bob <bob@test.com>" in result
        assert "Hi" in result

    def test_build_conversation_context_multiple_messages(self):
        messages = [
            {
                "snippet": "First message",
                "payload": {
                    "headers": [
                        {"name": "Subject", "value": "Subject1"},
                        {"name": "From", "value": "A <a@test.com>"},
                    ],
                    "body": {},
                    "parts": [],
                },
            },
            {
                "snippet": "Second message",
                "payload": {
                    "headers": [
                        {"name": "Subject", "value": "Subject1"},
                        {"name": "From", "value": "B <b@test.com>"},
                    ],
                    "body": {},
                    "parts": [],
                },
            },
        ]
        result = _build_conversation_context(messages)
        
        assert "Message 1:" in result
        assert "Message 2:" in result


class TestClassifyThread:
    @pytest.mark.asyncio
    @patch("app.services.thread_classifier.AsyncOpenAI")
    async def test_classify_thread_todo(self, mock_openai_class, db_session):
        mock_client = AsyncMock()
        mock_response = AsyncMock()
        mock_response.choices = [
            MagicMock(
                message=MagicMock(
                    content='{"status": "ToDo", "confidence": 0.95, "reason": "Client requested quote"}'
                )
            )
        ]
        mock_client.chat.completions.create = AsyncMock(return_value=mock_response)
        mock_openai_class.return_value = mock_client

        messages = [
            {
                "snippet": "Can you send me a quote?",
                "payload": {
                    "headers": [
                        {"name": "Subject", "value": "Quote Request"},
                        {"name": "From", "value": "Client <client@test.com>"},
                    ],
                    "body": {"data": ""},
                    "parts": [],
                },
            }
        ]

        result = await classify_thread("Quote Request", messages, 1, db_session)

        assert result.status == "ToDo"
        assert result.confidence == 0.95
        assert "quote" in result.reason.lower()

    @pytest.mark.asyncio
    @patch("app.services.thread_classifier.AsyncOpenAI")
    async def test_classify_thread_waiting(self, mock_openai_class, db_session):
        mock_client = AsyncMock()
        mock_response = AsyncMock()
        mock_response.choices = [
            MagicMock(
                message=MagicMock(
                    content='{"status": "Waiting", "confidence": 0.88, "reason": "Waiting for client reply"}'
                )
            )
        ]
        mock_client.chat.completions.create = AsyncMock(return_value=mock_response)
        mock_openai_class.return_value = mock_client

        messages = [
            {
                "snippet": "Thanks for the quote, I'll review and get back to you",
                "payload": {
                    "headers": [
                        {"name": "Subject", "value": "Re: Quote Request"},
                        {"name": "From", "value": "Client <client@test.com>"},
                    ],
                    "body": {"data": ""},
                    "parts": [],
                },
            }
        ]

        result = await classify_thread("Quote Request", messages, 1, db_session)

        assert result.status == "Waiting"
        assert result.confidence == 0.88

    @pytest.mark.asyncio
    @patch("app.services.thread_classifier.AsyncOpenAI")
    async def test_classify_thread_done(self, mock_openai_class, db_session):
        mock_client = AsyncMock()
        mock_response = AsyncMock()
        mock_response.choices = [
            MagicMock(
                message=MagicMock(
                    content='{"status": "Done", "confidence": 0.92, "reason": "Newsletter, no action needed"}'
                )
            )
        ]
        mock_client.chat.completions.create = AsyncMock(return_value=mock_response)
        mock_openai_class.return_value = mock_client

        messages = [
            {
                "snippet": "Weekly Newsletter",
                "payload": {
                    "headers": [
                        {"name": "Subject", "value": "Weekly Newsletter"},
                        {"name": "From", "value": "newsletter@example.com"},
                    ],
                    "body": {"data": ""},
                    "parts": [],
                },
            }
        ]

        result = await classify_thread("Weekly Newsletter", messages, 1, db_session)

        assert result.status == "Done"
        assert result.confidence == 0.92

    @pytest.mark.asyncio
    @patch("app.services.thread_classifier.AsyncOpenAI")
    async def test_classify_thread_invalid_status_default_todo(self, mock_openai_class, db_session):
        mock_client = AsyncMock()
        mock_response = AsyncMock()
        mock_response.choices = [
            MagicMock(
                message=MagicMock(
                    content='{"status": "InvalidStatus", "confidence": 0.5, "reason": "Test"}'
                )
            )
        ]
        mock_client.chat.completions.create = AsyncMock(return_value=mock_response)
        mock_openai_class.return_value = mock_client

        messages = [{"snippet": "", "payload": {"headers": [], "body": {}, "parts": []}}]

        result = await classify_thread("Test", messages, 1, db_session)

        assert result.status == "ToDo"

    @pytest.mark.asyncio
    @patch("app.services.thread_classifier.AsyncOpenAI")
    async def test_classify_thread_api_error_returns_default(self, mock_openai_class, db_session):
        mock_client = AsyncMock()
        mock_client.chat.completions.create = AsyncMock(side_effect=Exception("API Error"))
        mock_openai_class.return_value = mock_client

        messages = [{"snippet": "", "payload": {"headers": [], "body": {}, "parts": []}}]

        result = await classify_thread("Test", messages, 1, db_session)

        assert result.status == "ToDo"
        assert result.confidence == 0.3
        assert "failed" in result.reason.lower()


class TestClassifyThreadCategory:
    @pytest.mark.asyncio
    @patch("app.services.thread_classifier.AsyncOpenAI")
    async def test_classify_thread_category_primary(self, mock_openai_class, db_session, test_user):
        mock_client = AsyncMock()
        mock_response = AsyncMock()
        mock_response.choices = [
            MagicMock(
                message=MagicMock(
                    content='{"category": "Primary", "confidence": 0.92}'
                )
            )
        ]
        mock_client.chat.completions.create = AsyncMock(return_value=mock_response)
        mock_openai_class.return_value = mock_client

        messages = [
            {
                "snippet": "Can you help me?",
                "payload": {
                    "headers": [
                        {"name": "Subject", "value": "Help"},
                        {"name": "From", "value": "Colleague <colleague@company.com>"},
                    ],
                    "body": {"data": ""},
                    "parts": [],
                },
            }
        ]

        result, confidence = await classify_thread_category("Help", messages, 1, db_session)

        assert result == "Primary"
        assert confidence == 0.92

    @pytest.mark.asyncio
    @patch("app.services.thread_classifier.AsyncOpenAI")
    async def test_classify_thread_category_promotions(self, mock_openai_class, db_session, test_user):
        mock_client = AsyncMock()
        mock_response = AsyncMock()
        mock_response.choices = [
            MagicMock(
                message=MagicMock(
                    content='{"category": "Promotions", "confidence": 0.95}'
                )
            )
        ]
        mock_client.chat.completions.create = AsyncMock(return_value=mock_response)
        mock_openai_class.return_value = mock_client

        messages = [
            {
                "snippet": "50% off!",
                "payload": {
                    "headers": [
                        {"name": "Subject", "value": "Sale"},
                        {"name": "From", "value": "store@example.com"},
                    ],
                    "body": {"data": ""},
                    "parts": [],
                },
            }
        ]

        result, confidence = await classify_thread_category("Sale", messages, 1, db_session)

        assert result == "Promotions"
        assert confidence == 0.95


class TestClassifyThreadWithCategory:
    @pytest.mark.asyncio
    @patch("app.services.thread_classifier.AsyncOpenAI")
    async def test_classify_thread_with_category(self, mock_openai_class, db_session, test_user):
        mock_client = AsyncMock()
        
        status_response = AsyncMock()
        status_response.choices = [
            MagicMock(
                message=MagicMock(
                    content='{"status": "ToDo", "confidence": 0.90, "reason": "Needs response"}'
                )
            )
        ]
        
        category_response = AsyncMock()
        category_response.choices = [
            MagicMock(
                message=MagicMock(
                    content='{"category": "Primary", "confidence": 0.88}'
                )
            )
        ]
        
        async def create_side_effect(*args, **kwargs):
            if "status" in kwargs.get("messages", [[]])[0]["content"].lower():
                return status_response
            return category_response
        
        mock_client.chat.completions.create = AsyncMock(side_effect=create_side_effect)
        mock_openai_class.return_value = mock_client

        messages = [
            {
                "snippet": "Hello",
                "payload": {
                    "headers": [
                        {"name": "Subject", "value": "Hi"},
                        {"name": "From", "value": "John <john@test.com>"},
                    ],
                    "body": {"data": ""},
                    "parts": [],
                },
            }
        ]

        classification, category_id = await classify_thread_with_category(
            "Hi", messages, 1, db_session
        )

        assert classification.status == "ToDo"
        assert classification.confidence == 0.90
        assert classification.reason == "Needs response"


class TestThreadClassificationWithMockedLLM:
    @pytest.mark.asyncio
    @patch("app.services.thread_classifier.AsyncOpenAI")
    async def test_classify_thread_todo_mock(self, mock_openai_class):
        mock_client = AsyncMock()
        mock_response = AsyncMock()
        mock_response.choices = [
            MagicMock(
                message=MagicMock(
                    content='{"status": "ToDo", "confidence": 0.95, "reason": "Client requested quote"}'
                )
            )
        ]
        mock_client.chat.completions.create = AsyncMock(return_value=mock_response)
        mock_openai_class.return_value = mock_client

        from app.services.thread_classifier import classify_thread
        
        messages = [
            {
                "snippet": "Can you send me a quote?",
                "payload": {
                    "headers": [
                        {"name": "Subject", "value": "Quote Request"},
                        {"name": "From", "value": "Client <client@test.com>"},
                    ],
                    "body": {"data": ""},
                    "parts": [],
                },
            }
        ]

        class MockDB:
            pass
        
        result = await classify_thread("Quote Request", messages, 1, MockDB())

        assert result.status == "ToDo"
        assert result.confidence == 0.95

    @pytest.mark.asyncio
    @patch("app.services.thread_classifier.AsyncOpenAI")
    async def test_classify_thread_waiting_mock(self, mock_openai_class):
        mock_client = AsyncMock()
        mock_response = AsyncMock()
        mock_response.choices = [
            MagicMock(
                message=MagicMock(
                    content='{"status": "Waiting", "confidence": 0.88, "reason": "Waiting for client reply"}'
                )
            )
        ]
        mock_client.chat.completions.create = AsyncMock(return_value=mock_response)
        mock_openai_class.return_value = mock_client

        from app.services.thread_classifier import classify_thread
        
        messages = [
            {
                "snippet": "Thanks for the quote",
                "payload": {
                    "headers": [
                        {"name": "Subject", "value": "Re: Quote Request"},
                        {"name": "From", "value": "Client <client@test.com>"},
                    ],
                    "body": {"data": ""},
                    "parts": [],
                },
            }
        ]

        class MockDB:
            pass
        
        result = await classify_thread("Quote Request", messages, 1, MockDB())

        assert result.status == "Waiting"
        assert result.confidence == 0.88
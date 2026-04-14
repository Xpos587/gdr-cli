"""Tests for chat.py — session management, multi-turn, listing."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from chat import send_message, list_recent_chats, read_chat_history, continue_chat


class TestSendMessage:
    def test_single_message_returns_text(self):
        mock_client = MagicMock()
        mock_session = MagicMock()
        mock_output = MagicMock()
        mock_output.text = "Hello!"
        mock_session.send_message = AsyncMock(return_value=mock_output)
        mock_client.start_chat.return_value = mock_session
        mock_client.close = AsyncMock()

        with patch("chat._create_client", return_value=mock_client):
            import asyncio
            result = asyncio.run(send_message("Hi"))

        assert result == "Hello!"
        mock_client.close.assert_called_once()


class TestListRecentChats:
    def test_returns_chat_info_list(self):
        mock_client = MagicMock()
        mock_chat_info = MagicMock()
        mock_chat_info.cid = "c_abc123"
        mock_chat_info.title = "Test Chat"
        mock_chat_info.is_pinned = False
        mock_chat_info.timestamp = 1745000000.0
        mock_client.list_chats.return_value = [mock_chat_info]
        mock_client.close = AsyncMock()

        with patch("chat._create_client", return_value=mock_client):
            chats = list_recent_chats(profile="default")

        assert len(chats) == 1
        assert chats[0]["cid"] == "c_abc123"
        assert chats[0]["title"] == "Test Chat"

    def test_returns_empty_list_when_no_chats(self):
        mock_client = MagicMock()
        mock_client.list_chats.return_value = []
        mock_client.close = AsyncMock()

        with patch("chat._create_client", return_value=mock_client):
            chats = list_recent_chats(profile="default")

        assert chats == []


class TestReadChatHistory:
    def test_returns_turns(self):
        mock_client = MagicMock()
        mock_turn = MagicMock()
        mock_turn.role = "user"
        mock_turn.text = "Hello"
        mock_history = MagicMock()
        mock_history.cid = "c_abc123"
        mock_history.turns = [mock_turn]
        mock_client.read_chat = AsyncMock(return_value=mock_history)
        mock_client.close = AsyncMock()

        with patch("chat._create_client", return_value=mock_client):
            import asyncio
            history = asyncio.run(read_chat_history("c_abc123", profile="default"))

        assert history["cid"] == "c_abc123"
        assert len(history["turns"]) == 1
        assert history["turns"][0]["role"] == "user"

    def test_returns_none_when_chat_not_found(self):
        mock_client = MagicMock()
        mock_client.read_chat = AsyncMock(return_value=None)
        mock_client.close = AsyncMock()

        with patch("chat._create_client", return_value=mock_client):
            import asyncio
            history = asyncio.run(read_chat_history("c_nonexistent", profile="default"))

        assert history is None


class TestContinueChat:
    def test_sends_followup_message(self):
        mock_client = MagicMock()
        mock_session = MagicMock()
        mock_session.metadata = ["c_abc", "r_def", "rc_ghi"]
        mock_session.cid = "c_abc"
        mock_session.rid = "r_def"
        mock_output = MagicMock()
        mock_output.text = "The capital is Berlin."
        mock_output.metadata = ["c_abc", "r_new", "rc_new"]
        mock_session.send_message = AsyncMock(return_value=mock_output)
        mock_client.start_chat.return_value = mock_session
        mock_client.close = AsyncMock()

        with patch("chat._create_client", return_value=mock_client):
            import asyncio
            result = asyncio.run(continue_chat("What about Germany?", metadata=["c_abc", "r_def", "rc_ghi"], profile="default"))

        assert result == "The capital is Berlin."
        mock_client.start_chat.assert_called_once_with(metadata=["c_abc", "r_def", "rc_ghi"])

    def test_continues_without_metadata(self):
        mock_client = MagicMock()
        mock_session = MagicMock()
        mock_output = MagicMock()
        mock_output.text = "New chat."
        mock_output.metadata = ["c_new", "r_new", "rc_new"]
        mock_session.send_message = AsyncMock(return_value=mock_output)
        mock_client.start_chat.return_value = mock_session
        mock_client.close = AsyncMock()

        with patch("chat._create_client", return_value=mock_client):
            import asyncio
            result = asyncio.run(continue_chat("Hello", profile="default"))

        assert result == "New chat."
        mock_client.start_chat.assert_called_once_with()

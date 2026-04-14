"""Tests for repl.py — interactive chat REPL."""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from gdr_cli.repl import ChatRepl


class TestChatReplInit:
    def test_creates_repl_with_defaults(self):
        with patch("gdr_cli.repl._create_client") as mock_create:
            mock_client = MagicMock()
            mock_session = MagicMock()
            mock_client.start_chat.return_value = mock_session
            mock_create.return_value = mock_client

            repl = ChatRepl(profile="default")
            mock_create.assert_not_called()  # Lazy init

    def test_start_creates_client(self):
        with patch("gdr_cli.repl._create_client") as mock_create:
            mock_client = MagicMock()
            mock_session = MagicMock()
            mock_client.start_chat.return_value = mock_session
            mock_create.return_value = mock_client

            repl = ChatRepl(profile="default")
            asyncio.run(repl.start())

            mock_create.assert_called_once()
            mock_client.start_chat.assert_called_once()

    def test_start_with_metadata(self):
        with patch("gdr_cli.repl._create_client") as mock_create:
            mock_client = MagicMock()
            mock_session = MagicMock()
            mock_client.start_chat.return_value = mock_session
            mock_create.return_value = mock_client

            repl = ChatRepl(profile="default", metadata=["c_abc", "r_def", "rc_ghi"])
            asyncio.run(repl.start())

            mock_client.start_chat.assert_called_once_with(metadata=["c_abc", "r_def", "rc_ghi"])

    def test_cid_returns_session_cid(self):
        with patch("gdr_cli.repl._create_client") as mock_create:
            mock_client = MagicMock()
            mock_session = MagicMock()
            mock_session.cid = "c_abc123"
            mock_client.start_chat.return_value = mock_session
            mock_create.return_value = mock_client

            repl = ChatRepl(profile="default")
            asyncio.run(repl.start())

            assert repl.cid == "c_abc123"

    def test_cid_none_before_start(self):
        repl = ChatRepl(profile="default")
        assert repl.cid is None


class TestChatReplSend:
    def test_send_message_updates_metadata(self):
        with patch("gdr_cli.repl._create_client") as mock_create:
            mock_client = MagicMock()
            mock_session = MagicMock()
            mock_output = MagicMock()
            mock_output.text = "Hello!"
            mock_output.metadata = ["c_abc", "r_new", "rc_new"]
            mock_session.send_message = AsyncMock(return_value=mock_output)
            mock_session.cid = "c_abc"
            mock_session.rid = "r_new"
            mock_session.rcid = "rc_new"
            mock_client.start_chat.return_value = mock_session
            mock_create.return_value = mock_client

            repl = ChatRepl(profile="default")
            asyncio.run(repl.start())
            text = asyncio.run(repl.send("Hi there"))

            assert text == "Hello!"
            assert repl.metadata == ["c_abc", "r_new", "rc_new"]
            assert repl._turn_count == 1

    def test_send_empty_raises(self):
        with patch("gdr_cli.repl._create_client") as mock_create:
            mock_client = MagicMock()
            mock_client.start_chat.return_value = MagicMock()
            mock_create.return_value = mock_client

            repl = ChatRepl(profile="default")
            asyncio.run(repl.start())

            with pytest.raises(ValueError, match="empty"):
                asyncio.run(repl.send(""))

    def test_send_increments_turn_count(self):
        with patch("gdr_cli.repl._create_client") as mock_create:
            mock_client = MagicMock()
            mock_session = MagicMock()
            mock_output = MagicMock()
            mock_output.text = "Response"
            mock_output.metadata = ["c", "r1", "rc1"]
            mock_session.send_message = AsyncMock(return_value=mock_output)
            mock_client.start_chat.return_value = mock_session
            mock_create.return_value = mock_client

            repl = ChatRepl(profile="default")
            asyncio.run(repl.start())
            asyncio.run(repl.send("First"))
            asyncio.run(repl.send("Second"))

            assert repl._turn_count == 2


class TestChatReplClose:
    def test_close_clears_client(self):
        with patch("gdr_cli.repl._create_client") as mock_create:
            mock_client = MagicMock()
            mock_client.close = AsyncMock()
            mock_client.start_chat.return_value = MagicMock()
            mock_create.return_value = mock_client

            repl = ChatRepl(profile="default")
            asyncio.run(repl.start())
            assert repl.is_active

            asyncio.run(repl.close())
            assert not repl.is_active
            mock_client.close.assert_called_once()

    def test_close_when_not_started(self):
        repl = ChatRepl(profile="default")
        asyncio.run(repl.close())  # Should not raise

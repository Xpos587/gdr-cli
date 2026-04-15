"""Tests for repl.py — interactive chat REPL."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from repl import ChatRepl, _format_response, run_repl


class TestChatReplInit:
  def test_creates_repl_with_defaults(self):
    with patch("repl._create_client") as mock_create:
      mock_client = MagicMock()
      mock_session = MagicMock()
      mock_client.start_chat.return_value = mock_session
      mock_create.return_value = mock_client

      repl = ChatRepl(profile="default")
      del repl  # Unused - testing lazy init
      mock_create.assert_not_called()  # Lazy init

  def test_start_creates_client(self):
    with patch("repl._create_client") as mock_create:
      mock_client = MagicMock()
      mock_session = MagicMock()
      mock_client.start_chat.return_value = mock_session
      mock_create.return_value = mock_client

      repl = ChatRepl(profile="default")
      asyncio.run(repl.start())

      mock_create.assert_called_once()
      mock_client.start_chat.assert_called_once()

  def test_start_with_metadata(self):
    with patch("repl._create_client") as mock_create:
      mock_client = MagicMock()
      mock_session = MagicMock()
      mock_client.start_chat.return_value = mock_session
      mock_create.return_value = mock_client

      repl = ChatRepl(profile="default", metadata=["c_abc", "r_def", "rc_ghi"])
      asyncio.run(repl.start())

      mock_client.start_chat.assert_called_once_with(metadata=["c_abc", "r_def", "rc_ghi"])

  def test_cid_returns_session_cid(self):
    with patch("repl._create_client") as mock_create:
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

  def test_is_active_false_before_start(self):
    repl = ChatRepl(profile="default")
    assert not repl.is_active

  def test_is_active_true_after_start(self):
    with patch("repl._create_client") as mock_create:
      mock_client = MagicMock()
      mock_client.start_chat.return_value = MagicMock()
      mock_create.return_value = mock_client

      repl = ChatRepl(profile="default")
      asyncio.run(repl.start())
      assert repl.is_active


class TestChatReplSend:
  def test_send_message_updates_metadata(self):
    with patch("repl._create_client") as mock_create:
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
    with patch("repl._create_client") as mock_create:
      mock_client = MagicMock()
      mock_client.start_chat.return_value = MagicMock()
      mock_create.return_value = mock_client

      repl = ChatRepl(profile="default")
      asyncio.run(repl.start())

      with pytest.raises(ValueError, match="empty"):
        asyncio.run(repl.send(""))

  def test_send_whitespace_raises(self):
    with patch("repl._create_client") as mock_create:
      mock_client = MagicMock()
      mock_client.start_chat.return_value = MagicMock()
      mock_create.return_value = mock_client

      repl = ChatRepl(profile="default")
      asyncio.run(repl.start())

      with pytest.raises(ValueError, match="empty"):
        asyncio.run(repl.send("   "))

  def test_send_increments_turn_count(self):
    with patch("repl._create_client") as mock_create:
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

  def test_send_updates_metadata_each_turn(self):
    with patch("repl._create_client") as mock_create:
      mock_client = MagicMock()
      mock_session = MagicMock()
      mock_output1 = MagicMock()
      mock_output1.text = "R1"
      mock_output1.metadata = ["c", "r1", "rc1"]
      mock_output2 = MagicMock()
      mock_output2.text = "R2"
      mock_output2.metadata = ["c", "r2", "rc2"]
      mock_session.send_message = AsyncMock(side_effect=[mock_output1, mock_output2])
      mock_client.start_chat.return_value = mock_session
      mock_create.return_value = mock_client

      repl = ChatRepl(profile="default")
      asyncio.run(repl.start())
      asyncio.run(repl.send("First"))
      assert repl.metadata == ["c", "r1", "rc1"]
      asyncio.run(repl.send("Second"))
      assert repl.metadata == ["c", "r2", "rc2"]


class TestChatReplClose:
  def test_close_clears_client(self):
    with patch("repl._create_client") as mock_create:
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

  def test_close_clears_session(self):
    with patch("repl._create_client") as mock_create:
      mock_client = MagicMock()
      mock_client.close = AsyncMock()
      mock_client.start_chat.return_value = MagicMock()
      mock_create.return_value = mock_client

      repl = ChatRepl(profile="default")
      asyncio.run(repl.start())
      asyncio.run(repl.close())

      assert repl._session is None
      assert repl.cid is None


class TestFormatResponse:
  def test_formats_text(self, capsys):
    _format_response("Hello **world**")
    # Rich renders markdown — just check no error

  def test_formats_empty(self):
    _format_response("")


class TestRunRepl:
  @patch("prompt_toolkit.PromptSession")
  @patch("repl._create_client")
  def test_run_repl_quit_immediately(self, mock_create, mock_session_cls):
    mock_client = MagicMock()
    mock_session_obj = MagicMock()
    mock_session_obj.cid = "c_abc"
    mock_output = MagicMock()
    mock_output.text = "Hi"
    mock_output.metadata = ["c", "r", "rc"]
    mock_session_obj.send_message = AsyncMock(return_value=mock_output)
    mock_client.start_chat.return_value = mock_session_obj
    mock_client.close = AsyncMock()
    mock_create.return_value = mock_client

    prompt_session = MagicMock()
    prompt_session.prompt.side_effect = ["/quit"]
    mock_session_cls.return_value = prompt_session

    asyncio.run(run_repl(profile="default"))

    mock_client.close.assert_called_once()

  @patch("prompt_toolkit.PromptSession")
  @patch("repl._create_client")
  def test_run_repl_with_metadata_shows_resumed(self, mock_create, mock_session_cls):
    mock_client = MagicMock()
    mock_session_obj = MagicMock()
    mock_session_obj.cid = "c_abc"
    mock_client.start_chat.return_value = mock_session_obj
    mock_client.close = AsyncMock()
    mock_create.return_value = mock_client

    prompt_session = MagicMock()
    prompt_session.prompt.side_effect = ["/quit"]
    mock_session_cls.return_value = prompt_session

    asyncio.run(run_repl(profile="default", metadata=["c_abc", "r_def"]))

    mock_client.start_chat.assert_called_once_with(metadata=["c_abc", "r_def"])

  @patch("prompt_toolkit.PromptSession")
  @patch("repl._create_client")
  def test_run_repl_sends_message(self, mock_create, mock_session_cls):
    mock_client = MagicMock()
    mock_session_obj = MagicMock()
    mock_session_obj.cid = "c_abc"
    mock_output = MagicMock()
    mock_output.text = "Response"
    mock_output.metadata = ["c", "r", "rc"]
    mock_session_obj.send_message = AsyncMock(return_value=mock_output)
    mock_client.start_chat.return_value = mock_session_obj
    mock_client.close = AsyncMock()
    mock_create.return_value = mock_client

    prompt_session = MagicMock()
    prompt_session.prompt.side_effect = ["Hello", "/quit"]
    mock_session_cls.return_value = prompt_session

    asyncio.run(run_repl(profile="default"))

    mock_session_obj.send_message.assert_called_once_with("Hello")

  @patch("prompt_toolkit.PromptSession")
  @patch("repl._create_client")
  def test_run_repl_skips_empty_input(self, mock_create, mock_session_cls):
    mock_client = MagicMock()
    mock_session_obj = MagicMock()
    mock_session_obj.cid = "c_abc"
    mock_client.start_chat.return_value = mock_session_obj
    mock_client.close = AsyncMock()
    mock_create.return_value = mock_client

    prompt_session = MagicMock()
    prompt_session.prompt.side_effect = ["", "   ", "/quit"]
    mock_session_cls.return_value = prompt_session

    asyncio.run(run_repl(profile="default"))

    # send_message should never be called
    assert not mock_session_obj.send_message.called

  @patch("prompt_toolkit.PromptSession")
  @patch("repl._create_client")
  def test_run_repl_help_command(self, mock_create, mock_session_cls):
    mock_client = MagicMock()
    mock_session_obj = MagicMock()
    mock_session_obj.cid = "c_abc"
    mock_client.start_chat.return_value = mock_session_obj
    mock_client.close = AsyncMock()
    mock_create.return_value = mock_client

    prompt_session = MagicMock()
    prompt_session.prompt.side_effect = ["/help", "/quit"]
    mock_session_cls.return_value = prompt_session

    asyncio.run(run_repl(profile="default"))

    # Should not raise, just print help

  @patch("prompt_toolkit.PromptSession")
  @patch("repl._create_client")
  def test_run_repl_cid_command(self, mock_create, mock_session_cls):
    mock_client = MagicMock()
    mock_session_obj = MagicMock()
    mock_session_obj.cid = "c_test123"
    mock_client.start_chat.return_value = mock_session_obj
    mock_client.close = AsyncMock()
    mock_create.return_value = mock_client

    prompt_session = MagicMock()
    prompt_session.prompt.side_effect = ["/cid", "/quit"]
    mock_session_cls.return_value = prompt_session

    asyncio.run(run_repl(profile="default"))

    # Should not raise

  @patch("prompt_toolkit.PromptSession")
  @patch("repl._create_client")
  def test_run_repl_history_command(self, mock_create, mock_session_cls):
    mock_client = MagicMock()
    mock_session_obj = MagicMock()
    mock_session_obj.cid = "c_abc"
    mock_output = MagicMock()
    mock_output.text = "R"
    mock_output.metadata = ["c", "r", "rc"]
    mock_session_obj.send_message = AsyncMock(return_value=mock_output)
    mock_client.start_chat.return_value = mock_session_obj
    mock_client.close = AsyncMock()
    mock_create.return_value = mock_client

    prompt_session = MagicMock()
    prompt_session.prompt.side_effect = ["hi", "/history", "/quit"]
    mock_session_cls.return_value = prompt_session

    asyncio.run(run_repl(profile="default"))

    # Should not raise

  @patch("prompt_toolkit.PromptSession")
  @patch("repl._create_client")
  def test_run_repl_unknown_command(self, mock_create, mock_session_cls):
    mock_client = MagicMock()
    mock_session_obj = MagicMock()
    mock_session_obj.cid = "c_abc"
    mock_client.start_chat.return_value = mock_session_obj
    mock_client.close = AsyncMock()
    mock_create.return_value = mock_client

    prompt_session = MagicMock()
    prompt_session.prompt.side_effect = ["/unknown", "/quit"]
    mock_session_cls.return_value = prompt_session

    asyncio.run(run_repl(profile="default"))

    # Should print warning, not raise

  @patch("prompt_toolkit.PromptSession")
  @patch("repl._create_client")
  def test_run_repl_eof_exits(self, mock_create, mock_session_cls):
    mock_client = MagicMock()
    mock_session_obj = MagicMock()
    mock_session_obj.cid = "c_abc"
    mock_client.start_chat.return_value = mock_session_obj
    mock_client.close = AsyncMock()
    mock_create.return_value = mock_client

    prompt_session = MagicMock()
    prompt_session.prompt.side_effect = EOFError
    mock_session_cls.return_value = prompt_session

    asyncio.run(run_repl(profile="default"))

    mock_client.close.assert_called_once()

  @patch("prompt_toolkit.PromptSession")
  @patch("repl._create_client")
  def test_run_repl_send_error_breaks_loop(self, mock_create, mock_session_cls):
    mock_client = MagicMock()
    mock_session_obj = MagicMock()
    mock_session_obj.cid = "c_abc"
    mock_session_obj.send_message = AsyncMock(side_effect=RuntimeError("boom"))
    mock_client.start_chat.return_value = mock_session_obj
    mock_client.close = AsyncMock()
    mock_create.return_value = mock_client

    prompt_session = MagicMock()
    prompt_session.prompt.side_effect = ["hi"]  # Only one prompt before error
    mock_session_cls.return_value = prompt_session

    asyncio.run(run_repl(profile="default"))

    mock_client.close.assert_called_once()

  @patch("prompt_toolkit.PromptSession")
  @patch("repl._create_client")
  def test_run_repl_keyboard_interrupt_exits(self, mock_create, mock_session_cls):
    mock_client = MagicMock()
    mock_session_obj = MagicMock()
    mock_session_obj.cid = "c_abc"
    mock_client.start_chat.return_value = mock_session_obj
    mock_client.close = AsyncMock()
    mock_create.return_value = mock_client

    prompt_session = MagicMock()
    prompt_session.prompt.side_effect = KeyboardInterrupt
    mock_session_cls.return_value = prompt_session

    asyncio.run(run_repl(profile="default"))

    mock_client.close.assert_called_once()

  @patch("prompt_toolkit.PromptSession")
  @patch("repl._create_client")
  def test_run_repl_value_error_continues(self, mock_create, mock_session_cls):
    mock_client = MagicMock()
    mock_session_obj = MagicMock()
    mock_session_obj.cid = "c_abc"
    mock_output = MagicMock()
    mock_output.text = "ok"
    mock_output.metadata = ["c", "r", "rc"]
    # First call raises ValueError (empty), second succeeds
    mock_session_obj.send_message = AsyncMock(side_effect=[ValueError("empty"), mock_output])
    mock_client.start_chat.return_value = mock_session_obj
    mock_client.close = AsyncMock()
    mock_create.return_value = mock_client

    prompt_session = MagicMock()
    prompt_session.prompt.side_effect = ["", "hi", "/quit"]
    mock_session_cls.return_value = prompt_session

    asyncio.run(run_repl(profile="default"))

    # send_message called once (empty string skipped before send), then "hi" succeeds
    assert mock_session_obj.send_message.call_count == 1

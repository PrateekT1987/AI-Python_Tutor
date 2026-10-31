"""Tests for Python Tutor PyQt6 core logic."""

from __future__ import annotations

import sys
import os

# Set up offscreen platform before any Qt imports
os.environ['QT_QPA_PLATFORM'] = 'offscreen'

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from src.core.config import Config
from src.core.settings import (
    load_settings, save_settings, load_session, save_session, 
    clear_session, fit_messages
)
from src.core.parsers import (
    parse_blocks, parse_inline, parse_table, format_table,
    render_inline_html, render_text_html
)
from src.prompts import build_system_prompt, STARTERS, LEVELS
from src.core.workers import LLMWorker
from src.core.workers.llm_worker import ApiError


class TestConfig:
    def test_config_defaults(self, tmp_path):
        # Never touch the real per-user config: point at a temp path so a
        # stale saved value cannot make the defaults assertion flaky.
        c = Config(_config_path=tmp_path / "config.json")
        assert c.openrouter_base_url == "https://openrouter.ai/api/v1"
        assert c.model == "nvidia/nemotron-3-ultra-550b-a55b:free"
        assert c.temperature == 0.4
        assert c.max_tokens == 2000
        assert c.level == "Intermediate"

    def test_config_headers(self):
        c = Config()
        c.openrouter_api_key = "test-key"
        headers = c.headers
        assert headers["Authorization"] == "Bearer test-key"
        assert headers["Content-Type"] == "application/json; charset=utf-8"
        assert headers["Accept"] == "text/event-stream; charset=utf-8"

    def test_chat_completions_url(self):
        c = Config()
        c.openrouter_base_url = "https://api.example.com/v1"
        assert c.chat_completions_url == "https://api.example.com/v1/chat/completions"

    def test_saved_model_wins_over_default(self, tmp_path):
        """A model chosen in Settings must survive a restart."""
        path = tmp_path / "config.json"
        first = Config(_config_path=path)
        first.model = "saved/model"
        first.save()

        second = Config(_config_path=path)
        second.model = "env/default"
        second.load()
        assert second.model == "saved/model"


class TestSettings:
    def test_load_settings_defaults(self):
        clear_session()
        # Also clear settings by saving defaults
        save_settings({
            "level": "Intermediate",
            "model": "",
            "temperature": 0.4,
            "max_tokens": 2000,
            "geometry": "",
            "sandbox_memory_mb": 512,
            "sandbox_allow_network": False,
        })
        s = load_settings()
        assert s["level"] == "Intermediate"
        assert s["temperature"] == 0.4
    
    def test_save_and_load_settings(self):
        test_settings = {
            "level": "Advanced",
            "model": "test/model",
            "temperature": 0.7,
            "max_tokens": 1000,
            "geometry": "800x600",
            "sandbox_memory_mb": 256,
            "sandbox_allow_network": True,
        }
        save_settings(test_settings)
        loaded = load_settings()
        assert loaded["level"] == "Advanced"
        assert loaded["model"] == "test/model"
        assert loaded["temperature"] == 0.7
    
    def test_session_roundtrip(self):
        history = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi there!"},
        ]
        save_session(history)
        loaded = load_session()
        assert loaded == history
    
    def test_session_filters_bad_entries(self):
        bad_history = [
            {"role": "user", "content": "Valid"},
            {"role": "invalid", "content": "Should be filtered"},
            {"role": "assistant", "content": 123},  # Not a string
            "not a dict",
            {"role": "assistant", "content": "Also valid"},
        ]
        save_session(bad_history)
        loaded = load_session()
        assert len(loaded) == 2
        assert loaded[0]["content"] == "Valid"
        assert loaded[1]["content"] == "Also valid"
    
    def test_clear_session(self):
        save_session([{"role": "user", "content": "Test"}])
        clear_session()
        assert load_session() == []


class TestFitMessages:
    def test_fit_messages_under_budget(self):
        messages = [
            {"role": "system", "content": "System prompt"},
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi!"},
        ]
        result = fit_messages(messages, max_chars=1000)
        assert result == messages
    
    def test_fit_messages_drops_oldest(self):
        messages = [
            {"role": "system", "content": "System"},
            {"role": "user", "content": "Old message " * 50},
            {"role": "assistant", "content": "Old reply " * 50},
            {"role": "user", "content": "New message"},
            {"role": "assistant", "content": "New reply"},
        ]
        result = fit_messages(messages, max_chars=200)
        # Should keep system + newest turns
        assert result[0]["role"] == "system"
        assert "New message" in result[-2]["content"]
    
    def test_fit_messages_keeps_newest_oversized(self):
        messages = [
            {"role": "system", "content": "System"},
            {"role": "user", "content": "x" * 5000},
        ]
        result = fit_messages(messages, max_chars=100)
        assert len(result) == 2
        assert result[0]["role"] == "system"
        assert len(result[1]["content"]) <= 100


class TestParsers:
    def test_parse_blocks_plain_text(self):
        blocks = parse_blocks("hello world")
        assert len(blocks) == 1
        assert blocks[0].kind == "text"
        assert blocks[0].value == "hello world"
    
    def test_parse_blocks_fenced_code(self):
        blocks = parse_blocks("before\n```python\nprint('hi')\n```\nafter")
        assert len(blocks) == 3
        assert blocks[0].kind == "text"
        assert blocks[1].kind == "code"
        assert blocks[1].lang == "python"
        assert blocks[1].value == "print('hi')"
        assert blocks[2].kind == "text"
    
    def test_parse_blocks_info_string(self):
        blocks = parse_blocks('```python title="demo"\nx = 1\n```')
        assert len(blocks) == 1
        assert blocks[0].lang == "python"
        assert blocks[0].value == "x = 1"
    
    def test_parse_blocks_table(self):
        md = "| A | B |\n|---|---|\n| 1 | 2 |"
        blocks = parse_blocks(md)
        assert len(blocks) == 1
        assert blocks[0].kind == "table"
        assert "A" in blocks[0].value and "B" in blocks[0].value
    
    def test_parse_inline_bold(self):
        spans = parse_inline("**bold**")
        assert len(spans) == 1
        assert spans[0].type == "bold"
        assert spans[0].text == "bold"
    
    def test_parse_inline_italic(self):
        spans = parse_inline("*italic*")
        assert len(spans) == 1
        assert spans[0].type == "italic"
        assert spans[0].text == "italic"
    
    def test_parse_inline_code(self):
        spans = parse_inline("`code`")
        assert len(spans) == 1
        assert spans[0].type == "code"
        assert spans[0].text == "code"
    
    def test_parse_inline_mixed(self):
        spans = parse_inline("**bold** and *italic* and `code`")
        types = [s.type for s in spans]
        assert types == ["bold", "text", "italic", "text", "code"]
    
    def test_parse_table(self):
        md = "| A | B |\n|---|---|\n| 1 | 2 |"
        rows, widths = parse_table(md)
        assert rows == [["A", "B"], ["1", "2"]]
        assert widths == [1, 1]
    
    def test_format_table(self):
        rows = [["A", "B"], ["1", "2"]]
        widths = [1, 1]
        formatted = format_table(rows, widths)
        assert "│" in formatted
        assert "─┼─" in formatted


class TestMarkdownRendering:
    def test_paragraphs_are_separate(self):
        html = render_text_html("First paragraph.\n\nSecond paragraph.")
        assert html.count("<p") >= 2
        assert "First paragraph." in html
        assert "Second paragraph." in html

    def test_text_is_escaped(self):
        html = render_text_html("if x < 3 and a & b")
        assert "&lt; 3" in html
        assert "&amp;" in html

    def test_inline_markup_and_links(self):
        html = render_inline_html("**bold** and `code` and [docs](https://example.com)")
        assert "<strong>bold</strong>" in html
        assert "<code" in html
        assert 'href="https://example.com"' in html

    def test_unsafe_links_are_not_emitted(self):
        html = render_inline_html("[click](javascript:alert(1))")
        assert "href" not in html
        assert "click" in html

    def test_lists_and_headings(self):
        html = render_text_html("## Title\n\n- one\n- two\n\n1. first")
        assert "Title" in html
        assert "<ul" in html and "<ol" in html
        assert "<li" in html


class TestPrompts:
    def test_levels_defined(self):
        assert LEVELS == ["Beginner", "Intermediate", "Advanced"]
    
    def test_starters_for_each_level(self):
        for level in LEVELS:
            assert level in STARTERS
            assert len(STARTERS[level]) >= 3
    
    def test_build_system_prompt(self):
        for level in LEVELS:
            prompt = build_system_prompt(level)
            assert "Python tutor" in prompt
            assert len(prompt) > 100  # Substantial prompt
    
    def test_unknown_level_fallback(self):
        prompt = build_system_prompt("Unknown")
        # Should not crash, falls back to Intermediate
        assert "Python tutor" in prompt


class TestLLMWorker:
    def test_worker_creation(self):
        worker = LLMWorker(
            messages=[{"role": "user", "content": "test"}],
            model="test/model",
            temperature=0.5,
            max_tokens=100
        )
        assert worker.model == "test/model"
        assert worker.temperature == 0.5
        assert worker.max_tokens == 100
        assert not worker._cancelled
    
    def test_cancel(self):
        worker = LLMWorker(
            messages=[{"role": "user", "content": "test"}],
            model="test/model",
            temperature=0.5,
            max_tokens=100
        )
        worker.cancel()
        assert worker._cancelled
    
    def test_looks_truncated(self):
        worker = LLMWorker(
            messages=[{"role": "user", "content": "test"}],
            model="test/model",
            temperature=0.5,
            max_tokens=100
        )
        assert worker._looks_truncated("```python\nx = 1") is True
        assert worker._looks_truncated("complete answer") is False
        assert worker._looks_truncated("complete", truncated=True) is True

    @staticmethod
    def _worker() -> LLMWorker:
        return LLMWorker(
            messages=[{"role": "user", "content": "test"}],
            model="test/model",
            temperature=0.5,
            max_tokens=100,
        )

    @staticmethod
    def _fake_post(status: int, body: str = "", extra_headers: dict | None = None):
        class FakeResponse:
            status_code = status
            text = body
            headers = extra_headers or {}

            def __enter__(self):
                return self

            def __exit__(self, *exc_info):
                return False

        return lambda *args, **kwargs: FakeResponse()

    def test_auth_failure_is_not_retried(self, monkeypatch):
        worker = self._worker()
        monkeypatch.setattr(
            "src.core.workers.llm_worker.requests.post",
            self._fake_post(401),
        )
        try:
            list(worker._stream_chat(worker.messages, {"truncated": False}))
        except ApiError as exc:
            assert exc.retryable is False
            assert "OPENROUTER_API_KEY" in str(exc)
        else:
            raise AssertionError("auth failure should raise")

    def test_rate_limit_is_retryable(self, monkeypatch):
        worker = self._worker()
        calls = []

        class FakeResponse:
            status_code = 429
            text = ""
            headers = {"Retry-After": "0"}

            def __enter__(self):
                return self

            def __exit__(self, *exc_info):
                return False

        def fake_post(*args, **kwargs):
            calls.append(args)
            return FakeResponse()

        monkeypatch.setattr("src.core.workers.llm_worker.requests.post", fake_post)
        monkeypatch.setattr(worker, "_sleep_or_cancel", lambda delay: None)
        try:
            list(worker._stream_chat(worker.messages, {"truncated": False}))
        except ApiError as exc:
            assert exc.retryable is True
        else:
            raise AssertionError("rate limit should raise once retries are exhausted")
        assert len(calls) == worker.MAX_RETRIES + 1


if __name__ == "__main__":
    import pytest
    sys.exit(pytest.main([__file__, "-v"]))
"""Worker threads for LLM streaming and connection checks."""

from __future__ import annotations

import json
import time
from typing import Iterator

from PyQt6.QtCore import QThread, QObject, pyqtSignal
import requests

from src.core.config import config
from src.core.logging_setup import get_logger

log = get_logger(__name__)


class Cancelled(Exception):
    """Raised when streaming is cancelled."""
    pass


class ApiError(RuntimeError):
    """An HTTP error from the provider, with a retry decision attached."""

    def __init__(self, message: str, retryable: bool = False, retry_after: float = 0.0):
        super().__init__(message)
        self.retryable = retryable
        self.retry_after = retry_after


class LLMWorker(QObject):
    """Worker for streaming chat completions from OpenRouter."""

    token_received = pyqtSignal(str)
    finished = pyqtSignal(str, bool)  # text, truncated
    error = pyqtSignal(str)
    cancelled = pyqtSignal()
    status = pyqtSignal(str)

    # Retry settings
    MAX_RETRIES = 3
    RETRY_BASE_SECONDS = 0.8
    REQUEST_TIMEOUT = 60.0

    def __init__(self, messages: list[dict], model: str, temperature: float, max_tokens: int):
        super().__init__()
        self.messages = messages
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens
        self._cancelled = False
        self._text = ""

    def cancel(self):
        log.info("LLM streaming cancelled by user")
        self._cancelled = True

    def run(self):
        """Run the streaming chat completion."""
        self._text = ""
        flag = {"truncated": False}

        log.info("Starting LLM stream", model=self.model, temp=self.temperature, max_tokens=self.max_tokens)
        try:
            for token in self._stream_chat(self.messages, flag):
                if self._cancelled:
                    self.cancelled.emit()
                    return
                self._text += token
                self.token_received.emit(token)
        except Cancelled:
            log.info("LLM stream cancelled")
            self.cancelled.emit()
            return
        except Exception as exc:
            log.error("LLM stream error", error=str(exc))
            if len(self._text.strip()) >= 40:
                self.finished.emit(self._text, True)
                return
            self.error.emit(str(exc))
            return

        if not self._text.strip():
            log.warning("LLM returned empty response")
            self.error.emit("model returned an empty response")
            return

        # Auto-continue if the provider hit the token cap
        rounds = 0
        while self._looks_truncated(self._text, flag["truncated"]) and rounds < 2:
            if self._cancelled:
                self.cancelled.emit()
                return
            rounds += 1
            cont_messages = self.messages + [
                {"role": "assistant", "content": self._text},
                {"role": "user", "content": "Continue exactly where you left off."},
            ]
            flag = {"truncated": False}
            log.info("Auto-continuing truncated response", round=rounds)
            self.status.emit("Response was cut off — continuing…")
            try:
                for token in self._stream_chat(cont_messages, flag):
                    if self._cancelled:
                        self.cancelled.emit()
                        return
                    self._text += token
                    self.token_received.emit(token)
            except Cancelled:
                self.cancelled.emit()
                return
            except Exception as exc:
                log.warning("Continuation failed", error=str(exc))
                flag["truncated"] = True
                break

        log.info("LLM stream finished", truncated=flag["truncated"], chars=len(self._text))
        self.finished.emit(self._text, self._looks_truncated(self._text, flag["truncated"]))

    def _looks_truncated(self, text: str, truncated: bool = False) -> bool:
        if truncated:
            return True
        return text.count("```") % 2 == 1 or text.count("~~~") % 2 == 1

    def _retry_after(self, value: str | None) -> float:
        if not value:
            return 0.0
        try:
            return max(0.0, float(value.strip()))
        except ValueError:
            return 0.0

    def _sleep_or_cancel(self, delay: float):
        deadline = time.monotonic() + delay
        while True:
            if self._cancelled:
                raise Cancelled("stopped")
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                return
            time.sleep(min(0.2, remaining))

    def _iter_sse(self, resp, flag) -> Iterator[str]:
        # Ensure UTF-8 encoding for the response
        resp.encoding = "utf-8"
        # Read in tiny chunks so SSE deltas are surfaced as they arrive
        # instead of waiting for an internal 512-byte buffer to fill.
        for raw in resp.iter_lines(chunk_size=1, decode_unicode=True):
            if self._cancelled:
                raise Cancelled("stopped")
            if not raw:
                continue
            line = raw.strip()
            if not line.startswith("data:"):
                continue
            data = line[len("data:"):].strip()
            if not data or data == "[DONE]":
                continue
            try:
                chunk = json.loads(data)
            except json.JSONDecodeError:
                continue
            try:
                choice = chunk["choices"][0]
            except (KeyError, IndexError, TypeError):
                continue
            if flag is not None and choice.get("finish_reason") == "length":
                flag["truncated"] = True
            delta = choice.get("delta") or {}
            content = delta.get("content")
            if content:
                yield content

    def _stream_chat(self, messages: list[dict], flag: dict) -> Iterator[str]:
        """Yield text deltas for a streamed chat completion."""
        payload = {
            "model": self.model,
            "stream": True,
            "messages": messages,
            "max_tokens": self.max_tokens,
            "temperature": self.temperature,
        }

        attempt = 0
        while True:
            if self._cancelled:
                raise Cancelled("stopped")

            yielded = False
            try:
                log.debug("Sending request to OpenRouter", attempt=attempt, url=config.chat_completions_url)
                with requests.post(
                    config.chat_completions_url,
                    json=payload,
                    headers=config.headers,
                    stream=True,
                    timeout=(10, self.REQUEST_TIMEOUT),
                ) as resp:
                    status = resp.status_code
                    if status in (401, 403):
                        log.error("Authentication failed", status=status)
                        raise ApiError(
                            "authentication failed - check OPENROUTER_API_KEY "
                            "in Settings (Ctrl+,)"
                        )
                    if status == 429:
                        log.warning("Rate limited", status=status)
                        raise ApiError(
                            "rate limited",
                            retryable=True,
                            retry_after=self._retry_after(resp.headers.get("Retry-After")),
                        )
                    if status >= 500:
                        log.error("Server error", status=status)
                        raise ApiError(
                            f"OpenRouter returned HTTP {status}",
                            retryable=True,
                            retry_after=self._retry_after(resp.headers.get("Retry-After")),
                        )
                    if status >= 400:
                        detail = resp.text.strip().replace("\n", " ")[:160]
                        log.error("Client error", status=status, detail=detail)
                        raise ApiError(f"OpenRouter returned HTTP {status}: {detail}")

                    for piece in self._iter_sse(resp, flag):
                        yielded = True
                        yield piece
                    return

            except Cancelled:
                raise
            except requests.RequestException as exc:
                if yielded or attempt >= self.MAX_RETRIES:
                    log.error("Network error after retries", error=str(exc), attempts=attempt + 1)
                    raise RuntimeError(f"network error: {exc}") from exc
                delay = min(self.RETRY_BASE_SECONDS * (2 ** attempt), 10.0)
                detail = str(exc).splitlines()[0][:80]
                log.warning("Connection problem, retrying", error=detail, delay=delay, attempt=attempt + 1)
                self.status.emit(
                    f"Connection problem ({detail}) — retrying in {delay:.0f}s "
                    f"(attempt {attempt + 2}/{self.MAX_RETRIES + 1})…"
                )
                self._sleep_or_cancel(delay)
                attempt += 1

            except ApiError as exc:
                if not exc.retryable or yielded or attempt >= self.MAX_RETRIES:
                    log.error("API error (non-retryable or max retries)", error=str(exc), retryable=exc.retryable)
                    raise
                delay = max(self.RETRY_BASE_SECONDS * (2 ** attempt), exc.retry_after)
                detail = str(exc).splitlines()[0][:80]
                log.warning("Provider busy, retrying", error=detail, delay=delay, attempt=attempt + 1)
                self.status.emit(
                    f"Provider busy ({detail}) — retrying in {delay:.0f}s "
                    f"(attempt {attempt + 2}/{self.MAX_RETRIES + 1})…"
                )
                self._sleep_or_cancel(delay)
                attempt += 1

            except Exception as exc:
                if yielded or attempt >= self.MAX_RETRIES:
                    log.exception("Unexpected error in stream chat")
                    raise
                delay = self.RETRY_BASE_SECONDS * (2 ** attempt)
                detail = str(exc).splitlines()[0][:80]
                log.warning("Provider busy, retrying", error=detail, delay=delay, attempt=attempt + 1)
                self.status.emit(
                    f"Provider busy ({detail}) — retrying in {delay:.0f}s "
                    f"(attempt {attempt + 2}/{self.MAX_RETRIES + 1})…"
                )
                self._sleep_or_cancel(delay)
                attempt += 1


class LLMThread(QThread):
    """Thread wrapper for LLMWorker."""

    # Note: ``answer_finished`` is intentionally not called ``finished`` —
    # QThread already owns a no-argument ``finished`` signal.
    answer_finished = pyqtSignal(str, bool)
    error = pyqtSignal(str)
    token_received = pyqtSignal(str)
    cancelled = pyqtSignal()
    status = pyqtSignal(str)

    def __init__(self, messages: list[dict], model: str, temperature: float, max_tokens: int):
        super().__init__()
        self.worker = LLMWorker(messages, model, temperature, max_tokens)
        self.worker.moveToThread(self)

        # Forward worker signals
        self.started.connect(self.worker.run)
        self.worker.token_received.connect(self.token_received.emit)
        self.worker.status.connect(self.status.emit)
        self.worker.finished.connect(self.answer_finished.emit)
        self.worker.error.connect(self.error.emit)
        self.worker.cancelled.connect(self.cancelled.emit)

        # Tear down the worker, then stop this thread's event loop
        self.worker.finished.connect(self.worker.deleteLater)
        self.worker.error.connect(self.worker.deleteLater)
        self.worker.cancelled.connect(self.worker.deleteLater)
        self.worker.finished.connect(self.quit)
        self.worker.error.connect(self.quit)
        self.worker.cancelled.connect(self.quit)

    def cancel(self):
        self.worker.cancel()


class ConnectionTestThread(QThread):
    """Checks that the configured endpoint and API key are usable."""

    result = pyqtSignal(bool, str)

    def __init__(self, base_url: str, api_key: str):
        super().__init__()
        self.base_url = base_url
        self.api_key = api_key

    def run(self):
        base = self.base_url.rstrip("/")
        headers = {"Authorization": f"Bearer {self.api_key}"} if self.api_key else {}
        log.info("Testing connection", base_url=base, has_key=bool(self.api_key))
        try:
            resp = requests.get(f"{base}/auth/key", headers=headers, timeout=(5, 10))
            if resp.status_code == 200:
                log.info("Connection test passed", status=200)
                self.result.emit(True, "Connection OK — API key accepted.")
                return
            if resp.status_code in (401, 403):
                log.warning("Connection test: auth rejected", status=resp.status_code)
                self.result.emit(False, "API key rejected (HTTP 401/403).")
                return
            if resp.status_code == 404:
                # Some OpenRouter-compatible servers do not expose /auth/key.
                log.info("Auth endpoint not found, trying /models")
                check = requests.get(f"{base}/models", headers=headers, timeout=(5, 10))
                if check.status_code == 200:
                    log.info("Connection test passed via /models")
                    self.result.emit(True, "Server reachable (key could not be verified).")
                elif check.status_code in (401, 403):
                    log.warning("Connection test: auth rejected via /models")
                    self.result.emit(False, "API key rejected.")
                else:
                    log.warning("Connection test: unexpected status", status=check.status_code)
                    self.result.emit(False, f"Server returned HTTP {check.status_code}.")
                return
            log.warning("Connection test: unexpected status", status=resp.status_code)
            self.result.emit(False, f"Server returned HTTP {resp.status_code}.")
        except requests.RequestException as exc:
            log.error("Connection test: network error", error=str(exc))
            self.result.emit(False, f"Network error: {exc}")

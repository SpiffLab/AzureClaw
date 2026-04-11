"""Tests for ``azureclaw.llm.failover.FailoverChatClient``."""

from __future__ import annotations

import logging
from collections.abc import Mapping, Sequence
from typing import Any

import pytest
from agent_framework import BaseChatClient

import azureclaw
from azureclaw import FailoverChatClient, ProviderExhausted

# ─── Test fixtures: mock chat clients with controllable behavior ────────


class _CannedResponseClient(BaseChatClient):
    """A `BaseChatClient` that returns a sentinel string and records its calls.

    Subclasses :class:`BaseChatClient` (real, not a Protocol stub) so the
    failover client treats it like any production provider.
    """

    def __init__(self, response: str) -> None:
        super().__init__()
        self._response = response
        self.call_count = 0

    async def _inner_get_response(  # type: ignore[override]
        self,
        *,
        messages: Sequence[Any],
        stream: bool,
        options: Mapping[str, Any],
        **kwargs: Any,
    ) -> Any:
        self.call_count += 1
        return self._response


class _RaisingClient(BaseChatClient):
    """A `BaseChatClient` whose `get_response` raises a configurable exception.

    The exception class is dynamically named at construction so we can
    simulate transient vs non-transient errors without depending on the
    real provider SDKs at test time.
    """

    def __init__(self, exception_class_name: str, message: str = "boom") -> None:
        super().__init__()
        # Build a one-off Exception subclass with the requested name
        # so the failover client's class-name-based detection sees it.
        self._exc_class: type[Exception] = type(exception_class_name, (Exception,), {})
        self._message = message
        self.call_count = 0

    async def _inner_get_response(  # type: ignore[override]
        self,
        *,
        messages: Sequence[Any],
        stream: bool,
        options: Mapping[str, Any],
        **kwargs: Any,
    ) -> Any:
        self.call_count += 1
        raise self._exc_class(self._message)


# ─── Construction ────────────────────────────────────────────────────────


@pytest.mark.local
def test_construction_with_empty_list_raises() -> None:
    with pytest.raises(ValueError, match="provider"):
        FailoverChatClient(providers=[])


@pytest.mark.local
def test_construction_preserves_provider_order() -> None:
    a = _CannedResponseClient("a")
    b = _CannedResponseClient("b")
    c = _CannedResponseClient("c")

    failover = FailoverChatClient(providers=[a, b, c])

    assert failover._providers == [a, b, c]  # pyright: ignore[reportPrivateUsage]


# ─── Single-provider success ─────────────────────────────────────────────


@pytest.mark.local
async def test_first_provider_success_returns_without_consulting_others() -> None:
    a = _CannedResponseClient("from-a")
    b = _CannedResponseClient("from-b")

    failover = FailoverChatClient(providers=[a, b])
    result = await failover._inner_get_response(  # pyright: ignore[reportPrivateUsage]
        messages=[], stream=False, options={}
    )

    assert result == "from-a"
    assert a.call_count == 1
    assert b.call_count == 0


# ─── Transient failover ─────────────────────────────────────────────────


@pytest.mark.local
async def test_first_transient_fail_advances_to_second() -> None:
    a = _RaisingClient("RateLimitError")
    b = _CannedResponseClient("from-b")

    failover = FailoverChatClient(providers=[a, b])
    result = await failover._inner_get_response(  # pyright: ignore[reportPrivateUsage]
        messages=[], stream=False, options={}
    )

    assert result == "from-b"
    assert a.call_count == 1
    assert b.call_count == 1


@pytest.mark.local
async def test_api_connection_error_triggers_failover() -> None:
    a = _RaisingClient("APIConnectionError")
    b = _CannedResponseClient("from-b")

    failover = FailoverChatClient(providers=[a, b])
    result = await failover._inner_get_response(  # pyright: ignore[reportPrivateUsage]
        messages=[], stream=False, options={}
    )

    assert result == "from-b"


@pytest.mark.local
async def test_failover_logs_each_transient_error(
    caplog: pytest.LogCaptureFixture,
) -> None:
    a = _RaisingClient("APITimeoutError")
    b = _CannedResponseClient("from-b")

    failover = FailoverChatClient(providers=[a, b])
    with caplog.at_level(logging.WARNING):
        await failover._inner_get_response(  # pyright: ignore[reportPrivateUsage]
            messages=[], stream=False, options={}
        )

    assert any(
        "failing over" in rec.message and "APITimeoutError" in rec.message for rec in caplog.records
    )


# ─── Non-transient errors propagate immediately ─────────────────────────


@pytest.mark.local
async def test_non_transient_error_propagates_without_failover() -> None:
    a = _RaisingClient("AuthenticationError", message="bad key")
    b = _CannedResponseClient("from-b")

    failover = FailoverChatClient(providers=[a, b])
    with pytest.raises(Exception, match="bad key"):
        await failover._inner_get_response(  # pyright: ignore[reportPrivateUsage]
            messages=[], stream=False, options={}
        )

    assert a.call_count == 1
    assert b.call_count == 0  # second provider never consulted


# ─── ProviderExhausted ──────────────────────────────────────────────────


@pytest.mark.local
async def test_all_providers_transient_fail_raises_provider_exhausted() -> None:
    a = _RaisingClient("RateLimitError")
    b = _RaisingClient("APITimeoutError")
    c = _RaisingClient("InternalServerError")

    failover = FailoverChatClient(providers=[a, b, c])
    with pytest.raises(ProviderExhausted) as exc_info:
        await failover._inner_get_response(  # pyright: ignore[reportPrivateUsage]
            messages=[], stream=False, options={}
        )

    assert len(exc_info.value.errors) == 3
    error_class_names = [type(exc).__name__ for _, exc in exc_info.value.errors]
    assert error_class_names == [
        "RateLimitError",
        "APITimeoutError",
        "InternalServerError",
    ]


@pytest.mark.local
def test_provider_exhausted_message_is_informative() -> None:
    e = ProviderExhausted(
        errors=[
            ("ProviderA", RuntimeError("e1")),
            ("ProviderB", RuntimeError("e2")),
            ("ProviderC", RuntimeError("e3")),
        ]
    )
    assert "3" in str(e)
    assert "providers" in str(e).lower()


@pytest.mark.local
def test_provider_exhausted_is_runtime_error_subclass() -> None:
    assert issubclass(ProviderExhausted, RuntimeError)


@pytest.mark.local
def test_provider_exhausted_re_exported_from_package_root() -> None:
    assert hasattr(azureclaw, "ProviderExhausted")
    assert azureclaw.ProviderExhausted is ProviderExhausted


# ─── Streaming bypasses failover ────────────────────────────────────────


@pytest.mark.local
async def test_streaming_bypasses_failover_on_transient_error() -> None:
    a = _RaisingClient("RateLimitError")
    b = _CannedResponseClient("from-b")

    failover = FailoverChatClient(providers=[a, b])
    with pytest.raises(Exception):  # noqa: B017
        await failover._inner_get_response(  # pyright: ignore[reportPrivateUsage]
            messages=[], stream=True, options={}
        )

    assert a.call_count == 1
    assert b.call_count == 0  # streaming never advances to the next provider


@pytest.mark.local
async def test_streaming_success_returns_first_provider_response() -> None:
    a = _CannedResponseClient("stream-from-a")
    b = _CannedResponseClient("stream-from-b")

    failover = FailoverChatClient(providers=[a, b])
    result = await failover._inner_get_response(  # pyright: ignore[reportPrivateUsage]
        messages=[], stream=True, options={}
    )

    assert result == "stream-from-a"
    assert b.call_count == 0

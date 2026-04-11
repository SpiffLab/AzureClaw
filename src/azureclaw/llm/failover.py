"""Provider failover for AzureClaw's LLM stack.

The :class:`FailoverChatClient` wraps an ordered list of
:class:`agent_framework.BaseChatClient` instances and tries them in
declaration order. Transient errors (rate limits, connection failures,
5xx-class server errors) cause it to advance to the next provider.
Non-transient errors (authentication, validation) propagate immediately.
When every provider has been exhausted it raises :class:`ProviderExhausted`
with the per-provider error chain.

**Streaming caveat.** Streaming requests bypass failover and delegate to
the first provider only. Mid-stream retry across providers is unsafe
because chunks may already have been delivered to the user. The contract
is documented here and asserted by the spec scenarios.

Transient error detection is by class name string, not by class
identity. Each provider SDK ships its own exception hierarchy and the
class identities differ across packages, but the names are stable. The
allowlist is intentionally conservative — see :data:`_TRANSIENT_ERROR_NAMES`.
"""

from __future__ import annotations

import logging
from collections.abc import Mapping, Sequence
from typing import Any

from agent_framework import BaseChatClient

logger = logging.getLogger(__name__)


# Class names of exceptions that should trigger failover. Each provider
# SDK uses its own classes, but the names are convergent across the
# OpenAI, Anthropic, and Azure SDKs.
_TRANSIENT_ERROR_NAMES: tuple[str, ...] = (
    "RateLimitError",
    "APIConnectionError",
    "APITimeoutError",
    "InternalServerError",
    "ServiceUnavailableError",
    "BadGatewayError",
    "OverloadedError",
)


def _is_transient(exc: BaseException) -> bool:
    """Return True if ``exc`` is one of the documented transient errors."""
    return type(exc).__name__ in _TRANSIENT_ERROR_NAMES


class ProviderExhausted(RuntimeError):
    """Raised when every provider in a :class:`FailoverChatClient` failed.

    The :attr:`errors` attribute carries an ordered list of
    ``(provider_class_name, exception)`` tuples for telemetry and
    user-facing error messages.
    """

    def __init__(self, errors: list[tuple[str, BaseException]]) -> None:
        self.errors: list[tuple[str, BaseException]] = errors
        super().__init__(f"All {len(errors)} LLM providers failed; see .errors for the chain")


class FailoverChatClient(BaseChatClient):
    """A :class:`BaseChatClient` that wraps an ordered list of providers.

    Construction takes a non-empty list of providers. The list order is
    the failover order — the first provider is tried first. Transient
    errors advance to the next provider; non-transient errors propagate
    immediately; all-failed raises :class:`ProviderExhausted`.
    """

    def __init__(self, providers: Sequence[BaseChatClient]) -> None:
        if not providers:
            raise ValueError("FailoverChatClient requires at least one provider; got an empty list")
        super().__init__()
        self._providers: list[BaseChatClient] = list(providers)

    async def _inner_get_response(  # type: ignore[override]
        self,
        *,
        messages: Sequence[Any],
        stream: bool,
        options: Mapping[str, Any],
        **kwargs: Any,
    ) -> Any:
        # Streaming bypasses failover entirely. Mid-stream retry is
        # unsafe because chunks may already have been delivered to the
        # user. Delegate to the first provider's internal layer chain
        # and let any error propagate.
        if stream:
            return await self._providers[0]._inner_get_response(  # type: ignore[misc]  # noqa: SLF001
                messages=messages, stream=True, options=options, **kwargs
            )

        errors: list[tuple[str, BaseException]] = []
        for provider in self._providers:
            provider_name = type(provider).__name__
            try:
                # Call into the wrapped client's internal method directly
                # so each provider's own layer chain (function-invocation,
                # middleware, telemetry) still fires while preserving the
                # `options: Mapping[str, Any]` contract from BaseChatClient.
                return await provider._inner_get_response(  # type: ignore[misc]  # noqa: SLF001
                    messages=messages, stream=False, options=options, **kwargs
                )
            except Exception as exc:
                if _is_transient(exc):
                    logger.warning(
                        "%s raised %s; failing over to next provider",
                        provider_name,
                        type(exc).__name__,
                    )
                    errors.append((provider_name, exc))
                    continue
                # Non-transient errors propagate immediately — failover
                # cannot fix authentication or validation problems.
                raise

        raise ProviderExhausted(errors)

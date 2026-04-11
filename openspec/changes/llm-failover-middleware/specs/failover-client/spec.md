## ADDED Requirements

### Requirement: FailoverChatClient subclasses BaseChatClient
The package SHALL expose `azureclaw.llm.failover.FailoverChatClient` as a concrete subclass of `agent_framework.BaseChatClient`. The class implements the required `_inner_get_response` abstract method and is therefore instantiable. It accepts an ordered list of `BaseChatClient` instances at construction time.

#### Scenario: Construction with empty list raises
- **WHEN** `FailoverChatClient(providers=[])` is called
- **THEN** a `ValueError` is raised with a message that mentions `providers`

#### Scenario: Construction with one provider succeeds
- **WHEN** `FailoverChatClient(providers=[mock_provider])` is called
- **THEN** the resulting instance is a `BaseChatClient` and exposes `_providers` of length 1

#### Scenario: Construction with multiple providers preserves order
- **WHEN** `FailoverChatClient(providers=[a, b, c])` is called
- **THEN** the instance's `_providers` list is `[a, b, c]` in that exact order

### Requirement: Single-provider success path
When the first provider returns a response without raising, the failover client SHALL return that response and SHALL NOT consult any other provider.

#### Scenario: First provider succeeds
- **WHEN** `FailoverChatClient([provider_a, provider_b])._inner_get_response(...)` is called and `provider_a.get_response` returns a `ChatResponse`
- **THEN** the returned value is that `ChatResponse`
- **AND** `provider_b.get_response` is NOT called

### Requirement: Transient failure causes failover
When a provider raises an exception whose class name appears in the transient-error allowlist (`RateLimitError`, `APIConnectionError`, `APITimeoutError`, `InternalServerError`, `ServiceUnavailableError`, `BadGatewayError`, `OverloadedError`), the failover client SHALL log the failure and try the next provider in order.

#### Scenario: First provider raises RateLimitError, second succeeds
- **WHEN** `provider_a.get_response` raises a class named `RateLimitError` and `provider_b.get_response` returns a `ChatResponse`
- **THEN** the failover client returns the `ChatResponse` from `provider_b`

#### Scenario: First provider raises APIConnectionError, second succeeds
- **WHEN** `provider_a.get_response` raises a class named `APIConnectionError` and `provider_b.get_response` returns a `ChatResponse`
- **THEN** the failover client returns the `ChatResponse` from `provider_b`

#### Scenario: Failover logs each transient error
- **WHEN** the failover client advances from `provider_a` to `provider_b` after a transient error
- **THEN** the logger emits a warning whose message contains `"failing over"` and the error class name

### Requirement: Non-transient failure propagates immediately
When a provider raises an exception whose class name is NOT in the transient-error allowlist (e.g., `AuthenticationError`, `BadRequestError`, generic `ValueError`), the failover client SHALL re-raise immediately without consulting subsequent providers.

#### Scenario: Authentication error does not failover
- **WHEN** `provider_a.get_response` raises `AuthenticationError("bad key")`
- **THEN** `AuthenticationError` propagates out of the failover client
- **AND** `provider_b.get_response` is NOT called

#### Scenario: Validation error does not failover
- **WHEN** `provider_a.get_response` raises `ValueError("invalid argument")`
- **THEN** `ValueError` propagates out of the failover client
- **AND** `provider_b.get_response` is NOT called

### Requirement: All-providers-failed surfaces as ProviderExhausted
When every provider raises a transient error, the failover client SHALL raise `azureclaw.llm.failover.ProviderExhausted` whose `errors` attribute is a list of `(provider_class_name, exception)` tuples in the order the providers were tried.

#### Scenario: ProviderExhausted carries the per-provider error chain
- **WHEN** all three providers raise transient errors of class names `RateLimitError`, `APITimeoutError`, `InternalServerError`
- **THEN** `ProviderExhausted` is raised
- **AND** its `errors` attribute is a list of length 3 whose tuples carry the matching class names in declaration order

#### Scenario: ProviderExhausted message is informative
- **WHEN** `ProviderExhausted` is raised with three errors
- **THEN** `str(exc)` includes the count `"3"` and the phrase `"providers"`

### Requirement: Streaming requests bypass failover
When the caller requests a streaming response (`stream=True`), the failover client SHALL delegate to the first provider only and not attempt failover. Streaming failover is unsafe because chunks may already have been delivered to the user when an error occurs.

#### Scenario: Streaming delegates to first provider only
- **WHEN** `_inner_get_response(messages=..., stream=True, options=...)` is called and `provider_a.get_response` raises a `RateLimitError`
- **THEN** the error propagates immediately
- **AND** `provider_b.get_response` is NOT called

#### Scenario: Streaming success returns the first provider's stream
- **WHEN** `_inner_get_response(messages=..., stream=True, options=...)` is called and `provider_a.get_response` returns a stream
- **THEN** that stream is returned directly

### Requirement: ProviderExhausted public API
The package SHALL re-export `ProviderExhausted` from `azureclaw.__init__` so callers can `except azureclaw.ProviderExhausted` without reaching into submodules.

#### Scenario: ProviderExhausted is reachable from the package root
- **WHEN** a contributor runs `python -c "from azureclaw import ProviderExhausted; raise ProviderExhausted([])"`
- **THEN** the import succeeds
- **AND** the resulting exception is a `RuntimeError` subclass

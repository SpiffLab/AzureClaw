## Context

Five OpenSpec changes in: AzureClaw has a config model, an Azure credential factory, a complete Bicep blueprint, a MAF observability pipeline (with a placeholder warning when connection strings are `@kv:` literals), and a runnable FastAPI gateway with a hub primitive. What it does NOT have yet is the ability to actually talk to an LLM. The orchestrator (`triage-and-typed-routing`, change #7) is the first caller that needs an LLM client; this change builds that client and the failover layer that wraps it.

This change is also where the `@kv:` placeholder contract finally becomes real. The observability change (#4) shipped the @kv: fall-through warning explicitly as a stopgap until "llm-failover-middleware" delivered the resolver. That promise is honored here.

I introspected the actual Microsoft Agent Framework API surface before writing the spec:

- **`agent_framework.BaseChatClient`** is the abstract base class for chat clients. It has one abstract method, `_inner_get_response(*, messages, stream, options, **kwargs)`. Subclasses override that method; the public `get_response(messages, *, stream, options, ...)` wraps it with telemetry, middleware, and the `as_agent` factory.
- **`agent_framework.foundry.FoundryChatClient`** is the Foundry provider client. Constructor takes `project_endpoint`, `model`, `credential` (an Azure credential like `DefaultAzureCredential`).
- **`agent_framework.anthropic.AnthropicClient`** is the Anthropic provider client. Constructor takes `api_key` and `model`.
- **`agent_framework.openai.OpenAIChatClient`** is the OpenAI-compatible client. For Ollama (which exposes an OpenAI-compatible REST surface at `:11434/v1`), we construct it with an `openai.AsyncOpenAI(base_url=..., api_key="ollama")` instance.

Three subpackages (`agent-framework-foundry`, `agent-framework-anthropic`, plus the `agent-framework-openai` that comes transitively) join the dependency tree. Together with `azure-keyvault-secrets` they add 14 packages to the lockfile. Smaller than the observability change which added ~30.

## Goals / Non-Goals

**Goals:**

- A single `build_chat_client(config, credential, kv_client)` factory that takes a validated `AzureClawConfig` and returns a `BaseChatClient` ready to use.
- Per-provider builders that handle Foundry, Anthropic, and Ollama. Each builder is small (≤30 lines), validates its required config fields, and resolves `@kv:` API keys via the resolver.
- A `FailoverChatClient` that wraps an ordered list of providers, retries on transient errors with a documented allowlist of error class names, and surfaces a structured `ProviderExhausted` exception when every provider fails.
- A `resolve_kv_pointer` helper that's pure, importable from anywhere in the package, and used by both observability and the LLM factory.
- The observability function gains an optional `kv_client` parameter, becomes the first real caller of the resolver, and resolves `@kv:` connection strings before deciding the local-vs-Azure-Monitor branch.
- The gateway lifespan builds the KV client at startup and stashes it on `app.state.kv_client` for both observability and any future route handler.
- Every test is hermetic. The KV stub is in-memory; mock chat clients implement `BaseChatClient` directly; no real provider call is ever made.

**Non-Goals:**

- Any agent code that USES the chat client. The orchestrator (`triage-and-typed-routing`) is the first caller and ships in change #7.
- Real network calls to Foundry, Anthropic, Ollama, or Key Vault. CI does not have credentials for any of those.
- Streaming failover semantics. Streaming requests bypass failover and delegate to the first provider. Mid-stream retry across providers is unsafe (chunks may already be visible to the user) and complicated enough to warrant its own change if we ever need it.
- Token tracking, cost budgeting, sampling, or any other production tuning. Defaults are sufficient.
- Loading provider config from environment variables. `config.yaml` is the contract for now; environment-variable overrides land later if needed.
- A `key_vault.uri` field in `AzureClawConfig`. The config gets it via a follow-up change once the infra deploys and the operator sets the URL. Until then `build_keyvault_client(vault_uri=None, ...)` returns the stub regardless of environment.
- Custom telemetry attributes for failover events. The failover client logs via stdlib logging; OTel custom attributes land with the audit middleware in a later change.

## Decisions

### Decision: Subclass `BaseChatClient` for `FailoverChatClient`

**Why:** `BaseChatClient` is the canonical abstract base. Subclassing gives us:
- Free serialization (`from_dict`/`to_dict`/`from_json`/`to_json` via `SerializationMixin`)
- The public `get_response` wrapper that callers expect
- Compatibility with `as_agent(...)` so the failover client can be turned into an `Agent` without special-casing
- Compatibility with MAF middleware layers (`ChatMiddlewareLayer`, `FunctionInvocationLayer`) that wrap clients

The override goes on `_inner_get_response`, which is the abstract method on `BaseChatClient`. The override calls each underlying provider's PUBLIC `get_response` (not its `_inner_get_response`) so each provider's own telemetry/middleware/function-invocation layers fire normally.

**Alternatives considered:**
- A facade that holds the providers and exposes a thin `get_response` method but does NOT inherit from `BaseChatClient` (rejected: loses `as_agent`, loses serialization, breaks any caller that does `isinstance(client, BaseChatClient)`)
- An `AgentRunMiddleware` that catches errors and re-runs the agent against a swapped-in client (rejected: re-running the entire agent run is far more expensive than swapping the client; also requires diving into MAF's middleware ordering rules which are non-trivial)
- A new abstract base class layered on top of `BaseChatClient` (rejected: premature abstraction; one subclass does not justify it)

### Decision: Transient error classification by class name string

**Why:** Each provider SDK ships its own exception hierarchy. `openai.RateLimitError` and `anthropic.RateLimitError` are unrelated classes but represent the same condition. A registry of `(module, class_name)` tuples would be brittle and require updates whenever a provider renames or relocates an exception. Matching by class name (with no module) is a reasonable middle ground: it's resilient to package reorganizations and easy to extend.

The allowlist is conservative on purpose: rate limits, connection errors, timeouts, and 5xx-class errors. Authentication errors, permission errors, and validation errors are NOT retryable — they indicate a config bug or a quota exhaustion that failover cannot fix.

The allowlist:
- `RateLimitError` — rate limit hit; another provider may have headroom
- `APIConnectionError` — DNS, TCP, TLS handshake failed
- `APITimeoutError` — request exceeded the SDK's timeout
- `InternalServerError` — provider-side 500
- `ServiceUnavailableError` — provider-side 503
- `BadGatewayError` — provider-side 502
- `OverloadedError` — Anthropic-specific "Anthropic is overloaded"

**Alternatives considered:**
- Match by exception class identity (rejected: brittle across SDK versions)
- Match by HTTP status code (rejected: requires unwrapping the SDK error to find the response, not all SDKs preserve it)
- Retry on every exception (rejected: silently masks bugs)
- Configurable allowlist via config.yaml (deferred: useful but not load-bearing for the MVP; the constant is documented and easy to extend)

### Decision: Streaming bypasses failover

**Why:** Failover is a request-level concept. If provider A starts streaming chunks to the user and then fails midway, retrying with provider B means the user sees a confusing partial-then-restarted response. The right retry boundary for streaming would be the first chunk (if no chunk has been emitted yet, retry; if any chunk has been emitted, propagate). Implementing that correctly requires intercepting the stream's first iteration, which is complex enough to defer.

For the MVP, streaming requests delegate to the first provider only. If that provider raises mid-stream, the error propagates. Non-streaming requests get full failover.

The failover client documents this in its docstring and the spec scenarios make the contract explicit.

**Alternatives considered:**
- Implement first-chunk retry semantics (deferred: complex and not load-bearing for the MVP)
- Disallow streaming entirely (rejected: streaming is the default for most agent runs)
- Always failover and accept the partial-output UX (rejected: confusing for users)

### Decision: `ProviderExhausted` is a `RuntimeError` subclass with a `errors` attribute

**Why:** Callers want to:
1. `except ProviderExhausted` to handle the case where every provider failed
2. Inspect the per-provider error chain for telemetry / user-facing error messages
3. Distinguish from a bare `RuntimeError`

Subclassing `RuntimeError` (rather than `Exception` or a custom base) means the exception is naturally an "I tried everything I could" signal. The `errors` attribute is `list[tuple[str, BaseException]]` where the string is the provider class name. Exposing the per-provider class name (rather than the underlying SDK exception type) keeps the surface stable across SDK upgrades.

The `__str__` includes the count and the phrase "providers" so logs are informative without dumping every error.

**Alternatives considered:**
- Subclass `Exception` (rejected: less specific signal)
- Reraise the LAST error directly (rejected: loses context about earlier providers)
- Create a custom base `LLMError` hierarchy (rejected: premature; one error type is enough for now)

### Decision: KV resolver is a pure helper, not a class

**Why:** `resolve_kv_pointer(value, kv_client)` is a one-line operation conceptually: "if it's a `@kv:` pointer, swap it for the secret." Wrapping that in a class with a constructor and methods would be ceremony. The function is pure (no side effects beyond the `kv_client.get_secret` call), easy to test, and easy to compose into anywhere — observability, the LLM factory, future channel adapters, etc.

The Key Vault CLIENT is a class because the local-vs-real selection benefits from a stable Protocol type. The RESOLVER is a function because it doesn't have its own state.

**Alternatives considered:**
- Make resolution a method on `KeyVaultClientLike` (rejected: callers shouldn't have to know about the `@kv:` syntax; the helper centralizes it)
- Add resolution as a Pydantic validator on every field that could be `@kv:` (rejected: requires a custom validator type per field, doesn't compose with `from_yaml` cleanly)

### Decision: `build_chat_client` returns the underlying client directly when there is exactly one provider

**Why:** Wrapping a single-provider list in a `FailoverChatClient` adds a layer with no behavior (failover with one element either succeeds or surfaces `ProviderExhausted` containing one error — same as just propagating the original error). Returning the underlying client directly keeps the call stack one frame shallower and avoids confusing tracebacks.

**Alternatives considered:**
- Always wrap in `FailoverChatClient` (rejected: adds noise for the common single-provider case)
- Have a separate `build_single_chat_client` function (rejected: callers would have to know in advance how many providers were configured)

### Decision: The KV client lives on `app.state.kv_client`, not as a module-level singleton

**Why:** Same reasoning as `app.state.hub` from the gateway change: module-level singletons leak state between tests and break multi-app scenarios. The lifespan creates the client, attaches it to the app, and tears it down on shutdown. Tests get a fresh client per `TestClient(create_app(config))` invocation.

### Decision: Add a `kv_client` parameter to `setup_observability`, default `None`

**Why:** Backward compatibility for the existing observability tests. Six tests in `test_observability.py` already call `setup_observability(config)` with no second argument. Adding a required parameter would break all of them without adding behavior they care about. A keyword-only parameter with a `None` default is the minimum-change-required surface.

The observability function does the @kv: resolution **only** when a non-None `kv_client` is provided AND the connection string starts with `@kv:`. Otherwise it follows the old fall-through-to-console behavior.

## Risks / Trade-offs

- **Risk:** `agent-framework-anthropic` is a beta version (`1.0.0b260409` as of this writing). Beta packages can ship breaking changes between minors. → **Mitigation:** pin to `>=1.0.0b260409,<2`. If a breaking change ships, the failure surfaces in CI on the next dependency refresh and we update the test mocks. The actual `AnthropicClient` constructor surface (api_key, model) is small and stable.

- **Risk:** Class-name-based transient error detection silently misses an error type that should retry. → **Mitigation:** the allowlist is documented in `failover.py` with one comment per entry. Adding a new entry is a one-line change reviewable in a PR. If a real production failure mode shows a missed error, we add it.

- **Risk:** The Ollama path uses `agent_framework.openai.OpenAIChatClient` rather than a dedicated Ollama client (none exists in MAF). → **Mitigation:** Ollama exposes the OpenAI REST API so this is the canonical pattern. The constructor signature for `OpenAIChatClient` may change between MAF versions; if that happens we update the Ollama builder. The contract from outside is the same.

- **Risk:** The `_TRANSIENT_ERROR_NAMES` allowlist is global; one provider's `RateLimitError` may be a different SDK class than another's, but both match the same name. → **Mitigation:** intentional. The intent is "errors that look transient regardless of which SDK raised them." We never need to distinguish.

- **Risk:** Mock providers in tests don't subclass `BaseChatClient` but quack like one. → **Mitigation:** the test mocks DO subclass `BaseChatClient` and override `_inner_get_response` to either return a canned response or raise a canned error. They're real `BaseChatClient` instances, just with no network.

- **Risk:** The KV stub silently lets tests pass with secrets that don't exist in real Azure. → **Mitigation:** acceptable for the local marker; the stub raises `KeyError` on missing secrets so misconfiguration is visible. Real credential validation happens in the nightly Azure-marker tests (which don't exist yet but will land with `first-deploy-dev`).

- **Risk:** The factory passes through arbitrary `provider.kind` values; an unknown kind gets a generic `ValueError`. → **Mitigation:** the `ProviderConfig` Pydantic model already constrains `kind` to `Literal["foundry", "anthropic", "ollama"]`, so the unknown-kind branch is unreachable in practice. The factory raises anyway as a defense in depth.

## Migration Plan

Post-merge state:

1. `src/azureclaw/azure/keyvault.py` exists with the resolver, the Protocol, the stub, and the factory.
2. `src/azureclaw/llm/{__init__,client_factory,failover}.py` exist with `build_chat_client`, `FailoverChatClient`, `ProviderExhausted`.
3. `src/azureclaw/observability.py` accepts `kv_client` and resolves `@kv:` connection strings.
4. `src/azureclaw/gateway/app.py` lifespan builds the KV client and passes it to observability + stashes it on `app.state.kv_client`.
5. The `azureclaw` package re-exports `build_chat_client`, `FailoverChatClient`, `ProviderExhausted` alongside the existing surface.
6. `pyproject.toml` declares three new runtime dependencies; `uv.lock` is refreshed.
7. `pytest -m local` passes with the existing 44 tests + 16+ new ones.

**Rollback:** revert the PR. The dependency tree shrinks, the new modules disappear, the observability function reverts to single-argument. No external state.

## Open Questions

- Should `_TRANSIENT_ERROR_NAMES` be exposed as a configurable list via config.yaml? **Deferred.** The constant is documented and easy to edit; making it configurable adds a YAML schema field with little benefit until we have a real production failure mode that requires customization.

- Should `FailoverChatClient` track per-provider success / failure counts via OTel metrics? **Deferred to the audit middleware change.** That change adds custom span attributes for `provider`, `failover_count`, etc. which is a more natural place for the instrumentation.

- Should the Anthropic builder verify the API key format before constructing the client (e.g., must start with `sk-ant-`)? **No.** The `AnthropicClient` itself rejects malformed keys with a clear error on the first request. Adding a regex here would just create another place that needs updating when Anthropic changes its key format.

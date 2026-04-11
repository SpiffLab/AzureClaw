## Why

The orchestrator (which lands two changes from now) needs a `ChatClient` to talk to. AzureClaw's design commits to a **pluggable provider stack** with **automatic failover** — Foundry first, then Anthropic, then Ollama. Until this change lands, every call site that wants an LLM client has nowhere to get one.

This change ships three tightly coupled pieces in one PR because they share the same abstractions and would be hard to review separately:

1. **Key Vault `@kv:` resolver** — the helper that turns `"@kv:anthropic-api-key"` strings in config into the actual secret value via Azure Key Vault. The observability change committed this contract; this change delivers it.
2. **LLM provider factory** — `build_chat_client(config, credential)` that constructs a `BaseChatClient` per `providers:` entry (Foundry / Anthropic / Ollama) and returns a single facade.
3. **Failover client** — `FailoverChatClient`, a `BaseChatClient` subclass that wraps an ordered list of providers and retries on transient errors with a structured `ProviderExhausted` exception when every provider is exhausted.

## What Changes

- Add runtime dependencies to `pyproject.toml`: `agent-framework-foundry>=1.0,<2`, `agent-framework-anthropic>=1.0.0b260409,<2` (currently a beta), `azure-keyvault-secrets>=4.10,<5`
- Create `src/azureclaw/azure/keyvault.py`:
  - `KeyVaultClientLike` Protocol (one method `get_secret(name) -> str`)
  - `_LocalStubKeyVaultClient` — in-memory store, used for `environment="local"` and tests
  - `_SecretClientAdapter` — thin wrapper around `azure.keyvault.secrets.SecretClient` so the public surface is the simpler Protocol
  - `build_keyvault_client(vault_uri, environment, credential)` factory
  - `resolve_kv_pointer(value, kv_client)` — pure helper that returns the value unchanged unless it starts with `"@kv:"`, in which case it strips the prefix and calls `kv_client.get_secret(name)`
- Create `src/azureclaw/llm/__init__.py` re-exporting `build_chat_client`, `FailoverChatClient`, `ProviderExhausted`
- Create `src/azureclaw/llm/client_factory.py` with provider-specific builder functions:
  - `_build_foundry_client(provider, credential)` → `FoundryChatClient`
  - `_build_anthropic_client(provider, kv_client)` → `AnthropicClient` (resolving `@kv:` API keys)
  - `_build_ollama_client(provider)` → `OpenAIChatClient` with `openai.AsyncOpenAI(base_url=..., api_key="ollama")`
  - `build_chat_client(config, credential, kv_client) -> BaseChatClient` — drives the per-provider builders, validates that at least one provider is present, returns the single provider directly when there's only one and a `FailoverChatClient` wrapping all when there are multiple
- Create `src/azureclaw/llm/failover.py` with:
  - `ProviderExhausted(RuntimeError)` — carries the list of `(provider_name, exception)` tuples
  - `_TRANSIENT_ERROR_NAMES` — class names that are considered retryable (`RateLimitError`, `APIConnectionError`, `APITimeoutError`, `InternalServerError`, `ServiceUnavailableError`, `BadGatewayError`, `OverloadedError`)
  - `_is_transient(exc)` predicate
  - `FailoverChatClient(BaseChatClient)` — overrides `_inner_get_response` to delegate to providers in order; on transient errors advances to the next; on non-transient errors propagates immediately. Streaming requests bypass failover and delegate to the first provider only (mid-stream retry is unsafe).
- Update `src/azureclaw/observability.py` so `setup_observability(config, kv_client=None)` accepts an optional `kv_client` and resolves `@kv:` connection strings before deciding the branch. Backward compatible: callers that don't pass a `kv_client` get the existing fall-through-to-console behavior.
- Update `src/azureclaw/gateway/app.py` so the lifespan builds a Key Vault client (stub in local mode) and passes it to `setup_observability`. The lifespan also stashes the KV client on `app.state.kv_client` so future routes can reach it.
- Re-export `build_chat_client`, `FailoverChatClient`, `ProviderExhausted` from `azureclaw.__init__`
- Add 16+ new tests covering the resolver, the per-provider builders, the failover client, and the observability integration

**Non-goals (explicitly not in this change):**
- Any agent that actually USES the chat client (lands in `triage-and-typed-routing`, #7)
- Real network calls to any provider (every test mocks the underlying client)
- Streaming failover (unsafe; documented as a follow-up)
- Token tracking or budgeting (separate concern)
- Loading provider config from environment variables (config.yaml is the contract for now)
- Calling Azure Key Vault for real (every test uses the in-memory stub; the `dev`/`prod` path is reachable but unexercised in CI)

## Capabilities

### New Capabilities

- `keyvault-resolver`: the `@kv:` secret-pointer protocol, the Key Vault client factory, and the `resolve_kv_pointer` helper used by every other module that needs a secret
- `llm-providers`: the per-provider builder functions and the `build_chat_client(config, credential, kv_client)` factory that drives them
- `failover-client`: the `FailoverChatClient` + `ProviderExhausted` exception + transient-error classification

### Modified Capabilities

- `observability`: `setup_observability` accepts an optional `kv_client` parameter and uses it to resolve `@kv:` connection strings into real Application Insights connection strings before deciding the local-vs-Azure-Monitor branch
- `gateway`: the lifespan builds a Key Vault client and stashes it on `app.state.kv_client` alongside the existing hub and config

## Impact

- **Affected systems:** local working tree only; no Azure resource is touched (every test uses the in-memory KV stub and mocked provider clients)
- **Affected dependencies:** `pyproject.toml` gains `agent-framework-foundry`, `agent-framework-anthropic`, `azure-keyvault-secrets`. `uv.lock` grows by ~14 packages (the two MAF subpackages plus their transitive deps: `anthropic`, `openai`, `azure-ai-inference`, `azure-ai-projects`, `azure-storage-blob`, etc.)
- **Affected APIs:** introduces `azureclaw.{build_chat_client, FailoverChatClient, ProviderExhausted}` as public symbols. Also `azureclaw.azure.keyvault.{KeyVaultClientLike, build_keyvault_client, resolve_kv_pointer}`.
- **Affected docs:** none in this change (orchestrator docs land with `triage-and-typed-routing`)
- **Reversibility:** fully reversible — revert the PR. No external state.

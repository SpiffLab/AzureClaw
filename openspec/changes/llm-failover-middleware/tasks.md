## 1. Dependencies

- [ ] 1.1 Add `agent-framework-foundry>=1.0,<2` to `pyproject.toml`
- [ ] 1.2 Add `agent-framework-anthropic>=1.0.0b260409,<2` to `pyproject.toml`
- [ ] 1.3 Add `azure-keyvault-secrets>=4.10,<5` to `pyproject.toml`
- [ ] 1.4 Run `uv sync --extra dev` and confirm the lockfile picks up the ~14 new packages

## 2. Key Vault resolver

- [ ] 2.1 Create `src/azureclaw/azure/keyvault.py`
- [ ] 2.2 Define `KeyVaultClientLike` Protocol with `get_secret(self, name: str) -> str`
- [ ] 2.3 Define private `_LocalStubKeyVaultClient` with optional `secrets: dict[str, str]` constructor; raise `KeyError` on missing secrets
- [ ] 2.4 Define private `_SecretClientAdapter` that wraps `azure.keyvault.secrets.SecretClient` and exposes `get_secret(name) -> str` returning `secret.value`
- [ ] 2.5 Define `build_keyvault_client(vault_uri, environment, credential)` factory that returns the stub for `local` or missing `vault_uri`, otherwise lazy-imports the SDK and returns the real adapter
- [ ] 2.6 Define `resolve_kv_pointer(value, kv_client) -> str | None` pure helper

## 3. LLM provider factory

- [ ] 3.1 Create `src/azureclaw/llm/__init__.py`
- [ ] 3.2 Create `src/azureclaw/llm/client_factory.py`
- [ ] 3.3 Implement `_build_foundry_client(provider, credential)` validating `provider.endpoint`
- [ ] 3.4 Implement `_build_anthropic_client(provider, kv_client)` resolving `@kv:` API keys
- [ ] 3.5 Implement `_build_ollama_client(provider)` constructing an `openai.AsyncOpenAI` and passing it to `OpenAIChatClient`
- [ ] 3.6 Implement `build_chat_client(config, credential, kv_client) -> BaseChatClient` that validates non-empty providers, dispatches per-kind, returns the single client directly when there's exactly one provider, otherwise wraps in `FailoverChatClient`

## 4. Failover client

- [ ] 4.1 Create `src/azureclaw/llm/failover.py`
- [ ] 4.2 Define `_TRANSIENT_ERROR_NAMES` constant tuple (RateLimitError, APIConnectionError, APITimeoutError, InternalServerError, ServiceUnavailableError, BadGatewayError, OverloadedError)
- [ ] 4.3 Define `_is_transient(exc) -> bool` predicate
- [ ] 4.4 Define `ProviderExhausted(RuntimeError)` carrying `errors: list[tuple[str, BaseException]]`
- [ ] 4.5 Define `FailoverChatClient(BaseChatClient)`:
  - Constructor takes `providers: list[BaseChatClient]`, raises `ValueError` if empty
  - Override `_inner_get_response(*, messages, stream, options, **kwargs)`
  - Streaming bypass: if `stream=True`, delegate to `providers[0].get_response(...)` directly
  - Non-streaming: iterate providers; on transient error, log + advance; on non-transient, re-raise; if all fail, raise `ProviderExhausted`
- [ ] 4.6 Re-export `FailoverChatClient`, `ProviderExhausted`, `build_chat_client` from `azureclaw.llm.__init__` and from `azureclaw.__init__`

## 5. Observability integration

- [ ] 5.1 Update `src/azureclaw/observability.py` `setup_observability` signature to accept a keyword-only `kv_client: KeyVaultClientLike | None = None` parameter
- [ ] 5.2 Add a resolution step inside the function: if `connection_string` starts with `@kv:` AND `kv_client is not None` AND `environment != "local"`, try `resolve_kv_pointer` and replace `connection_string` with the result; on `KeyError` (or any exception), log a warning and leave the original placeholder so the existing fall-through branch handles it
- [ ] 5.3 Update the `local` mode branch to NOT attempt resolution (local mode is hermetic by contract)

## 6. Gateway integration

- [ ] 6.1 Update `src/azureclaw/gateway/app.py` lifespan to build a Key Vault client via `build_keyvault_client(vault_uri=None, environment=config.environment, credential=build_credential(config.environment))`
- [ ] 6.2 Stash the client on `app.state.kv_client`
- [ ] 6.3 Pass the client to `setup_observability(config, kv_client=app.state.kv_client)`

## 7. Tests — Key Vault resolver

- [ ] 7.1 Create `tests/test_keyvault_resolver.py`
- [ ] 7.2 Test: `KeyVaultClientLike` Protocol is reachable; isinstance check works with the stub
- [ ] 7.3 Test: stub returns seeded secrets
- [ ] 7.4 Test: stub raises `KeyError` on missing secret
- [ ] 7.5 Test: `build_keyvault_client(environment="local")` returns the stub even when `vault_uri` is set
- [ ] 7.6 Test: `build_keyvault_client(vault_uri=None, environment="dev")` returns the stub
- [ ] 7.7 Test: `resolve_kv_pointer(None, ...)` returns `None`
- [ ] 7.8 Test: `resolve_kv_pointer("plain", ...)` returns `"plain"`
- [ ] 7.9 Test: `resolve_kv_pointer("@kv:foo", stub_with_foo_value_bar)` returns `"bar"`
- [ ] 7.10 Test: `resolve_kv_pointer("@kv:missing", empty_stub)` raises `KeyError`
- [ ] 7.11 Test: `resolve_kv_pointer("", ...)` returns `""` (no KV call)

## 8. Tests — LLM factory + failover

- [ ] 8.1 Create `tests/test_llm_factory.py`
- [ ] 8.2 Test: empty providers list raises `ValueError`
- [ ] 8.3 Test: single Foundry provider returns a `FoundryChatClient` directly (not wrapped)
- [ ] 8.4 Test: single Anthropic provider returns an `AnthropicClient` directly
- [ ] 8.5 Test: single Ollama provider returns an `OpenAIChatClient` directly
- [ ] 8.6 Test: three providers return a `FailoverChatClient` whose `_providers` list has length 3 in declaration order
- [ ] 8.7 Test: Foundry without endpoint raises `ValueError`
- [ ] 8.8 Test: Anthropic builder resolves `@kv:` api_key via the kv_client stub
- [ ] 8.9 Test: Anthropic builder raises on missing api_key
- [ ] 8.10 Test: Ollama builder normalizes base_url with `/v1` suffix
- [ ] 8.11 Test: Ollama builder raises on missing base_url
- [ ] 8.12 Create `tests/test_failover_client.py`
- [ ] 8.13 Define a `_MockChatClient(BaseChatClient)` test fixture that returns a canned `ChatResponse` or raises a canned exception named at construction time
- [ ] 8.14 Test: `FailoverChatClient([])` raises `ValueError`
- [ ] 8.15 Test: first provider succeeds → no second call
- [ ] 8.16 Test: first transient-fails, second succeeds → returns second's response
- [ ] 8.17 Test: first non-transient-fails → re-raises immediately, no second call
- [ ] 8.18 Test: all transient-fail → raises `ProviderExhausted` with N errors
- [ ] 8.19 Test: streaming request bypasses failover (calls only first provider)
- [ ] 8.20 Test: `ProviderExhausted` is a `RuntimeError` subclass and reachable from the package root

## 9. Tests — observability integration

- [ ] 9.1 Update `tests/test_observability.py`:
  - [ ] 9.1.1 Add a test: `@kv:` connection string in dev mode with a stub kv_client containing the secret takes the Azure Monitor branch with the resolved value
  - [ ] 9.1.2 Add a test: `@kv:` connection string in dev mode with a stub kv_client missing the secret falls back to console (does not raise)
  - [ ] 9.1.3 Add a test: `@kv:` connection string in local mode is NOT resolved even when a populated kv_client is provided
  - [ ] 9.1.4 Confirm existing tests still pass with the new signature (kv_client defaults to None)

## 10. Tests — gateway integration

- [ ] 10.1 Update `tests/test_gateway_app.py`:
  - [ ] 10.1.1 Add a test: `app.state.kv_client` is set after lifespan startup and is a `KeyVaultClientLike`
  - [ ] 10.1.2 Add a test: `setup_observability` was invoked with the same `kv_client` instance now stashed on `app.state.kv_client`

## 11. Verification

- [ ] 11.1 `uv run ruff check src tests` — clean
- [ ] 11.2 `uv run ruff format --check src tests` — clean
- [ ] 11.3 `uv run pyright src tests` — 0 errors
- [ ] 11.4 `uv run pytest -m local -v` — every existing test still passes plus 16+ new
- [ ] 11.5 `bicep build infra/main.bicep` — sanity (this PR doesn't touch infra)
- [ ] 11.6 `npx -y @fission-ai/openspec validate llm-failover-middleware` — clean

## 12. Commit and PR

- [ ] 12.1 Commit (1) — OpenSpec artifacts only — `spec: llm-failover-middleware — Key Vault resolver, LLM factory, failover client`
- [ ] 12.2 Commit (2) — implementation — `feat: llm-failover-middleware implementation`
- [ ] 12.3 Push `feature/llm-failover-middleware`
- [ ] 12.4 Open PR against `develop`
- [ ] 12.5 Watch CI; merge when green

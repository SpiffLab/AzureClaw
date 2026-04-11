## ADDED Requirements

### Requirement: build_chat_client factory
The package SHALL expose `azureclaw.llm.client_factory.build_chat_client(config: AzureClawConfig, credential, kv_client) -> BaseChatClient`. The function inspects `config.providers` and:

- Raises `ValueError` if `config.providers` is empty
- Constructs one underlying `BaseChatClient` per provider entry, in declaration order, via the per-kind builder function
- Returns the single underlying client directly when there is exactly one provider
- Returns a `FailoverChatClient` wrapping the ordered list of underlying clients when there are two or more providers

#### Scenario: Empty providers list raises
- **WHEN** `build_chat_client` is called with a config whose `providers` list is empty
- **THEN** a `ValueError` is raised with a message that mentions `providers`

#### Scenario: Single provider returns the underlying client directly
- **WHEN** `build_chat_client` is called with a config whose `providers` list has exactly one entry of kind `"foundry"`
- **THEN** the returned object is a `FoundryChatClient` instance (not a `FailoverChatClient`)

#### Scenario: Multiple providers return a FailoverChatClient
- **WHEN** `build_chat_client` is called with a config whose `providers` list has three entries
- **THEN** the returned object is a `FailoverChatClient` whose `_providers` list has length 3
- **AND** `_providers[0]` is the underlying client for `providers[0]`, etc. (declaration order preserved)

### Requirement: Foundry provider builder
The factory SHALL build a Foundry chat client from a `ProviderConfig` whose `kind == "foundry"` by calling `agent_framework.foundry.FoundryChatClient(project_endpoint=provider.endpoint, model=provider.model, credential=credential)`. If `provider.endpoint` is `None` the builder SHALL raise `ValueError` with a message naming the missing field.

#### Scenario: Foundry builder requires endpoint
- **WHEN** `build_chat_client` is called with a Foundry provider whose `endpoint` is `None`
- **THEN** `ValueError` is raised with a message that mentions `endpoint`

#### Scenario: Foundry builder passes credential through
- **WHEN** `build_chat_client` is called with a Foundry provider and a stub credential
- **THEN** the returned `FoundryChatClient` was constructed with `credential` set to that stub

### Requirement: Anthropic provider builder
The factory SHALL build an Anthropic chat client from a `ProviderConfig` whose `kind == "anthropic"` by calling `agent_framework.anthropic.AnthropicClient(api_key=resolved_api_key, model=provider.model)`. The `resolved_api_key` SHALL be the result of `resolve_kv_pointer(provider.api_key, kv_client)` so `@kv:` pointers are transparently resolved before construction. If the resolved API key is `None` or empty after resolution the builder SHALL raise `ValueError` naming the missing field.

#### Scenario: Anthropic builder resolves @kv: api_key via the kv_client
- **WHEN** `build_chat_client` is called with an Anthropic provider whose `api_key` is `"@kv:anthropic-api-key"` and a stub KV client containing `{"anthropic-api-key": "sk-ant-real"}`
- **THEN** the returned `AnthropicClient` was constructed with `api_key="sk-ant-real"`

#### Scenario: Anthropic builder requires api_key
- **WHEN** `build_chat_client` is called with an Anthropic provider whose `api_key` is `None`
- **THEN** `ValueError` is raised with a message that mentions `api_key`

#### Scenario: Anthropic builder errors on unresolvable @kv: pointer
- **WHEN** `build_chat_client` is called with an Anthropic provider whose `api_key` is `"@kv:missing"` and a stub KV client that does not have that secret
- **THEN** the underlying `KeyError` from the resolver propagates (the builder does not swallow it)

### Requirement: Ollama provider builder
The factory SHALL build an Ollama chat client from a `ProviderConfig` whose `kind == "ollama"` by constructing an `openai.AsyncOpenAI(base_url=f"{provider.base_url}/v1", api_key="ollama")` and passing it to `agent_framework.openai.OpenAIChatClient(async_client=..., model=provider.model)` (or whatever named parameter the SDK uses). If `provider.base_url` is `None` the builder SHALL raise `ValueError`.

#### Scenario: Ollama builder requires base_url
- **WHEN** `build_chat_client` is called with an Ollama provider whose `base_url` is `None`
- **THEN** `ValueError` is raised with a message that mentions `base_url`

#### Scenario: Ollama builder normalizes the base_url
- **WHEN** `build_chat_client` is called with an Ollama provider whose `base_url` is `"http://localhost:11434"`
- **THEN** the underlying `openai.AsyncOpenAI` was constructed with `base_url="http://localhost:11434/v1"`
- **AND** the `api_key` is the literal string `"ollama"` (Ollama ignores it but the OpenAI SDK requires a non-empty value)

### Requirement: Provider declaration order is preserved end to end
The order in which providers are declared in `config.providers` SHALL be the order in which the failover client tries them. The first declared provider is tried first. Reordering the providers list in YAML changes the failover order with no other code change required.

#### Scenario: Reordering providers in config reorders the failover list
- **WHEN** `build_chat_client` is called with providers `[anthropic, foundry, ollama]`
- **THEN** the returned `FailoverChatClient._providers` list is `[anthropic_client, foundry_client, ollama_client]`

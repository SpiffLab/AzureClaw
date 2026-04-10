# AzureClaw

> Azure-native, Microsoft Agent Framework re-imagining of [OpenClaw](https://github.com/openclaw/openclaw).

AzureClaw is a Python-based personal AI assistant that bridges popular chat platforms (WhatsApp, Telegram, Discord, iMessage, Microsoft Teams) into a multi-agent orchestrator built on **Microsoft Agent Framework 1.0**. It is inspired by OpenClaw's local-first design but reimagined for Azure: every Microsoft-provided service is used where one exists, with on-prem hybrid connectivity provided through **Azure Relay Hybrid Connections**.

## Status

Early bootstrap. The repository currently contains:

- The OpenSpec scaffolding and the unified living spec at `openspec/project.md`
- The day-one repo metadata (CI, dev container, templates, license)
- Empty package directories ready for the first OpenSpec change to populate

**Nothing is deployed.** No Azure resources have been provisioned. The first deployment is gated behind merged OpenSpec changes and a manual workflow_dispatch with required reviewer.

## Architecture at a glance

| Concern | Choice |
|---|---|
| Agent runtime | Microsoft Agent Framework 1.0 (`AIAgent`, `WorkflowBuilder`, `MagenticBuilder`) |
| Orchestration | MAF graph workflow with typed edges + Magentic-One research team |
| LLM backend | Pluggable behind `ChatClient`; default ordering Foundry → Anthropic → Ollama |
| Memory | Azure Cosmos DB (raw turns) + Azure AI Search (vector recall) + Azure OpenAI embeddings |
| Tools | MCP servers (browser, canvas) + `AIFunction` tools (cron, channel actions); approval-required for destructive ops |
| Hosting | Azure Container Apps + ACR + APIM, all behind Managed Identity + Key Vault |
| Observability | OpenTelemetry → Application Insights via `azure-monitor-opentelemetry` |
| On-prem reach | Azure Relay (Hybrid Connections) + per-site `azureclaw-bridge` connector |
| Channel adapters | WhatsApp, Telegram, Discord, iMessage (via Mac connector), Microsoft Teams |
| Dev process | OpenSpec spec-driven development — every change lands via `/opsx:propose` → `/opsx:apply` → `/opsx:archive` |

The full architecture lives in [`openspec/project.md`](openspec/project.md).

## Repository layout

```
AzureClaw/
  openspec/                  # spec-driven dev metadata (project.md + changes/ + archive/)
  src/azureclaw/             # main Python package (populated by upcoming changes)
  azureclaw-bridge/          # on-prem connector daemon
  infra/                     # Bicep modules for Azure provisioning
  tests/                     # pytest suite (unit + integration + e2e)
  docs/                      # architecture docs and runbooks
  .devcontainer/             # reproducible dev environment
  .github/                   # CI workflows, CODEOWNERS, PR/issue templates
```

## Getting started

The dev environment is captured in `.devcontainer/devcontainer.json`. Open the repo in VS Code with the Dev Containers extension and you get Python 3.13, Node 20.19+, the Azure CLI, `azd`, Bicep, and Bun pre-installed.

Locally:

```bash
# Install uv (https://docs.astral.sh/uv/) then:
uv sync
uv run pytest -m local
```

The `local` test marker uses SQLite and in-memory fallbacks so contributors can validate the orchestrator/middleware/memory paths without an Azure subscription.

## Contributing

Every change starts as an OpenSpec proposal:

```bash
# In a Claude Code session (or any of the 20+ supported assistants):
/opsx:propose <change-name>
/opsx:verify <change-name>
/opsx:apply <change-name>
```

See `openspec/project.md` for the architecture and `openspec/changes/` for the active proposal queue. Open issues using the **Change request** template in `.github/ISSUE_TEMPLATE/`.

## License

MIT — see [`LICENSE`](LICENSE).

## Acknowledgements

- [OpenClaw](https://github.com/openclaw/openclaw) for the original vision of a multi-channel, multi-tool personal assistant
- [Microsoft Agent Framework](https://github.com/microsoft/agent-framework) for the orchestration substrate
- [Fission-AI/OpenSpec](https://github.com/Fission-AI/OpenSpec) for the spec-driven development workflow

# Running the AzureClaw gateway locally

This runbook walks through booting the AzureClaw FastAPI gateway on your workstation with no Azure dependency, for local development and smoke testing. It assumes you've already run `uv sync --extra dev` after cloning the repo.

## One-time setup

```bash
cp config.example.yaml config.yaml
```

`config.yaml` is already gitignored — it's your local working copy. Leave every `@kv:` placeholder as-is; the gateway handles those by falling back to local-friendly defaults (console OTel exporter, no channel credentials, no Azure calls).

## Boot the gateway

```bash
uv run uvicorn azureclaw.gateway.app:get_app --factory --reload --port 18789
```

What each flag does:

- `azureclaw.gateway.app:get_app` — the module:callable reference. `get_app` is a factory that loads `config.yaml` and returns a fresh `FastAPI` instance.
- `--factory` — tells uvicorn to call `get_app()` rather than expecting a module-level `app` object. Required when using the factory pattern.
- `--reload` — auto-restart the server when source files change. Dev-only; never use in production.
- `--port 18789` — matches OpenClaw's original gateway port so muscle memory transfers. Use any free port you like.

You should see something like:

```
INFO:     Will watch for changes in these directories: ['...']
INFO:     Uvicorn running on http://127.0.0.1:18789 (Press CTRL+C to quit)
INFO:     Started reloader process [...] using WatchFiles
INFO:     Started server process [...]
INFO:     Waiting for application startup.
INFO:     observability wired to console exporter (environment=local)
INFO:     Application startup complete.
```

The "observability wired to console exporter" line confirms the lifespan ran `setup_observability(config)` and took the local branch. From this point on, every MAF-emitted OpenTelemetry span gets dumped to your terminal.

## Sanity check

```bash
curl http://localhost:18789/healthz
```

Expected response:

```json
{"status": "ok", "package": "azureclaw", "version": "0.0.0"}
```

If you get a connection error, the server is not running or crashed at startup — check the uvicorn terminal for tracebacks. The most common cause is `config.yaml` missing from the current directory.

## Point at a different config file

```bash
AZURECLAW_CONFIG=/path/to/alt.yaml uv run uvicorn azureclaw.gateway.app:get_app --factory --port 18789
```

`get_app()` reads `AZURECLAW_CONFIG` from the environment and defaults to `./config.yaml` only if the env var is unset. Useful for switching between a personal dev config and a CI-friendly one.

## Verify the gateway is listening *only* on localhost

```bash
uv run uvicorn azureclaw.gateway.app:get_app --factory --host 127.0.0.1 --port 18789
```

The gateway has no authentication yet (APIM handles Entra validation at the edge in production; the `a2a-interop-apim` OpenSpec change ships the gateway-side header-trust middleware). **Do not expose the local gateway on `0.0.0.0` or a public interface** until that change lands.

## Run the test suite

```bash
uv run pytest -m local
```

The test suite boots the gateway via `fastapi.testclient.TestClient` — no real uvicorn server, no real port. It exercises the full inbound → hub → outbound round-trip using the `InProcTestAdapter`. Every test is hermetic and requires no Azure credential.

## Seeing telemetry

Local mode uses MAF's console exporter (via `agent_framework.observability.configure_otel_providers(enable_console_exporters=True)`). Spans land on stdout as structured JSON-ish lines. Grep for specific events:

```bash
uv run uvicorn azureclaw.gateway.app:get_app --factory --port 18789 2>&1 | grep -i 'span\|event'
```

Once a real Application Insights connection string is configured in `config.yaml` and the environment is set to `dev` or `prod`, the same spans flow to App Insights instead — see `docs/runbooks/observability.md` for KQL queries.

## Troubleshooting

**"ModuleNotFoundError: No module named 'azureclaw'"** — you forgot `uv sync` or you're running Python directly instead of via `uv run`. The package is installed into the `.venv` that `uv` manages.

**"FileNotFoundError: config.yaml"** — create it: `cp config.example.yaml config.yaml`.

**"uvicorn: error: unrecognized arguments: --factory"** — your uvicorn is older than 0.20. Run `uv sync` to pick up the pinned version (0.32+).

**Port already in use** — something else is on 18789. Use a different port (e.g., `--port 8080`).

**Observability line says "falling back to the console exporter"** — that's the expected warning when your config has an `@kv:` connection string placeholder. The Key Vault resolver lands in the `llm-failover-middleware` change (#6); until then, this warning is informational only.

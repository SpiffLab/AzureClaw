# Observability runbook

AzureClaw exports OpenTelemetry spans, metrics, and logs through Microsoft Agent Framework's auto-instrumentation. In production those flow to **Application Insights** via `azure-monitor-opentelemetry`. In local-dev they go to the console exporter and you can read them in your terminal.

This runbook is a starter pack of KQL queries an oncall engineer or developer would actually paste into the Application Insights workspace. They cover the AzureClaw audit log: agent runs, tool calls, workflow supersteps, provider failover, and approval requests.

## How to use

1. Open the Application Insights resource for the dev or prod environment in the Azure portal.
2. Click **Logs** in the left rail to open the KQL editor.
3. Paste any of the queries below.
4. Adjust the time range in the top bar (default 24h is usually fine for incident triage).
5. Save the ones you use repeatedly to the workspace's saved queries panel.

The queries below assume MAF auto-instrumentation is active, which means agent runs land in `dependencies`, tool calls land in `dependencies` with the `tool` cloud role, and structured logs land in `traces`. Custom span attributes such as `session_id`, `channel`, and `entra_oid` are added by the audit middleware that lands in a later OpenSpec change — until then the queries that filter on those attributes will return empty result sets, but the queries themselves still parse and run.

---

## 1. All spans for a single session

```kql
union dependencies, traces, requests
| where customDimensions.session_id == "<paste-session-id>"
| project timestamp, itemType, name, duration, success, customDimensions
| order by timestamp asc
```

Use this when a user reports "my conversation broke." The session id is on the channel-side `ChannelMessage` envelope and is logged at every workflow superstep.

## 2. Spans grouped by channel

```kql
dependencies
| where timestamp > ago(1h)
| extend channel = tostring(customDimensions.channel)
| where isnotempty(channel)
| summarize count(), avg_ms = avg(duration), p95_ms = percentile(duration, 95)
    by channel
| order by count_ desc
```

Quick "is one channel hot or slow" check. Each channel adapter (WhatsApp, Telegram, Discord, iMessage, Teams) tags its spans with `channel`.

## 3. Tool-call latency P50 / P95

```kql
dependencies
| where timestamp > ago(1h)
| where type == "InProc" and name startswith "tool."
| summarize
    p50_ms = percentile(duration, 50),
    p95_ms = percentile(duration, 95),
    p99_ms = percentile(duration, 99),
    count_ = count()
    by tool = name
| order by p95_ms desc
```

The first thing to check when "agents feel slow." MAF emits one span per tool/MCP call with name `tool.<name>`.

## 4. Provider failover events

```kql
traces
| where timestamp > ago(24h)
| where message has "provider failover"
| extend
    from_provider = tostring(customDimensions.from_provider),
    to_provider = tostring(customDimensions.to_provider),
    error_class = tostring(customDimensions.error_class)
| project timestamp, from_provider, to_provider, error_class, message
| order by timestamp desc
```

Watches for the `llm-failover-middleware` advancing through providers. Frequent failovers from Foundry → Anthropic → Ollama mean Foundry has a capacity or rate-limit issue.

## 5. Approval request lifecycle

```kql
let requests_emitted = traces
    | where message == "approval requested"
    | extend approval_id = tostring(customDimensions.approval_id)
    | project approval_id, requested_at = timestamp,
              tool = tostring(customDimensions.tool),
              session = tostring(customDimensions.session_id);
let resolutions = traces
    | where message in ("approval approved", "approval denied")
    | extend approval_id = tostring(customDimensions.approval_id)
    | project approval_id, resolved_at = timestamp, decision = message;
requests_emitted
| join kind=leftouter resolutions on approval_id
| extend wait_seconds = datetime_diff('second', resolved_at, requested_at)
| project requested_at, session, tool, approval_id, decision, wait_seconds
| order by requested_at desc
```

Shows how long users sit on approval prompts and which decisions they make. A high `wait_seconds` is a UX signal — the prompt is unclear or the channel notification is being missed.

## 6. Errors by agent name

```kql
exceptions
| where timestamp > ago(24h)
| extend agent = tostring(customDimensions.agent_name)
| where isnotempty(agent)
| summarize count(), latest_error = take_any(outerMessage)
    by agent, problemId
| order by count_ desc
```

Bucket agent errors by the agent that emitted them (Triage, Chat, Magentic worker, channel adapter, …) plus the problem id, so you can spot a regression in one specialist without chasing every individual stack trace.

## 7. Top 20 most expensive tool calls

```kql
dependencies
| where timestamp > ago(24h)
| where name startswith "tool."
| top 20 by duration desc
| project timestamp, tool = name, duration_ms = duration,
          session = tostring(customDimensions.session_id),
          channel = tostring(customDimensions.channel)
```

The hit-list. Look at this when the bill or the tail latency is high.

## 8. Workflow superstep durations

```kql
dependencies
| where timestamp > ago(1h)
| where name startswith "workflow.superstep"
| summarize
    p50_ms = percentile(duration, 50),
    p95_ms = percentile(duration, 95),
    count_ = count()
    by name
| order by p95_ms desc
```

MAF emits one span per workflow superstep (Triage, handoff, Magentic round, etc.). High P95 on a specific superstep narrows the bottleneck to the agent that runs in it.

## 9. End-to-end latency from inbound message to response

```kql
requests
| where timestamp > ago(1h)
| where name == "POST /webhooks/*"
| project
    timestamp,
    operation_id,
    channel = tostring(customDimensions.channel),
    duration_ms = duration,
    success
| summarize
    p50_ms = percentile(duration_ms, 50),
    p95_ms = percentile(duration_ms, 95),
    count_ = count(),
    success_rate = countif(success == true) * 100.0 / count()
    by channel
| order by p95_ms desc
```

The user-facing latency by channel. The gateway's webhook handlers are auto-instrumented by `opentelemetry-instrumentation-fastapi` (which `azure-monitor-opentelemetry` enables for free).

## 10. Cross-boundary on-prem audit trail

```kql
dependencies
| where timestamp > ago(24h)
| extend site_id = tostring(customDimensions.site_id)
| where isnotempty(site_id)
| project timestamp, site_id, name, duration,
          tool = tostring(customDimensions.tool),
          decision = tostring(customDimensions.decision)
| order by timestamp desc
```

Every span tagged with a `site_id` is a request that crossed the Azure → on-prem boundary via the `azureclaw-bridge` connector. This is the auditable record of what the cloud agent did at the user's site.

---

## Tips

- **Saved queries:** the Azure portal lets you save any of these to the workspace. Save them under "AzureClaw" and the on-call gets them by default.
- **Workbooks:** convert any query above into a tile in an Azure Monitor Workbook for a single-pane dashboard. The most useful tiles are #2 (channels), #3 (tool latency), #5 (approval lifecycle), and #9 (end-to-end latency).
- **Alerts:** create a metric alert on "spans where success == false" grouped by `agent_name` to page on-call when error rates spike.
- **Live Metrics:** for active incidents, the App Insights "Live Metrics" view shows requests per second, dependency calls, and exceptions in real time without writing KQL.
- **Local dev:** when running with the console exporter (the default for `environment: local`), the same span attributes appear in stdout. `grep tool` or `jq` your way through them.

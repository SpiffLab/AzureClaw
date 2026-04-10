---
name: Bug report
about: Something is broken or behaving unexpectedly
title: "bug: "
labels: ["bug", "needs-triage"]
---

## What happened

<!-- A clear description of the bug. Include the channel (Discord/Telegram/...) and whether the affected path uses Azure or the local-dev fallbacks. -->

## What you expected

<!-- What should have happened instead. -->

## Repro steps

1.
2.
3.

## Environment

- AzureClaw commit: <!-- `git rev-parse --short HEAD` -->
- Python version:
- Channel adapter(s) involved:
- Azure region (if applicable):
- Running with `memory.backend: cosmos_aisearch | sqlite`?
- LLM provider that handled the failing request:

## Logs / traces

<!-- Paste the relevant Application Insights span IDs or local OTel console output. Redact secrets. -->

```
```

## Notes

<!-- Anything else that might help. -->

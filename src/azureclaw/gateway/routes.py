"""Core routes for the AzureClaw gateway.

Currently just ``GET /healthz``. Every channel adapter change
contributes its own ``APIRouter`` for its webhook surface; the
orchestrator change (``triage-and-typed-routing``) adds the internal
routes that the orchestrator exposes (session inspection, etc.).
"""

from __future__ import annotations

from fastapi import APIRouter

from azureclaw._version import __version__

router = APIRouter()


@router.get("/healthz")
async def healthz() -> dict[str, str]:
    """Return a stable JSON payload for liveness probes.

    Reachable without authentication — ACA's default probe and the
    external monitoring tools hit this route and cannot carry Entra
    tokens.
    """
    return {
        "status": "ok",
        "package": "azureclaw",
        "version": __version__,
    }

"""Smoke tests proving the ``azureclaw`` package is importable and exports the
public surface declared by the ``package-skeleton`` capability.
"""

from __future__ import annotations

import pytest


@pytest.mark.local
def test_package_imports_and_exposes_version() -> None:
    import azureclaw

    assert isinstance(azureclaw.__version__, str)
    assert azureclaw.__version__ != ""


@pytest.mark.local
def test_package_exports_config_class() -> None:
    import azureclaw

    assert hasattr(azureclaw, "AzureClawConfig")
    # Confirm it is the same class re-exported from the submodule
    from azureclaw.config import AzureClawConfig

    assert azureclaw.AzureClawConfig is AzureClawConfig

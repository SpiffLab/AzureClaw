"""Single source of truth for ``azureclaw.__version__``.

Kept in its own module so every caller (``azureclaw.__init__``,
``azureclaw.gateway.routes``, future observability attributes, build
artifacts) can read the version without importing the full package
surface. Avoids a circular import between ``__init__.py`` and the
gateway subpackage.
"""

from __future__ import annotations

__version__ = "0.0.0"

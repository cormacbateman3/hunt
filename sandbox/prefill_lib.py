"""Sandbox shim over the production prefill package.

The real code lives in:
    prefill/core.py               extractor + resolver (pure; prompts in prefill/config/)
    apps/prefill/services.py      ReferenceData (Django ORM vocab snapshot) + job orchestration

This module only bootstraps Django so the notebook can import everything as `P`:
    P.ReferenceData()  P.extract(...)  P.resolve(...)  P.reload_config()  P.MAX_IMAGE_EDGE ...

Reads of knobs pass through to prefill.core, so `P.reload_config()` changes are live.
To change knobs, edit prefill/config/*.json|md and call P.reload_config().
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def bootstrap_django() -> None:
    # Jupyter runs an asyncio event loop; Django blocks sync ORM calls from an async
    # context unless we opt in. Safe in a notebook/script (this only guards real async
    # web requests). Must be set before any ORM access.
    os.environ.setdefault("DJANGO_ALLOW_ASYNC_UNSAFE", "true")
    from django.apps import apps as _apps
    if _apps.ready:
        return
    sys.path.insert(0, str(PROJECT_ROOT))
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.development")
    import django
    django.setup()


bootstrap_django()

from prefill import core as _core  # noqa: E402,F401
from apps.prefill.services import ReferenceData  # noqa: E402,F401


def __getattr__(name):
    """Live passthrough to prefill.core (MAX_IMAGE_EDGE, extract, resolve, ...)."""
    return getattr(_core, name)

"""KeystoneBid image-prefill package (pure logic — no Django, no AWS).

Import `prefill.core` for the extractor + resolver; the DB-backed vocab provider
and the job orchestration live in `apps.prefill`.
"""
from prefill import core  # noqa: F401


def __getattr__(name):
    return getattr(core, name)

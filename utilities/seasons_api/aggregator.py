"""Runs adapters across the state registry and collects results.

Every state in the registry ends up in the output exactly once, tagged
with what actually happened: records pulled, an explicit error, or
"not implemented" with the real source URL. Nothing is silently
omitted — a state missing from the output would look identical to a
state with zero open seasons, which is the one failure mode this
module exists to prevent.
"""
from __future__ import annotations

from .adapters.eregulations import EregulationsAdapter
from .models import StateResult
from .registry import ADAPTER_EREGULATIONS, ADAPTER_NOT_APPLICABLE, ADAPTER_UNIMPLEMENTED, REGISTRY, StateEntry

_ADAPTERS = {
    ADAPTER_EREGULATIONS: EregulationsAdapter,
}


def run(
    state_codes: list[str] | None = None,
    season_start_year: int = 2026,
    request_delay_seconds: float = 1.0,
) -> list[StateResult]:
    """Run the appropriate adapter for each requested state.

    `state_codes=None` runs every state in the registry.
    """
    entries: list[StateEntry] = (
        list(REGISTRY.values())
        if state_codes is None
        else [REGISTRY[c.upper()] for c in state_codes]
    )

    results: list[StateResult] = []
    adapter_instances: dict[str, object] = {}

    for entry in entries:
        if entry.adapter_type in (ADAPTER_UNIMPLEMENTED, ADAPTER_NOT_APPLICABLE):
            results.append(
                StateResult(
                    state_code=entry.code,
                    state_name=entry.name,
                    adapter_type=entry.adapter_type,
                    error=entry.note,
                )
            )
            continue

        adapter_cls = _ADAPTERS.get(entry.adapter_type)
        if adapter_cls is None:
            results.append(
                StateResult(
                    state_code=entry.code,
                    state_name=entry.name,
                    adapter_type=entry.adapter_type,
                    error=f"no adapter class registered for type '{entry.adapter_type}'",
                )
            )
            continue

        adapter = adapter_instances.setdefault(
            entry.adapter_type, adapter_cls(request_delay_seconds=request_delay_seconds)
        )
        try:
            results.append(adapter.fetch(entry, season_start_year))
        except Exception as exc:  # noqa: BLE001 - never let one state crash the run
            results.append(
                StateResult(
                    state_code=entry.code,
                    state_name=entry.name,
                    adapter_type=entry.adapter_type,
                    error=f"unhandled adapter exception: {exc}",
                )
            )

    return results

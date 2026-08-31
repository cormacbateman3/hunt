"""Adapter contract. One adapter class per distinct source shape."""
from __future__ import annotations

from abc import ABC, abstractmethod

from ..models import StateResult
from ..registry import StateEntry


class BaseAdapter(ABC):
    """Turns one StateEntry into a StateResult.

    Adapters must never raise for "this page had no data" — that's a
    StateResult with an empty records list. They should raise (and let
    the caller record it as StateResult.error) only for genuine
    failures: network errors, unexpected HTML, HTTP errors. The
    aggregator is responsible for catching that and recording it
    explicitly rather than dropping the state silently.
    """

    adapter_type: str

    @abstractmethod
    def fetch(self, entry: StateEntry, season_start_year: int) -> StateResult:
        ...

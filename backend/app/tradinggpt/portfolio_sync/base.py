from __future__ import annotations

from typing import Protocol

from .models import PortfolioSnapshot


class PortfolioProvider(Protocol):
    @property
    def source(self) -> str:
        """Return the provider source identifier."""

    def get_snapshot(
        self,
    ) -> PortfolioSnapshot:
        """Return the current portfolio snapshot."""

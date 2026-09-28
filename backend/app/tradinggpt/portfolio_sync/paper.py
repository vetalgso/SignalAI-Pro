from __future__ import annotations

from .models import PortfolioSnapshot


class PaperPortfolioProvider:
    @property
    def source(self) -> str:
        return "PAPER"

    def get_snapshot(
        self,
    ) -> PortfolioSnapshot:
        return PortfolioSnapshot(
            source="PAPER",
            balances=[],
            open_orders=[],
            positions=[],
            total_wallet_balance=0.0,
        )

from __future__ import annotations

from typing import Any, Protocol

from .models import (
    AssetBalance,
    ExchangePosition,
    OpenOrder,
    PortfolioSnapshot,
)


class BinancePortfolioClientProtocol(Protocol):
    def get_account(
        self,
    ) -> dict[str, Any]:
        """Return Binance Spot account data."""

    def get_open_orders(
        self,
        **params: Any,
    ) -> list[dict[str, Any]]:
        """Return Binance Spot open orders."""


class BinancePortfolioProvider:
    def __init__(
        self,
        *,
        client: BinancePortfolioClientProtocol,
    ) -> None:
        self._client = client

    @property
    def source(self) -> str:
        return "BINANCE"

    def get_snapshot(
        self,
    ) -> PortfolioSnapshot:
        account = self._client.get_account()
        raw_orders = self._client.get_open_orders()

        balances = self._map_balances(
            account.get("balances", [])
        )
        open_orders = self._map_open_orders(
            raw_orders
        )
        positions = self._build_spot_positions(
            balances
        )

        return PortfolioSnapshot(
            source="BINANCE",
            balances=balances,
            open_orders=open_orders,
            positions=positions,
            total_wallet_balance=None,
        )

    @classmethod
    def _map_balances(
        cls,
        raw_balances: object,
    ) -> list[AssetBalance]:
        if not isinstance(raw_balances, list):
            return []

        balances: list[AssetBalance] = []

        for raw_balance in raw_balances:
            if not isinstance(raw_balance, dict):
                continue

            asset = str(
                raw_balance.get("asset", "")
            ).strip()

            free = cls._to_float(
                raw_balance.get("free")
            )
            locked = cls._to_float(
                raw_balance.get("locked")
            )

            if not asset:
                continue

            if free <= 0.0 and locked <= 0.0:
                continue

            balances.append(
                AssetBalance(
                    asset=asset,
                    free=max(free, 0.0),
                    locked=max(locked, 0.0),
                )
            )

        return balances

    @classmethod
    def _map_open_orders(
        cls,
        raw_orders: object,
    ) -> list[OpenOrder]:
        if not isinstance(raw_orders, list):
            return []

        orders: list[OpenOrder] = []

        for raw_order in raw_orders:
            if not isinstance(raw_order, dict):
                continue

            order_id = raw_order.get("orderId")
            symbol = str(
                raw_order.get("symbol", "")
            ).strip()
            side = str(
                raw_order.get("side", "")
            ).upper()

            if (
                order_id is None
                or not symbol
                or side not in {"BUY", "SELL"}
            ):
                continue

            client_order_id = raw_order.get(
                "clientOrderId"
            )

            orders.append(
                OpenOrder(
                    exchange_order_id=str(order_id),
                    client_order_id=(
                        str(client_order_id)
                        if client_order_id is not None
                        else None
                    ),
                    symbol=symbol,
                    side=side,
                    order_type=str(
                        raw_order.get(
                            "type",
                            "UNKNOWN",
                        )
                    ).upper(),
                    status=str(
                        raw_order.get(
                            "status",
                            "UNKNOWN",
                        )
                    ).upper(),
                    price=max(
                        cls._to_float(
                            raw_order.get("price")
                        ),
                        0.0,
                    ),
                    original_quantity=max(
                        cls._to_float(
                            raw_order.get("origQty")
                        ),
                        0.0,
                    ),
                    executed_quantity=max(
                        cls._to_float(
                            raw_order.get(
                                "executedQty"
                            )
                        ),
                        0.0,
                    ),
                )
            )

        return orders

    @staticmethod
    def _build_spot_positions(
        balances: list[AssetBalance],
    ) -> list[ExchangePosition]:
        return [
            ExchangePosition(
                symbol=balance.asset,
                quantity=balance.total,
                entry_price=None,
                unrealized_pnl=0.0,
            )
            for balance in balances
        ]

    @staticmethod
    def _to_float(
        value: object,
    ) -> float:
        try:
            return float(value)
        except (TypeError, ValueError):
            return 0.0

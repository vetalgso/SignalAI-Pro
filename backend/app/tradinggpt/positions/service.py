from __future__ import annotations

from app.models.trading_position import TradingPosition

from .manager import PositionManager
from .repository import TradingPositionRepository
from .schemas import PositionCreateRequest


class PositionService:
    def __init__(
        self,
        *,
        repository: TradingPositionRepository,
    ) -> None:
        self._repository = repository
        self._manager = PositionManager(
            repository=repository
        )

    def create(
        self,
        request: PositionCreateRequest,
    ) -> dict[str, object]:
        position = self._repository.create(
            exchange=request.exchange,
            market_type=request.market_type,
            symbol=request.symbol,
            side=request.side,
            quantity=request.quantity,
            entry_price=request.entry_price,
            stop_loss=request.stop_loss,
            take_profit_1=request.take_profit_1,
            take_profit_2=request.take_profit_2,
            journal_order_id=request.journal_order_id,
            tp1_close_percent=(
                request.tp1_close_percent
            ),
            price_source=request.price_source,
            max_price_deviation_percent=(
                request.max_price_deviation_percent
            ),
            metadata_payload=(
                request.metadata_payload
            ),
        )

        self._repository._session.commit()
        self._repository._session.refresh(position)

        return PositionManager.serialize(
            position,
            actions=["POSITION_CREATED"],
        )

    def get(
        self,
        position_id: int,
    ) -> dict[str, object] | None:
        position = self._repository.get(position_id)

        if position is None:
            return None

        return PositionManager.serialize(position)

    def list_positions(
        self,
        *,
        status: str | None,
        exchange: str | None,
        symbol: str | None,
        limit: int,
    ) -> list[dict[str, object]]:
        positions = self._repository.list_positions(
            status=status,
            exchange=exchange,
            symbol=symbol,
            limit=limit,
        )

        return [
            PositionManager.serialize(position)
            for position in positions
        ]

    def update_price(
        self,
        *,
        position_id: int,
        current_price: float,
    ) -> dict[str, object] | None:
        position = self._repository.get(position_id)

        if position is None:
            return None

        result = self._manager.update_price(
            position=position,
            current_price=current_price,
        )

        self._repository._session.commit()
        self._repository._session.refresh(position)

        return PositionManager.serialize(
            position,
            actions=list(result["actions"]),
        )

    def close(
        self,
        *,
        position_id: int,
        exit_price: float,
    ) -> dict[str, object] | None:
        position = self._repository.get(position_id)

        if position is None:
            return None

        result = self._manager.close_manually(
            position=position,
            exit_price=exit_price,
        )

        self._repository._session.commit()
        self._repository._session.refresh(position)

        return PositionManager.serialize(
            position,
            actions=list(result["actions"]),
        )

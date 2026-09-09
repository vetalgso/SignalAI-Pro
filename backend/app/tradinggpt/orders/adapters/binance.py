from __future__ import annotations

from decimal import Decimal, ROUND_DOWN
from typing import Any, Protocol

from ..execution_models import OrderExecutionResult
from ..models import ExchangeName, OrderIntent
from ..validation_models import OrderPreviewResult, SymbolTradingRules


class BinanceClientProtocol(Protocol):
    def create_order(self, **params: Any) -> dict[str, Any]: ...
    def get_order(self, **params: Any) -> dict[str, Any]: ...
    def cancel_order(self, **params: Any) -> dict[str, Any]: ...
    def get_open_orders(self, **params: Any) -> list[dict[str, Any]]: ...
    def get_symbol_info(self, symbol: str) -> dict[str, Any] | None: ...
    def get_symbol_ticker(self, **params: Any) -> dict[str, Any]: ...
    def get_asset_balance(self, **params: Any) -> dict[str, Any] | None: ...


class BinanceOrderAdapter:
    def __init__(self, *, client: BinanceClientProtocol, testnet: bool = True) -> None:
        self._client = client
        self._testnet = testnet

    @property
    def exchange(self) -> ExchangeName:
        return "BINANCE"

    def execute(self, *, intent: OrderIntent, client_order_id: str) -> OrderExecutionResult:
        if intent.exchange != self.exchange:
            raise ValueError("BinanceOrderAdapter only supports BINANCE orders.")
        if intent.market_type != "SPOT":
            return self._failed(intent.symbol, intent.side, intent.order_type, client_order_id, None, intent.quantity, "Binance futures execution is not supported by this adapter.")

        preview = self.preview(intent=intent)
        if not preview.valid:
            return self._failed(intent.symbol, intent.side, intent.order_type, client_order_id, None, intent.quantity, "Pre-trade validation failed: " + "; ".join(preview.errors))

        normalized_intent = OrderIntent(
            exchange=intent.exchange,
            market_type=intent.market_type,
            symbol=intent.symbol,
            side=intent.side,
            order_type=intent.order_type,
            quantity=preview.normalized_quantity,
            reference_price=preview.normalized_price,
            stop_loss=intent.stop_loss,
            take_profit_1=intent.take_profit_1,
            take_profit_2=intent.take_profit_2,
            leverage=intent.leverage,
            reduce_only=intent.reduce_only,
        )
        try:
            response = self._client.create_order(**self._build_order_params(normalized_intent, client_order_id))
        except Exception as exc:
            return self._failed(intent.symbol, intent.side, intent.order_type, client_order_id, None, intent.quantity, f"Binance order failed: {exc}")
        return self._map_response(response, intent.symbol, intent.side, intent.order_type, client_order_id, normalized_intent.quantity, "Binance order status")

    def get_order(self, *, symbol: str, order_id: str) -> OrderExecutionResult:
        try:
            response = self._client.get_order(symbol=symbol, orderId=order_id)
        except Exception as exc:
            return self._failed(symbol, "BUY", "LIMIT", "", order_id, 0.0, f"Binance get order failed: {exc}")
        return self._map_response(response, symbol, "BUY", "LIMIT", "", 0.0, "Binance order status")

    def cancel_order(self, *, symbol: str, order_id: str) -> OrderExecutionResult:
        try:
            response = self._client.cancel_order(symbol=symbol, orderId=order_id)
        except Exception as exc:
            return self._failed(symbol, "BUY", "LIMIT", "", order_id, 0.0, f"Binance cancel order failed: {exc}")
        return self._map_response(response, symbol, "BUY", "LIMIT", "", 0.0, "Binance cancel status")

    def list_open_orders(self, *, symbol: str | None = None) -> list[OrderExecutionResult]:
        try:
            responses = self._client.get_open_orders(**({"symbol": symbol} if symbol else {}))
        except Exception as exc:
            return [self._failed(symbol or "", "BUY", "LIMIT", "", None, 0.0, f"Binance open orders failed: {exc}")]
        return [self._map_response(r, symbol or "", "BUY", "LIMIT", "", 0.0, "Binance order status") for r in responses]

    def get_symbol_rules(self, *, symbol: str) -> SymbolTradingRules:
        info = self._client.get_symbol_info(symbol)
        if not info:
            raise ValueError(f"Binance symbol is unavailable: {symbol}.")
        filters = {str(item.get("filterType")): item for item in info.get("filters", []) if isinstance(item, dict)}
        lot = filters.get("LOT_SIZE", {})
        price = filters.get("PRICE_FILTER", {})
        notional = filters.get("MIN_NOTIONAL", filters.get("NOTIONAL", {}))
        return SymbolTradingRules(
            exchange="BINANCE",
            symbol=symbol,
            status=str(info.get("status", "UNKNOWN")),
            base_asset=str(info.get("baseAsset", "")),
            quote_asset=str(info.get("quoteAsset", "")),
            min_quantity=self._optional_float(lot.get("minQty")),
            max_quantity=self._optional_float(lot.get("maxQty")),
            quantity_step=self._optional_float(lot.get("stepSize")),
            min_price=self._optional_float(price.get("minPrice")),
            max_price=self._optional_float(price.get("maxPrice")),
            price_tick=self._optional_float(price.get("tickSize")),
            min_notional=self._optional_float(notional.get("minNotional")),
        )

    def preview(self, *, intent: OrderIntent) -> OrderPreviewResult:
        errors: list[str] = []
        warnings: list[str] = []
        rules = self.get_symbol_rules(symbol=intent.symbol)
        quantity = self._floor_step(intent.quantity, rules.quantity_step)
        price = intent.reference_price
        if intent.order_type == "MARKET":
            ticker = self._client.get_symbol_ticker(symbol=intent.symbol)
            price = self._optional_float(ticker.get("price"))
        normalized_price = self._floor_step(price, rules.price_tick) if price is not None else None

        if rules.status != "TRADING": errors.append(f"Symbol status is {rules.status}, not TRADING.")
        if quantity <= 0: errors.append("Quantity becomes zero after step-size normalization.")
        if rules.min_quantity is not None and quantity < rules.min_quantity: errors.append(f"Quantity {quantity} is below minimum {rules.min_quantity}.")
        if rules.max_quantity is not None and quantity > rules.max_quantity: errors.append(f"Quantity {quantity} exceeds maximum {rules.max_quantity}.")
        if intent.order_type == "LIMIT" and normalized_price is None: errors.append("LIMIT order requires a price.")
        if normalized_price is not None:
            if rules.min_price is not None and normalized_price < rules.min_price: errors.append(f"Price {normalized_price} is below minimum {rules.min_price}.")
            if rules.max_price is not None and normalized_price > rules.max_price: errors.append(f"Price {normalized_price} exceeds maximum {rules.max_price}.")

        notional = quantity * normalized_price if normalized_price is not None else None
        if rules.min_notional is not None and notional is not None and notional < rules.min_notional:
            errors.append(f"Order notional {notional:.8f} is below minimum {rules.min_notional}.")

        balance_asset = rules.quote_asset if intent.side == "BUY" else rules.base_asset
        available = None
        balance_getter = getattr(self._client, "get_asset_balance", None)
        if balance_getter is not None and balance_asset:
            raw = balance_getter(asset=balance_asset)
            available = self._optional_float(raw.get("free")) if isinstance(raw, dict) else 0.0
            required = notional if intent.side == "BUY" else quantity
            if required is not None and available is not None and available < required:
                errors.append(f"Insufficient {balance_asset} balance: available {available}, required {required:.8f}.")
        else:
            warnings.append("Balance check was skipped because the client does not expose get_asset_balance.")

        if quantity != intent.quantity: warnings.append(f"Quantity normalized from {intent.quantity} to {quantity}.")
        if price is not None and normalized_price != price: warnings.append(f"Price normalized from {price} to {normalized_price}.")

        return OrderPreviewResult(
            exchange="BINANCE", symbol=intent.symbol, side=intent.side, order_type=intent.order_type,
            valid=not errors, requested_quantity=intent.quantity, normalized_quantity=quantity,
            requested_price=intent.reference_price, normalized_price=normalized_price,
            estimated_notional=notional, available_balance=available, balance_asset=balance_asset or None,
            errors=errors, warnings=warnings,
        )

    @staticmethod
    def _build_order_params(intent: OrderIntent, client_order_id: str) -> dict[str, object]:
        params: dict[str, object] = {"symbol": intent.symbol, "side": intent.side, "type": intent.order_type, "quantity": BinanceOrderAdapter._decimal_string(intent.quantity), "newClientOrderId": client_order_id, "newOrderRespType": "FULL"}
        if intent.order_type == "LIMIT":
            if intent.reference_price is None: raise ValueError("Reference price is required for LIMIT orders.")
            params["price"] = BinanceOrderAdapter._decimal_string(intent.reference_price)
            params["timeInForce"] = "GTC"
        return params

    def _map_response(self, response: dict[str, Any], fallback_symbol: str, fallback_side: str, fallback_order_type: str, fallback_client_order_id: str, fallback_quantity: float, message_prefix: str) -> OrderExecutionResult:
        exchange_status = str(response.get("status", "UNKNOWN")).upper()
        status = {"FILLED":"FILLED", "NEW":"OPEN", "PARTIALLY_FILLED":"PARTIALLY_FILLED", "CANCELED":"CANCELED", "REJECTED":"REJECTED", "EXPIRED":"REJECTED", "EXPIRED_IN_MATCH":"REJECTED"}.get(exchange_status, "FAILED")
        requested = self._to_float(response.get("origQty"), fallback_quantity)
        filled = self._to_float(response.get("executedQty"), 0.0)
        avg = self._resolve_average_price(response, filled)
        oid = response.get("orderId")
        cid = response.get("clientOrderId") or response.get("origClientOrderId") or fallback_client_order_id
        return OrderExecutionResult("BINANCE", str(response.get("symbol", fallback_symbol)), str(response.get("side", fallback_side)).upper(), str(response.get("type", fallback_order_type)).upper(), status, str(cid), str(oid) if oid is not None else None, requested, filled, avg, self._testnet, f"{message_prefix}: {exchange_status}.")

    def _failed(self, symbol: str, side: str, order_type: str, client_order_id: str, exchange_order_id: str | None, requested_quantity: float, message: str) -> OrderExecutionResult:
        return OrderExecutionResult("BINANCE", symbol, side, order_type, "FAILED", client_order_id, exchange_order_id, requested_quantity, 0.0, None, self._testnet, message)

    @staticmethod
    def _resolve_average_price(response: dict[str, Any], filled_quantity: float) -> float | None:
        fills = response.get("fills")
        if isinstance(fills, list) and fills:
            total_qty = sum(BinanceOrderAdapter._to_float(f.get("qty"), 0.0) for f in fills if isinstance(f, dict))
            total_quote = sum(BinanceOrderAdapter._to_float(f.get("qty"), 0.0) * BinanceOrderAdapter._to_float(f.get("price"), 0.0) for f in fills if isinstance(f, dict))
            if total_qty > 0: return total_quote / total_qty
        cumulative = BinanceOrderAdapter._to_float(response.get("cummulativeQuoteQty"), 0.0)
        return cumulative / filled_quantity if filled_quantity > 0 and cumulative > 0 else None

    @staticmethod
    def _floor_step(value: float | None, step: float | None) -> float:
        if value is None: return 0.0
        if not step: return float(value)
        dvalue, dstep = Decimal(str(value)), Decimal(str(step))
        return float((dvalue / dstep).to_integral_value(rounding=ROUND_DOWN) * dstep)

    @staticmethod
    def _decimal_string(value: float) -> str:
        return format(value, ".16g")

    @staticmethod
    def _to_float(value: object, default: float) -> float:
        try: return float(value)
        except (TypeError, ValueError): return default

    @staticmethod
    def _optional_float(value: object) -> float | None:
        try: return float(value)
        except (TypeError, ValueError): return None

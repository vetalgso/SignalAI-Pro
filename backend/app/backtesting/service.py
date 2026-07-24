from __future__ import annotations

from typing import Any

from app.indicators.service import calculate_indicator_snapshot
from app.signal_engine.service import build_signal_analysis


def run_backtest(candles: list[dict[str, Any]], warmup: int = 220) -> dict[str, Any]:
    if len(candles) <= warmup + 1:
        raise ValueError(f"At least {warmup + 2} candles are required")

    trades: list[dict[str, Any]] = []
    equity = 1.0
    peak = 1.0
    max_drawdown = 0.0
    i = warmup

    while i < len(candles) - 1:
        snapshot = calculate_indicator_snapshot(candles[: i + 1])
        analysis = build_signal_analysis(snapshot)
        if analysis["action"] == "WAIT" or not analysis["levels"]:
            i += 1
            continue

        side = analysis["action"]
        entry = float(candles[i + 1]["open"])
        planned_entry = float(analysis["levels"]["entry"])
        planned_sl = float(analysis["levels"]["stop_loss"])
        planned_tp = float(analysis["levels"]["take_profit"])
        risk_distance = abs(planned_entry - planned_sl)
        if risk_distance <= 0:
            i += 1
            continue

        stop = entry - risk_distance if side == "LONG" else entry + risk_distance
        target = entry + risk_distance * 2 if side == "LONG" else entry - risk_distance * 2
        exit_price = float(candles[-1]["close"])
        outcome = "OPEN"
        exit_index = len(candles) - 1

        for j in range(i + 1, len(candles)):
            high = float(candles[j]["high"])
            low = float(candles[j]["low"])
            # Conservative rule: if both are touched in one candle, count stop first.
            if side == "LONG":
                if low <= stop:
                    exit_price, outcome, exit_index = stop, "LOSS", j
                    break
                if high >= target:
                    exit_price, outcome, exit_index = target, "WIN", j
                    break
            else:
                if high >= stop:
                    exit_price, outcome, exit_index = stop, "LOSS", j
                    break
                if low <= target:
                    exit_price, outcome, exit_index = target, "WIN", j
                    break

        r_multiple = ((exit_price - entry) / risk_distance) * (1 if side == "LONG" else -1)
        r_multiple = max(-1.0, min(2.0, r_multiple))
        equity *= 1 + r_multiple * 0.01  # fixed 1% account risk per trade
        peak = max(peak, equity)
        max_drawdown = max(max_drawdown, (peak - equity) / peak * 100)
        trades.append({
            "side": side,
            "entry_time": candles[i + 1]["open_time"],
            "exit_time": candles[exit_index]["close_time"],
            "entry": round(entry, 8),
            "stop_loss": round(stop, 8),
            "take_profit": round(target, 8),
            "exit": round(exit_price, 8),
            "outcome": outcome,
            "r_multiple": round(r_multiple, 4),
            "confidence": analysis["confidence"],
        })
        i = max(i + 1, exit_index + 1)

    wins = sum(t["outcome"] == "WIN" for t in trades)
    losses = sum(t["outcome"] == "LOSS" for t in trades)
    closed = wins + losses
    total_r = sum(t["r_multiple"] for t in trades)
    gross_profit = sum(max(0, t["r_multiple"]) for t in trades)
    gross_loss = abs(sum(min(0, t["r_multiple"]) for t in trades))
    return {
        "summary": {
            "candles": len(candles),
            "trades": len(trades),
            "wins": wins,
            "losses": losses,
            "open": len(trades) - closed,
            "win_rate": round((wins / closed * 100) if closed else 0, 2),
            "total_r": round(total_r, 4),
            "return_percent": round((equity - 1) * 100, 2),
            "max_drawdown_percent": round(max_drawdown, 2),
            "profit_factor": round(gross_profit / gross_loss, 3) if gross_loss else None,
            "risk_per_trade_percent": 1.0,
        },
        "trades": trades[-100:],
        "assumptions": [
            "Signals use only candles available at decision time.",
            "Entry is the next candle open.",
            "Risk is fixed at 1% per trade and reward target is 2R.",
            "Fees, slippage and funding are not included.",
            "If stop and target occur in one candle, stop is counted first.",
        ],
    }

"""Twelve Data MCP server.

Exposes the Twelve Data market-data API as MCP tools so Claude Desktop (or any
MCP client) can pull live quotes, historical series, technical indicators,
forex rates, and fundamentals into a chat.

The Twelve Data API key is resolved from, in order:
  1. the TWELVEDATA_API_KEY environment variable
  2. a `.env` file sitting next to this script

Run standalone (stdio transport, what Claude Desktop uses):
    ./.venv/bin/python td_mcp_server.py
"""

from __future__ import annotations

import functools
import sys
from pathlib import Path
from typing import Any, Callable, Optional

from mcp.server.fastmcp import FastMCP
from twelvedata import TDClient


# --------------------------------------------------------------------------- #
# API key resolution
# --------------------------------------------------------------------------- #
def _resolve_api_key() -> Optional[str]:
    import os

    key = os.environ.get("TWELVEDATA_API_KEY")
    if key:
        return key.strip()

    env_path = Path(__file__).with_name(".env")
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            name, _, value = line.partition("=")
            if name.strip() == "TWELVEDATA_API_KEY":
                return value.strip().strip("\"'")
    return None


API_KEY = _resolve_api_key()
if not API_KEY:
    print(
        "[twelvedata-mcp] WARNING: TWELVEDATA_API_KEY not found "
        "(env var or .env). Tools will return an error until it is set.",
        file=sys.stderr,
    )

_td = TDClient(apikey=API_KEY) if API_KEY else None


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def _normalize(data: Any) -> Any:
    """Unwrap SDK result objects and turn tuples into lists (JSON-friendly)."""
    if hasattr(data, "as_json"):
        data = data.as_json()
    if isinstance(data, tuple):
        data = list(data)
    return data


def _result(data: Any) -> dict:
    """Guarantee a dict at the top level (some MCP clients require object output)."""
    data = _normalize(data)
    return data if isinstance(data, dict) else {"values": data}


def tool_call(fn: Callable) -> Callable:
    """Wrap a tool body: guard on the API key and convert exceptions to a
    clean {"error": ...} payload instead of crashing the server."""

    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        if _td is None:
            return {
                "error": "TWELVEDATA_API_KEY is not configured. Set it in the "
                "environment or in the .env file next to td_mcp_server.py."
            }
        try:
            return fn(*args, **kwargs)
        except Exception as exc:  # noqa: BLE001 - surface any SDK/HTTP error to the client
            return {"error": f"{type(exc).__name__}: {exc}"}

    return wrapper


mcp = FastMCP(
    "twelvedata",
    instructions=(
        "Live and historical market data via Twelve Data. Use search_symbols to "
        "resolve a company/ticker, get_price/get_quote for the latest snapshot, "
        "get_time_series for OHLCV history, get_technical_indicator (see "
        "list_indicators) for RSI/MACD/SMA/etc., get_exchange_rate & "
        "convert_currency for forex, and get_company_profile/get_statistics/"
        "get_earnings/get_dividends for fundamentals. Symbols are like 'AAPL', "
        "'MSFT', 'BTC/USD', 'USD/JPY'. Prices are point-in-time, not investment "
        "advice."
    ),
)


# --------------------------------------------------------------------------- #
# Reference / discovery
# --------------------------------------------------------------------------- #
@mcp.tool()
@tool_call
def search_symbols(query: str, outputsize: int = 10) -> dict:
    """Search for instruments (stocks, ETFs, forex, crypto) by name or ticker.

    Args:
        query: Company name or ticker fragment, e.g. "Apple" or "AAPL".
        outputsize: Max number of matches to return (default 10).
    """
    res = _normalize(_td.symbol_search(symbol=query, outputsize=outputsize))
    res = list(res) if isinstance(res, list) else res
    return {"query": query, "count": len(res), "results": res}


@mcp.tool()
def list_indicators() -> dict:
    """List the technical-indicator names accepted by get_technical_indicator."""
    ts = TDClient(apikey="x").time_series(symbol="AAPL", interval="1day")
    names = sorted(m[len("with_"):] for m in dir(ts) if m.startswith("with_"))
    return {"count": len(names), "indicators": names}


# --------------------------------------------------------------------------- #
# Prices & quotes
# --------------------------------------------------------------------------- #
@mcp.tool()
@tool_call
def get_price(symbol: str) -> dict:
    """Latest real-time price for a symbol (e.g. 'AAPL', 'BTC/USD')."""
    res = _normalize(_td.price(symbol=symbol))
    price = res.get("price") if isinstance(res, dict) else res
    return {"symbol": symbol.upper(), "price": float(price)}


@mcp.tool()
@tool_call
def get_quote(symbol: str, interval: str = "1day") -> dict:
    """Full quote snapshot: open/high/low/close, volume, change, 52-week range.

    Args:
        symbol: e.g. "AAPL", "MSFT", "BTC/USD".
        interval: Bar interval for the quote (default "1day").
    """
    return _result(_td.quote(symbol=symbol, interval=interval))


@mcp.tool()
@tool_call
def get_time_series(
    symbol: str,
    interval: str = "1day",
    outputsize: int = 30,
    order: str = "desc",
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
) -> dict:
    """Historical OHLCV time series.

    Args:
        symbol: e.g. "AAPL", "EUR/USD".
        interval: 1min, 5min, 15min, 30min, 45min, 1h, 2h, 4h, 1day, 1week, 1month.
        outputsize: Number of bars (max 5000; ignored if start/end given).
        order: "desc" (newest first) or "asc".
        start_date: Optional "YYYY-MM-DD" (or "YYYY-MM-DD HH:MM:SS") lower bound.
        end_date: Optional upper bound, same format.
    """
    kwargs: dict[str, Any] = dict(
        symbol=symbol, interval=interval, outputsize=outputsize, order=order
    )
    if start_date:
        kwargs["start_date"] = start_date
    if end_date:
        kwargs["end_date"] = end_date
    values = _normalize(_td.time_series(**kwargs))
    return {
        "symbol": symbol.upper(),
        "interval": interval,
        "count": len(values) if isinstance(values, list) else None,
        "values": values,
    }


@mcp.tool()
@tool_call
def get_technical_indicator(
    symbol: str,
    indicator: str,
    interval: str = "1day",
    outputsize: int = 30,
    params: Optional[dict] = None,
) -> dict:
    """Compute a technical indicator over a symbol's time series.

    Args:
        symbol: e.g. "AAPL".
        indicator: Indicator name from list_indicators (e.g. "rsi", "macd",
            "sma", "ema", "bbands", "stoch", "adx", "atr", "vwap").
        interval: Bar interval (default "1day").
        outputsize: Number of bars to return (default 30).
        params: Optional indicator parameters, e.g. {"time_period": 14} for rsi,
            {"fast_period": 12, "slow_period": 26, "signal_period": 9} for macd.
    """
    method = f"with_{indicator.lower().strip()}"
    ts = _td.time_series(symbol=symbol, interval=interval, outputsize=outputsize)
    if not hasattr(ts, method):
        return {
            "error": f"Unknown indicator '{indicator}'. "
            "Call list_indicators for valid names."
        }
    ts = getattr(ts, method)(**(params or {}))
    values = _normalize(ts)
    return {
        "symbol": symbol.upper(),
        "indicator": indicator.lower().strip(),
        "interval": interval,
        "params": params or {},
        "values": values,
    }


# --------------------------------------------------------------------------- #
# Forex
# --------------------------------------------------------------------------- #
@mcp.tool()
@tool_call
def get_exchange_rate(symbol: str) -> dict:
    """Current exchange rate for a currency pair, e.g. symbol="USD/JPY"."""
    return _result(_td.exchange_rate(symbol=symbol))


@mcp.tool()
@tool_call
def convert_currency(symbol: str, amount: float) -> dict:
    """Convert an amount across a currency pair.

    Args:
        symbol: Pair "FROM/TO", e.g. "USD/EUR".
        amount: Amount in the FROM currency.
    """
    return _result(_td.currency_conversion(symbol=symbol, amount=amount))


# --------------------------------------------------------------------------- #
# Fundamentals (availability depends on your Twelve Data plan)
# --------------------------------------------------------------------------- #
@mcp.tool()
@tool_call
def get_company_profile(symbol: str) -> dict:
    """Company profile: sector, industry, description, employees, website."""
    return _result(_td.get_profile(symbol=symbol))


@mcp.tool()
@tool_call
def get_statistics(symbol: str) -> dict:
    """Key statistics & valuation: market cap, P/E, margins, dividend yield, etc."""
    return _result(_td.get_statistics(symbol=symbol))


@mcp.tool()
@tool_call
def get_earnings(symbol: str) -> dict:
    """Historical and upcoming earnings (EPS estimate vs. actual)."""
    return _result(_td.get_earnings(symbol=symbol))


@mcp.tool()
@tool_call
def get_dividends(symbol: str) -> dict:
    """Dividend payment history for a symbol."""
    return _result(_td.get_dividends(symbol=symbol))


# --------------------------------------------------------------------------- #
# Account
# --------------------------------------------------------------------------- #
@mcp.tool()
@tool_call
def get_api_usage() -> dict:
    """Current API credit usage against your plan's rate limit."""
    return _result(_td.api_usage())


if __name__ == "__main__":
    mcp.run()

"""Quickstart for the Twelve Data SDK.

Reads TWELVEDATA_API_KEY from the environment (or a .env file if present),
fetches a daily time series for AAPL, prints it as a pandas DataFrame, and
saves a candlestick chart.

Run:
    source .venv/bin/activate
    python example.py
"""

import os
from pathlib import Path

from twelvedata import TDClient


def load_env() -> None:
    """Minimal .env loader so we don't need python-dotenv."""
    env_file = Path(__file__).with_name(".env")
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            os.environ.setdefault(key.strip(), value.strip())


def main() -> None:
    load_env()
    api_key = os.environ.get("TWELVEDATA_API_KEY")
    if not api_key:
        raise SystemExit(
            "Set TWELVEDATA_API_KEY (copy .env.example to .env and fill it in)."
        )

    td = TDClient(apikey=api_key)

    ts = td.time_series(
        symbol="AAPL",
        interval="1day",
        outputsize=30,
    )

    # pandas extra
    df = ts.as_pandas()
    print(df.head())

    # plotly extra -> interactive HTML chart
    ts.as_plotly_figure().write_html("aapl.html")
    print("Wrote aapl.html")


if __name__ == "__main__":
    main()

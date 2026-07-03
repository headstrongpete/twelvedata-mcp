# twelvedata

Python environment for the [Twelve Data](https://twelvedata.com/) SDK, plus an
**MCP server** that exposes live market data to Claude Desktop.

## Setup

```bash
git clone https://github.com/headstrongpete/twelvedata-mcp.git
cd twelvedata-mcp
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## API key

Get a key at https://twelvedata.com/account/api-keys, then:

```bash
cp .env.example .env   # edit .env and paste your key
```

Both the example script and the MCP server read `TWELVEDATA_API_KEY` from the
environment, falling back to this `.env` file.

## Run the example

```bash
source .venv/bin/activate
python example.py       # fetches AAPL, prints a DataFrame, writes aapl.html
```

## MCP server (Claude Desktop)

`td_mcp_server.py` is an MCP server that lets Claude pull market data into a chat.

**Tools exposed:**

| Tool | Description |
|------|-------------|
| `search_symbols` | Find tickers by name/ticker |
| `get_price` | Latest real-time price |
| `get_quote` | Full quote (OHLCV, change, 52-wk range) |
| `get_time_series` | Historical OHLCV bars |
| `get_technical_indicator` | Any of 103 indicators (RSI, MACD, SMA, …) |
| `list_indicators` | Names accepted by `get_technical_indicator` |
| `get_exchange_rate` | Forex rate for a pair (e.g. `USD/JPY`) |
| `convert_currency` | Convert an amount across a pair |
| `get_company_profile` | Sector, industry, description (plan-dependent) |
| `get_statistics` | Valuation & key stats (plan-dependent) |
| `get_earnings` | Earnings history/estimates (plan-dependent) |
| `get_dividends` | Dividend history (plan-dependent) |
| `get_api_usage` | Remaining API credits on your plan |

### Wiring it into Claude Desktop

Add a `twelvedata` entry to your `claude_desktop_config.json`:

- macOS: `~/Library/Application Support/Claude/claude_desktop_config.json`
- Windows: `%APPDATA%\Claude\claude_desktop_config.json`

```json
{
  "mcpServers": {
    "twelvedata": {
      "command": "/absolute/path/to/twelvedata-mcp/.venv/bin/python",
      "args": ["/absolute/path/to/twelvedata-mcp/td_mcp_server.py"]
    }
  }
}
```

Use **absolute** paths. The API key is **not** stored in the config — the
server loads it from the `.env` file next to `td_mcp_server.py`.

**To activate: fully quit and reopen Claude Desktop.** Then in a chat, the
`twelvedata` tools appear under the tools/🔌 menu. Try: *"What's the current RSI
for NVDA?"* or *"Compare the last month of AAPL vs MSFT."*

### Run / debug the server manually

```bash
source .venv/bin/activate
python td_mcp_server.py          # stdio server (Ctrl-C to stop)
# or inspect it interactively:
mcp dev td_mcp_server.py
```

## Notes

- The websocket extra is named **`websocket`** (installs `websocket-client`),
  not `websocket-client`. Pinned versions are in `requirements-lock.txt`.
- Fundamentals tools (`get_company_profile`, `get_statistics`, `get_earnings`,
  `get_dividends`) depend on your Twelve Data plan; on the free tier they may
  return an "not available" error, which the tool surfaces cleanly.
- Prices are point-in-time market data, not investment advice.

## License

[MIT](LICENSE) © Peter Squires

# PolyEdge Analyzer

**Polymarket Sports EV/Edge Scanner** — A Windows desktop app that analyzes Polymarket sports prediction markets in real-time, showing expected value, edge, and Kelly-based stake recommendations.

> **⚠️ RISK WARNING**: This software is an **informational tool only**. It does NOT guarantee profits. You may lose your entire investment. Prediction market participation may be restricted in your jurisdiction. This is NOT financial advice. Use at your own risk.

---

## One-Line Install (Windows)

Open **PowerShell** and run:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -Command "irm https://raw.githubusercontent.com/baekins/polyedge-analyzer/main/install.ps1 | iex"
```

> Replace `OWNER` with the actual GitHub username/org.

This will:
1. Download the latest `.exe` from GitHub Releases
2. Install to `%LOCALAPPDATA%\PolyEdgeAnalyzer\`
3. Create a Desktop shortcut
4. Create a Start Menu entry

### First Run

1. Double-click the **PolyEdgeAnalyzer** shortcut on your Desktop
2. **Accept the risk disclaimer** (required on first run)
3. Click **🔄 Refresh Now** to load sports markets
4. Double-click any row to open that market on Polymarket

---

## What It Shows

For each sports market outcome (Yes/No):

| Column | Meaning |
|--------|---------|
| Bid/Ask/Mid | Current orderbook prices |
| Spread | Ask − Bid |
| Depth | Total liquidity on bid/ask sides |
| Fee (bps) | Polymarket fee rate in basis points |
| p̂ | Estimated true probability |
| q_eff | Effective buy price (fees + slippage included) |
| Edge | p̂ − q_eff (positive = potential opportunity) |
| EV/$ | Expected value per dollar risked |
| ROI% | Expected return on investment |
| Kelly | Raw Kelly criterion fraction |
| Stake | Recommended stake (half-Kelly, capped) |

### How Calculations Work

- **Effective price**: `q_eff = q / (1 − r × min(q, 1−q) × q)` where `r` = fee rate
- **Edge**: `p̂ − q_eff`
- **Kelly fraction**: `f* = (p̂ − q_eff) / (1 − q_eff)`
- **Stake**: `min(bankroll × f* × kelly_fraction, bankroll × max_bet_pct)`

All values shown are **conditional estimates**, not guarantees. The "edge" depends entirely on the accuracy of probability estimates, which are inherently uncertain.

---

## Settings

Click **⚙️ Settings** to configure:

- **Bankroll**: Your total capital in USDT (default: 5,000)
- **Kelly fraction**: Fraction of full Kelly to use (default: 0.5 = half-Kelly)
- **Max bet %**: Maximum single bet as % of bankroll (default: 3%)
- **Min edge / Min liquidity**: Filter thresholds
- **Refresh interval**: Auto-refresh period in seconds
- **Claude AI**: Optional AI-powered risk analysis (requires API key)
- **Probability weights**: Weights for market/sportsbook/model/AI signals

### Claude AI Integration (Optional)

If you have an Anthropic API key:

1. Open Settings → enable "Claude analysis"
2. Enter your `sk-ant-...` key
3. Claude will provide structured risk summaries and factor analysis

Claude is used for **context and risk flagging only** — it does not "predict" outcomes. Calls are cached and throttled to manage costs.

### Environment Variables

You can alternatively set `ANTHROPIC_API_KEY` as an environment variable instead of entering it in Settings.

---

## Developer Setup

### Prerequisites
- Python 3.11+
- Git

### Quick Start

```powershell
git clone https://github.com/baekins/polyedge-analyzer.git
cd polyedge-analyzer
.\run_local.ps1
```

Or manually:

```bash
python -m venv .venv
.venv\Scripts\activate   # Windows
pip install -e ".[dev]"
python -m app.main
```

### Run Tests

```bash
pytest tests/ -v
```

### Build EXE Locally

```bash
pip install pyinstaller
pyinstaller --onefile --windowed --name PolyEdgeAnalyzer app/main.py
```

### Lint & Type Check

```bash
ruff check .
mypy app/ core/
```

---

## Project Structure

```
polyedge_analyzer/
├── app/
│   ├── main.py              # GUI entry point
│   ├── ui_mainwindow.py     # PySide6 main window, dialogs
│   ├── settings.py          # Config persistence (JSON)
│   └── logging_config.py    # Logging setup
├── core/
│   ├── polymarket_gamma.py  # Gamma API client (market discovery)
│   ├── polymarket_clob.py   # CLOB REST + WebSocket (prices/orderbook)
│   ├── pricing.py           # Fee & slippage → q_eff
│   ├── ev.py                # Edge, EV, ROI calculations
│   ├── staking.py           # Kelly criterion + caps
│   ├── models.py            # Probability combination (p̂)
│   ├── odds_providers.py    # External odds plugin interface
│   ├── claude_client.py     # Anthropic SDK wrapper
│   └── schemas.py           # Pydantic data models
├── tests/
│   └── test_ev_kelly_fee.py # 20+ test cases
├── .github/workflows/
│   └── release.yml          # CI: build exe + GitHub Release
├── install.ps1              # One-line Windows installer
├── uninstall.ps1            # Uninstaller
├── run_local.ps1            # Developer local run script
├── pyproject.toml           # Project config
├── LICENSE                  # MIT
└── README.md                # This file
```

---

## Troubleshooting

### Windows SmartScreen Warning
On first run, Windows may show "Windows protected your PC". Click **More info** → **Run anyway**. This is normal for unsigned executables.

### Network Errors
- Ensure you have internet access
- Polymarket API may be unavailable in some regions
- The app retries failed requests up to 3 times automatically

### No Markets Shown
- Click Refresh — initial load may take 10–20 seconds
- Check that Polymarket has active sports markets
- Lower the min edge / min liquidity filters

### Uninstall

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File uninstall.ps1
```

Or manually delete `%LOCALAPPDATA%\PolyEdgeAnalyzer\` and the Desktop shortcut.

---

## Disclaimer & Legal

**THIS SOFTWARE IS PROVIDED "AS IS" WITHOUT WARRANTY OF ANY KIND.**

- This tool does **not** place orders or execute trades automatically
- All analysis is based on mathematical models with **inherent uncertainty**
- Past performance does **not** predict future results
- You are solely responsible for any financial decisions and losses
- Prediction market participation may violate laws in your jurisdiction
- The developers assume **no liability** for any financial losses
- This is **not** investment, trading, or gambling advice
- Consult a qualified financial advisor before making trading decisions

**Use responsibly. Never risk money you cannot afford to lose.**

---

## License

MIT — see [LICENSE](LICENSE)

"""PySide6 Main Window for PolyEdge Analyzer."""

from __future__ import annotations

import csv
import logging
import webbrowser
from datetime import datetime
from functools import partial
from pathlib import Path
from typing import Optional

from PySide6.QtCore import Qt, QThread, Signal, QTimer
from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QStatusBar,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from core.schemas import AnalysisRow, AppSettings
from app.settings import load_settings, save_settings

logger = logging.getLogger(__name__)

COLUMNS = [
    "Event", "Market", "Outcome", "Bid", "Ask", "Mid", "Spread",
    "Depth(B)", "Depth(A)", "Fee(bps)", "p̂", "q_eff",
    "Edge", "EV/$ ", "ROI%", "Kelly", "Stake($)", "Confidence", "Flags",
]

POLYMARKET_BASE = "https://polymarket.com/event/"


class DisclaimerDialog(QDialog):
    """First-run risk disclaimer that must be accepted."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("⚠️ Risk Disclaimer – PolyEdge Analyzer")
        self.setMinimumSize(520, 400)
        layout = QVBoxLayout(self)

        text = QTextEdit()
        text.setReadOnly(True)
        text.setHtml("""
        <h2>⚠️ IMPORTANT – PLEASE READ CAREFULLY</h2>
        <p><b>PolyEdge Analyzer is an informational analysis tool ONLY.</b></p>
        <ul>
        <li><b>NO GUARANTEE OF PROFIT.</b> Past performance does not indicate future results.
        All predictions, edge calculations, and stake recommendations are <i>estimates based on
        mathematical models and market data</i>. They can be — and often are — wrong.</li>
        <li><b>RISK OF TOTAL LOSS.</b> You may lose your entire bankroll. Prediction markets
        involve substantial financial risk. Never risk money you cannot afford to lose.</li>
        <li><b>NOT FINANCIAL ADVICE.</b> This software does not constitute investment, trading,
        or gambling advice. Consult a qualified financial advisor before making decisions.</li>
        <li><b>LEGAL COMPLIANCE.</b> Prediction market participation may be restricted or
        prohibited in your jurisdiction. You are solely responsible for compliance with all
        applicable laws and regulations.</li>
        <li><b>MODEL LIMITATIONS.</b> Probability estimates rely on market data, optional
        external odds, and AI analysis — all of which have inherent errors and biases.
        The "edge" shown is a <i>conditional estimate</i>, not a guaranteed advantage.</li>
        <li><b>NO AUTO-TRADING.</b> This tool does NOT place orders on your behalf. Any
        trading decision is yours alone.</li>
        </ul>
        <p>By clicking "I Understand & Accept", you acknowledge these risks and agree that
        the developers bear no responsibility for any financial losses incurred.</p>
        """)
        layout.addWidget(text)

        self.check = QCheckBox("I have read and understand the risks described above")
        layout.addWidget(self.check)

        self.buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        self.buttons.button(QDialogButtonBox.StandardButton.Ok).setText("I Understand & Accept")
        self.buttons.button(QDialogButtonBox.StandardButton.Ok).setEnabled(False)
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        self.check.toggled.connect(
            lambda checked: self.buttons.button(QDialogButtonBox.StandardButton.Ok).setEnabled(checked)
        )
        layout.addWidget(self.buttons)


class SettingsDialog(QDialog):
    """Settings configuration dialog."""

    def __init__(self, settings: AppSettings, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Settings")
        self.setMinimumWidth(450)
        self.settings = settings.model_copy()

        layout = QVBoxLayout(self)

        # Bankroll group
        grp_bank = QGroupBox("Bankroll & Staking")
        form1 = QFormLayout(grp_bank)

        self.bankroll_spin = QDoubleSpinBox()
        self.bankroll_spin.setRange(1, 1_000_000)
        self.bankroll_spin.setValue(settings.bankroll)
        self.bankroll_spin.setPrefix("$ ")
        form1.addRow("Bankroll (USDT):", self.bankroll_spin)

        self.kelly_spin = QDoubleSpinBox()
        self.kelly_spin.setRange(0.01, 1.0)
        self.kelly_spin.setSingleStep(0.05)
        self.kelly_spin.setValue(settings.kelly_fraction)
        form1.addRow("Kelly fraction:", self.kelly_spin)

        self.max_bet_spin = QDoubleSpinBox()
        self.max_bet_spin.setRange(0.001, 0.5)
        self.max_bet_spin.setSingleStep(0.005)
        self.max_bet_spin.setValue(settings.max_bet_pct)
        form1.addRow("Max bet % of bankroll:", self.max_bet_spin)

        layout.addWidget(grp_bank)

        # Filter group
        grp_filter = QGroupBox("Filters")
        form2 = QFormLayout(grp_filter)

        self.min_edge_spin = QDoubleSpinBox()
        self.min_edge_spin.setRange(-1.0, 1.0)
        self.min_edge_spin.setSingleStep(0.01)
        self.min_edge_spin.setValue(settings.min_edge)
        form2.addRow("Min edge:", self.min_edge_spin)

        self.min_liq_spin = QDoubleSpinBox()
        self.min_liq_spin.setRange(0, 1_000_000)
        self.min_liq_spin.setValue(settings.min_liquidity)
        form2.addRow("Min liquidity ($):", self.min_liq_spin)

        self.refresh_spin = QSpinBox()
        self.refresh_spin.setRange(5, 600)
        self.refresh_spin.setValue(settings.refresh_interval_sec)
        self.refresh_spin.setSuffix(" sec")
        form2.addRow("Refresh interval:", self.refresh_spin)

        layout.addWidget(grp_filter)

        # Claude group
        grp_claude = QGroupBox("Claude AI (Optional)")
        form3 = QFormLayout(grp_claude)

        self.claude_check = QCheckBox("Enable Claude analysis")
        self.claude_check.setChecked(settings.claude_enabled)
        form3.addRow(self.claude_check)

        self.api_key_edit = QLineEdit()
        self.api_key_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.api_key_edit.setText(settings.anthropic_api_key)
        self.api_key_edit.setPlaceholderText("sk-ant-...")
        form3.addRow("Anthropic API Key:", self.api_key_edit)

        layout.addWidget(grp_claude)

        # Weights group
        grp_weights = QGroupBox("Probability Weights")
        form4 = QFormLayout(grp_weights)
        self.w_mkt_spin = QDoubleSpinBox(); self.w_mkt_spin.setRange(0, 1); self.w_mkt_spin.setSingleStep(0.05); self.w_mkt_spin.setValue(settings.w_mkt)
        self.w_books_spin = QDoubleSpinBox(); self.w_books_spin.setRange(0, 1); self.w_books_spin.setSingleStep(0.05); self.w_books_spin.setValue(settings.w_books)
        self.w_model_spin = QDoubleSpinBox(); self.w_model_spin.setRange(0, 1); self.w_model_spin.setSingleStep(0.05); self.w_model_spin.setValue(settings.w_model)
        self.w_claude_spin = QDoubleSpinBox(); self.w_claude_spin.setRange(0, 1); self.w_claude_spin.setSingleStep(0.05); self.w_claude_spin.setValue(settings.w_claude)
        form4.addRow("w_mkt (market):", self.w_mkt_spin)
        form4.addRow("w_books (sportsbook):", self.w_books_spin)
        form4.addRow("w_model (stat model):", self.w_model_spin)
        form4.addRow("w_claude (AI):", self.w_claude_spin)
        layout.addWidget(grp_weights)

        # Buttons
        btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        btns.accepted.connect(self._save_and_accept)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

    def _save_and_accept(self) -> None:
        self.settings.bankroll = self.bankroll_spin.value()
        self.settings.kelly_fraction = self.kelly_spin.value()
        self.settings.max_bet_pct = self.max_bet_spin.value()
        self.settings.min_edge = self.min_edge_spin.value()
        self.settings.min_liquidity = self.min_liq_spin.value()
        self.settings.refresh_interval_sec = self.refresh_spin.value()
        self.settings.claude_enabled = self.claude_check.isChecked()
        self.settings.anthropic_api_key = self.api_key_edit.text().strip()
        self.settings.w_mkt = self.w_mkt_spin.value()
        self.settings.w_books = self.w_books_spin.value()
        self.settings.w_model = self.w_model_spin.value()
        self.settings.w_claude = self.w_claude_spin.value()
        self.accept()


# ── Worker thread for fetching data ─────────────────────────────────────────

class FetchWorker(QThread):
    """Background worker that fetches Polymarket data and runs analysis."""

    finished = Signal(list)  # list[AnalysisRow]
    error = Signal(str)
    progress = Signal(str)

    def __init__(self, settings: AppSettings, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.settings = settings

    def run(self) -> None:
        try:
            from core.polymarket_gamma import GammaClient
            from core.polymarket_clob import CLOBClient
            from core.pricing import compute_q_eff
            from core.ev import compute_edge, compute_ev_per_dollar, compute_roi_pct, compute_kelly_fraction
            from core.staking import compute_stake
            from core.models import combine_probabilities
            from core.schemas import FeeInfo

            self.progress.emit("Fetching sports markets from Gamma...")
            gamma = GammaClient()
            markets = gamma.fetch_all_sports_markets(max_pages=3, page_size=50)
            self.progress.emit(f"Found {len(markets)} markets. Fetching prices...")

            clob = CLOBClient()
            rows: list[AnalysisRow] = []

            for mkt in markets:
                for token in mkt.tokens:
                    try:
                        price_info = clob.get_price_info(token.token_id)
                        if price_info.best_ask is None:
                            continue

                        fee_info = clob.get_fee_rate(token.token_id)

                        ep = compute_q_eff(price_info.best_ask, fee_info)

                        # p̂ = market mid (MVP default)
                        p_mkt = price_info.mid if price_info.mid else price_info.best_ask
                        p_hat = combine_probabilities(p_mkt)

                        edge = compute_edge(p_hat, ep.q_eff)
                        ev_dollar = compute_ev_per_dollar(p_hat, ep.q_eff)
                        roi = compute_roi_pct(p_hat, ep.q_eff)
                        kelly = compute_kelly_fraction(p_hat, ep.q_eff)
                        stake = compute_stake(
                            p_hat, ep.q_eff,
                            bankroll=self.settings.bankroll,
                            kelly_fraction=self.settings.kelly_fraction,
                            max_bet_pct=self.settings.max_bet_pct,
                        )

                        rows.append(AnalysisRow(
                            market_question=mkt.question,
                            event_title=mkt.event_title,
                            outcome=token.outcome,
                            token_id=token.token_id,
                            slug=mkt.event_slug or mkt.slug,
                            best_bid=price_info.best_bid,
                            best_ask=price_info.best_ask,
                            mid=price_info.mid,
                            spread=price_info.spread,
                            bid_depth=price_info.bid_depth,
                            ask_depth=price_info.ask_depth,
                            fee_rate_bps=fee_info.fee_rate_bps,
                            p_hat=p_hat,
                            q_eff=ep.q_eff,
                            edge=edge,
                            ev_per_dollar=ev_dollar,
                            roi_pct=roi,
                            kelly_raw=kelly,
                            stake=stake,
                        ))
                    except Exception as exc:
                        logger.warning("Error processing token %s: %s", token.token_id, exc)

            self.progress.emit(f"Analysis complete. {len(rows)} outcomes processed.")
            self.finished.emit(rows)
        except Exception as exc:
            logger.exception("FetchWorker failed")
            self.error.emit(str(exc))


# ── Main Window ──────────────────────────────────────────────────────────────

class MainWindow(QMainWindow):
    def __init__(self, settings: AppSettings) -> None:
        super().__init__()
        self.settings = settings
        self._rows: list[AnalysisRow] = []
        self._worker: FetchWorker | None = None
        self._auto_timer: QTimer | None = None

        self.setWindowTitle("PolyEdge Analyzer – Polymarket Sports EV Scanner")
        self.setMinimumSize(1200, 700)

        self._build_ui()
        self._apply_style()

    # ── UI construction ───────────────────────────────────────────────────

    def _build_ui(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)

        # Top bar
        top = QHBoxLayout()
        self.btn_refresh = QPushButton("🔄 Refresh Now")
        self.btn_refresh.clicked.connect(self._on_refresh)
        top.addWidget(self.btn_refresh)

        self.btn_realtime = QPushButton("⚡ Real-time: OFF")
        self.btn_realtime.setCheckable(True)
        self.btn_realtime.toggled.connect(self._toggle_realtime)
        top.addWidget(self.btn_realtime)

        top.addStretch()

        self.lbl_filter = QLabel("Min edge:")
        top.addWidget(self.lbl_filter)
        self.edge_filter = QDoubleSpinBox()
        self.edge_filter.setRange(-1, 1)
        self.edge_filter.setSingleStep(0.01)
        self.edge_filter.setValue(self.settings.min_edge)
        self.edge_filter.valueChanged.connect(self._apply_filters)
        top.addWidget(self.edge_filter)

        top.addWidget(QLabel("Min liq:"))
        self.liq_filter = QDoubleSpinBox()
        self.liq_filter.setRange(0, 1_000_000)
        self.liq_filter.setValue(self.settings.min_liquidity)
        self.liq_filter.valueChanged.connect(self._apply_filters)
        top.addWidget(self.liq_filter)

        self.btn_export = QPushButton("📥 Export CSV")
        self.btn_export.clicked.connect(self._export_csv)
        top.addWidget(self.btn_export)

        self.btn_settings = QPushButton("⚙️ Settings")
        self.btn_settings.clicked.connect(self._open_settings)
        top.addWidget(self.btn_settings)

        root.addLayout(top)

        # Warning banner
        warn = QLabel(
            "⚠️ This tool provides conditional estimates only — NOT financial advice. "
            "You may lose your entire investment. Use responsibly."
        )
        warn.setStyleSheet("background: #FFF3CD; color: #856404; padding: 6px; border-radius: 4px; font-weight: bold;")
        warn.setWordWrap(True)
        root.addWidget(warn)

        # Table
        self.table = QTableWidget(0, len(COLUMNS))
        self.table.setHorizontalHeaderLabels(COLUMNS)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSortingEnabled(True)
        self.table.setAlternatingRowColors(True)
        self.table.doubleClicked.connect(self._on_row_double_click)
        root.addWidget(self.table)

        # Status bar
        self.status = QStatusBar()
        self.setStatusBar(self.status)
        self.status.showMessage("Ready – click Refresh to load markets")

    def _apply_style(self) -> None:
        self.setStyleSheet("""
            QMainWindow { background: #1a1a2e; }
            QWidget { color: #e0e0e0; font-family: 'Segoe UI', sans-serif; }
            QTableWidget { background: #16213e; alternate-background-color: #1a2744;
                           gridline-color: #2a3a5c; selection-background-color: #0f3460; }
            QHeaderView::section { background: #0f3460; color: #e0e0e0; padding: 4px;
                                   border: 1px solid #2a3a5c; font-weight: bold; }
            QPushButton { background: #0f3460; color: #e0e0e0; border: 1px solid #2a3a5c;
                          padding: 6px 14px; border-radius: 4px; }
            QPushButton:hover { background: #1a5276; }
            QPushButton:checked { background: #e94560; }
            QDoubleSpinBox, QSpinBox, QLineEdit, QComboBox {
                background: #16213e; color: #e0e0e0; border: 1px solid #2a3a5c; padding: 3px; }
            QGroupBox { color: #a0c4ff; border: 1px solid #2a3a5c; margin-top: 10px; padding-top: 14px; }
            QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 5px; }
        """)

    # ── data loading ──────────────────────────────────────────────────────

    def _on_refresh(self) -> None:
        if self._worker and self._worker.isRunning():
            self.status.showMessage("Fetch already in progress...")
            return
        self.btn_refresh.setEnabled(False)
        self.status.showMessage("Fetching data...")
        self._worker = FetchWorker(self.settings, self)
        self._worker.finished.connect(self._on_data_ready)
        self._worker.error.connect(self._on_fetch_error)
        self._worker.progress.connect(lambda msg: self.status.showMessage(msg))
        self._worker.start()

    def _on_data_ready(self, rows: list[AnalysisRow]) -> None:
        self._rows = rows
        self._populate_table(rows)
        self.btn_refresh.setEnabled(True)
        self.status.showMessage(
            f"Loaded {len(rows)} outcomes at {datetime.now().strftime('%H:%M:%S')}"
        )

    def _on_fetch_error(self, msg: str) -> None:
        self.btn_refresh.setEnabled(True)
        self.status.showMessage(f"Error: {msg}")
        QMessageBox.warning(self, "Fetch Error", f"Could not load data:\n{msg}")

    # ── table ─────────────────────────────────────────────────────────────

    def _populate_table(self, rows: list[AnalysisRow]) -> None:
        self.table.setSortingEnabled(False)
        self.table.setRowCount(0)

        filtered = self._filter_rows(rows)

        self.table.setRowCount(len(filtered))
        for i, row in enumerate(filtered):
            items = [
                row.event_title[:40],
                row.market_question[:50],
                row.outcome,
                f"{row.best_bid:.3f}" if row.best_bid is not None else "—",
                f"{row.best_ask:.3f}" if row.best_ask is not None else "—",
                f"{row.mid:.3f}" if row.mid is not None else "—",
                f"{row.spread:.4f}" if row.spread is not None else "—",
                f"{row.bid_depth:.0f}",
                f"{row.ask_depth:.0f}",
                f"{row.fee_rate_bps:.0f}",
                f"{row.p_hat:.1%}",
                f"{row.q_eff:.4f}",
                f"{row.edge:+.4f}",
                f"{row.ev_per_dollar:+.4f}",
                f"{row.roi_pct:+.1f}%",
                f"{row.kelly_raw:.4f}",
                f"${row.stake:.2f}",
                row.confidence,
                row.claude_flags,
            ]
            for j, val in enumerate(items):
                item = QTableWidgetItem(str(val))
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                # Color-code edge
                if j == 12:  # edge column
                    try:
                        edge_val = row.edge
                        if edge_val > 0.02:
                            item.setForeground(QColor("#4ade80"))
                        elif edge_val > 0:
                            item.setForeground(QColor("#a3e635"))
                        else:
                            item.setForeground(QColor("#f87171"))
                    except Exception:
                        pass
                self.table.setItem(i, j, item)

        self.table.setSortingEnabled(True)

    def _filter_rows(self, rows: list[AnalysisRow]) -> list[AnalysisRow]:
        min_edge = self.edge_filter.value()
        min_liq = self.liq_filter.value()
        return [
            r for r in rows
            if r.edge >= min_edge and (r.bid_depth + r.ask_depth) >= min_liq
        ]

    def _apply_filters(self) -> None:
        if self._rows:
            self._populate_table(self._rows)

    # ── real-time toggle ──────────────────────────────────────────────────

    def _toggle_realtime(self, checked: bool) -> None:
        if checked:
            self.btn_realtime.setText("⚡ Real-time: ON")
            interval = self.settings.refresh_interval_sec * 1000
            self._auto_timer = QTimer(self)
            self._auto_timer.timeout.connect(self._on_refresh)
            self._auto_timer.start(interval)
            self._on_refresh()
        else:
            self.btn_realtime.setText("⚡ Real-time: OFF")
            if self._auto_timer:
                self._auto_timer.stop()
                self._auto_timer = None

    # ── row actions ───────────────────────────────────────────────────────

    def _on_row_double_click(self) -> None:
        row_idx = self.table.currentRow()
        if row_idx < 0:
            return
        filtered = self._filter_rows(self._rows)
        if row_idx >= len(filtered):
            return
        row = filtered[row_idx]
        url = f"{POLYMARKET_BASE}{row.slug}"
        webbrowser.open(url)

    # ── CSV export ────────────────────────────────────────────────────────

    def _export_csv(self) -> None:
        if not self._rows:
            QMessageBox.information(self, "Export", "No data to export. Refresh first.")
            return
        path, _ = QFileDialog.getSaveFileName(self, "Export CSV", "polyedge_export.csv", "CSV (*.csv)")
        if not path:
            return
        try:
            filtered = self._filter_rows(self._rows)
            with open(path, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(COLUMNS)
                for row in filtered:
                    writer.writerow([
                        row.event_title, row.market_question, row.outcome,
                        row.best_bid, row.best_ask, row.mid, row.spread,
                        row.bid_depth, row.ask_depth, row.fee_rate_bps,
                        f"{row.p_hat:.4f}", f"{row.q_eff:.4f}",
                        f"{row.edge:.4f}", f"{row.ev_per_dollar:.4f}",
                        f"{row.roi_pct:.2f}", f"{row.kelly_raw:.4f}",
                        f"{row.stake:.2f}", row.confidence, row.claude_flags,
                    ])
            self.status.showMessage(f"Exported {len(filtered)} rows to {path}")
        except Exception as exc:
            QMessageBox.warning(self, "Export Error", str(exc))

    # ── settings dialog ───────────────────────────────────────────────────

    def _open_settings(self) -> None:
        dlg = SettingsDialog(self.settings, self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self.settings = dlg.settings
            save_settings(self.settings)
            self.edge_filter.setValue(self.settings.min_edge)
            self.liq_filter.setValue(self.settings.min_liquidity)
            self.status.showMessage("Settings saved.")

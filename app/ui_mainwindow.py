"""PySide6 메인 윈도우 – PolyEdge Analyzer (한글 UI)."""

from __future__ import annotations

import csv
import logging
import webbrowser
from datetime import datetime
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
    "이벤트", "마켓", "결과", "매수호가", "매도호가", "중간가", "스프레드",
    "매수잔량", "매도잔량", "수수료(bps)", "추정확률(p̂)", "유효매수가(q_eff)",
    "엣지", "EV/$", "ROI%", "켈리비율", "추천금액($)", "시그널", "신뢰도", "비고",
]

POLYMARKET_BASE = "https://polymarket.com/event/"


class DisclaimerDialog(QDialog):
    """첫 실행 시 리스크 면책 동의 대화상자."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("⚠️ 위험 고지 – PolyEdge Analyzer")
        self.setMinimumSize(520, 400)
        layout = QVBoxLayout(self)

        text = QTextEdit()
        text.setReadOnly(True)
        text.setHtml("""
        <h2>⚠️ 중요 – 반드시 읽어주세요</h2>
        <p><b>PolyEdge Analyzer는 정보 분석 도구입니다.</b></p>
        <ul>
        <li><b>수익을 보장하지 않습니다.</b> 모든 예측, 엣지 계산, 베팅 추천은
        수학적 모델과 시장 데이터에 기반한 <i>추정치</i>이며, 틀릴 수 있습니다.</li>
        <li><b>원금 전액 손실 가능.</b> 예측 시장은 높은 재무적 위험을 수반합니다.
        잃어도 되는 금액만 투자하세요.</li>
        <li><b>투자 조언이 아닙니다.</b> 이 소프트웨어는 투자, 트레이딩, 도박 조언을
        제공하지 않습니다. 결정 전 전문 재무 상담사와 상의하세요.</li>
        <li><b>법률 준수 책임.</b> 예측 시장 참여가 귀하의 관할 지역에서 제한되거나
        금지될 수 있습니다. 관련 법률 준수는 본인의 책임입니다.</li>
        <li><b>모델의 한계.</b> 확률 추정은 시장 데이터, 외부 배당률, AI 분석에 의존하며,
        모두 본질적인 오류와 편향을 가집니다.</li>
        <li><b>자동 매매 없음.</b> 이 도구는 주문을 대신 실행하지 않습니다.
        모든 거래 결정은 본인의 책임입니다.</li>
        </ul>
        <p>"동의합니다"를 클릭하면 위 위험을 인지하고, 개발자가 어떠한
        재무적 손실에 대해서도 책임지지 않음에 동의합니다.</p>
        """)
        layout.addWidget(text)

        self.check = QCheckBox("위의 위험 고지를 읽고 이해했습니다")
        layout.addWidget(self.check)

        self.buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        self.buttons.button(QDialogButtonBox.StandardButton.Ok).setText("동의합니다")
        self.buttons.button(QDialogButtonBox.StandardButton.Cancel).setText("취소")
        self.buttons.button(QDialogButtonBox.StandardButton.Ok).setEnabled(False)
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        self.check.toggled.connect(
            lambda checked: self.buttons.button(QDialogButtonBox.StandardButton.Ok).setEnabled(checked)
        )
        layout.addWidget(self.buttons)


class SettingsDialog(QDialog):
    """설정 대화상자."""

    def __init__(self, settings: AppSettings, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("설정")
        self.setMinimumWidth(480)
        self.settings = settings.model_copy()

        layout = QVBoxLayout(self)

        # 자금 & 스테이킹
        grp_bank = QGroupBox("자금 및 베팅 설정")
        form1 = QFormLayout(grp_bank)

        self.bankroll_spin = QDoubleSpinBox()
        self.bankroll_spin.setRange(1, 1_000_000)
        self.bankroll_spin.setValue(settings.bankroll)
        self.bankroll_spin.setPrefix("$ ")
        form1.addRow("총 자금 (USDT):", self.bankroll_spin)

        self.kelly_spin = QDoubleSpinBox()
        self.kelly_spin.setRange(0.01, 1.0)
        self.kelly_spin.setSingleStep(0.05)
        self.kelly_spin.setValue(settings.kelly_fraction)
        self.kelly_spin.setToolTip("0.25 = Quarter-Kelly (보수적 권장)\n0.50 = Half-Kelly\n1.0 = Full-Kelly (위험)")
        form1.addRow("켈리 비율:", self.kelly_spin)

        self.max_bet_spin = QDoubleSpinBox()
        self.max_bet_spin.setRange(0.001, 0.5)
        self.max_bet_spin.setSingleStep(0.005)
        self.max_bet_spin.setValue(settings.max_bet_pct)
        form1.addRow("최대 베팅 (자금 대비 %):", self.max_bet_spin)

        self.min_stake_spin = QDoubleSpinBox()
        self.min_stake_spin.setRange(0.1, 100.0)
        self.min_stake_spin.setValue(settings.min_stake)
        self.min_stake_spin.setPrefix("$ ")
        form1.addRow("최소 베팅 금액:", self.min_stake_spin)

        layout.addWidget(grp_bank)

        # 필터
        grp_filter = QGroupBox("필터 설정")
        form2 = QFormLayout(grp_filter)

        self.min_edge_spin = QDoubleSpinBox()
        self.min_edge_spin.setRange(-1.0, 1.0)
        self.min_edge_spin.setSingleStep(0.01)
        self.min_edge_spin.setValue(settings.min_edge)
        form2.addRow("최소 엣지:", self.min_edge_spin)

        self.min_liq_spin = QDoubleSpinBox()
        self.min_liq_spin.setRange(0, 1_000_000)
        self.min_liq_spin.setValue(settings.min_liquidity)
        form2.addRow("최소 유동성 ($):", self.min_liq_spin)

        self.refresh_spin = QSpinBox()
        self.refresh_spin.setRange(5, 600)
        self.refresh_spin.setValue(settings.refresh_interval_sec)
        self.refresh_spin.setSuffix(" 초")
        form2.addRow("새로고침 간격:", self.refresh_spin)

        layout.addWidget(grp_filter)

        # Claude AI
        grp_claude = QGroupBox("Claude AI (선택사항)")
        form3 = QFormLayout(grp_claude)

        self.claude_check = QCheckBox("Claude 분석 활성화")
        self.claude_check.setChecked(settings.claude_enabled)
        form3.addRow(self.claude_check)

        self.api_key_edit = QLineEdit()
        self.api_key_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.api_key_edit.setText(settings.anthropic_api_key)
        self.api_key_edit.setPlaceholderText("sk-ant-...")
        form3.addRow("Anthropic API 키:", self.api_key_edit)

        layout.addWidget(grp_claude)

        # 확률 가중치
        grp_weights = QGroupBox("확률 소스 가중치")
        form4 = QFormLayout(grp_weights)
        self.w_mkt_spin = QDoubleSpinBox(); self.w_mkt_spin.setRange(0, 1); self.w_mkt_spin.setSingleStep(0.05); self.w_mkt_spin.setValue(settings.w_mkt)
        self.w_books_spin = QDoubleSpinBox(); self.w_books_spin.setRange(0, 1); self.w_books_spin.setSingleStep(0.05); self.w_books_spin.setValue(settings.w_books)
        self.w_model_spin = QDoubleSpinBox(); self.w_model_spin.setRange(0, 1); self.w_model_spin.setSingleStep(0.05); self.w_model_spin.setValue(settings.w_model)
        self.w_claude_spin = QDoubleSpinBox(); self.w_claude_spin.setRange(0, 1); self.w_claude_spin.setSingleStep(0.05); self.w_claude_spin.setValue(settings.w_claude)
        form4.addRow("마켓 (Polymarket):", self.w_mkt_spin)
        form4.addRow("스포츠북:", self.w_books_spin)
        form4.addRow("통계 모델:", self.w_model_spin)
        form4.addRow("AI (Claude):", self.w_claude_spin)
        layout.addWidget(grp_weights)

        # 버튼
        btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        btns.button(QDialogButtonBox.StandardButton.Ok).setText("저장")
        btns.button(QDialogButtonBox.StandardButton.Cancel).setText("취소")
        btns.accepted.connect(self._save_and_accept)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

    def _save_and_accept(self) -> None:
        self.settings.bankroll = self.bankroll_spin.value()
        self.settings.kelly_fraction = self.kelly_spin.value()
        self.settings.max_bet_pct = self.max_bet_spin.value()
        self.settings.min_stake = self.min_stake_spin.value()
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
    """백그라운드 워커: Polymarket 데이터 수집 및 분석."""

    finished = Signal(list)  # list[AnalysisRow]
    error = Signal(str)
    progress = Signal(str)

    def __init__(self, settings: AppSettings, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.settings = settings

    def run(self) -> None:
        try:
            from core.polymarket_gamma import GammaClient
            from core.pricing import compute_q_eff
            from core.ev import (
                compute_edge, compute_ev_per_dollar, compute_roi_pct,
                compute_kelly_fraction, classify_signal,
            )
            from core.staking import compute_stake
            from core.models import combine_probabilities, compute_confidence_score
            from core.schemas import FeeInfo

            self.progress.emit("Gamma API에서 활성 마켓 조회 중...")
            gamma = GammaClient()
            markets = gamma.fetch_all_active_markets(max_pages=5, page_size=20)
            self.progress.emit(f"{len(markets)}개 마켓 발견. 분석 중...")

            # 기본 수수료: Polymarket taker fee ~2% (200 bps)
            _FEE_BPS = 200.0
            default_fee = FeeInfo(fee_rate_bps=_FEE_BPS, fee_rate=_FEE_BPS / 10000)

            rows: list[AnalysisRow] = []

            for mkt in markets:
                # Gamma API가 이미 마켓 단위 가격 데이터를 제공
                # outcome_prices: [Yes가격, No가격, ...]
                outcome_prices = mkt.outcome_prices or []

                for idx, token in enumerate(mkt.tokens):
                    try:
                        # 토큰별 가격 결정
                        if idx < len(outcome_prices) and outcome_prices[idx] > 0:
                            token_price = outcome_prices[idx]
                        elif mkt.best_ask is not None:
                            token_price = mkt.best_ask
                        else:
                            continue  # 가격 데이터 없으면 스킵

                        # bid/ask 추정 (Gamma 마켓 레벨 데이터 활용)
                        best_ask = token_price
                        best_bid = mkt.best_bid if mkt.best_bid is not None else max(0.01, token_price - 0.02)
                        spread = mkt.spread if mkt.spread is not None else abs(best_ask - best_bid)
                        mid = (best_bid + best_ask) / 2

                        # 유효 매수가 계산 (수수료 반영)
                        ep = compute_q_eff(best_ask, default_fee)

                        # p̂ = 마켓 중간가 기반 추정확률
                        p_mkt = mid if mid > 0 else best_ask
                        p_hat = combine_probabilities(p_mkt)

                        # 유동성 기반 잔량 추정 (Gamma는 총 유동성만 제공)
                        est_depth = mkt.liquidity / max(len(mkt.tokens), 1) / 2
                        bid_depth = est_depth
                        ask_depth = est_depth

                        # 신뢰도 점수
                        conf_score = compute_confidence_score(
                            spread=spread,
                            bid_depth=bid_depth,
                            ask_depth=ask_depth,
                            num_sources=1,
                        )

                        edge = compute_edge(p_hat, ep.q_eff)
                        ev_dollar = compute_ev_per_dollar(p_hat, ep.q_eff)
                        roi = compute_roi_pct(p_hat, ep.q_eff)
                        kelly = compute_kelly_fraction(p_hat, ep.q_eff)

                        stake = compute_stake(
                            p_hat, ep.q_eff,
                            bankroll=self.settings.bankroll,
                            kelly_fraction=self.settings.kelly_fraction,
                            max_bet_pct=self.settings.max_bet_pct,
                            min_stake=self.settings.min_stake,
                            confidence=conf_score,
                            available_liquidity=mkt.liquidity,
                        )

                        signal = classify_signal(
                            edge=edge,
                            roi_pct=roi,
                            confidence_score=conf_score,
                            bid_depth=bid_depth,
                            ask_depth=ask_depth,
                        )

                        rows.append(AnalysisRow(
                            market_question=mkt.question,
                            event_title=mkt.event_title,
                            outcome=token.outcome,
                            token_id=token.token_id,
                            slug=mkt.event_slug or mkt.slug,
                            best_bid=best_bid,
                            best_ask=best_ask,
                            mid=mid,
                            spread=spread,
                            bid_depth=bid_depth,
                            ask_depth=ask_depth,
                            fee_rate_bps=default_fee.fee_rate_bps,
                            p_hat=p_hat,
                            q_eff=ep.q_eff,
                            edge=edge,
                            ev_per_dollar=ev_dollar,
                            roi_pct=roi,
                            kelly_raw=kelly,
                            stake=stake,
                            signal=signal,
                            confidence_score=conf_score,
                        ))
                    except Exception as exc:
                        logger.warning("토큰 처리 오류 %s: %s", token.token_id, exc)

            # 엣지 기준 내림차순 정렬
            rows.sort(key=lambda r: r.edge, reverse=True)
            self.progress.emit(f"분석 완료. {len(rows)}개 결과 처리됨.")
            self.finished.emit(rows)
        except Exception as exc:
            logger.exception("FetchWorker 오류")
            self.error.emit(str(exc))


# ── Main Window ──────────────────────────────────────────────────────────────

class MainWindow(QMainWindow):
    def __init__(self, settings: AppSettings) -> None:
        super().__init__()
        self.settings = settings
        self._rows: list[AnalysisRow] = []
        self._worker: FetchWorker | None = None
        self._auto_timer: QTimer | None = None

        self.setWindowTitle("PolyEdge Analyzer – 폴리마켓 스포츠 EV 스캐너")
        self.setMinimumSize(1280, 720)

        self._build_ui()
        self._apply_style()

    # ── UI construction ───────────────────────────────────────────────────

    def _build_ui(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)

        # 상단 툴바
        top = QHBoxLayout()

        self.btn_fetch = QPushButton("📊 마켓 분석")
        self.btn_fetch.setToolTip("Polymarket에서 스포츠 마켓을 가져와 EV 분석합니다")
        self.btn_fetch.clicked.connect(self._on_refresh)
        self.btn_fetch.setMinimumWidth(120)
        top.addWidget(self.btn_fetch)

        self.btn_realtime = QPushButton("⚡ 실시간: 꺼짐")
        self.btn_realtime.setCheckable(True)
        self.btn_realtime.toggled.connect(self._toggle_realtime)
        top.addWidget(self.btn_realtime)

        top.addStretch()

        self.lbl_filter = QLabel("최소 엣지:")
        top.addWidget(self.lbl_filter)
        self.edge_filter = QDoubleSpinBox()
        self.edge_filter.setRange(-1, 1)
        self.edge_filter.setSingleStep(0.01)
        self.edge_filter.setValue(self.settings.min_edge)
        self.edge_filter.valueChanged.connect(self._apply_filters)
        top.addWidget(self.edge_filter)

        top.addWidget(QLabel("최소 유동성:"))
        self.liq_filter = QDoubleSpinBox()
        self.liq_filter.setRange(0, 1_000_000)
        self.liq_filter.setValue(self.settings.min_liquidity)
        self.liq_filter.valueChanged.connect(self._apply_filters)
        top.addWidget(self.liq_filter)

        self.btn_export = QPushButton("📥 CSV 내보내기")
        self.btn_export.clicked.connect(self._export_csv)
        top.addWidget(self.btn_export)

        self.btn_settings = QPushButton("⚙️ 설정")
        self.btn_settings.clicked.connect(self._open_settings)
        top.addWidget(self.btn_settings)

        root.addLayout(top)

        # 경고 배너
        warn = QLabel(
            "⚠️ 이 도구는 조건부 추정치만 제공합니다 — 투자 조언이 아닙니다. "
            "원금 전액을 잃을 수 있습니다. 책임감 있게 사용하세요."
        )
        warn.setStyleSheet(
            "background: #FFF3CD; color: #856404; padding: 6px; "
            "border-radius: 4px; font-weight: bold;"
        )
        warn.setWordWrap(True)
        root.addWidget(warn)

        # 테이블
        self.table = QTableWidget(0, len(COLUMNS))
        self.table.setHorizontalHeaderLabels(COLUMNS)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSortingEnabled(True)
        self.table.setAlternatingRowColors(True)
        self.table.doubleClicked.connect(self._on_row_double_click)
        root.addWidget(self.table)

        # 하단 요약 바
        bottom = QHBoxLayout()
        self.lbl_summary = QLabel("")
        self.lbl_summary.setStyleSheet("color: #a0c4ff; font-size: 12px; padding: 4px;")
        bottom.addWidget(self.lbl_summary)
        bottom.addStretch()
        root.addLayout(bottom)

        # 상태 바
        self.status = QStatusBar()
        self.setStatusBar(self.status)
        self.status.showMessage("준비 완료 – [📊 마켓 분석] 버튼을 클릭하여 시작하세요")

    def _apply_style(self) -> None:
        self.setStyleSheet("""
            QMainWindow { background: #1a1a2e; }
            QWidget { color: #e0e0e0; font-family: 'Segoe UI', 'Malgun Gothic', sans-serif; font-size: 13px; }
            QTableWidget { background: #16213e; alternate-background-color: #1a2744;
                           gridline-color: #2a3a5c; selection-background-color: #0f3460; }
            QHeaderView::section { background: #0f3460; color: #e0e0e0; padding: 4px;
                                   border: 1px solid #2a3a5c; font-weight: bold; font-size: 12px; }
            QPushButton { background: #0f3460; color: #e0e0e0; border: 1px solid #2a3a5c;
                          padding: 8px 16px; border-radius: 4px; font-weight: bold; }
            QPushButton:hover { background: #1a5276; }
            QPushButton:checked { background: #e94560; }
            QPushButton:disabled { background: #2a2a4e; color: #666; }
            QDoubleSpinBox, QSpinBox, QLineEdit, QComboBox {
                background: #16213e; color: #e0e0e0; border: 1px solid #2a3a5c; padding: 3px; }
            QGroupBox { color: #a0c4ff; border: 1px solid #2a3a5c; margin-top: 10px; padding-top: 14px; }
            QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 5px; }
        """)

    # ── data loading ──────────────────────────────────────────────────────

    def _on_refresh(self) -> None:
        if self._worker and self._worker.isRunning():
            self.status.showMessage("이미 데이터 조회 중...")
            return
        self.btn_fetch.setEnabled(False)
        self.btn_fetch.setText("📊 분석 중...")
        self.status.showMessage("데이터 조회 중...")
        self._worker = FetchWorker(self.settings, self)
        self._worker.finished.connect(self._on_data_ready)
        self._worker.error.connect(self._on_fetch_error)
        self._worker.progress.connect(lambda msg: self.status.showMessage(msg))
        self._worker.start()

    def _on_data_ready(self, rows: list[AnalysisRow]) -> None:
        self._rows = rows
        self._populate_table(rows)
        self.btn_fetch.setEnabled(True)
        self.btn_fetch.setText("📊 마켓 분석")

        # 요약 통계
        buy_count = sum(1 for r in rows if r.signal in ("매수", "강력매수"))
        total_stake = sum(r.stake for r in rows)
        avg_edge = sum(r.edge for r in rows) / len(rows) * 100 if rows else 0

        self.lbl_summary.setText(
            f"총 {len(rows)}개 결과 | 매수 시그널 {buy_count}개 | "
            f"총 추천 베팅 ${total_stake:,.0f} | 평균 엣지 {avg_edge:+.2f}%"
        )
        self.status.showMessage(
            f"{len(rows)}개 결과 로드 완료 ({datetime.now().strftime('%H:%M:%S')})"
        )

    def _on_fetch_error(self, msg: str) -> None:
        self.btn_fetch.setEnabled(True)
        self.btn_fetch.setText("📊 마켓 분석")
        self.status.showMessage(f"오류: {msg}")
        QMessageBox.warning(self, "조회 오류", f"데이터를 불러올 수 없습니다:\n{msg}")

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
                f"{row.bid_depth:,.0f}",
                f"{row.ask_depth:,.0f}",
                f"{row.fee_rate_bps:.0f}",
                f"{row.p_hat:.1%}",
                f"{row.q_eff:.4f}",
                f"{row.edge:+.2%}",
                f"{row.ev_per_dollar:+.4f}",
                f"{row.roi_pct:+.1f}%",
                f"{row.kelly_raw:.3f}",
                f"${row.stake:,.0f}" if row.stake > 0 else "—",
                row.signal,
                f"{row.confidence_score:.0%}",
                row.claude_flags,
            ]
            for j, val in enumerate(items):
                item = QTableWidgetItem(str(val))
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)

                # 시그널 색상
                if j == 17:  # signal column
                    if val == "강력매수":
                        item.setForeground(QColor("#22d3ee"))
                        item.setFont(QFont("Segoe UI", weight=QFont.Weight.Bold))
                    elif val == "매수":
                        item.setForeground(QColor("#4ade80"))
                    elif val == "보류":
                        item.setForeground(QColor("#fbbf24"))
                    else:  # 패스
                        item.setForeground(QColor("#f87171"))

                # 엣지 색상
                if j == 12:  # edge column
                    try:
                        edge_val = row.edge
                        if edge_val > 0.03:
                            item.setForeground(QColor("#22d3ee"))
                        elif edge_val > 0.01:
                            item.setForeground(QColor("#4ade80"))
                        elif edge_val > 0:
                            item.setForeground(QColor("#a3e635"))
                        else:
                            item.setForeground(QColor("#f87171"))
                    except Exception:
                        pass

                # ROI 색상
                if j == 14:
                    try:
                        if row.roi_pct > 5:
                            item.setForeground(QColor("#22d3ee"))
                        elif row.roi_pct > 0:
                            item.setForeground(QColor("#4ade80"))
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
            self.btn_realtime.setText("⚡ 실시간: 켜짐")
            interval = self.settings.refresh_interval_sec * 1000
            self._auto_timer = QTimer(self)
            self._auto_timer.timeout.connect(self._on_refresh)
            self._auto_timer.start(interval)
            self._on_refresh()
        else:
            self.btn_realtime.setText("⚡ 실시간: 꺼짐")
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
            QMessageBox.information(self, "내보내기", "내보낼 데이터가 없습니다. 먼저 마켓을 분석하세요.")
            return
        path, _ = QFileDialog.getSaveFileName(self, "CSV 내보내기", "polyedge_export.csv", "CSV (*.csv)")
        if not path:
            return
        try:
            filtered = self._filter_rows(self._rows)
            with open(path, "w", newline="", encoding="utf-8-sig") as f:
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
                        f"{row.stake:.2f}", row.signal,
                        f"{row.confidence_score:.2f}", row.claude_flags,
                    ])
            self.status.showMessage(f"{len(filtered)}개 행을 {path}에 내보냄")
        except Exception as exc:
            QMessageBox.warning(self, "내보내기 오류", str(exc))

    # ── settings dialog ───────────────────────────────────────────────────

    def _open_settings(self) -> None:
        dlg = SettingsDialog(self.settings, self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self.settings = dlg.settings
            save_settings(self.settings)
            self.edge_filter.setValue(self.settings.min_edge)
            self.liq_filter.setValue(self.settings.min_liquidity)
            self.status.showMessage("설정이 저장되었습니다.")

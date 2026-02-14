"""PolyEdge Analyzer – application entry point."""

from __future__ import annotations

import sys
import os


def main() -> None:
    # Ensure core/ is importable when running from repo root or as bundled exe
    app_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if app_dir not in sys.path:
        sys.path.insert(0, app_dir)

    from app.logging_config import setup_logging
    setup_logging()

    from PySide6.QtWidgets import QApplication

    from app.settings import (
        has_accepted_disclaimer,
        load_settings,
        save_settings,
        set_disclaimer_accepted,
    )
    from app.ui_mainwindow import DisclaimerDialog, MainWindow

    app = QApplication(sys.argv)
    app.setApplicationName("PolyEdge Analyzer")
    app.setOrganizationName("PolyEdge")

    # First-run disclaimer
    if not has_accepted_disclaimer():
        dlg = DisclaimerDialog()
        if dlg.exec() != DisclaimerDialog.DialogCode.Accepted:
            sys.exit(0)
        set_disclaimer_accepted()

    settings = load_settings()
    window = MainWindow(settings)
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()

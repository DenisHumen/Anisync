"""App bootstrap."""
from __future__ import annotations

import logging
import signal as _signal
import sys

from PySide6.QtCore import QTimer
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication

from anisync.core.registry import load_all
from anisync.ui.assets import logo_path
from anisync.utils.async_runner import shutdown as shutdown_async
from anisync.utils.logging import setup as setup_logging


def run(argv: list[str]) -> int:
    setup_logging(logging.INFO)
    load_all()

    app = QApplication(argv)
    app.setApplicationName("Anisync")
    app.setOrganizationName("Anisync")
    # Wayland matches windows to their .desktop entry by this name; without
    # it the panel/dock shows a generic icon on modern Linux sessions.
    app.setDesktopFileName("anisync")
    icon = logo_path()
    if icon.exists():
        app.setWindowIcon(QIcon(str(icon)))

    # Allow Ctrl+C to terminate gracefully
    _signal.signal(_signal.SIGINT, _signal.SIG_DFL)
    # Wake the Qt event loop periodically so SIGINT is checked
    keepalive = QTimer()
    keepalive.start(500)
    keepalive.timeout.connect(lambda: None)

    from anisync.ui.main_window import MainWindow

    win = MainWindow()
    win.show()

    code = app.exec()
    shutdown_async()
    return code


if __name__ == "__main__":  # pragma: no cover
    sys.exit(run(sys.argv))

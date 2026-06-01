"""Account page — sign-in / register UI, centered card layout."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QStackedLayout,
    QVBoxLayout,
    QWidget,
)

from anisync.core.auth import Account, AuthError, AuthService
from anisync.core.config import Config
from anisync.utils.async_runner import run_async


class AuthPage(QWidget):
    def __init__(self) -> None:
        super().__init__()
        cfg = Config.load()
        self._svc = AuthService(cfg.auth_backend_url)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet("background: transparent;")
        outer.addWidget(scroll)

        body = QWidget()
        body.setStyleSheet("background: transparent;")
        scroll.setWidget(body)

        body_l = QVBoxLayout(body)
        body_l.setContentsMargins(64, 32, 64, 60)
        body_l.setSpacing(20)

        kicker = QLabel("YOUR ACCOUNT")
        kicker.setObjectName("kicker")
        body_l.addWidget(kicker)

        title = QLabel("Account")
        title.setObjectName("h1")
        body_l.addWidget(title)

        subtitle = QLabel(
            "Sign in to sync your library and history across devices."
            if self._svc.is_configured
            else "Cloud accounts are coming soon — this build runs in offline mode. "
                 "Your favorites, lists and history are saved locally."
        )
        subtitle.setStyleSheet("color:#9A9AA5; font-size:14px;")
        subtitle.setWordWrap(True)
        subtitle.setMaximumWidth(640)
        body_l.addWidget(subtitle)

        body_l.addSpacing(8)

        # ── centered card ──
        card_row = QHBoxLayout()
        card_row.addStretch(1)
        card = QFrame()
        card.setObjectName("card")
        card.setMinimumWidth(440)
        card.setMaximumWidth(520)
        card_row.addWidget(card)
        card_row.addStretch(1)
        body_l.addLayout(card_row)

        c = QVBoxLayout(card)
        c.setContentsMargins(28, 28, 28, 28)
        c.setSpacing(16)

        # Tabs
        tabs = QHBoxLayout()
        tabs.setSpacing(8)
        self._tab_login = QPushButton("Sign in")
        self._tab_register = QPushButton("Create account")
        for b in (self._tab_login, self._tab_register):
            b.setCheckable(True)
            b.setObjectName("outlined")
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            tabs.addWidget(b, 1)
        self._tab_login.setChecked(True)
        self._tab_login.clicked.connect(lambda: self._switch(0))
        self._tab_register.clicked.connect(lambda: self._switch(1))
        c.addLayout(tabs)

        self._stack = QStackedLayout()
        c.addLayout(self._stack)

        # ── Sign-in form ──
        login_w = QWidget()
        lf = QFormLayout(login_w)
        lf.setSpacing(12)
        lf.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        self._login_user = QLineEdit()
        self._login_user.setPlaceholderText("username")
        self._login_pass = QLineEdit()
        self._login_pass.setEchoMode(QLineEdit.EchoMode.Password)
        self._login_pass.setPlaceholderText("password")
        lf.addRow("Username", self._login_user)
        lf.addRow("Password", self._login_pass)
        self._login_btn = QPushButton("Sign in")
        self._login_btn.setObjectName("primary")
        self._login_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._login_btn.clicked.connect(self._do_login)
        lf.addRow("", self._login_btn)
        self._stack.addWidget(login_w)

        # ── Register form ──
        reg_w = QWidget()
        rf = QFormLayout(reg_w)
        rf.setSpacing(12)
        rf.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        self._reg_user = QLineEdit()
        self._reg_email = QLineEdit()
        self._reg_email.setPlaceholderText("you@example.com")
        self._reg_pass = QLineEdit()
        self._reg_pass.setEchoMode(QLineEdit.EchoMode.Password)
        rf.addRow("Username", self._reg_user)
        rf.addRow("Email", self._reg_email)
        rf.addRow("Password", self._reg_pass)
        self._reg_btn = QPushButton("Create account")
        self._reg_btn.setObjectName("primary")
        self._reg_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._reg_btn.clicked.connect(self._do_register)
        rf.addRow("", self._reg_btn)
        self._stack.addWidget(reg_w)

        self._status_lbl = QLabel("")
        self._status_lbl.setObjectName("muted")
        self._status_lbl.setWordWrap(True)
        c.addWidget(self._status_lbl)

        self._me_box = QVBoxLayout()
        c.addLayout(self._me_box)

        body_l.addStretch(1)

        self._refresh_account()

    # ── helpers ──

    def _switch(self, idx: int) -> None:
        self._stack.setCurrentIndex(idx)
        self._tab_login.setChecked(idx == 0)
        self._tab_register.setChecked(idx == 1)
        for b in (self._tab_login, self._tab_register):
            b.style().unpolish(b); b.style().polish(b)

    def _refresh_account(self) -> None:
        while self._me_box.count():
            item = self._me_box.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()
        acc = AuthService.current_account()
        if not acc:
            return
        lbl = QLabel(f"Signed in as <b>{acc.username}</b>")
        lbl.setStyleSheet("padding-top:6px;")
        self._me_box.addWidget(lbl)
        out = QPushButton("Sign out")
        out.setObjectName("ghost")
        out.clicked.connect(self._sign_out)
        self._me_box.addWidget(out)

    def _do_login(self) -> None:
        u = self._login_user.text().strip()
        p = self._login_pass.text()
        if not u or not p:
            self._status_lbl.setText("Please fill in both fields.")
            return
        self._login_btn.setEnabled(False)
        self._status_lbl.setText("Signing in…")
        run_async(
            self._svc.login(u, p),
            on_done=lambda acc: self._on_signed(acc, "Signed in."),
            on_error=self._on_auth_err,
        )

    def _do_register(self) -> None:
        u = self._reg_user.text().strip()
        e = self._reg_email.text().strip()
        p = self._reg_pass.text()
        if not u or not e or not p:
            self._status_lbl.setText("Please fill in all fields.")
            return
        self._reg_btn.setEnabled(False)
        self._status_lbl.setText("Creating account…")
        run_async(
            self._svc.register(u, e, p),
            on_done=lambda acc: self._on_signed(acc, "Account created."),
            on_error=self._on_auth_err,
        )

    def _on_signed(self, acc: Account, msg: str) -> None:
        self._login_btn.setEnabled(True)
        self._reg_btn.setEnabled(True)
        self._status_lbl.setText(msg)
        self._refresh_account()

    def _on_auth_err(self, exc: Exception) -> None:
        self._login_btn.setEnabled(True)
        self._reg_btn.setEnabled(True)
        self._status_lbl.setText(str(exc))

    def _sign_out(self) -> None:
        AuthService.sign_out()
        self._status_lbl.setText("Signed out.")
        self._refresh_account()

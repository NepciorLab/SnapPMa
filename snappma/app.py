"""Glowny obiekt programu: ikona w obszarze powiadomien, PrintScreen, zrzut, ustawienia, aktualizacje."""
from __future__ import annotations

from PySide6.QtCore import QObject, QThreadPool, QTimer
from PySide6.QtGui import QAction, QCursor, QGuiApplication
from PySide6.QtWidgets import QMenu, QSystemTrayIcon

from . import autostart, updater
from .annotations import ToolState
from .hotkey import PrintScreenHook
from .i18n import tr
from .icons import app_icon
from .session import CaptureSession
from .settings import Settings
from .settings_dialog import SettingsDialog
from .version import APP_NAME, __version__

UPDATE_FIRST_CHECK_MS = 20_000
UPDATE_INTERVAL_MS = 6 * 3600 * 1000
UPDATE_RETRY_MS = 30_000
RECAPTURE_DELAY_MS = 180       # tyle czeka ponowny zrzut, zeby zniknely poprzednie nakladki


class SnapPMaApp(QObject):
    def __init__(self, settings: Settings, quiet_start: bool = False):
        super().__init__()
        self.settings = settings
        self.state = ToolState(settings.get("Tools/color"), settings.get("Tools/width"))
        self.session = CaptureSession(self.state, self)
        self.session.done.connect(self._on_done)
        self.dialog: SettingsDialog | None = None
        self._pending_update: str | None = None
        self._manual_check = False
        self._update_signals = updater.UpdateSignals()
        self._update_signals.result.connect(self._on_update_result)

        self.tray = QSystemTrayIcon(app_icon(), self)
        self.tray.setToolTip(f"{APP_NAME} – PrintScreen")
        self.menu = QMenu()
        act_capture = QAction(tr("Capture area (PrintScreen)"), self.menu)
        act_capture.triggered.connect(lambda: QTimer.singleShot(250, self.capture))
        act_settings = QAction(tr("Settings…"), self.menu)
        act_settings.triggered.connect(self.open_settings)
        act_update = QAction(tr("Check for updates"), self.menu)
        act_update.triggered.connect(lambda: self.check_updates(manual=True))
        act_exit = QAction(tr("Exit"), self.menu)
        act_exit.triggered.connect(lambda: QGuiApplication.quit())
        for a in (act_capture, act_settings, act_update):
            self.menu.addAction(a)
        self.menu.addSeparator()
        self.menu.addAction(act_exit)
        self.tray.setContextMenu(self.menu)
        self.tray.activated.connect(self._on_tray)
        self.tray.show()

        self.hotkey = PrintScreenHook(self)
        self.hotkey.pressed.connect(self.capture)
        if not self.hotkey.start():
            self.tray.showMessage(APP_NAME, tr("Could not hook the PrintScreen key."), QSystemTrayIcon.Warning, 6000)
        elif not quiet_start and settings.get("Program/notify_start"):
            self.tray.showMessage(APP_NAME, tr("SnapPMa is running. Press PrintScreen to capture."),
                                  QSystemTrayIcon.Information, 3000)

        # wpis autostartu odswiezamy przy kazdym starcie (program mogl zostac przeniesiony albo zaktualizowany)
        if settings.get("Program/autostart"):
            try:
                autostart.set_enabled(True)
            except OSError:
                pass
        updater.cleanup_old()
        self._update_timer = QTimer(self)
        self._update_timer.timeout.connect(self._auto_check)
        self._update_timer.start(UPDATE_INTERVAL_MS)
        QTimer.singleShot(UPDATE_FIRST_CHECK_MS, self._auto_check)

    # ---------- zrzut ----------
    def capture(self) -> None:
        if self.session.active:                 # PrintScreen w trakcie zrzutu zaczyna od nowa
            self.session.cancel()
            QTimer.singleShot(RECAPTURE_DELAY_MS, self.session.start)
        else:
            self.session.start()

    def _on_done(self, image) -> None:
        self.settings.set("Tools/color", self.state.color.name())
        self.settings.set("Tools/width", self.state.width)
        if image is None:
            return
        QGuiApplication.clipboard().setImage(image)
        if self.settings.get("Program/notify"):
            self.tray.showMessage(APP_NAME, tr("Copied to the clipboard") + f" ({image.width()} × {image.height()})",
                                  QSystemTrayIcon.Information, 2000)

    # ---------- tray i ustawienia ----------
    def _on_tray(self, reason) -> None:
        if reason == QSystemTrayIcon.Trigger:
            self.menu.popup(QCursor.pos())
            self.menu.activateWindow()
        elif reason == QSystemTrayIcon.DoubleClick:
            self.open_settings()

    def open_settings(self) -> None:
        self.menu.hide()
        if self.dialog is not None:
            self.dialog.raise_()
            self.dialog.activateWindow()
            return
        self.dialog = SettingsDialog(self.settings)
        self.dialog.checkRequested.connect(lambda: self.check_updates(manual=True))
        self.dialog.finished.connect(self._dialog_closed)
        self.dialog.open()

    def _dialog_closed(self, _result) -> None:
        self.dialog = None
        if self.settings.get("Program/auto_update"):
            QTimer.singleShot(1000, self._auto_check)

    # ---------- aktualizacje ----------
    def _auto_check(self) -> None:
        if self.settings.get("Program/auto_update") and updater.can_install():
            self.check_updates(manual=False)

    def check_updates(self, manual: bool) -> None:
        self._manual_check = manual
        job = updater.UpdateJob(str(self.settings.get("Program/github_repo")), __version__,
                                updater.can_install(), self._update_signals)
        QThreadPool.globalInstance().start(job)

    def _on_update_result(self, status: str, version: str, info: str, error: str) -> None:
        manual = self._manual_check
        if status == "current":
            if manual:
                self._message(tr("You have the latest version.") + f" ({__version__})")
        elif status == "error":
            if manual:
                self._message(tr("Update check failed.") + f" {error}", warning=True)
        elif status == "newer":                 # uruchomienie ze zrodel: tylko informacja
            self._message(tr("A newer version is available:") + f" {version}\n{info}")
        elif status == "ready":
            self._pending_update = info
            self._message(tr("Installing the update:") + f" {version}")
            self._apply_update()

    def _apply_update(self) -> None:
        if self._pending_update is None:
            return
        if self.session.active or self.dialog is not None:      # nie przerywamy pracy uzytkownika
            QTimer.singleShot(UPDATE_RETRY_MS, self._apply_update)
            return
        path, self._pending_update = self._pending_update, None
        try:
            updater.install_update(path)
        except Exception as exc:  # noqa: BLE001
            self._message(tr("Update failed.") + f" {exc}", warning=True)
            return
        self.hotkey.stop()
        updater.restart_app()
        QGuiApplication.quit()

    def _message(self, text: str, warning: bool = False) -> None:
        self.tray.showMessage(APP_NAME, text, QSystemTrayIcon.Warning if warning else QSystemTrayIcon.Information, 5000)

    def shutdown(self) -> None:
        self.hotkey.stop()
        self.tray.hide()

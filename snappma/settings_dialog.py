"""Okno ustawien: autostart, aktualizacja z GitHuba, jezyk."""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (QCheckBox, QComboBox, QDialog, QFormLayout, QHBoxLayout, QLabel, QLineEdit,
                               QMessageBox, QPushButton, QVBoxLayout)

from . import autostart
from .i18n import tr
from .icons import app_icon
from .settings import Settings
from .updater import valid_repo
from .version import APP_NAME, __date__, __version__


class SettingsDialog(QDialog):
    checkRequested = Signal()

    def __init__(self, settings: Settings, parent=None):
        super().__init__(parent)
        self.settings = settings
        self.setWindowTitle(f"{APP_NAME} – {tr('Settings')}")
        self.setWindowIcon(app_icon())
        self.setMinimumWidth(420)

        self.cb_autostart = QCheckBox(tr("Start with Windows"))
        self.cb_autostart.setChecked(autostart.is_enabled())
        self.cb_update = QCheckBox(tr("Update automatically from GitHub"))
        self.cb_update.setChecked(bool(settings.get("Program/auto_update")))
        self.cb_notify_start = QCheckBox(tr("Show a notification at startup"))
        self.cb_notify_start.setChecked(bool(settings.get("Program/notify_start")))
        self.cb_notify = QCheckBox(tr("Show a notification after copying"))
        self.cb_notify.setChecked(bool(settings.get("Program/notify")))
        self.ed_repo = QLineEdit(str(settings.get("Program/github_repo")))
        self.ed_repo.setPlaceholderText("owner/name")
        self.cmb_lang = QComboBox()
        self.cmb_lang.addItem(tr("Automatic (system)"), "auto")
        for code, name in (("en", "English"), ("pl", "Polski"), ("de", "Deutsch")):
            self.cmb_lang.addItem(name, code)
        self.cmb_lang.setCurrentIndex(max(0, self.cmb_lang.findData(settings.get("Program/language"))))

        form = QFormLayout()
        form.addRow(self.cb_autostart)
        form.addRow(self.cb_update)
        form.addRow(tr("GitHub repository (owner/name)"), self.ed_repo)
        form.addRow(self.cb_notify_start)
        form.addRow(self.cb_notify)
        form.addRow(tr("Language"), self.cmb_lang)
        note = QLabel(tr("The language changes after restarting the program."))
        note.setStyleSheet("color: gray;")

        btn_check = QPushButton(tr("Check for updates now"))
        btn_check.clicked.connect(self._check)
        btn_ok = QPushButton(tr("OK"))
        btn_ok.setDefault(True)
        btn_ok.clicked.connect(self.accept)
        btn_cancel = QPushButton(tr("Cancel"))
        btn_cancel.clicked.connect(self.reject)
        row = QHBoxLayout()
        row.addWidget(btn_check)
        row.addStretch(1)
        row.addWidget(btn_ok)
        row.addWidget(btn_cancel)

        version = QLabel(f"{APP_NAME} {__version__} ({__date__})")
        version.setAlignment(Qt.AlignRight)
        version.setStyleSheet("color: gray;")

        root = QVBoxLayout(self)
        root.addLayout(form)
        root.addWidget(note)
        root.addLayout(row)
        root.addWidget(version)

    def _save_repo(self) -> bool:
        repo = self.ed_repo.text().strip()
        if not valid_repo(repo):
            QMessageBox.warning(self, APP_NAME, tr("Enter the repository as owner/name."))
            return False
        self.settings.set("Program/github_repo", repo)
        return True

    def _check(self) -> None:
        if self._save_repo():
            self.checkRequested.emit()

    def accept(self) -> None:
        if not self._save_repo():
            return
        s = self.settings
        s.set("Program/auto_update", self.cb_update.isChecked())
        s.set("Program/notify_start", self.cb_notify_start.isChecked())
        s.set("Program/notify", self.cb_notify.isChecked())
        s.set("Program/language", self.cmb_lang.currentData())
        s.set("Program/autostart", self.cb_autostart.isChecked())
        try:
            autostart.set_enabled(self.cb_autostart.isChecked())
        except OSError as exc:
            QMessageBox.warning(self, APP_NAME, f"{tr('Could not change the Windows startup entry.')}\n{exc}")
        super().accept()

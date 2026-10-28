"""SnapPMa: PrintScreen -> zaznacz obszar -> narysuj strzalki, ramki, linie -> Ctrl+C kopiuje do schowka."""
from __future__ import annotations

import os
import sys


def set_taskbar_identity() -> None:
    try:
        import ctypes
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("Madon.SnapPMa")
    except Exception:  # noqa: BLE001
        pass


def main(argv: list[str]) -> int:
    if "--selftest" in argv:                    # samotest bez okna: SnapPMa.exe --selftest wynik.txt
        os.environ["QT_QPA_PLATFORM"] = "offscreen"
        out = argv[argv.index("--selftest") + 1] if len(argv) > argv.index("--selftest") + 1 else "selftest.txt"
        from snappma.selftest import run
        return run(out)

    from PySide6.QtWidgets import QApplication, QMessageBox, QSystemTrayIcon

    from snappma import i18n, single_instance
    from snappma.app import SnapPMaApp
    from snappma.icons import app_icon
    from snappma.settings import Settings
    from snappma.version import APP_NAME

    set_taskbar_identity()
    qapp = QApplication(argv)
    qapp.setQuitOnLastWindowClosed(False)
    qapp.setApplicationName(APP_NAME)
    qapp.setWindowIcon(app_icon())
    settings = Settings()
    i18n.set_language(settings.get("Program/language"))

    restarted = bool(os.environ.pop("SNAPPMA_RESTART", ""))
    if not single_instance.acquire(wait_seconds=15.0 if restarted else 0.0):
        return 0                                # SnapPMa juz dziala (ikona w obszarze powiadomien)
    if not QSystemTrayIcon.isSystemTrayAvailable():
        QMessageBox.critical(None, APP_NAME, i18n.tr("The system tray is not available."))
        return 1

    window = SnapPMaApp(settings, quiet_start="--autostart" in argv or restarted)
    qapp.aboutToQuit.connect(window.shutdown)
    return qapp.exec()


if __name__ == "__main__":
    sys.exit(main(sys.argv))

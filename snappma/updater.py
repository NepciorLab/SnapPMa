"""Aktualizacja z GitHuba: ostatnie wydanie (Releases) z plikiem SnapPMa.exe.

Sprawdzenie i pobranie dzieja sie w tle. Zainstalowanie: zmiana nazwy dzialajacego exe na .old (system na to pozwala),
wstawienie nowego pliku pod stara nazwa i ponowne uruchomienie programu.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import urllib.request
from pathlib import Path

from PySide6.QtCore import QObject, QRunnable, Signal

from .paths import app_dir, is_frozen, launch_command
from .version import APP_NAME, __version__

EXE_NAME = f"{APP_NAME}.exe"
API_URL = "https://api.github.com/repos/{repo}/releases/latest"
USER_AGENT = f"{APP_NAME}/{__version__}"


def parse_version(text: str) -> tuple[int, ...]:
    parts = []
    for p in text.strip().lstrip("vV").split("."):
        digits = "".join(ch for ch in p if ch.isdigit())
        parts.append(int(digits) if digits else 0)
    return tuple(parts)


def valid_repo(text: str) -> bool:
    return bool(re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", text.strip()))


def pick_asset(release: dict) -> dict | None:
    """Plik .exe z wydania: najpierw SnapPMa.exe, potem dowolny .exe."""
    assets = [a for a in (release.get("assets") or []) if str(a.get("browser_download_url", "")).startswith("https://")]
    for a in assets:
        if str(a.get("name", "")).lower() == EXE_NAME.lower():
            return a
    return next((a for a in assets if str(a.get("name", "")).lower().endswith(".exe")), None)


def fetch_release(repo: str, timeout: float = 15.0) -> dict:
    req = urllib.request.Request(API_URL.format(repo=repo.strip()),
                                 headers={"User-Agent": USER_AGENT, "Accept": "application/vnd.github+json"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def new_exe_path() -> Path:
    cur = Path(sys.executable)
    return cur.with_name(cur.name + ".new")


def download(url: str, dest: Path, expected_size: int = 0, timeout: float = 60.0) -> None:
    if not url.startswith("https://"):
        raise ValueError("only https downloads are allowed")
    part = dest.with_name(dest.name + ".part")
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp, open(part, "wb") as out:
            while True:
                chunk = resp.read(1 << 16)
                if not chunk:
                    break
                out.write(chunk)
        size = part.stat().st_size
        with open(part, "rb") as f:
            magic = f.read(2)
        if magic != b"MZ" or (expected_size and size != expected_size):
            raise OSError("downloaded file is incomplete or is not an .exe")
        os.replace(part, dest)
    finally:
        part.unlink(missing_ok=True)


class UpdateSignals(QObject):
    # status: current | newer | ready | error; version; informacja (adres albo sciezka pliku); komunikat bledu
    result = Signal(str, str, str, str)


class UpdateJob(QRunnable):
    """install=True: nowsza wersja jest od razu pobierana do pliku .new (status `ready`); False: tylko informacja."""

    def __init__(self, repo: str, current: str, install: bool, signals: UpdateSignals):
        super().__init__()
        self.repo, self.current, self.install, self.signals = repo, current, install, signals

    def run(self) -> None:
        try:
            if not valid_repo(self.repo):
                raise ValueError("invalid repository name")
            release = fetch_release(self.repo)
            version = str(release.get("tag_name", "")).lstrip("vV")
            if not version or parse_version(version) <= parse_version(self.current):
                self.signals.result.emit("current", version, "", "")
                return
            asset = pick_asset(release)
            if asset is None:
                raise LookupError(f"release {version} has no {EXE_NAME}")
            if not self.install:
                self.signals.result.emit("newer", version, str(asset["browser_download_url"]), "")
                return
            dest = new_exe_path()
            download(str(asset["browser_download_url"]), dest, int(asset.get("size") or 0))
            self.signals.result.emit("ready", version, str(dest), "")
        except Exception as exc:  # noqa: BLE001 - siec, JSON, dysk: kazdy blad ma byc pokazany, nie przerwac programu
            self.signals.result.emit("error", "", "", str(exc))


def can_install() -> bool:
    return is_frozen()


def install_update(new_file: str) -> None:
    """Podmienia dzialajacy SnapPMa.exe na pobrany plik. Przy bledzie zostaje stary plik."""
    if not is_frozen():
        raise RuntimeError("update works only in the packaged .exe")
    cur = Path(sys.executable)
    new = Path(new_file)
    old = cur.with_name(cur.name + ".old")
    old.unlink(missing_ok=True)
    os.replace(cur, old)
    try:
        os.replace(new, cur)
    except OSError:
        os.replace(old, cur)
        raise


def cleanup_old() -> None:
    """Usuwa pozostalosci po poprzedniej aktualizacji."""
    if not is_frozen():
        return
    cur = Path(sys.executable)
    for suffix in (".old", ".new", ".new.part"):
        try:
            cur.with_name(cur.name + suffix).unlink(missing_ok=True)
        except OSError:
            pass


def restart_app() -> None:
    """Uruchamia nowa, niezalezna instancje (wywolujacy powinien potem zamknac biezaca)."""
    env = dict(os.environ)
    env["SNAPPMA_RESTART"] = "1"                   # nowa instancja czeka, az stara zwolni mutex
    env["PYINSTALLER_RESET_ENVIRONMENT"] = "1"      # rozpakowuje sie osobno, nie korzysta z katalogu rodzica
    flags = getattr(subprocess, "DETACHED_PROCESS", 0) | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
    subprocess.Popen(launch_command(), cwd=str(app_dir()), env=env, creationflags=flags, close_fds=True)

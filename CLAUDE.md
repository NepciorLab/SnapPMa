# SnapPMa: kontekst projektu

Program pod Windows 11 (Python + PySide6): PrintScreen -> zaznaczenie prostokąta -> adnotacje (ołówek, linia, strzałka, prostokąt, strzałka-kursor) -> Ctrl+C kopiuje do schowka. Działa w zasobniku. Interfejs EN (domyślny) / PL / DE. Autor: Przemysław Madoń.

## Uruchamianie, testy, budowa
- Środowisko: `.\setup_env.ps1` (`.venv`, `requirements-dev.txt`). Uruchomienie: `run.bat`. Testy: `python -m pytest tests` (offscreen, nic nie pokazuje na ekranie; `conftest.py` ustawia `QT_QPA_PLATFORM=offscreen`).
- Samotest bez okna: `python main.py --selftest wynik.txt` (to samo robi `SnapPMa.exe --selftest`); `snappma/selftest.py` symuluje myszą zaznaczenie i rysowanie na sztucznym zrzucie.
- Budowa: `.\build.ps1` -> `dist\SnapPMa.exe` (ikona `assets/SnapPMa.ico` z `tools_make_icon.py`). Skrypty `.ps1` czysty ASCII. Przed wydaniem podnieś `__version__` w `snappma/version.py`; wydanie na GitHubie = Release z tagiem `v<wersja>` i plikiem `SnapPMa.exe`.
- NIE uruchamiaj programu na ekranie użytkownika bez pytania (haczyk klawiatury połyka PrintScreen; użytkownik często gra).

## Architektura (`snappma/`)
- `hotkey.py`: `WH_KEYBOARD_LL` w osobnym wątku (`PrintScreenHook`), logika w czystej `PrintScreenFilter` (połyka sam PrintScreen, przepuszcza Ctrl/Alt/Win+PrintScreen i zdarzenia wstrzyknięte; autopowtarzanie nie wywołuje zrzutu drugi raz).
- `session.py`: `CaptureSession` robi zrzuty WSZYSTKICH monitorów (`QScreen.grabWindow(0)`) przed pokazaniem nakładek; po jednej `CaptureOverlay` na monitor; `foreground.bring_to_front` daje klawiaturę nakładce (program w tle nie ma prawa do pierwszego planu).
- `overlay.py`: faza `select` -> `edit`; zrzut trzymany w pikselach fizycznych (`shot`, DPR 1), współrzędne okna i adnotacji logiczne, przeliczenie `fx, fy` przy rysowaniu i w `render_result`. Uchwyty zmiany rozmiaru, przesuwanie wnętrza (bez narzędzia), rysowanie tylko od punktu wewnątrz zaznaczenia, punkty przycinane do zaznaczenia, Shift przy linii/strzałce = oś, przy prostokącie = kwadrat. Logika zdarzeń jest w `_press/_move/_release` (wywoływane też z testów).
- `annotations.py`: `Item`, `paint_item` (to samo rysowanie w podglądzie i wyniku), `render_result` (wycina zaznaczenie z fizycznego zrzutu i rysuje adnotacje ze skalą), geometria strzałki i kursora (kursor jest ZAWSZE biały z cienką czarną obwódką, kolor wyboru go nie dotyczy).
- `toolbar.py` + `icons.py`: pasek (narzędzia, cofnij, 7 kolorów + własny, suwak grubości, kopiuj, anuluj); ikony rysowane w kodzie. Wszystkie kontrolki `NoFocus`, żeby Ctrl+C/Esc zawsze trafiały do nakładki. Kliknięcie w pusty fragment paska jest połykane.
- `app.py`: ikona w zasobniku (lewy i prawy klik = menu, podwójny = Ustawienia), schowek (`setImage`), aktualizacje, ponowny zrzut przy PrintScreen w trakcie zrzutu.
- `settings.py` (`SnapPMa.ini` obok programu albo w %APPDATA%), `settings_dialog.py`, `autostart.py` (HKCU Run, polecenie z `--autostart`), `updater.py` (GitHub API `releases/latest`, plik `SnapPMa.exe` z wydania, tylko https, podmiana exe -> `.old`, restart z `SNAPPMA_RESTART`), `single_instance.py` (mutex).
- `i18n.py` + `translations.py`: kluczem jest angielski tekst w `tr("...")`; każdy nowy tekst musi mieć wpis PL i DE (pilnuje `tests/test_i18n.py`).

## Ustalenia
- Nie zweryfikowane na prawdziwym ekranie (powstało, gdy użytkownik grał): haczyk klawiatury, skalowanie DPI na wielu monitorach, fokus nakładki, menu zasobnika przy lewym kliknięciu, okno wyboru własnego koloru nad nakładką, zapis wydania i aktualizacja z GitHuba. Po pierwszym uruchomieniu na ekranie sprawdzić te punkty.
- Nazwa programu, pakietu, katalogu i plików to SnapPMa (wcześniej SnapMark). Repozytorium `NepciorLab/SnapPMa` (prywatne; aktualizacja z GitHuba używa niezalogowanego API, więc przy prywatnym repozytorium nie zadziała), wersja startowa 0.0.1.
- Ikony pędzla, linii, strzałki i prostokąta na pasku są żółte (`icons.YELLOW`), reszta jasna.

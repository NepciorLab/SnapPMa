# SnapPMa

Zrzuty ekranu z adnotacjami dla Windows 11 (Python + PySide6).

**PrintScreen** -> zaznacz prostokąt myszą -> narysuj strzałki, ramki, linie, malowanie -> **Ctrl+C** kopiuje obraz do schowka.
Program działa w obszarze powiadomień (zasobniku), zaraz po starcie jest zminimalizowany. Klawisz PrintScreen jest
przechwytywany, więc Windows nie otwiera już Narzędzia Wycinanie. Kombinacje z Ctrl, Alt i Win (np. Win+PrintScreen,
Alt+PrintScreen) działają jak zwykle.

## Obsługa

1. PrintScreen: ekran przyciemnia się, przeciągnij myszą prostokąt (prawy przycisk albo Esc anuluje).
2. Zaznaczenie można zmienić: uchwyty na bokach i rogach zmieniają rozmiar, przeciągnięcie wnętrza (bez wybranego narzędzia) przesuwa.
3. Pasek narzędzi pod zaznaczeniem (albo nad nim, gdy zabrakło miejsca):
   - **Pędzel** (rysowanie odręczne), **Linia**, **Strzałka**, **Prostokąt**, **Tekst** (Arial, rozmiar z listy na pasku albo rolka myszy przy narzędziu Tekst; kliknij i pisz, Enter zatwierdza, Shift+Enter nowa linia, Esc odrzuca; zatwierdzony tekst przeciągasz myszą, dwuklik edytuje), **Strzałka jak kursor myszy** (zawsze biała z cienką czarną obwódką; kliknięcie stawia, przeciągnięcie przesuwa),
   - **Cofnij** (Ctrl+Z), **kolor** (7 gotowych + „…” własny), **grubość linii** (suwak albo rolka myszy), **kopiuj** (zielony ptaszek), **anuluj**.
   - **Shift** przy linii i strzałce: linia dokładnie pozioma albo pionowa; przy prostokącie: kwadrat.
   - Ponowne kliknięcie wybranego narzędzia wyłącza je (wtedy można przesuwać i zmieniać zaznaczenie).
4. **Ctrl+C** (albo zielony ptaszek) kopiuje wycinek razem z adnotacjami do schowka. Rozmiar zrzutu to rozmiar w pikselach fizycznych ekranu.
5. PrintScreen podczas zaznaczania zaczyna zrzut od nowa. Wiele monitorów: zaznaczanie odbywa się na jednym monitorze.

## Ikona w zasobniku

Kliknięcie (lewym lub prawym przyciskiem) otwiera menu: Zrób zrzut, **Ustawienia…**, Sprawdź aktualizacje, Zakończ. Podwójne kliknięcie otwiera Ustawienia.

Ustawienia: **uruchamiaj razem z Windows** (wpis `HKCU\...\Run`, bez uprawnień administratora), **aktualizuj automatycznie z GitHuba**,
repozytorium GitHub, powiadomienie po uruchomieniu i po skopiowaniu, język (EN / PL / DE, zmiana po restarcie). Plik ustawień `SnapPMa.ini` leży obok programu
(a gdy tam nie wolno pisać, w `%APPDATA%\SnapPMa`). Kolor i grubość linii są pamiętane.

## Aktualizacje z GitHuba

Program pyta GitHub API o ostatnie wydanie (Release) repozytorium z Ustawień (domyślnie `NepciorLab/SnapPMa`, zmień w `snappma/version.py` albo w Ustawieniach).
Jeśli numer w tagu (np. `v1.0.1`) jest większy od zainstalowanego, pobiera z wydania plik `SnapPMa.exe`, podmienia działający plik (stary zostaje jako `.old`)
i uruchamia się ponownie (nie w trakcie zrzutu). Sprawdza 20 s po starcie i co 6 godzin, a ręcznie z menu. Działa tylko w spakowanym `.exe`.

Wydanie: podnieś `__version__` w `snappma/version.py`, `.\build.ps1`, na GitHubie utwórz Release z tagiem `v<wersja>` i dołącz `dist\SnapPMa.exe`.

## Uruchamianie, testy, budowa

```powershell
.\setup_env.ps1            # raz: .venv + zależności
.\run.bat                  # uruchomienie (ikona w zasobniku, PrintScreen aktywny)
.\.venv\Scripts\python.exe -m pytest tests     # testy bez okna (offscreen)
.\build.ps1                # dist\SnapPMa.exe
dist\SnapPMa.exe --selftest wynik.txt         # samotest bez okna
```

# KORAD KWR 102 Unofficial Software PL/EN

**v1.0 — by Horde97**

Nieoficjalne, niezależne oprogramowanie sterujące dla zasilacza laboratoryjnego KORAD KWR102 (seria KWR100).
Unofficial, independent control software for the KORAD KWR102 laboratory power supply (KWR100 series).

> **Projekt niezależny — niepowiązany z firmą KORAD.**
> **Independent project — not affiliated with KORAD.**
> 
📥 Pobierz program / Download

Gotowy plik KORAD Monitor.exe znajdziesz w zakładce Releases. The prebuilt KORAD Monitor.exe is available under Releases.
<img width="1944" height="1542" alt="Image" src="https://github.com/user-attachments/assets/42dcb4db-2050-4c2a-854e-246d2d7a527b" />
---
⚠️ Uwaga: antywirus może zgłosić fałszywy alarm

Windows Defender, SmartScreen lub inny program antywirusowy może oznaczyć plik jako podejrzany. To normalne i nie oznacza, że plik zawiera wirusa. Dzieje się tak, ponieważ program został spakowany narzędziem PyInstaller i nie jest podpisany cyfrowo (podpis kosztuje kilkaset dolarów rocznie). Tą samą metodą pakowanych jest tysiące legalnych programów w Pythonie.

Jeśli mi nie ufasz — i słusznie, bo nie powinieneś ufać obcym plikom .exe — kod źródłowy jest w całości dostępny w tym repozytorium. Możesz go przejrzeć i samodzielnie zbudować plik .exe (instrukcja niżej) albo po prostu uruchomić program bezpośrednio z kodu.

⚠️ Note: antivirus may report a false positive

Windows Defender, SmartScreen or another antivirus may flag the file as suspicious. This is normal and does not mean the file contains a virus. It happens because the program is packaged with PyInstaller and is not code-signed (signing costs several hundred dollars per year). Thousands of legitimate Python programs are distributed the same way.

If you don't trust it — and you shouldn't blindly trust .exe files from strangers — the full source code is available in this repository. You can review it and build the .exe yourself (instructions below), or simply run the program directly from source.

## 🇵🇱 Wersja polska

### Co to jest

Program do sterowania i monitorowania zasilacza laboratoryjnego KORAD KWR102 przez port USB/RS232.
Powstał jako alternatywa dla oficjalnego oprogramowania producenta.

### Funkcje

- Odczyt na żywo napięcia, prądu i mocy
- Wykres prądu w czasie rzeczywistym z automatycznym skalowaniem osi
- Ustawianie napięcia i prądu (pola tekstowe oraz przyciski +/- z konfigurowalnym krokiem)
- Włączanie/wyłączanie wyjścia
- 5 własnych profili szybkiego wywołania (zapisywanych lokalnie)
- Zabezpieczenia OVP / OCP, blokada panelu, priorytet CV/CC
- Rejestr najwyższego zmierzonego prądu (zachowywany między uruchomieniami)
- Reset wszystkich ustawień jednym przyciskiem
- Interfejs w języku polskim i angielskim (przełączany w ustawieniach ⚙)
- Wszystkie ustawienia zapisywane automatycznie do pliku `korad_config.json`

### Wymagania

- **Windows 64-bit**
- Zasilacz KORAD KWR102 podłączony kablem USB
- Zainstalowany sterownik USB-serial dla kabla zasilacza (zwykle CH340 lub podobny) —
  bez niego zasilacz nie pojawi się jako port COM w systemie

### Instalacja i uruchomienie

**Opcja 1 — gotowy program (najprostsza):**

Pobierz plik `KORAD Monitor.exe` i uruchom go. Nie wymaga instalacji Pythona ani żadnych bibliotek.

> ⚠️ Windows SmartScreen może wyświetlić ostrzeżenie, ponieważ plik nie jest podpisany
> cyfrowo. Kliknij **„Więcej informacji" → „Uruchom mimo to"**.

**Opcja 2 — uruchomienie z kodu źródłowego:**

```
python -m pip install pyserial matplotlib
python korad_gui_v4.py
```

**Samodzielne zbudowanie pliku .exe:**

```
python -m pip install pyinstaller
python -m PyInstaller --onefile --windowed --icon=korad_icon.ico --name "KORAD Monitor" korad_gui_v4.py
```

Gotowy plik pojawi się w podfolderze `dist`.

### Pierwsze uruchomienie

1. Podłącz zasilacz do komputera kablem USB i włącz go.
2. Uruchom program.
3. Wybierz port COM z listy (zwykle wykrywany automatycznie) i prędkość **115200**.
4. Kliknij **Połącz**. Jeśli wszystko działa, obok przycisku pojawi się identyfikacja zasilacza.

### ⚠️ Ostrzeżenie / Odpowiedzialność

**Używasz tego oprogramowania na własną odpowiedzialność.**

Program steruje rzeczywistym zasilaczem laboratoryjnym. Nieprawidłowe ustawienia napięcia lub
prądu mogą trwale uszkodzić podłączony sprzęt. Zawsze sprawdź nastawy przed włączeniem wyjścia.

Autor nie ponosi odpowiedzialności za jakiekolwiek szkody, uszkodzenia sprzętu ani straty
wynikające z użytkowania tego oprogramowania.

### Licencja

Projekt open source na licencji **MIT** (pełna treść w pliku `LICENSE`).

Oznacza to, że możesz swobodnie:

- ✅ używać programu do dowolnych celów, także komercyjnych
- ✅ modyfikować kod i dostosowywać go do własnych potrzeb
- ✅ rozpowszechniać oryginał i własne wersje

Pod jednym warunkiem:

- ❗ **musisz zachować informację o oryginalnym autorze** (plik `LICENSE` z nazwiskiem autora
  oraz notatką o prawach autorskich). Nie możesz przypisać sobie autorstwa tego programu.

### Znaki towarowe i niezależność projektu

Jest to **nieoficjalny projekt niezależny**, nietworzony, niesponsorowany, niewspierany ani
w żaden sposób niepowiązany z firmą KORAD ani jej podmiotami zależnymi.

KORAD, KWR102 i wszelkie inne nazwy produktów są znakami towarowymi swoich właścicieli i użyto
ich wyłącznie w celu opisowym — aby wskazać, z jakim urządzeniem to oprogramowanie współpracuje.

Program powstał w całości od zera. Protokół komunikacji ustalono metodą obserwacji transmisji
szeregowej pomiędzy urządzeniem a komputerem, wyłącznie w celu zapewnienia interoperacyjności
z zakupionym urządzeniem. Nie wykorzystano żadnego kodu, grafik ani materiałów producenta.

---

## 🇬🇧 English version

### What is this

Control and monitoring software for the KORAD KWR102 laboratory power supply over USB/RS232.
Created as an alternative to the manufacturer's official software.

### Features

- Live voltage, current and power readout
- Real-time current waveform with automatic axis scaling
- Voltage and current setpoints (text fields and +/- buttons with configurable step)
- Output on/off control
- 5 custom quick-call profiles (stored locally)
- OVP / OCP protection, panel lock, CV/CC priority
- Peak current record (persists between sessions)
- One-click reset of all settings
- Polish and English interface (switchable in settings ⚙)
- All settings saved automatically to `korad_config.json`

### Requirements

- **Windows 64-bit**
- KORAD KWR102 power supply connected via USB
- USB-serial driver installed for the supply's cable (usually CH340 or similar) —
  without it the device will not appear as a COM port

### Installation

**Option 1 — prebuilt executable (easiest):**

Download `KORAD Monitor.exe` and run it. No Python or libraries required.

> ⚠️ Windows SmartScreen may show a warning because the file is not code-signed.
> Click **"More info" → "Run anyway"**.

**Option 2 — run from source:**

```
python -m pip install pyserial matplotlib
python korad_gui_v4.py
```

**Build the .exe yourself:**

```
python -m pip install pyinstaller
python -m PyInstaller --onefile --windowed --icon=korad_icon.ico --name "KORAD Monitor" korad_gui_v4.py
```

The result appears in the `dist` subfolder.

### First run

1. Connect the power supply via USB and switch it on.
2. Launch the program.
3. Select the COM port (usually auto-detected) and baud rate **115200**.
4. Click **Establish connection**. On success, the supply's identification appears next to the button.

### ⚠️ Disclaimer

**Use this software at your own risk.**

This program controls a real laboratory power supply. Incorrect voltage or current settings may
permanently damage connected equipment. Always verify your setpoints before enabling the output.

The author accepts no liability for any damage, equipment failure or loss resulting from the use
of this software.

### License

Open source under the **MIT License** (full text in the `LICENSE` file).

You are free to:

- ✅ use the software for any purpose, including commercial
- ✅ modify the code and adapt it to your needs
- ✅ redistribute the original and your own versions

On one condition:

- ❗ **you must retain the original author attribution** (the `LICENSE` file including the
  author's name and copyright notice). You may not claim this software as your own work.

### Trademarks and project independence

This is an **unofficial, independent project**. It is not created, sponsored, endorsed by, or
affiliated with KORAD or any of its subsidiaries in any way.

KORAD, KWR102 and all other product names are trademarks of their respective owners and are used
here purely descriptively — to indicate which device this software works with.

This software was written entirely from scratch. The communication protocol was determined by
observing serial traffic between the device and a computer, solely for the purpose of achieving
interoperability with a purchased device. No manufacturer code, artwork or materials were used.

---

*KORAD KWR 102 Monitor v1.0 — by Horde97*

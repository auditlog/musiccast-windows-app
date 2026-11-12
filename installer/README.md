# Instalator Windows x64

Budowanie wymaga Windows x64, działającego środowiska `.venv-win` z Pythonem
3.12/3.13 x64 oraz [Inno Setup 6.3 lub nowszego](https://jrsoftware.org/isdl.php).
Na komputerze docelowym Python i Inno Setup nie są potrzebne.

Uruchom z katalogu projektu:

```bat
build-installer-windows.cmd
```

Skrypt instaluje zależności budowania w `.venv-win`, wykonuje testy, buduje pakiet
PyInstaller, używa `build\VBCABLE_Driver_Pack46.zip` albo pobiera tę paczkę z serwera producenta,
sprawdza strukturę archiwum i kompiluje Inno Setup. Wynik dla bieżącej wersji:

```text
dist\installer\MusicCastBridge-0.2.1-Setup-x64.exe
```

Wersja pochodzi z `__version__` w `src/musiccast_bridge/__init__.py`.
PyInstaller zapisuje FileVersion i ProductVersion w EXE, a build odczytuje
je z gotowego pliku i porównuje z wersją projektu. Inno Setup używa tego samego
numeru. Flaga `--skip-app-build` wymaga zgodnego build-info.json i wersji PE;
stary pakiet 0.1.0 nie zostanie opakowany jako 0.2.0.

Build odczytuje `remote.origin.url` i dołącza adres GitHuba do aplikacji.
Bez Gita na PATH odczytuje zwykły `.git/config`. Możesz wskazać inne repozytorium
wydań przez `MUSICCAST_RELEASE_REPOSITORY=auditlog/musiccast-windows-app`
lub ustawienia aplikacji.
Sprawdzanie korzysta z publicznych GitHub Releases; publikacja samego commita,
pushu lub tagu nie udostępnia nowej wersji updaterowi.

Instalator zawiera wszystkie potrzebne pliki i nie pobiera zależności podczas
instalacji na komputerze docelowym. Nie jest jeszcze podpisany naszym certyfikatem.
Paczka VB-CABLE zachowuje pliki i podpisy producenta; nie modyfikujemy sterownika.

Pierwsze okno instalatora zawsze pozwala wybrać Polski lub English. W wersji
0.2.1 wybór obejmuje interfejs, MIT, zasady korzystania, prywatność i objaśnienia
składników zewnętrznych. Polski tekst MIT jest pełnym tłumaczeniem informacyjnym;
angielski oryginał pozostaje dołączony do pakietu i dostępny w aplikacji.
Oryginalne licencje bibliotek nie są zastępowane tłumaczeniami.

Każda instalacja zapisuje w `install.ini` język i znacznik nowego wyboru.
Aplikacja stosuje ten wybór raz przy najbliższym uruchomieniu, także po ponownej
instalacji tej samej wersji, zachowując pozostałe preferencje użytkownika.
Późniejsza zmiana w Ustawienia → Ogólne pozostaje zapamiętana. Instalator nie
uruchamia aplikacji w celu zmiany ustawień podczas instalacji sterownika.
Okna Windows/UAC i instalatora producenta VB-CABLE używają własnego języka.

Zasoby dokumentów są w `src/musiccast_bridge/legal_texts/pl` oraz `en`.
Po edycji dwujęzycznych plików w katalogu projektu uruchom
`python scripts/localize_documents.py`. Testy kontrolują ich zgodność; polskie
tłumaczenie MIT jest utrzymywane oddzielnie. Build dołącza także `qtbase_pl.qm`,
aby standardowe okno wyboru pliku używało języka aplikacji niezależnie od Windows.
Build dołącza MIT, zasady korzystania, prywatność, pełne teksty LGPLv3/GPLv3 oraz
dostępne licencje i metadane zależności. Przed publiczną dystrybucją wykonaj
[procedurę wydania LGPL](../licenses/README.md), w tym publikację odpowiadających
źródeł bibliotek. Samo wygenerowanie pliku Setup.exe nie potwierdza tego etapu.

Automatyczne przełączanie wyjścia Windows jest domyślnie wyłączone i wymaga
wyboru urządzenia w ustawieniach aplikacji. Korzysta z lokalnego pomocnika
PowerShell/Core Audio; nie instaluje dodatkowego sterownika. Testy buildu
sprawdzają kompilację pomocnika i odczyt urządzeń bez zmiany wyjścia.

## Paczka lokalna i istniejący build EXE

Jeśli ZIP pobrano wcześniej, przekaż oryginalną paczkę standardowego VB-CABLE:

```bat
build-installer-windows.cmd --vbcable-zip "C:\pobrane\VBCABLE_Driver_Pack46.zip"
```

Aby opakować istniejący folder `dist\MusicCastBridge` bez ponawiania budowania
aplikacji i testów, dodaj `--skip-app-build`. Nie używaj paczek kabli A+B, C+D ani
Hi-Fi Cable. Kompilator można wskazać zmienną `ISCC_EXE`, jeśli nie został znaleziony
w PATH lub standardowym katalogu instalacji Inno Setup.

Build wymaga SHA-256 sprawdzonego Pack46:
`bc44e8974191a5a2427d6c979e2dab08dbb09925f3f435dfa2f0ba3e45b6eb90`.
Inna paczka zatrzymuje budowanie. Skróty archiwum i każdego pliku są zapisywane w
`build\installer\vbcable-package.json`. Punktem odniesienia jest oryginalna paczka
użytkownika, którą sprawdzono lokalnie; nie jest to niezależne potwierdzenie
pochodzenia przez serwer producenta. Archiwum powinno pochodzić z
[oficjalnej strony VB-Audio](https://vb-audio.com/Cable/).
Nie wykonujemy instalatora VB-CABLE na komputerze budującym.

## Zachowanie Setup.exe

- Aplikacja trafia do `%LOCALAPPDATA%\Programs\MusicCastBridge`, ze skrótem w menu
  Start i opcjonalnym skrótem na pulpicie. Instalacja aplikacji jest dla bieżącego
  użytkownika. Nie zmienia lokalizacji jego ustawień ani poświadczeń AirPlay.
- Wybrany składnik VB-CABLE sprawdza urządzenie klasy MEDIA przez lokalne CIM.
  Zmiana nazwy samego wyjścia audio nie powoduje reinstalacji sterownika.
  Wykryty sterownik nie jest przeinstalowywany. Kod urządzenia 14 oznacza restart;
  pozostałe problemy urządzenia wymagają sprawdzenia zamiast obietnicy naprawy restartem.
- Przy braku kabla uruchamiany jest oryginalny instalator `VBCABLE_Setup_x64.exe`
  z `-i -h`, z podniesieniem uprawnień tylko dla tego procesu. Anulowanie UAC
  lub błąd wykrywania zatrzymuje etap zależności; można ponowić próbę lub wrócić
  do wyboru samej aplikacji.
- Po zakończeniu procesu ponownie sprawdzana jest obecność urządzenia. Nie
  zakładamy znaczenia nieudokumentowanych kodów wyjścia producenta. Jeżeli
  urządzenia nadal nie wykryto, instalator zgłasza brak potwierdzenia zamiast
  ogłaszać sukces. Nowa instalacja kabla oznacza wymagany restart; aplikacja
  nie uruchamia się automatycznie przed nim.
- Pierwszy start bez wcześniejszych ustawień preferuje standardowe wyjście
  CABLE Input, jeśli wybrano składnik VB-CABLE. Brak jednoznacznego wyjścia
  blokuje start dźwięku do czasu jego wskazania. Istniejący wybór użytkownika
  jest zachowywany. Przypisanie przeglądarki/Spotify do CABLE Input wykonuje
  użytkownik w mikserze Windows. Producent opisuje, że Windows może zmienić
  domyślne urządzenie po instalacji nowego sterownika; warto je wtedy sprawdzić.
- Odinstalowanie usuwa pliki aplikacji oraz skróty. Wspólny sterownik, ustawienia,
  logi i poświadczenia użytkownika pozostają. Uruchomioną aplikację należy
  zamknąć przez Ctrl+Q przed aktualizacją lub odinstalowaniem.

VB-CABLE jest produktem VB-Audio Software i jest udostępniany jako donationware.
Informacja o autorze i możliwości wsparcia projektu jest dołączona do instalatora
oraz plików aplikacji. Obowiązują [warunki dystrybucji producenta](https://vb-audio.com/Services/licensing.htm).

## Stan weryfikacji

12 listopada 2026 użytkownik potwierdził udany natywny build **0.2.0**.
Sprawdzono pliki `dist\installer\MusicCastBridge-0.2.0-Setup-x64.exe`
(39 904 089 bajtów) oraz `dist\MusicCastBridge\MusicCastBridge.exe`.
Oba pliki mają w zasobach PE **FileVersion 0.2.0.0** i **ProductVersion 0.2.0.0**.
Nie uruchamiano instalatora w ramach tej kontroli.

Build zawiera poprawkę IID `IMMDeviceCollection`, wersjonowanie EXE i obsługę
sprawdzania GitHub Releases. Test natywny pozostaje włączony w pełnym procesie
budowania. Poprawki językowe 0.2.1 wymagają nowego buildu; istniejące pliki 0.2.0
ich nie zawierają. [Pełny zakres weryfikacji](../docs/VALIDATION.md).

W `build-info.json` gotowej aplikacji pole repozytorium jest puste. Sprawdzanie
aktualizacji wymaga wpisania adresu w ustawieniach albo zbudowania pakietu
z poprawnym origin lub `MUSICCAST_RELEASE_REPOSITORY`.

Testy Qt na Windows korzystają domyślnie z backendu `windows` i czcionki
Segoe UI 10, zgodnie z aplikacją. Jawne ustawienie `QT_QPA_PLATFORM` nadal ma
pierwszeństwo. Kontrola geometrii i wymóg zaliczenia testów przed pakowaniem
pozostają aktywne.

Sprawdzono rzeczywistą paczkę Pack46: 1 324 680 bajtów, 31 plików, pełna zgodność
kopii ze skrótami.
Pliki INF potwierdzają `DeviceName="VB-Audio Virtual Cable"` i usługę `VBAudioVACMME`.
Kod testów używa także syntetycznych archiwów i nie instaluje sterowników.
Testy klasyfikacji CIM w PowerShell są dołączone do buildu Windows.

Do sprawdzenia na komputerze docelowym: uruchomienie instalatora Pack46,
wykrywanie istniejącego i nowego kabla, anulowanie UAC, restart, aktualizacja
przy działającej aplikacji, odinstalowanie z zachowaniem sterownika oraz start
na komputerze bez Pythona. Obecność gotowego pliku instalatora nie potwierdza
jeszcze tych scenariuszy.

Weryfikacja na Windows powinna objąć obydwa języki, zapisywanie ustawień, start
na CABLE Input, zatrzymanie, wyjście przez Ctrl+Q, ręczną zmianę wyjścia w trakcie
przesyłania, odłączenie poprzedniego urządzenia i odzyskanie trasy po awarii.
Dla 0.2.1 sprawdź wybór PL i EN w pierwszym oknie, jednolity język dokumentów
instalatora i aplikacji, język okna pliku oraz zmianę języka przez reinstalację
i późniejszą zmianę w ustawieniach. Pozostałe preferencje powinny zostać zachowane.

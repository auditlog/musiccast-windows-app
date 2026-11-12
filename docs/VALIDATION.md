# Weryfikacja MusicCast Bridge

## Język aplikacji i instalatora 0.2.1 — 12 listopada 2026

- `python3 scripts/check.py --sandbox`: **141 testów, 120 zaliczonych,
  21 pominiętych**. Pominięto 20 testów Qt i jeden natywny Core Audio.
  Ruff, compileall i `scripts/localize_documents.py --check` przeszły.
- Audyt znalazł dwujęzyczne dokumenty w czytniku aplikacji i na stronie
  informacyjnej instalatora, nieprzetłumaczone opisy CLI oraz zewnętrzne błędy
  przechodzące do interfejsu. Poprawiono te ścieżki. Własne komunikaty używają
  katalogu PL/EN; techniczne zdarzenia raportu i metadane urządzeń pozostają
  w oryginalnym brzmieniu, z objaśnieniem w oknie diagnostyki.
- Testy sprawdzają komplet jawnych kluczy i pól formatowania, etykiety poza
  katalogiem, komunikaty zewnętrznych błędów, zgodność zasobów dokumentów z
  odpowiednimi sekcjami plików źródłowych oraz odrzucanie nieznanych ścieżek
  i języków. Polski MIT jest oznaczony jako tłumaczenie informacyjne; angielski
  oryginał jest dostępny osobno. Oryginalnych licencji bibliotek nie tłumaczono.
- Inno ma jawny wybór języka na początku oraz osobne LicenseFile/InfoBeforeFile
  dla PL i EN. Testy sprawdzają ścieżki, komplet dokumentów w stagingu i BOM UTF-8.
  Znacznik nowego wyboru języka stosuje go raz przy następnym starcie, również
  po reinstalacji tej samej wersji. Testy potwierdzają zachowanie pozostałych
  preferencji i późniejszych zmian języka w aplikacji.
- Zbudowano czysty wheel **0.2.1** w katalogu tymczasowym i sprawdzono wszystkie
  10 dokumentów, katalog tłumaczeń, pomocnik Windows, metadane wersji i MIT.
  Angielski MIT w paczce jest bajtowo zgodny z plikiem LICENSE projektu.
  W zainstalowanej zależności Windows potwierdzono obecność qtbase_pl.qm;
  spec jawnie dołącza go do EXE. Dodano testy języka standardowego okna pliku
  i czytnika dokumentów, ale są tu pominięte razem z pozostałymi testami Qt.
- JEV wskazał wariant znacznika wyboru instalatora. Wymaganie wyboru języka
  podał użytkownik; zachowanie pozostałych preferencji, późniejszych wyborów
  w aplikacji i brak uruchamiania pomocniczej instancji podczas instalacji
  sterownika były priorytetami przyjętymi podczas implementacji.
- Przegląd JEV 14 grup zmian: `escalate`, `safe_to_apply=0.29`, composite
  0.6823. Ocena miała niską pewność i nie wskazała konkretnego defektu.
  Nie ponawiano jej. Niezależne testy logiki i pakowania przeszły;
  natywna kompilacja Inno 0.2.1 oraz renderowanie Qt pozostają niepotwierdzone.

Istniejący instalator i EXE w dist mają nadal wersję **0.2.0**. Aby uwzględnić
poprawki, potrzebny jest pełny `build-installer-windows.cmd` w Windows.
Próba natywna powinna objąć wybór PL i EN przed kreatorem, dokumenty instalatora,
język aplikacji i okna pliku, reinstalację z innym językiem oraz późniejszą zmianę
w ustawieniach. Okna UAC/Windows i oryginalnego instalatora VB-CABLE używają
własnego języka.

## Potwierdzony build Windows 0.2.0 — 12 listopada 2026

- Użytkownik potwierdził powodzenie buildu po poprawce COM.
- Instalator `dist/installer/MusicCastBridge-0.2.0-Setup-x64.exe` istnieje
  i ma 39 904 089 bajtów. Istnieje również aplikacja w `dist/MusicCastBridge`.
- Niezależnie odczytano zasoby PE obu plików: FileVersion i ProductVersion
  wynoszą **0.2.0.0**. Odczyt nie uruchamiał żadnego z plików EXE.
- Wersja w build-info.json to 0.2.0; pole `repository` jest puste zarówno
  w pliku przygotowanym przez build, jak i w dołączonym do aplikacji.
  Kontrola aktualizacji wymaga skonfigurowania repozytorium.
- Udany build nie potwierdza instalacji na innym komputerze, przełączania audio
  podczas odtwarzania ani rzeczywistej odpowiedzi z GitHub Releases. Te próby
  pozostają do wykonania oddzielnie.

## Wersja 0.2.0, GitHub i poprawka COM — 12 listopada 2026

- Log Windows użytkownika: 118 z 119 testów zaliczonych, w tym 15 testów Qt.
  Jedyny błąd pochodził z QueryInterface dla błędnego IID kolekcji urządzeń.
  `IMMDeviceCollection` poprawiono na `0BD7A1BE-7A1A-44DB-8397-CC5392387B5E`
  według [nagłówka Microsoft SDK](https://github.com/microsoft/win32metadata/blob/main/generation/WinSDK/RecompiledIdlHeaders/um/mmdeviceapi.h).
  Dodano przenośny test regresji. Natywny test enumeracji pozostaje w bramce buildu.
- Lokalnie: **134 testy, 115 zaliczonych, 19 pominiętych** — 18 Qt i jeden
  natywny Core Audio. Ruff i compileall przeszły. Sprawdzono numeryczne
  porównywanie wersji, niepoprawne tagi i adresy, brak logowania, offline,
  brak publicznego wydania, limit API i ograniczenie odpowiedzi do 1 MiB.
- Generator wersji tworzy i sprawdza wartości FileVersion/ProductVersion
  z jednego `__version__`. Test wykonuje wygenerowane wyrażenie VSVersionInfo
  z konstruktorami zapisującymi argumenty. Natywny spec po COLLECT odczytuje
  wersję PE z rzeczywistego EXE; starego pakietu nie można przepakować pod nową
  wersją przez `--skip-app-build` bez zgodnych metadanych i zasobu PE.
- GitHub jest ustalany z origin podczas buildu, z odczytem `.git/config`, jeśli
  brakuje `git.exe`. Testy sprawdzają normalizację HTTPS/SSH oraz odrzucanie
  poświadczeń i innych hostów. Sprawdzenie w tle nie uruchamia instalatora;
  strona wydania otwiera się po kliknięciu użytkownika. Uaktualniono prywatność.
- Priorytety sprawdzania przy starcie i korzystania z repozytorium projektu
  wynikają z prośby użytkownika. Wariant powiadomienia i ręcznego otwarcia
  wydania wybrano po ocenie JEV, przy przyjętych podczas implementacji
  priorytetach ciągłości audio i niewykonywania pobranego kodu automatycznie.
- Przegląd JEV: `escalate`, `safe_to_apply=0.38`, composite 0.7371; brak
  konkretnego wskazanego defektu. Niska pewność dotyczyła przede wszystkim
  pokrycia testami. Nie ponawiano tej samej oceny. Niezależne testy logiki
  przeszły, a testów natywnych nie zastępowano atrapą deklarującą sukces.

W tym środowisku `.git` jest pustym, chronionym widokiem, a uruchamianie Windows
przez WSL jest zablokowane. Natywny build został następnie potwierdzony przez
użytkownika, a zasoby wersji odczytano bez uruchamiania EXE — patrz sekcja powyżej.
Nadal nie potwierdzono rzeczywistego adresu remote ani odpowiedzi z repozytorium
wydań na GitHubie.

## MIT, języki i automatyczna trasa Windows — 12 listopada 2026

- Bieżący przebieg: **119 testów, 103 zaliczone, 16 pominiętych**. Pominięto
  15 testów Qt i jeden natywny test odczytu Core Audio. Ruff i compileall przeszły.
- Testy trasy sprawdzają osobne wyjścia console/multimedia, zachowanie wyjścia
  komunikacji, respektowanie ręcznej zmiany, brak celu, częściowy błąd zmiany,
  odłączenie poprzedniego urządzenia, odzyskanie zapisu po restarcie oraz
  wielokrotne anulowanie podczas zmiany systemowej. Testy używają atrap Core Audio.
- Testy sesji potwierdzają przygotowanie trasy przed startem audio i przywrócenie
  po błędzie startu. Test cyklu AirPlay sprawdza wywołanie sprzątania po błędzie
  wykrywania odbiornika.
- Sprawdzono zapis języka i trasy, pierwszy start według języka instalatora bez
  nadpisywania istniejących ustawień, komplet jawnych kluczy tłumaczeń,
  zgodność pól formatowania i separator dziesiętny PL/EN.
- Testy pakowania sprawdzają dołączenie MIT, LGPLv3/GPLv3, dokumentów i wykazu
  zależności. Pełne teksty licencji skopiowano bez zmian z systemowych
  `/usr/share/common-licenses`. Nie zmieniono oryginalnej paczki VB-CABLE.
- Dodatkowo zbudowano czysty wheel Pythona w katalogu tymczasowym i sprawdzono
  `License-Expression: MIT`, katalog tłumaczeń, pomocnik Windows oraz dokumenty
  i teksty licencji w paczce. Nie jest to build EXE Windows.
- Wybór lokalnego pomocnika Core Audio i stosowania języka od następnego startu
  oceniono w JEV. Wymagania funkcji podał użytkownik; priorytety stabilności
  bieżącego strumienia, braku nowej zależności i zachowania ręcznych zmian
  przyjęto podczas implementacji.
- Przegląd JEV 16 plików: `escalate`, `safe_to_apply=0.30`, composite 0.7094.
  Zwrócił niską pewność, w szczególności dla testów i poprawności natywnego
  pomocnika, bez konkretnego opisu defektu. Nie ponawiano tej samej oceny.
  Niezależne testy logiki przeszły; rzeczywisty COM i renderowanie pozostają
  nierozstrzygnięte do próby na Windows.

Wywołanie PowerShell z tego WSL nadal kończy się
`UtilBindVsockAnyPort: socket failed 1`. Nie przebudowano instalatora ani nie
sprawdzono nowego UI, COM, przełączania urządzeń i Inno Setup na Windows.
Późniejszy potwierdzony build 0.2.0 zawiera te zmiany — patrz sekcja powyżej.

Przed wydaniem: zbudować w Windows, sprawdzić oba języki i skalowanie, zmianę
na CABLE Input, stop/wyjście, ręczną zmianę wyjścia podczas grania, odłączenie
urządzenia i odzyskanie po awarii. Przy publicznej dystrybucji wykonać też
[procedurę LGPL](../licenses/README.md), z publikacją odpowiadających źródeł
i sprawdzeniem atrybucji kodu wbudowanego w Qt. Zebrane dokumenty nie są
potwierdzeniem wykonania tych etapów.

## Wcześniejszy zakres weryfikacji

## Sprawdzone lokalnie

- Wcześniejszy przebieg: **100 przypadków, 87 zaliczonych, 13 testów Qt pominiętych**.
  Polecenie: `python3 scripts/check.py --sandbox`.
- Użytkownik uruchomił również testy w Windows: 87 testów logiki przeszło,
  13 testów Qt zgłosiło błąd rozmiaru przy wymuszonym backendzie `offscreen`
  i ostrzeżeniu o braku czcionek. Poprawiono domyślny backend Windows na natywny
  i ustawiono czcionkę jak w aplikacji; natywna powtórka tej poprawki pozostaje
  do wykonania. Kontrola rozmiaru nie została pominięta ani wyłączona.
- Ruff: `check src tests scripts MusicCastBridge.spec` — bez uwag.
- Kompilacja składni Python i demonstracyjne polecenia CLI status/głośność przeszły.
- Testy stdlib obejmują skalę i kroki głośności, aktualny Max Volume, flagi
  niedostępności, odrzucanie nieobsługiwanych źródeł i poleceń odtwarzania.
- Test klienta HTTP sprawdza kod odpowiedzi Yamahy, format parametrów i brak
  automatycznego ponawiania polecenia ze skutkami ubocznymi.
- Testy rzeczywistego bufora PCM sprawdzają nagłówek WAV, ograniczenie kolejki,
  wyrzucanie całych ramek, ciszę oraz odblokowanie czytelnika po zatrzymaniu.
- Testy sesji używają atrap pyatv i transportu. Sprawdzają potwierdzanie zasilania
  i wejścia AirPlay, zachowanie głośności oraz wyciszenia amplitunera, automatyczne
  otwarcie strumienia po potwierdzeniu gotowości, anulowanie przygotowania i zamykanie.
- Testy pomiarów obejmują szczyt/RMS, brak próbek, przerwy w callbackach, dodaną
  ciszę, odstępy nadajnika i brak deklaracji procentowej dostawy.
- Testy retransmisji sprawdzają przejście 65535 → 0, identyczną treść powtórzeń,
  brak pakietu, błąd wysłania, duże żądanie oraz obcy i niepełny datagram.
  Dodatkowa próba z klasą `PacketFifo` ze źródła zainstalowanego pyatv 0.18.0
  potwierdziła cztery powtórzenia przez granicę numeracji bez zmiany zawartości.
- Testy Qt obejmują także wybór kabla bez startu audio i odmowę startu po utracie
  zapamiętanego wyjścia; pozostają pominięte z powodu braku PySide6.
- Testy podglądu transmisji sprawdzają Mb/s i pakiety/s na podstawie rzeczywistego
  czasu, osobne powtórzenia, zmianę sesji/próby, reset liczników, nieaktualne dane,
  zatrzymanie oraz izolację kopii stanu. Test Qt sprawdza aktualizację odczytów
  bez poleceń do amplitunera i zmiany rozmiaru okna; lokalnie jest pominięty.
- Tryb demonstracyjny klienta CLI uruchomiony bez zewnętrznych pakietów.
- Zmiana układu: źródłowo sprawdzono brak kontenera przewijania, stały rozmiar
  oraz wypełnianie pola IP bez wysyłania polecenia połączenia. Testy Qt obejmują
  stały rozmiar, transfer IP, długie napisy i emoji oraz granice obszaru pulpitu;
  w tym środowisku pozostają pominięte z powodu braku PySide6.

## Przegląd źródeł

Niezależny przegląd znalazł wczesne lokalne Playing w pyatv przed RTSP RECORD,
brak anulowania przygotowania oraz brak przycisku Stop amplitunera. Poprawiono te
przypadki i dodano testy. Kolejna uwaga o równoległym dekodowaniu i zamykaniu pliku
została odtworzona, naprawiona blokadą dekodera i potwierdzona testem.
Ostatni werdykt `ship` dotyczy wyłącznie ocenianej poprawki źródłowej.

Przegląd JEV poprawki startu zwrócił `escalate`: `safe_to_apply=0.21`, pewność oceny
poprawności `0.32`. Nie wskazał konkretnego defektu. Niezależnie sprawdzono ścieżkę
głośności w zainstalowanym źródle pyatv 0.18.0 oraz testy startu i sprzątania zasobów.
Wynik JEV nie potwierdza gotowości do wydania; nadal brakuje próby bieżącej zmiany
z rzeczywistymi zależnościami Windows i amplitunerem.

Przegląd JEV diagnostyki i trasy VB-CABLE: `escalate`, `safe_to_apply=0.43`,
pewność oceny poprawności `0.80`. Nie wskazał konkretnego defektu. Testy i próba
z rzeczywistą klasą FIFO sprawdzają logikę; sterownik, routing, Qt i WASAPI
wymagają sprawdzenia w Windows. JEV nie był ponawiany przy niezmienionych danych.

Przegląd podglądu transmisji: JEV `escalate`, `safe_to_apply=0.37`, pewność oceny
poprawności `0.74`. Brak konkretnego wskazanego defektu. Testy obliczeń i istniejące
testy cyklu strumienia przeszły; nowy układ i zegar Qt wymagają próby w Windows.

## Ograniczenia środowiska

Przygotowano źródła zintegrowanego instalatora Inno Setup i skrypt budowania.
Testy obejmują zachowanie plików paczki, kontrolę skrótu wersji, odrzucanie
niebezpiecznych archiwów, kolejność etapów buildu, profil pierwszego startu,
zachowanie istniejących ustawień i zwalnianie znacznika uruchomionej aplikacji.
Sprawdzono rzeczywistą paczkę użytkownika Pack46 (31 plików) oraz nazwę kontrolera
i usługi w INF. Nie uruchomiono instalatora sterownika ani kompilatora Inno Setup.
Szczegóły i próby wymagane na Windows: [installer/README.md](../installer/README.md).

Przegląd JEV końcowych źródeł instalatora zwrócił `escalate`,
`safe_to_apply=0.23`; brak konkretnego wskazanego defektu. Drugą ocenę wykonano
po znalezieniu rzeczywistej paczki, dodaniu jej skrótu i poprawieniu wykrywania
według faktycznego INF. Testy i kontrola kopii paczki przeszły. Nie potwierdzono
działania natywnego instalatora; wynik JEV nie zastępuje tych brakujących prób.

Nie można było pobrać PySide6/pyatv/PyAudioWPatch z PyPI: brak DNS/dostępu sieciowego,
a polityka automatycznie odrzuca rozszerzenie uprawnień. Wywołanie Windows Python
z WSL zwraca `UtilBindVsockAnyPort: socket failed 1`. Wysyłanie przez `socketpair`
również jest zablokowane; lokalne testy asyncio używają jawnego przełącznika
`scripts/check.py --sandbox`, który dodaje okresowy zegar pętli.

Użytkownik potwierdził później stabilny odsłuch z trasą wirtualną. Jego log pokazuje
312 powtórzeń przekazanych do UDP bez błędów, bez dodanej ciszy i odrzuceń.
Aktualny podgląd w głównym oknie wymaga sprawdzenia w Windows.
Lokalnie nie potwierdzono renderowania Qt,
przechwytywania WASAPI, integracji z rzeczywistym pyatv, opóźnienia ani budowy EXE.
Atrapy nie są dowodem kompatybilności sprzętowej.

## Pierwsza próba w Windows

1. Instalacja przez `install-windows.cmd`, następnie `demo-windows.cmd`.
   Sprawdzenie kontrolek, klawiatury, stałego okna bez przewijania, normalnego
   i zwartego układu na różnych DPI oraz zasobnika. „Użyj IP” ma wypełniać
   pole połączenia; sam wybór wyniku nie powinien uruchamiać połączenia.
2. Połączenie z IP amplitunera; porównanie źródeł i głośności z MusicCast.
   Sprawdzenie zmian wykonanych fizycznym pilotem i odzyskania połączenia.
3. Ręczne włączenie/czuwanie przy Network Standby On, wyciszenie i małe zmiany głośności.
4. Test cichego `test.wav` i reakcji na zatrzymanie, zmianę źródła i czuwanie.
5. WASAPI: aktywny dźwięk, cisza, ponowne odtwarzanie, odłączenie wyjścia,
   zatrzymanie podczas łączenia i zamknięcie aplikacji.
6. Sprawdzenie poziomu startowego AirPlay, zachowania wyciszenia i Max Volume,
   pomiar opóźnienia oraz dłuższy odsłuch.
   Dla odsłuchu tylko na Yamasze: instalacja VB-CABLE, routing przeglądarki na
   CABLE Input przy 100%, osobne wyciszenie głośników. Po restarcie aplikacji
   sprawdzenie odtworzenia wyjścia po nazwie; po odłączeniu brak samoczynnego
   przejścia na głośniki. Porównanie poziomu źródła, dodanej ciszy, przerw nadajnika
   i liczników retransmisji z momentami słyszalnych zaników.
7. Build EXE, uruchomienie pakietu na Windows bez środowiska deweloperskiego.

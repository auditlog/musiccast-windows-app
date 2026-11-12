# MusicCast Bridge

Aplikacja na Windows do sterowania Yamahą R-N602 i przesyłania dźwięku komputera
przez AirPlay. Interfejs jest dostępny po polsku i po angielsku. Własny kod
projektu jest udostępniany na [licencji MIT](LICENSE).

Publiczne repozytorium: [musiccast-windows-app](https://github.com/auditlog/musiccast-windows-app).
Pliki z katalogów `build` i `dist` nie są częścią repozytorium.
Gotowy lokalny build opisano poniżej. Stabilne wydanie do pobrania musi zostać
oddzielnie opublikowane w [GitHub Releases](https://github.com/auditlog/musiccast-windows-app/releases).

## Instalator aplikacji

Aktualna wersja źródeł i lokalnego buildu to **0.2.3**. Gotowy instalator
Windows x64 znajduje się w katalogu projektu:

**`dist\installer\MusicCastBridge-0.2.3-Setup-x64.exe`**.

Dla projektu w `C:\code\musiccast` pełna ścieżka to
`C:\code\musiccast\dist\installer\MusicCastBridge-0.2.3-Setup-x64.exe`.
Plik ma około 40 MB. Sprawdzono, że aplikacja i instalator mają w metadanych
Windows **FileVersion 0.2.3.0** i **ProductVersion 0.2.3.0**, a pakiet zawiera
adres aktualizacji `auditlog/musiccast-windows-app`.

Ta wersja zawiera poprawki startu AirPlay i wykrywania wyjść audio, większy bufor
retransmisji oraz pobieranie i uruchamianie aktualizacji w aplikacji.
Po kolejnych zmianach źródeł przebuduj instalator
poleceniem `build-installer-windows.cmd`. Istniejący EXE nie zmienia się po edycji
plików projektu.

1. Uruchom instalator i wybierz **Polski** albo **English** w pierwszym oknie.
   Możesz też skopiować sam instalator na inny komputer.
   Do instalacji i działania aplikacji nie są potrzebne Python ani Inno Setup.
2. Wybierz **Aplikacja i VB-CABLE**, aby móc słuchać tylko na Yamasze, albo
   **Sama aplikacja**, jeśli chcesz korzystać z istniejącego wyjścia audio.
   Brakujący VB-CABLE wymaga zgody administratora i restartu Windows.
   Istniejący sterownik jest zachowywany.
3. Po instalacji i ewentualnym restarcie uruchom **MusicCast Bridge** z menu Start.
   Kliknij **Szukaj → Użyj IP → Połącz**. Trasę przez kabel ustaw według instrukcji
   [YouTube i dźwięk Windows](#youtube-i-dźwięk-windows).

Aplikacja instaluje się domyślnie w `%LOCALAPPDATA%\Programs\MusicCastBridge`.
Instalator zawiera zależności, więc podczas instalacji nie trzeba ich pobierać.
Odinstalowanie aplikacji zachowuje wspólny sterownik VB-CABLE i ustawienia użytkownika.

Od wersji 0.2.1 wybrany język obejmuje interfejs instalatora, wyświetlane w nim
dokumenty i aplikację przy najbliższym uruchomieniu. Ponowna instalacja stosuje
nowy wybór języka raz, zachowując pozostałe ustawienia. Późniejsza zmiana języka
w ustawieniach aplikacji pozostaje zapamiętana do kolejnego wyboru w instalatorze.
Okna Windows, UAC i zewnętrznego instalatora VB-CABLE używają własnego języka.

Aby zbudować nowy instalator, zainstaluj na komputerze budującym Inno Setup 6.3+
i uruchom **`build-installer-windows.cmd`**.
[Instrukcja budowania i zakres weryfikacji](installer/README.md).

## Uruchomienie ze źródeł w Windows

Pobierz kod przez **Code → Download ZIP** na GitHubie albo sklonuj repozytorium:

```powershell
git clone https://github.com/auditlog/musiccast-windows-app.git
cd musiccast-windows-app
```

W pobranym folderze:

1. Potrzebny jest **Python 3.13 lub 3.12 dla Windows x64**. Jeśli masz już 3.13,
   nie musisz instalować 3.12. Instalator sprawdza najpierw `py -3.13`, potem
   `py -3.12`, a następnie `python` z PATH. Zachowuje też istniejące, zgodne środowisko
   `.venv-win`. Jeśli nie masz żadnej z tych wersji, zainstaluj ją z
   [python.org](https://www.python.org/downloads/windows/) z opcją **Python Launcher**
   lub dodaniem Pythona do PATH.
2. Otwórz ten folder w Eksploratorze i uruchom **`install-windows.cmd`**.
   Skrypt pobiera zależności do lokalnego `.venv-win`; nie wymaga instalowania
   sterownika audio ani uprawnień administratora.
3. Uruchom **`start-windows.cmd`**.
4. Kliknij **Szukaj**, wybierz znalezioną Yamahę i kliknij **Użyj IP**, aby wpisać
   jej adres do pola połączenia. Następnie kliknij **Połącz**. Możesz też wpisać
   adres ręcznie — znajdziesz go w **SETUP → Network → Information → IP**.

Okno ma dwie kolumny i stały rozmiar dobierany przy uruchomieniu do czcionki
i skalowania Windows. Główne okno nie ma pasków przewijania. Długie tytuły,
nazwy urządzeń i komunikaty mają pełną treść dostępną po najechaniu kursorem.

Komputer i amplituner powinny być w tej samej sieci lokalnej. Jeśli zapora zapyta
o dostęp aplikacji, zezwól na dostęp w swojej sieci prywatnej. Wyszukiwanie SSDP
i AirPlay mogą nie działać w sieci gościnnej, przez VPN lub przy izolacji klientów.
Połączenie po znanym IP pozwala ominąć problem z samym wyszukiwaniem SSDP.

Do wybudzania przez sieć ustaw na Yamasze **Network → Standby → On**.
Przycisk **Do czuwania** przełącza amplituner w standby.

## Ustawienia / Settings

Przycisk **Ustawienia… / Settings…** otwiera cztery zakładki:

- **Ogólne / General**: język Polski/English i pozostawianie aplikacji przy
  zegarze po zamknięciu okna. Zmiana języka działa od następnego uruchomienia.
  Ustawienia są zapisywane od razu po kliknięciu **Zapisz / Save**.
- **Dźwięk Windows / Windows audio**: opcjonalne automatyczne przełączanie
  domyślnego wyjścia podczas słuchania i wybór docelowego urządzenia.
- **Licencje i zasady / Licenses and terms**: MIT, zasady korzystania,
  prywatność i informacje o bibliotekach oraz VB-CABLE w języku aplikacji.
  Dokumenty są dostępne lokalnie, bez konta i połączenia z internetem.
  Polski widok MIT zawiera pełne tłumaczenie informacyjne; osobna pozycja
  udostępnia angielski oryginał. Oryginalne licencje bibliotek zachowują swoje
  brzmienie i są dostępne przez osobny przycisk.
- **Aktualizacje / Updates**: zainstalowana wersja, sprawdzanie przy starcie,
  źródłowe repozytorium GitHub, ręczne sprawdzenie i otwarcie strony nowego wydania.

Aby słuchać tylko na Yamasze, w zakładce dźwięku włącz **Automatycznie
przełączaj wyjście Windows podczas słuchania**, wybierz **CABLE Input** i zapisz.
Kliknięcie **Słuchaj z komputera / Listen from PC** przełączy domyślne wyjście
Windows, a aplikacja będzie przechwytywać dźwięk z tej trasy. **Zatrzymaj
przesyłanie / Stop streaming**, błąd strumienia lub zakończenie aplikacji
przywróci poprzednie wyjście. Mikrofon i domyślne wyjście rozmów pozostają bez zmian.
Opcja jest domyślnie wyłączona. Zmiany wyjścia wymagają zatrzymania przesyłania.

Automatyczna trasa dotyczy programów używających domyślnego wyjścia Windows.
Jeśli przeglądarka lub Spotify ma osobne przypisanie w mikserze, ustaw tam
**Domyślne / Default** albo **CABLE Input**. Ustaw głośność kabla i odtwarzacza
na 100%, a poziom odsłuchu reguluj Yamahą. Aplikacja nie podnosi samoczynnie
głośności Windows ani amplitunera.

Ręczna zmiana wyjścia Windows podczas słuchania nie zostanie nadpisana przy
zatrzymaniu. Po awarii procesu lub odłączeniu poprzedniego urządzenia użyj
**Przywróć wyjście / Restore output** w ustawieniach albo wybierz wyjście
ręcznie w Windows. Zamknięcie do zasobnika pozostawia przesyłanie i trasę
aktywne; pełne wyjście to **Zakończ / Quit** w menu przy zegarze albo Ctrl+Q.

Po kolejnych zmianach źródeł zbuduj EXE/instalator ponownie, aby je uwzględnić.

Przyciski, podpowiedzi, komunikaty i standardowe okno wyboru pliku używają
języka aplikacji. Nazwy urządzeń, utworów i wejść otrzymane z Yamahy lub Windows
oraz techniczne pola raportu diagnostycznego zachowują oryginalną treść.
Po zmianie dwujęzycznych dokumentów źródłowych odśwież ich zasoby poleceniem
`python scripts/localize_documents.py`. Opcja `--check` sprawdza ich aktualność;
ta zgodność jest też kontrolowana przez testy przed budowaniem instalatora.

## Wersjonowanie i aktualizacje

Numer wersji ma jedno źródło: `__version__` w
[`src/musiccast_bridge/__init__.py`](src/musiccast_bridge/__init__.py).
Pakiet Pythona, EXE i instalator korzystają z tej wartości. Build zapisuje
Windows **FileVersion** i **ProductVersion**, po czym odczytuje je z gotowego
EXE i porównuje z zadeklarowaną wersją. Wersja jest też w tytule okna i w
ustawieniach. Obecna wersja źródeł to **0.2.3**.

Przy starcie program domyślnie sprawdza najnowsze stabilne **GitHub Release**,
w tle i bez przerywania audio. Dostępna aktualizacja zmienia przycisk na
**Nowa wersja!**. Od wersji **0.2.3** w zakładce Aktualizacje kliknij
**Pobierz aktualizację**, a po weryfikacji pliku **Zainstaluj i zamknij aplikację**.
Pobieranie pokazuje postęp i nie przerywa audio. Instalacja zatrzymuje transmisję,
przywraca poprzednie wyjście Windows, zamyka aplikację i otwiera dotychczasowy
instalator ze wskazanym folderem i samą aplikacją (bez ponownej instalacji VB-CABLE).
W ostatnim kroku kreatora możesz ponownie uruchomić aplikację. Ustawienia zostają
zachowane. Funkcja instalacji działa w wersji EXE Windows x64.

Instalator musi mieć nazwę `MusicCastBridge-X.Y.Z-Setup-x64.exe` i rozmiar oraz
`digest` SHA-256 w danych zasobu GitHub Release. Brak tych danych pozostawia
przycisk otwarcia strony wydania. Plik jest pobierany przez HTTPS z GitHuba i jego
serwerów plików; rozmiar i suma są sprawdzane przed udostępnieniem instalacji
oraz ponownie przed uruchomieniem. Błąd pobrania pozwala ponowić próbę.
Sprawdzanie przy starcie można wyłączyć. Brak internetu lub limit GitHuba jest
pokazywany w tej zakładce.

Od **0.2.2** aplikacja ma wbudowane domyślne repozytorium
**`auditlog/musiccast-windows-app`**. Działa ono również przy uruchamianiu
ze źródeł i budowaniu z ZIP-a bez metadanych Git. W ustawieniach puste pole
pokazuje domyślny URL i korzysta z niego bez potrzeby ręcznego wpisywania.

Podczas buildu można wskazać inne repozytorium zmienną
`MUSICCAST_RELEASE_REPOSITORY=auditlog/musiccast-windows-app`.
Bez tej zmiennej build sprawdza `remote.origin.url`, a gdy go nie ma, używa
wbudowanego adresu. Bez `git.exe` na Windows odczyta zwykły `.git/config`.
Repozytorium zapisane w buildzie ma pierwszeństwo przed wbudowanym adresem;
własny adres wpisany w ustawieniach ma pierwszeństwo przed oboma. To pozwala
korzystać z forków i osobnych publicznych repozytoriów wydań. Uruchomienie
aplikacji i sprawdzenie aktualizacji nie wymagają Gita.

W **0.2.0** wpisz ręcznie w **Ustawienia → Aktualizacje → Repozytorium GitHub**:
**`https://github.com/auditlog/musiccast-windows-app`**, kliknij **Zapisz**, a potem
**Sprawdź teraz**. Możesz też podać samo `auditlog/musiccast-windows-app`.
Wskazujesz adres repozytorium; aplikacja sama tworzy adres zapytania API.

Sprawdzanie bez logowania wymaga publicznych wydań. Sam commit, push ani tag
nie zastępują publikacji GitHub Release. Aby udostępnić nową wersję:

1. Uruchom `build-installer-windows.cmd`. Dla bieżącej wersji wynikiem jest
   `dist\installer\MusicCastBridge-0.2.3-Setup-x64.exe`.
2. Opublikuj stabilny, publiczny GitHub Release z tagiem **v0.2.3** i dołącz
   wygenerowany instalator.
3. Przy publicznej dystrybucji dołącz źródła i informacje wymagane przez LGPL
   zgodnie z [instrukcją wydania](licenses/README.md).

Przy kolejnym wydaniu zwiększ najpierw `__version__`, np. do `0.2.4`.
Tag wydania, wersja aplikacji i nazwa instalatora powinny mieć ten sam numer.

Samo sprawdzanie aktualizacji pobiera opis wydania z `api.github.com`. Pobranie
instalatora wymaga kliknięcia. Więcej w [prywatności](PRIVACY.md).

**`demo-windows.cmd`** pokazuje panel z przykładowymi danymi. Tryb demonstracyjny
nie łączy się z fizycznym amplitunerem i nie wysyła dźwięku.

## Co jest zaimplementowane

- Wykrywanie urządzeń w sieci i ręczne połączenie po IP/nazwie.
- Włączanie i czuwanie, głośność, wyciszanie i wybór źródła.
- Źródła i zakres głośności odczytywane z API urządzenia.
- Pokazywanie rzeczywistej głośności w dB, jeśli zwraca ją firmware; w przeciwnym
  razie procent całego zakresu. Przyciski Ciszej/Głośniej używają kroku Yamahy.
- Respektowanie ustawienia Max Volume i chwilowej niedostępności regulacji.
- Odtwarzanie/pauza/stop/poprzedni/następny tylko wtedy, gdy źródło zgłasza obsługę.
- Odświeżanie stanu co dwie sekundy, także po zmianie ustawień pilotem lub MusicCast.
- Przechwytywanie wybranego wyjścia Windows przez WASAPI i nadawanie przez AirPlay.
- Test AirPlay z pliku WAV/FLAC/MP3/OGG, aby oddzielnie sprawdzić połączenie audio.
- Działanie przy zegarze, zatrzymanie dźwięku z menu zasobnika, wyjście przez Ctrl+Q.
- Zapamiętanie adresu amplitunera i ustawienia zamykania okna.

Samo połączenie, wyszukiwanie i odświeżanie nie zmieniają ustawień amplitunera.
Przycisk **Słuchaj z komputera** może go wybudzić i uruchamia nadawanie AirPlay.
Jeśli Yamaha wymaga uwierzytelnienia, wpisz hasło AirPlay lub kod pokazany na
amplitunerze w oknie aplikacji. W Windows aplikacja zapamiętuje zaakceptowane
hasło i wynik parowania dla danego amplitunera w Menedżerze poświadczeń.
AirPlay przełącza źródło podczas zestawiania połączenia. Wybranie innego źródła lub
czuwania w tej aplikacji najpierw zatrzymuje jej strumień.

## YouTube i dźwięk Windows

Włącz film lub muzykę w przeglądarce, a następnie kliknij **Słuchaj z komputera**.
Aplikacja wybudza amplituner, wybiera wejście AirPlay i rozpoczyna odtwarzanie
po potwierdzeniu gotowości. Korzysta z bieżącej głośności i wyciszenia Yamahy.
Przy wybudzaniu obowiązuje poziom startowy skonfigurowany w amplitunerze.
Domyślnie przechwytywane jest bieżące domyślne wyjście Windows. Możesz wybrać inne
po kliknięciu **Odśwież wyjścia**. Zmiana domyślnego wyjścia Windows w trakcie
sesji wymaga zatrzymania i ponownego uruchomienia przesyłania.

To jest kopia dźwięku wyjścia komputera, razem z powiadomieniami odtwarzanymi na
tym wyjściu. Nie ma jeszcze wyboru pojedynczej aplikacji ani karty przeglądarki.
Lokalne głośniki nie są automatycznie wyciszane. Można przekierować dźwięk
przez VB-CABLE, ręcznie albo opcją w ustawieniach. Głośność aplikacji, odtwarzacza
i przechwytywanego wyjścia Windows może wpływać na poziom wysyłanego dźwięku.
Wyciszenie zwykłego wyjścia Windows może wyciszyć również przechwytywany strumień.

Przycisk **Tylko Yamaha…** otwiera ustawienia osobnej trasy dźwięku:

1. Jeśli VB-CABLE nie jest jeszcze zainstalowany, wybierz go w instalatorze
   MusicCast Bridge albo zainstaluj [paczkę producenta](https://vb-audio.com/Cable/)
   jako administrator. Po doinstalowaniu sterownika zrestartuj Windows.
2. W mikserze głośności Windows ustaw wyjście przeglądarki lub Spotify na
   **CABLE Input**. Głośność aplikacji, odtwarzacza i tego wyjścia ustaw na 100%.
3. W oknie **Tylko Yamaha…** odśwież wyjścia i wybierz kabel. Uruchom
   **Słuchaj z komputera** w głównym oknie. Wybór wyjścia jest zapamiętywany po
   nazwie; gdy go zabraknie lub nazwa nie jest jednoznaczna, przesyłanie czeka na
   jawny wybór zamiast przechodzić na głośniki.
4. Głośniki komputera można wyciszyć niezależnie. Muzyka płynie przez kabel,
   a głośność odsłuchu reguluje Yamaha. Pozostaw CABLE aktywny i wyłącz jego
   opcję „Nasłuchuj tego urządzenia”, jeśli jest włączona.

Zintegrowany instalator może doinstalować brakujący sterownik; przy uruchomieniu
ze źródeł można zainstalować go osobno. Aplikacja pomaga wybrać kabel i otworzyć
ustawienia; może też automatycznie przełączać domyślne wyjście Windows.
Indywidualne przypisanie przeglądarki/Spotify do wyjścia wykonuje się w Windows.
Ta trasa zachowuje poziom i dynamikę źródła przy ustawieniu aplikacji na 100%.
Nie stosuje automatycznej normalizacji ani dodatkowego wzmocnienia.

AirPlay wprowadza buforowanie, zwykle około dwóch sekund, do którego dochodzą
bufory programu. **Synchronizacja z obrazem YouTube na PC nie jest zaimplementowana.**
Dokładne opóźnienie trzeba zmierzyć na R-N602. Przechwytywanie chronionych lub
wyłącznych strumieni audio może być niedostępne.

Głośnością i wyciszeniem steruje API Yamahy. Nadajnik AirPlay pomija automatyczne
polecenia głośności biblioteki. Próbki są odblokowywane automatycznie po potwierdzeniu
startu sesji oraz włączonego amplitunera z wybranym wejściem AirPlay. Zmiana głośności
respektuje aktualny Max Volume. Test pliku czeka na gotowość przed odtwarzaniem.

Spotify można nadal odtwarzać bezpośrednio przez Spotify Connect. Wybór źródła
Spotify w tym panelu nie zastępuje wybierania utworów w aplikacji Spotify.

## Wersja EXE

Uruchom **`build-windows.cmd`** w Windows. Skrypt instaluje narzędzie budujące,
wykonuje testy i tworzy **`dist\MusicCastBridge\MusicCastBridge.exe`**.
Kopiuj cały folder `MusicCastBridge`, razem z dołączonymi bibliotekami Qt.
Na docelowym komputerze gotowy pakiet nie wymaga Pythona.

Ten folder jest również tworzony podczas budowania instalatora. Gotowy
`Setup.exe` z sekcji [Instalator aplikacji](#instalator-aplikacji) pozwala
zainstalować aplikację ze skrótami i możliwością odinstalowania.

## Licencja i zasady korzystania

- Własny kod: [MIT](LICENSE). Zależności zachowują swoje licencje.
- [Zasady korzystania / Terms of use](TERMS.md).
- [Prywatność / Privacy](PRIVACY.md): lokalne ustawienia i logi, poświadczenia
  AirPlay w Menedżerze poświadczeń Windows, bez analityki i wysyłania raportów.
- [Składniki zewnętrzne](THIRD_PARTY_NOTICES.md): Qt/PySide6 na LGPLv3 oraz
  opcjonalny VB-CABLE na warunkach VB-Audio Software.
- [Przygotowanie publicznego wydania](licenses/README.md): komplet licencji,
  źródła bibliotek LGPL i informacje o autorach kodu wbudowanego w Qt.

Build dołącza dokumenty i dostępne licencje pakietów. Przed publiczną dystrybucją
trzeba także udostępnić odpowiadające źródła bibliotek LGPL i sprawdzić
atrybucje wbudowanych składników Qt według powyższej instrukcji.

## Diagnostyka i testy

Z terminala Windows, w folderze projektu:

```powershell
.venv-win\Scripts\python.exe -m musiccast_bridge.cli --host 192.168.1.50 status
.venv-win\Scripts\python.exe -m musiccast_bridge.cli tone test.wav
.venv-win\Scripts\python.exe -m musiccast_bridge.cli --host 192.168.1.50 stream test.wav --volume 5
.venv-win\Scripts\python.exe -m unittest discover -s tests -v
```

Pierwsze polecenie tylko odczytuje stan. Drugie tworzy krótki, cichy plik testowy.
Trzecie świadomie uruchamia odtwarzanie przy 5% zakresu amplitunera.
Argument `--volume` jest wymaganym, jawnym wyborem poziomu. Zatrzymasz przez Ctrl+C.

Log: **`%LOCALAPPDATA%\MusicCastBridge\musiccast.log`**, ustawienia w tym samym folderze.
Przycisk **Diagnostyka…** otwiera raport aktualizowany podczas przesyłania.
W głównym oknie sekcja **Transmisja** odświeża się co sekundę. Pokazuje ruch
audio RTP w Mb/s i pakietach/s, osobno powtórzenia, bufor źródła, dodaną ciszę,
błędy powtórzeń oraz najdłuższą przerwę nadajnika. Mb/s obejmują dane RTP;
nagłówki UDP/IP i ruch innych aplikacji nie są wliczane. Wolna przepustowość
łącza pozostaje niezmierzona. Podgląd nie generuje dodatkowego ruchu testowego.
Po ponownym połączeniu zaczyna nowy pomiar; przy braku świeżych danych ukrywa
bieżące prędkości. Szczegółowe znaczenie wartości znajduje się w podpowiedziach.
Raport zawiera etapy i czasy RTSP, kody odpowiedzi, lokalne porty, liczniki
synchronizacji UDP i pakietów audio oraz wyniki prób odzyskania połączenia.
**Kopiuj raport** pozwala przekazać przebieg ostatniej sesji do analizy.

Co pięć sekund `stream_health` pokazuje również:

- `capture_peak_dbfs` i `capture_rms_dbfs`: szczyt i RMS przechwyconych próbek
  od poprzedniego pomiaru; `null` oznacza poziom zerowy lub brak próbek, co
  rozróżnia `capture_samples`. `capture_clipped_samples` liczy próbki na granicy
  zakresu 16 bitów; sam licznik nie dowodzi przesterowania oryginalnego nagrania.
- `capture_max_gap_ms` i `capture_idle_ms`: najdłuższą przerwę między callbackami
  od początku próby i czas od ostatniego callbacku.
- `inserted_silence_ms` / `underflow_reads`: łączną ilość ciszy dodanej przy
  braku danych oraz liczbę takich odczytów, po otwarciu strumienia. Cisza aplikacji
  lub brak aktywnego odtwarzacza również może powodować takie odczyty.
- `max_send_gap_ms` / `send_gaps_over_50ms`: najdłuższy odstęp między wysłaniami
  od początku próby i liczbę odstępów powyżej 50 ms.
- `requested_packets`: liczbę żądanych pakietów, wliczając ponowione prośby.
  `retransmitted_packets` oznacza przekazanie powtórzeń do UDP;
  `retransmit_unavailable` — brak żądanego pakietu w buforze w danym momencie;
  `retransmit_send_errors` — błąd wysłania powtórzenia.
  Od 0.2.3 bufor retransmisji AirPlay 1 przechowuje 4096 pakietów (około 33 s
  przy 44,1 kHz), bez zwiększania opóźnienia odtwarzania.
  `max_retransmit_age_packets` pokazuje największy odstęp żądanej sekwencji
  od ostatniej wysłanej. Pozwala rozpoznać spóźnione żądania; nie potwierdza
  usunięcia strat sieciowych ani odtworzenia pakietów przez Yamahę.
  `retransmitted_bytes` liczy dane przekazane ponownie do UDP, a `buffered_ms`
  podaje przeliczoną długość kolejki źródła.

Nie są to procenty utraconych pakietów ani potwierdzenie odsłuchu. Yamaha nie
potwierdza odbioru i odtworzenia każdej próbki; `delivery_confirmed` pozostaje
`false`. Brak żądań powtórzeń nie dowodzi pełnej dostawy. Obsługa retransmisji
uwzględnia przejście numeracji 65535 → 0 i zachowuje oryginalną treść pakietów.

Po błędzie sieciowym aplikacja podejmuje do dwóch ponownych prób po 2 i 4 sekundach.
Po timeoutcie `RECORD` lub `/info` próbuje uproszczonego startu AirPlay 1.
Każda ponowna próba potwierdza gotowość amplitunera i korzysta z jego aktualnej
głośności. Po odzyskaniu połączenia dźwięk jest odblokowywany automatycznie.
**Zatrzymaj przesyłanie** anuluje również oczekującą ponowną próbę.
Przechwycony dźwięk nie jest zapisywany na dysku. Program nie uruchamia publicznego
serwera ani nie wymaga konta w usłudze pośredniczącej.

Testy bez zależności GUI: `PYTHONPATH=src python3 -m unittest discover -s tests -v`.
W sandboxie, który blokuje wysyłanie przez lokalne gniazdo wybudzające asyncio:
`python3 scripts/check.py --sandbox`. Ten przełącznik dodaje wyłącznie okresowe
wybudzenie pętli testowej; nie odblokowuje sieci.

Stan sprawdzeń i plan próby na urządzeniu: [docs/VALIDATION.md](docs/VALIDATION.md).

## Technologia

Python 3.12/3.13, PySide6/Qt Widgets, Yamaha Extended Control API przez HTTP,
PyAudioWPatch/WASAPI, pyatv/RAOP. Nie ma własnego sterownika jądra Windows.

- [API Yamahy — dokument producenta w kopii PDF](https://manuals.plus/m/88274905cc7408510f59bfb64641f911363f689dfa454f3dd9100a1dc141681e.pdf)
- [Instrukcja R-N602](https://data.yamaha.com/files/download/other_assets/6/793536/web_ZS22650-1_R-N602_om_U_EnFr.pdf)
- [pyatv: przesyłanie audio](https://pyatv.dev/development/stream/)
- [PyAudioWPatch](https://github.com/s0d3s/PyAudioWPatch)

Biblioteki zachowują własne licencje, dołączane przy pakowaniu. Projekt nie jest
oficjalnym produktem Yamahy.

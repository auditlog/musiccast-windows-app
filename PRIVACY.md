# MusicCast Bridge — prywatność / privacy

## Polski

Aplikacja nie ma kont użytkownika, analityki ani automatycznego wysyłania
raportów do twórców. Wyszukiwanie urządzeń, sterowanie i przesyłanie dźwięku
korzystają z sieci lokalnej. Dane audio są przechwytywane w pamięci i wysyłane
do wybranego odbiornika; aplikacja nie zapisuje nagrań na dysku.

Sprawdzanie aktualizacji, domyślnie włączone przy starcie, łączy się przez HTTPS
z `api.github.com` i pobiera opis najnowszego stabilnego wydania ze wskazanego
repozytorium. GitHub otrzymuje adres IP oraz wersję aplikacji w nagłówku
User-Agent. Zapytanie nie zawiera dźwięku, adresu Yamahy, poświadczeń AirPlay
ani raportu diagnostycznego. Sprawdzanie można wyłączyć w Ustawieniach →
Aktualizacje. Ręczne sprawdzenie wykonuje to samo zapytanie.

Ustawienia, logi oraz zapis poprzedniej trasy audio są przechowywane lokalnie
w `%LOCALAPPDATA%\MusicCastBridge`. Zapis obejmuje język, adres amplitunera,
nazwę/identyfikator wyjścia dźwięku i preferencje. Hasła AirPlay i dane parowania
trafiają do Menedżera poświadczeń Windows, nie do pliku ustawień ani raportu.
Logi mogą zawierać adresy IP, nazwy urządzeń, czasy połączeń i liczniki błędów.
Przed ręcznym udostępnieniem raportu sprawdź jego treść.
Ustawienia obejmują również adres repozytorium aktualizacji, wybór sprawdzania
przy starcie oraz znacznik ostatniego wyboru języka w instalatorze. Adres źródłowego repozytorium jest także zapisywany w pakiecie EXE;
nie są dołączane hasła ani tokeny GitHuba z konfiguracji Gita.

Otwarcie odsyłacza do producenta lub innej strony uruchamia przeglądarkę i
podlega zasadom tej witryny. Budowanie instalatora może pobierać zależności
i paczkę VB-CABLE; gotowy instalator zawiera te pliki. Osobno uruchamiany
instalator VB-CABLE podlega warunkom producenta.

Odinstalowanie zachowuje ustawienia, logi, poświadczenia oraz wspólny sterownik
VB-CABLE. Aby usunąć dane aplikacji, zakończ ją, przywróć wyjście Windows,
usuń katalog `%LOCALAPPDATA%\MusicCastBridge` i odpowiednie wpisy MusicCast
Bridge w Menedżerze poświadczeń Windows. Nie usuwaj sterownika, jeśli używa
go inne oprogramowanie.

## English

The application has no user accounts, analytics, or automatic report uploads.
Discovery, receiver control, and audio streaming use the local network. Audio
is captured in memory and sent to the selected receiver; recordings are not
saved to disk.

Update checks, enabled at startup by default, use HTTPS to `api.github.com`
to read the selected repository's latest stable release. GitHub receives your
IP address and the application version in the User-Agent header. Requests do
not include audio, your Yamaha's address, AirPlay credentials, or diagnostics.
Disable startup checks in Settings → Updates. Manual checks make the same request.

Settings, logs, and the previous audio-route journal are stored locally in
`%LOCALAPPDATA%\MusicCastBridge`. They include language, receiver address,
audio device name/identifier, and preferences. AirPlay passwords and pairing
data are stored in Windows Credential Manager, not in settings or diagnostics.
Logs may contain IP addresses, device names, connection times, and error
counters. Review reports before sharing them manually.
Settings also include the update repository, startup-check preference, and
a marker for the last language selection in the installer. The
repository address is embedded in built applications; GitHub passwords and
tokens from Git configuration are not included.

External links open your browser and are subject to the destination site's
policies. Building an installer may download dependencies and VB-CABLE; the
finished installer includes these files. The separate VB-CABLE installer is
subject to its vendor's terms.

Uninstalling preserves settings, logs, credentials, and the shared VB-CABLE
driver. To remove application data, quit, restore your Windows playback output,
delete `%LOCALAPPDATA%\MusicCastBridge`, and remove the MusicCast Bridge entries
from Windows Credential Manager. Keep the shared driver if other software
uses it.

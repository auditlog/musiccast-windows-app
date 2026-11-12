Prywatność

Aplikacja nie ma kont użytkownika, analityki ani automatycznego wysyłania
raportów do twórców. Wyszukiwanie urządzeń, sterowanie i przesyłanie dźwięku
korzystają z sieci lokalnej. Dane audio są przechwytywane w pamięci i wysyłane
do wybranego odbiornika; aplikacja nie zapisuje nagrań na dysku.

Sprawdzanie aktualizacji, domyślnie włączone przy starcie, łączy się przez HTTPS
z api.github.com i pobiera opis najnowszego stabilnego wydania ze wskazanego
repozytorium. GitHub otrzymuje adres IP oraz wersję aplikacji w nagłówku
User-Agent. Zapytanie nie zawiera dźwięku, adresu Yamahy, poświadczeń AirPlay
ani raportu diagnostycznego. Sprawdzanie można wyłączyć w Ustawieniach →
Aktualizacje. Ręczne sprawdzenie wykonuje to samo zapytanie.

Kliknięcie „Pobierz aktualizację” pobiera instalator przez HTTPS z GitHuba i jego
serwerów plików (release-assets.githubusercontent.com lub objects.githubusercontent.com).
GitHub otrzymuje adres IP i wersję aplikacji. Plik trafia do podkatalogu updates
w lokalnych danych aplikacji. Przed uruchomieniem aplikacja sprawdza rozmiar
i SHA-256 z opisu wydania. Instalacja wymaga osobnego kliknięcia, zamyka aplikację
i uruchamia jej instalator. Pobieranie i instalacja nie są wykonywane w tle automatycznie.

Ustawienia, logi oraz zapis poprzedniej trasy audio są przechowywane lokalnie
w %LOCALAPPDATA%\MusicCastBridge. Zapis obejmuje język, adres amplitunera,
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
usuń katalog %LOCALAPPDATA%\MusicCastBridge i odpowiednie wpisy MusicCast
Bridge w Menedżerze poświadczeń Windows. Nie usuwaj sterownika, jeśli używa
go inne oprogramowanie.

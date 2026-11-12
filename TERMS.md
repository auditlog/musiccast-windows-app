# MusicCast Bridge — zasady korzystania / terms of use

## Polski

Własny kod MusicCast Bridge jest udostępniany na licencji MIT, opisanej w pliku
LICENSE. Można go używać, zmieniać i rozpowszechniać, także komercyjnie, z
zachowaniem wymaganych informacji o autorach i licencji. Niniejsze objaśnienia
nie ograniczają praw przyznanych przez MIT ani licencje składników zewnętrznych.

Program może sprawdzać nowe stabilne wydania na GitHubie przy starcie; tę opcję
można wyłączyć w ustawieniach. Po otrzymaniu informacji o aktualizacji użytkownik
otwiera stronę wydania, pobiera instalator i uruchamia go po zakończeniu aplikacji.

Program steruje wskazanym amplitunerem w sieci lokalnej. Przycisk rozpoczęcia
przesyłania może go wybudzić i przełączyć na AirPlay. Użytkownik wybiera wyjście
Windows do przechwytywania. Dźwięki innych aplikacji i powiadomień kierowane na
to wyjście również mogą trafić do amplitunera. AirPlay wprowadza opóźnienie;
aplikacja nie zapewnia synchronizacji obrazu na komputerze z dźwiękiem.

Automatyczna zmiana domyślnego wyjścia Windows jest opcją w ustawieniach,
domyślnie wyłączoną. Dotyczy wyjścia zwykłych aplikacji i multimediów, bez
zmiany mikrofonu i domyślnego wyjścia rozmów. Aplikacje mające własne przypisanie
w mikserze Windows mogą wymagać ręcznego wyboru „Domyślne” albo CABLE Input.
Zatrzymanie przesyłania, jego błąd lub zakończenie aplikacji powoduje próbę
przywrócenia poprzedniego wyjścia. Późniejsza ręczna zmiana użytkownika jest
zachowywana. Po awarii procesu lub odłączeniu urządzenia może być potrzebny
przycisk „Przywróć wyjście” w ustawieniach albo ręczna zmiana w Windows.
Zamknięcie do zasobnika pozostawia aplikację i przesyłanie uruchomione.

Program jest dostarczany na warunkach braku gwarancji i ograniczenia
odpowiedzialności opisanych w MIT, w zakresie dopuszczalnym przez obowiązujące
prawo. Postanowienia te nie wyłączają bezwzględnie obowiązujących praw użytkownika.
Szczegóły składników zewnętrznych są w THIRD_PARTY_NOTICES.md. VB-CABLE jest
odrębnym produktem VB-Audio Software, udostępnianym jako donationware, i nie
staje się oprogramowaniem MIT przez dołączenie do instalatora.

## English

MusicCast Bridge's own code is provided under the MIT license in LICENSE.
Use, modification, and redistribution, including commercial use, are permitted
subject to its copyright and license notice requirements. These explanations
do not restrict rights granted by MIT or third-party licenses.

The program can check GitHub for stable releases at startup; this can be disabled
in settings. After an update notification, the user opens the release page,
downloads the installer, and runs it after quitting the application.

The program controls the selected receiver on the local network. Starting a
stream may wake it and select AirPlay. You choose the Windows playback output
to capture. Other applications and notifications using that output may also
be sent to the receiver. AirPlay introduces latency; synchronization with
video on the computer is not provided.

Automatic Windows default-output switching is optional and disabled by default.
It changes console and multimedia playback defaults, leaving the microphone
and communications default unchanged. Applications with their own output
assignment in the Windows mixer may need to be set to Default or CABLE Input.
Stopping, stream failure, or quitting attempts to restore the previous output.
A subsequent manual output change is respected. After a process crash or a
device disconnection, use Restore output in settings or select the output in
Windows. Closing to the tray keeps the application and stream running.

The MIT warranty disclaimer and liability limitation apply to the extent
permitted by law; mandatory statutory user rights are unaffected. See
THIRD_PARTY_NOTICES.md for dependencies. VB-CABLE is a separate VB-Audio Software
donationware product and is not relicensed under MIT by this installer.

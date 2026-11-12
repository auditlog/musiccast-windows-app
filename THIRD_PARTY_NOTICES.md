# MusicCast Bridge — składniki zewnętrzne / third-party components

## Polski

MIT dotyczy własnego kodu i dokumentacji MusicCast Bridge. Zależności zachowują
własne prawa autorskie i licencje. To niezależny projekt, nie oficjalny produkt
Yamahy ani VB-Audio.

### Qt / Qt for Python (PySide6 i Shiboken), 6.8.3

Prawa autorskie: The Qt Company Ltd. i pozostali współtwórcy.
Biblioteki społecznościowe są używane na LGPL w wersji 3, bez zmian.
Oryginalne teksty LGPLv3 i GPLv3 są dołączone do katalogu licenses, a dostępne
licencje zależności do third-party-licenses w pakiecie Windows. Plik INDEX.txt
zawiera ich wykaz. Oryginały zachowują język autorów.

Aplikacja używa współdzielonych bibliotek DLL Qt. Możesz zastąpić je zmodyfikowanymi,
zgodnymi wersjami oraz analizować aplikację w zakresie potrzebnym do debugowania
zmian w tych bibliotekach. Aplikacja nie ogranicza tych uprawnień LGPL. Zachowaj
cały katalog aplikacji; nie usuwaj i nie blokuj jej bibliotek współdzielonych.

Źródła odpowiednich wersji bibliotek i instrukcja budowania:

- Qt 6.8.3: https://download.qt.io/archive/qt/6.8/6.8.3/single/
- PySide6/Shiboken 6.8.3: https://download.qt.io/official_releases/QtForPython/pyside6/PySide6-6.8.3-src/
- Budowanie: https://doc.qt.io/qtforpython-6.8/building_from_source/index.html
- Obowiązki licencyjne: https://www.qt.io/development/open-source-lgpl-obligations

Przy publikowaniu wydania udostępnij odpowiadające źródła bibliotek obok pliku
instalatora albo spełnij inną właściwą opcję udostępniania źródeł LGPLv3/GPLv3.
Same odsyłacze do producenta nie są pisemną ofertą dystrybutora. Procedura wydania
i zakres weryfikacji są opisane w licenses/README.md.

### Pozostałe zależności

- pyatv: MIT; https://github.com/postlund/pyatv
- PyAudioWPatch: Apache-2.0; https://github.com/s0d3s/PyAudioWPatch
- PortAudio, dołączone do PyAudioWPatch: licencja typu MIT; http://www.portaudio.com/
- Python: licencja Python Software Foundation; https://www.python.org/psf/license/
- PyInstaller: GPL z wyjątkiem pozwalającym rozpowszechniać wygenerowaną aplikację
  na jej własnej licencji; https://pyinstaller.org/en/stable/license.html

Zależności pośrednie zachowują własne licencje. Ich dostępne teksty i informacje
z metadanych środowiska budowania znajdują się w third-party-licenses i pliku
DEPENDENCIES.json. Ten wykaz nie zmienia licencji tych składników na MIT.

### VB-CABLE — opcjonalna, niezmieniona paczka producenta

Prawa autorskie: VB-Audio Software / Vincent Burel.
Źródło: https://www.vb-cable.com/
Produkt: https://vb-audio.com/Cable/
Warunki, darowizny i zakup licencji: https://vb-audio.com/Services/licensing.htm

VB-CABLE jest udostępniany jako donationware. Jeśli jest przydatny, możesz
wesprzeć jego autorów darowizną lub zakupem licencji. Użycie i wdrożenia
profesjonalne podlegają warunkom producenta i mogą wymagać zakupu licencji.
Standardowa paczka jest dołączona bez zmian; kable A+B i C+D nie są dołączane.
Oryginalne pliki i informacje producenta są zachowane, a sterownik instaluje
oryginalny instalator VB-Audio. Odinstalowanie MusicCast Bridge pozostawia
wspólny sterownik VB-CABLE.

## English

MIT applies to MusicCast Bridge's own code and documentation. Dependencies
retain their original copyrights and licenses. This is an independent project,
not an official Yamaha or VB-Audio product.

### Qt / Qt for Python (PySide6 and Shiboken), 6.8.3

Copyright The Qt Company Ltd. and other contributors.
The community libraries are used under LGPL version 3, without modification.
Original LGPLv3 and GPLv3 texts are included in licenses. Available dependency
licenses are copied to third-party-licenses in the Windows app bundle, with an
INDEX.txt file. Original license texts retain their authors' language.

The application uses shared Qt DLLs. You may replace them with interface-compatible
modified versions and reverse engineer the application as needed to debug your
modifications to those libraries. The application imposes no restriction on these
LGPL rights. Keep the complete application directory; do not remove or lock its
shared libraries.

Corresponding upstream source and build instructions:

- Qt 6.8.3: https://download.qt.io/archive/qt/6.8/6.8.3/single/
- PySide6/Shiboken 6.8.3: https://download.qt.io/official_releases/QtForPython/pyside6/PySide6-6.8.3-src/
- Build: https://doc.qt.io/qtforpython-6.8/building_from_source/index.html
- License obligations: https://www.qt.io/development/open-source-lgpl-obligations

Release distributors must provide the corresponding library sources alongside
the binary download, or fulfill another applicable source-distribution option
under LGPLv3/GPLv3. Upstream links alone are not a distributor's written source
offer. See licenses/README.md for the release procedure and verification limits.

### Other dependencies

- pyatv: MIT; https://github.com/postlund/pyatv
- PyAudioWPatch: Apache-2.0; https://github.com/s0d3s/PyAudioWPatch
- PortAudio, inside PyAudioWPatch: MIT-style license; http://www.portaudio.com/
- Python: Python Software Foundation license; https://www.python.org/psf/license/
- PyInstaller: GPL with its application-bundling exception, permitting distribution
  of the generated application under its own license;
  https://pyinstaller.org/en/stable/license.html

Transitive dependencies retain their own licenses. Available texts and build
environment metadata are in third-party-licenses and DEPENDENCIES.json. This
inventory does not relicense those components under MIT.

### VB-CABLE — optional, unmodified vendor package

Copyright VB-Audio Software / Vincent Burel.
Origin: https://www.vb-cable.com/
Product: https://vb-audio.com/Cable/
Terms, donation, and license purchase: https://vb-audio.com/Services/licensing.htm

VB-CABLE is donationware. If useful, support its authors by donating or purchasing
a license. Professional use and deployments are subject to the vendor's terms
and may require licenses. The standard package is bundled unchanged; additional
cables A+B and C+D are not included. Original vendor files and notices are
preserved, and the vendor's own installer installs the driver. Uninstalling
MusicCast Bridge leaves the shared VB-CABLE driver installed.

# Release licensing / licencje wydania

MusicCast Bridge's own code: ../LICENSE (MIT).
The complete, unchanged LGPLv3, GPLv3 and Apache-2.0 texts are included here.
These are license documents, not a relicensing of this application under GPL.

## Before publishing a Windows binary

1. Build normally with `build-installer-windows.cmd`. It runs the tests and
   collects dependency notices, version/license metadata, the project's MIT
   license, terms, privacy information and the vendor's VB-CABLE notice.
   `build-windows.cmd` also collects these notices for the portable app.
2. Keep the complete `third-party-licenses` directory. Review its INDEX.txt and
   DEPENDENCIES.json against the bundled DLLs and Python distributions. Metadata
   may describe a choice of licenses; this project uses Qt/PySide6/Shiboken
   under LGPLv3. A copied commercial-license template does not grant a commercial
   Qt license.
3. For the pinned Qt/PySide6 6.8.3 dependencies, obtain and retain the corresponding
   source archives from the upstream locations below, including their notices:
   - https://download.qt.io/archive/qt/6.8/6.8.3/single/qt-everywhere-src-6.8.3.tar.xz
   - https://download.qt.io/official_releases/QtForPython/pyside6/PySide6-6.8.3-src/pyside-setup-everywhere-src-6.8.3.tar.xz
   These downloads total roughly 1 GB. They are separate release artifacts, not
   silently downloaded during a normal application build.
4. Publish those sources at the same download location as the binary, with
   equivalent access, and direct users to them from the release description.
   Keep them available for that version. Include the application's source and
   build scripts as well. If distributing offline, distribute the sources
   alongside it or meet another applicable GPLv3/LGPLv3 source-delivery option.
5. Qt embeds additional third-party code. Include the attribution notices
   corresponding to the shipped Qt modules/plugins and verify any non-LGPL
   runtime DLL redistribution terms. Inspect the source archive's LICENSES,
   REUSE metadata and module attribution files; a list of Python distribution
   metadata alone does not cover these embedded components.
6. Keep Qt as replaceable shared DLLs. Do not add signature checks or terms that
   prohibit replacing interface-compatible Qt libraries or debugging those
   modifications. Check the resulting app after a compatible library swap.

Upstream build instructions:
https://doc.qt.io/qtforpython-6.8/building_from_source/index.html

The build collects known notices; it does not certify every release's legal
compliance. This development environment cannot download the Qt source archives
or run the Windows installer. The source publication, embedded Qt attributions,
and a native library-replacement test must be verified for a public release.

## Polski

Plik LICENSE w katalogu projektu zawiera MIT dla własnego kodu. LGPL/GPL/Apache
w tym katalogu dotyczą odpowiednich zależności. Budowanie dołącza dokumenty
i dostępne licencje pakietów, lecz nie zastępuje sprawdzenia wydania.

Przed publicznym udostępnieniem instalatora pobierz źródła odpowiadające
bibliotekom Qt/PySide6/Shiboken 6.8.3 z powyższych adresów i opublikuj je obok
pliku EXE, z równoważnym dostępem. Dołącz też kod aplikacji i skrypty budowania.
Źródła Qt mają około 1 GB; nie są automatycznie pobierane ani wkładane do
instalatora. Sprawdź dodatkowe informacje o autorach kodu wbudowanego w Qt
i warunki dołączanych bibliotek DLL. Same linki do serwera Qt ani sam zbiór
metadanych Pythona nie wystarczają do potwierdzenia wszystkich obowiązków.

Zachowaj możliwość podmiany zgodnych bibliotek DLL i sprawdź działanie na Windows.
VB-CABLE zachowuje osobne warunki producenta opisane w THIRD_PARTY_NOTICES.md.

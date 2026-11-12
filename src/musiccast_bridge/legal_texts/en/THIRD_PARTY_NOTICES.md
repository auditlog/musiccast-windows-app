Third-party components

MIT applies to MusicCast Bridge's own code and documentation. Dependencies
retain their original copyrights and licenses. This is an independent project,
not an official Yamaha or VB-Audio product.

Qt / Qt for Python (PySide6 and Shiboken), 6.8.3

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

Other dependencies

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

VB-CABLE — optional, unmodified vendor package

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

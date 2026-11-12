# Build on Windows with: python -m PyInstaller --clean MusicCastBridge.spec
# ruff: noqa: F821
# Analysis/PYZ/EXE/COLLECT are provided by the PyInstaller spec interpreter.
import json
import runpy
from importlib.util import find_spec
from pathlib import Path

from PyInstaller.utils.hooks import collect_all, copy_metadata

version_tools = runpy.run_path(str(Path(SPECPATH) / "scripts/version_info.py"))
version_file, build_info = version_tools["prepare_version_info"](SPECPATH)
qt_polish = Path(find_spec("PySide6").origin).parent / "translations/qtbase_pl.qm"
if not qt_polish.is_file():
    raise FileNotFoundError("Missing Qt Polish translations: qtbase_pl.qm")

datas, binaries, hiddenimports = [], [], []
for package in ("pyatv", "pyaudiowpatch", "miniaudio"):
    package_datas, package_binaries, package_hidden = collect_all(package)
    datas += package_datas
    binaries += package_binaries
    hiddenimports += package_hidden
datas += copy_metadata("pyatv", recursive=True)
datas += [
    (str(qt_polish), "musiccast_bridge/qt_translations"),
    ("src/musiccast_bridge/legal_texts", "musiccast_bridge/legal_texts"),
    (str(build_info), "musiccast_bridge"),
    ("src/musiccast_bridge/en.json", "musiccast_bridge"),
    ("src/musiccast_bridge/windows_output.ps1", "musiccast_bridge"),
    ("src/musiccast_bridge/update_installer.ps1", "musiccast_bridge"),
    ("LICENSE", "legal"),
    ("TERMS.md", "legal"),
    ("PRIVACY.md", "legal"),
    ("THIRD_PARTY_NOTICES.md", "legal"),
    ("licenses", "legal/licenses"),
]

analysis = Analysis(
    ["scripts/desktop-entry.py"],
    pathex=["src"],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["PySide6.QtQml", "PySide6.QtQuick", "tkinter"],
    noarchive=False,
)
pyz = PYZ(analysis.pure)
exe = EXE(
    pyz,
    analysis.scripts,
    [],
    exclude_binaries=True,
    name="MusicCastBridge",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    version=str(version_file),
)
collection = COLLECT(
    exe, analysis.binaries, analysis.datas, strip=False, upx=False, name="MusicCastBridge"
)
version_tools["verify_exe_version"](
    Path(DISTPATH) / "MusicCastBridge/MusicCastBridge.exe",
    json.loads(build_info.read_text(encoding="utf-8"))["version"],
)

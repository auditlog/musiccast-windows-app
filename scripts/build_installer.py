"""Build the Windows app and an offline Setup.exe with the standard VB-CABLE package."""

import argparse
import os
import platform
import runpy
import shutil
import struct
import subprocess
import sys
from pathlib import Path

from installer_tools import PackageError, collect_licenses, download_cable, prepare_installer

ROOT = Path(__file__).resolve().parent.parent


def find_compiler():
    explicit = os.environ.get("ISCC_EXE")
    if explicit:
        if Path(explicit).is_file():
            return explicit
        raise PackageError("ISCC_EXE wskazuje nieistniejący plik kompilatora.")
    found = shutil.which("ISCC.exe")
    if found:
        return found
    for variable, suffix in (
        ("LOCALAPPDATA", "Programs"),
        ("ProgramFiles(x86)", ""),
        ("ProgramFiles", ""),
    ):
        base = os.environ.get(variable)
        if base:
            for major in (7, 6):
                candidate = Path(base) / suffix / f"Inno Setup {major}" / "ISCC.exe"
                if candidate.is_file():
                    return str(candidate)
    raise PackageError(
        "Zainstaluj Inno Setup 6.3 lub nowszy: https://jrsoftware.org/isdl.php. "
        "Możesz też ustawić ISCC_EXE na pełną ścieżkę ISCC.exe."
    )


def run(command):
    subprocess.run(command, cwd=ROOT, check=True)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--vbcable-zip", type=Path, help="Lokalna oryginalna paczka standardowego VB-CABLE"
    )
    parser.add_argument(
        "--skip-app-build", action="store_true", help="Użyj istniejącego folderu dist"
    )
    args = parser.parse_args(argv)
    try:
        if sys.platform != "win32" or struct.calcsize("P") != 8 or platform.machine() != "AMD64":
            raise PackageError("Budowanie wymaga Pythona Windows x64 na systemie Windows x64.")
        compiler = find_compiler()
        if args.skip_app_build:
            readers = runpy.run_path(str(Path(__file__).resolve().parent.parent /
                                        "src/musiccast_bridge/versioning.py"))
            version_tools = runpy.run_path(str(Path(__file__).with_name("version_info.py")))
            version_tools["verify_existing_bundle"](
                ROOT / "dist/MusicCastBridge", readers["project_version"](ROOT))
        if not args.skip_app_build:
            run([sys.executable, "-m", "pip", "install", "-e", ".[build]"])
            run([sys.executable, "-m", "unittest", "discover", "-s", "tests", "-v"])
        powershell = Path(os.environ.get("SystemRoot", r"C:\Windows")) / (
            "System32/WindowsPowerShell/v1.0/powershell.exe"
        )
        run(
            [
                str(powershell),
                "-NoProfile",
                "-NonInteractive",
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                str(ROOT / "installer" / "test-detection.ps1"),
            ]
        )
        if not args.skip_app_build:
            run(
                [
                    sys.executable,
                    "-m",
                    "PyInstaller",
                    "--noconfirm",
                    "--clean",
                    "MusicCastBridge.spec",
                ]
            )
        collect_licenses(ROOT / "dist" / "MusicCastBridge")
        archive = (
            args.vbcable_zip.resolve()
            if args.vbcable_zip
            else ROOT / "build" / "VBCABLE_Driver_Pack46.zip"
        )
        if not args.vbcable_zip and not archive.is_file():
            archive.parent.mkdir(parents=True, exist_ok=True)
            download_cable(archive)
        version = prepare_installer(ROOT, archive)
        run([compiler, "/Qp", str(ROOT / "installer" / "MusicCastBridge.iss")])
        artifact = ROOT / "dist" / "installer" / f"MusicCastBridge-{version}-Setup-x64.exe"
        if not artifact.is_file():
            raise PackageError("Kompilator nie utworzył oczekiwanego pliku instalatora.")
        print(f"Gotowe: {artifact}")
        return 0
    except (PackageError, OSError, ValueError, subprocess.CalledProcessError) as error:
        print(f"Nie udało się zbudować instalatora: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

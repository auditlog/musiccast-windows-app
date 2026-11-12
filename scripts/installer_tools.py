"""Stage the original standard VB-CABLE package for an offline Inno Setup build."""

import hashlib
import importlib.metadata
import json
import re
import runpy
import shutil
import stat
import sys
import tempfile
import urllib.parse
import urllib.request
import zipfile
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath

CABLE_URL = "https://download.vb-audio.com/Download_CABLE/VBCABLE_Driver_Pack46.zip"
CABLE_SHA256 = "bc44e8974191a5a2427d6c979e2dab08dbb09925f3f435dfa2f0ba3e45b6eb90"
MAX_DOWNLOAD = 64 * 1024 * 1024
MAX_EXPANDED = 256 * 1024 * 1024
MAX_FILES = 500


class PackageError(Exception):
    pass


def collect_licenses(app_directory):
    """Copy available installed dependency license texts into the distributable."""
    target = Path(app_directory) / "third-party-licenses"
    target.mkdir(parents=True, exist_ok=True)
    copied = []
    inventory = []
    for distribution in importlib.metadata.distributions():
        name = re.sub(r"[^a-zA-Z0-9_.-]", "_", distribution.metadata.get("Name", "unknown"))
        inventory.append(
            {
                "name": name,
                "version": distribution.metadata.get("Version", "unknown"),
                "license": distribution.metadata.get("License-Expression")
                or distribution.metadata.get("License", "See license files"),
            }
        )
        for entry in distribution.files or ():
            relative = Path(str(entry))
            if (
                relative.is_absolute()
                or ".." in relative.parts
                or not any(part.endswith(".dist-info") for part in relative.parts)
                or not relative.name.casefold().startswith(
                    ("license", "copying", "notice", "copyright")
                )
            ):
                continue
            source = Path(distribution.locate_file(entry))
            if source.is_file():
                destination = target / name / relative
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(source, destination)
                copied.append(str(destination.relative_to(target)))
    project = Path(__file__).resolve().parent.parent
    for source in (
        project / "LICENSE",
        project / "TERMS.md",
        project / "PRIVACY.md",
        project / "THIRD_PARTY_NOTICES.md",
    ):
        shutil.copyfile(source, Path(app_directory) / source.name)
    for source in (project / "licenses").rglob("*"):
        if source.is_file():
            destination = target / source.relative_to(project / "licenses")
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, destination)
            copied.append(str(destination.relative_to(target)))
    python_license = Path(sys.base_prefix) / "LICENSE.txt"
    if python_license.is_file():
        destination = target / "Python-LICENSE.txt"
        shutil.copyfile(python_license, destination)
        copied.append(destination.name)
    (target / "INDEX.txt").write_text("\n".join(sorted(copied)) + "\n", encoding="utf-8")
    (target / "DEPENDENCIES.json").write_text(
        json.dumps(sorted(inventory, key=lambda item: item["name"]), ensure_ascii=False, indent=2)
        + "\n",
        encoding="utf-8",
    )


def download_cable(target):
    """Download a fixed vendor release; never execute it on the build machine."""
    target = Path(target)
    try:
        with urllib.request.urlopen(CABLE_URL, timeout=60) as response, target.open("wb") as output:
            final = urllib.parse.urlsplit(response.url)
            if final.scheme != "https" or final.hostname != "download.vb-audio.com":
                raise PackageError("Pobieranie przekierowano poza serwer producenta VB-Audio.")
            total = 0
            while chunk := response.read(64 * 1024):
                total += len(chunk)
                if total > MAX_DOWNLOAD:
                    raise PackageError("Paczka VB-CABLE przekracza limit rozmiaru.")
                output.write(chunk)
    except Exception:
        target.unlink(missing_ok=True)
        raise


def _archive_members(archive):
    if len(archive.infolist()) > MAX_FILES:
        raise PackageError("Paczka VB-CABLE zawiera zbyt wiele wpisów.")
    files = []
    seen = set()
    expanded = 0
    for entry in archive.infolist():
        name = entry.filename.replace("\\", "/")
        parts = name.rstrip("/").split("/")
        if (
            not name
            or name.startswith("/")
            or any(part in {"", ".", ".."} for part in parts)
            or any(any(char in part for char in ':<>"|?*') for part in parts)
            or any(part.endswith((".", " ")) for part in parts)
            or any(
                re.fullmatch(r"(?i)(CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])(\..*)?", part)
                for part in parts
            )
            or stat.S_ISLNK(entry.external_attr >> 16)
        ):
            raise PackageError("Paczka zawiera niedozwoloną ścieżkę lub dowiązanie.")
        key = name.rstrip("/").casefold()
        if key in seen:
            raise PackageError("Paczka zawiera powtarzające się nazwy plików Windows.")
        seen.add(key)
        if entry.is_dir():
            continue
        files.append((entry, PurePosixPath(*parts)))
        expanded += entry.file_size
        if len(files) > MAX_FILES or expanded > MAX_EXPANDED or entry.file_size > MAX_DOWNLOAD:
            raise PackageError("Paczka VB-CABLE przekracza limit plików lub rozmiaru.")
    return files


def stage_cable(archive_path, target):
    """Validate first, then replace unchanged files in a build-only directory."""
    archive_path, target = Path(archive_path), Path(target)
    if archive_path.stat().st_size > MAX_DOWNLOAD:
        raise PackageError("Paczka VB-CABLE przekracza limit rozmiaru.")
    try:
        with zipfile.ZipFile(archive_path) as archive:
            members = _archive_members(archive)
            setups = [
                path for _, path in members if path.name.casefold() == "vbcable_setup_x64.exe"
            ]
            if len(setups) != 1:
                raise PackageError("Nie znaleziono jednoznacznego instalatora VB-CABLE x64.")
            root = setups[0].parent
            if any(not path.is_relative_to(root) for _, path in members):
                raise PackageError(
                    "Pliki paczki znajdują się poza folderem instalatora producenta."
                )
            names = [
                str(path.relative_to(root)).casefold()
                for _, path in members
                if path.is_relative_to(root)
            ]
            if not all(
                any(name.endswith(ext) for name in names) for ext in (".inf", ".cat", ".sys")
            ):
                raise PackageError("Niekompletna paczka sterownika: brakuje INF, CAT lub SYS.")
            target.parent.mkdir(parents=True, exist_ok=True)
            with tempfile.TemporaryDirectory(dir=target.parent) as temporary:
                staged = Path(temporary) / "package"
                staged.mkdir()
                hashes = {}
                for entry, relative in members:
                    destination = staged.joinpath(*relative.parts)
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    with archive.open(entry) as source, destination.open("wb") as output:
                        shutil.copyfileobj(source, output)
                    hashes[str(relative)] = hashlib.sha256(destination.read_bytes()).hexdigest()
                setup = staged.joinpath(*setups[0].parts)
                if setup.read_bytes()[:2] != b"MZ":
                    raise PackageError("Instalator VB-CABLE nie jest plikiem wykonywalnym Windows.")
                # Only this generated staging directory is replaced; never a user-supplied source.
                if target.exists():
                    shutil.rmtree(target)
                staged.replace(target)
    except (zipfile.BadZipFile, RuntimeError) as error:
        raise PackageError(f"Nie można odczytać paczki VB-CABLE: {error}") from error
    return target.joinpath(*root.parts), {
        "vendor_url": CABLE_URL,
        "archive_sha256": hashlib.sha256(archive_path.read_bytes()).hexdigest(),
        "prepared_at": datetime.now(UTC).isoformat(),
        "files": hashes,
    }


def stage_localized_documents(project, target):
    assets = Path(project) / "src/musiccast_bridge/legal_texts"
    for language in ("pl", "en"):
        (Path(target) / f"license-{language}.txt").write_text(
            (assets / language / "LICENSE.txt").read_text(encoding="utf-8"),
            encoding="utf-8-sig",
        )
        documents = [
            (assets / language / name).read_text(encoding="utf-8").strip()
            for name in ("TERMS.md", "PRIVACY.md", "THIRD_PARTY_NOTICES.md", "VB-CABLE.txt")
        ]
        (Path(target) / f"info-{language}.txt").write_text(
            "\n\n".join(documents) + "\n", encoding="utf-8-sig",
        )


def prepare_installer(project, cable_zip):
    project = Path(project).resolve()
    if Path(cable_zip).stat().st_size > MAX_DOWNLOAD:
        raise PackageError("Paczka VB-CABLE przekracza limit rozmiaru.")
    archive_hash = hashlib.sha256(Path(cable_zip).read_bytes()).hexdigest()
    if archive_hash != CABLE_SHA256:
        raise PackageError(
            "Paczka różni się od sprawdzonego VB-CABLE Pack46. "
            f"Otrzymany SHA-256: {archive_hash}. Nie utworzono instalatora."
        )
    version_reader = runpy.run_path(str(Path(__file__).resolve().parent.parent /
                                       "src/musiccast_bridge/versioning.py"))["project_version"]
    try:
        version = version_reader(project)
    except ValueError as error:
        raise PackageError("Instalator wymaga poprawnej wersji X.Y.Z.") from error
    if not re.fullmatch(r"\d+\.\d+\.\d+", version):
        raise PackageError("Instalator wymaga wersji w formacie X.Y.Z.")
    app = project / "dist" / "MusicCastBridge"
    if not (app / "MusicCastBridge.exe").is_file():
        raise PackageError("Najpierw zbuduj dist/MusicCastBridge/MusicCastBridge.exe.")
    build = project / "build" / "installer"
    cable_root, manifest = stage_cable(cable_zip, build / "vbcable")
    manifest["app_version"] = version
    (build / "VB-CABLE-NOTICE.txt").write_text(
        (project / "installer" / "VB-CABLE-NOTICE.txt").read_text(encoding="utf-8"),
        encoding="utf-8-sig",
    )
    stage_localized_documents(project, build)
    (build / "vbcable-package.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    definitions = {
        "BridgeVersion": version,
        "AppBundlePath": str(app),
        "CableRootPath": str(cable_root),
        "StagePath": str(build),
    }
    # Quotes and line breaks would change the Inno preprocessor input.
    if any(any(char in value for char in '\r\n"') for value in definitions.values()):
        raise PackageError("Ścieżka projektu nie może zawierać cudzysłowu ani nowej linii.")
    (build / "generated.iss").write_text(
        "\n".join(f'#define {key} "{value}"' for key, value in definitions.items()) + "\n",
        encoding="utf-8-sig",
    )
    return version

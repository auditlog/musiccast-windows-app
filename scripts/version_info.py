"""Generate Windows PE version resources and frozen repository metadata."""

import json
import os
import runpy
from pathlib import Path


def prepare_version_info(project):
    project = Path(project)
    functions = runpy.run_path(str(project / "src/musiccast_bridge/versioning.py"))
    version = functions["project_version"](project)
    numbers = (*functions["version_tuple"](version), 0)
    explicit = os.environ.get("MUSICCAST_RELEASE_REPOSITORY", "")
    repository = (
        functions["github_repository"](explicit)
        if explicit
        else functions["origin_repository"](project)
    )
    folder = project / "build" / "version"
    folder.mkdir(parents=True, exist_ok=True)
    strings = {
        "CompanyName": "MusicCast Bridge contributors",
        "FileDescription": "MusicCast Bridge",
        "FileVersion": version,
        "InternalName": "MusicCastBridge",
        "LegalCopyright": "Copyright (c) 2026 MusicCast Bridge contributors. MIT license.",
        "OriginalFilename": "MusicCastBridge.exe",
        "ProductName": "MusicCast Bridge",
        "ProductVersion": version,
    }
    fields = ",\n".join(f"StringStruct({key!r}, {value!r})" for key, value in strings.items())
    resource = (
        "VSVersionInfo(ffi=FixedFileInfo("
        f"filevers={numbers!r}, prodvers={numbers!r}, "
        "mask=0x3f, flags=0, OS=0x40004, fileType=1, subtype=0, date=(0, 0)), "
        "kids=[StringFileInfo([StringTable('040904B0', [" + fields + "])]), "
        "VarFileInfo([VarStruct('Translation', [1033, 1200])])])\n"
    )
    version_file = folder / "windows-version-info.txt"
    version_file.write_text(resource, encoding="utf-8")
    metadata_file = folder / "build-info.json"
    metadata_file.write_text(
        json.dumps({"version": version, "repository": repository}) + "\n", encoding="utf-8"
    )
    print(f"EXE version: {version}; GitHub: {repository or '(not configured)'}")
    return version_file, metadata_file


def verify_exe_version(filename, expected):
    """Fail the native build if its PE resource differs from the declared version."""
    import pefile

    numbers = tuple(int(value) for value in expected.split(".")) + (0,)
    with pefile.PE(str(filename)) as executable:
        info = executable.VS_FIXEDFILEINFO[0]
        actual = (
            info.FileVersionMS >> 16,
            info.FileVersionMS & 0xFFFF,
            info.FileVersionLS >> 16,
            info.FileVersionLS & 0xFFFF,
        )
        product = (
            info.ProductVersionMS >> 16,
            info.ProductVersionMS & 0xFFFF,
            info.ProductVersionLS >> 16,
            info.ProductVersionLS & 0xFFFF,
        )
    if actual != numbers or product != numbers:
        raise ValueError(f"EXE version mismatch: {actual}, product={product}, expected={numbers}")


def verify_existing_bundle(folder, expected):
    folder = Path(folder)
    metadata = json.loads(
        (folder / "_internal/musiccast_bridge/build-info.json").read_text(encoding="utf-8")
    )
    if metadata.get("version") != expected:
        raise ValueError("Existing app bundle has a different version; run a full build")
    verify_exe_version(folder / "MusicCastBridge.exe", expected)

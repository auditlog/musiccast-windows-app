"""Read shipped legal texts without network access or an account."""

import sys
from pathlib import Path

from .i18n import language


def document(name, locale=None):
    if name not in {"LICENSE", "LICENSE_ORIGINAL", "TERMS.md", "PRIVACY.md",
                    "THIRD_PARTY_NOTICES.md", "VB-CABLE.txt"}:
        raise ValueError("Unknown legal document")
    locale = locale or language()
    if locale not in {"pl", "en"}:
        raise ValueError("Unknown document language")
    if name == "LICENSE_ORIGINAL":
        locale, name = "en", "LICENSE"
    filename = "LICENSE.txt" if name == "LICENSE" else name
    return (Path(__file__).with_name("legal_texts") / locale / filename).read_text(encoding="utf-8")


def library_licenses():
    root = (
        Path(sys.executable).parent / "third-party-licenses"
        if getattr(sys, "frozen", False)
        else Path(__file__).resolve().parents[2] / "licenses"
    )
    return root if root.is_dir() else Path(sys.prefix) / "share/musiccast-bridge/licenses"

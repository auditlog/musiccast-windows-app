"""Generate monolingual app documents from the bilingual reference documents.

Run after editing TERMS.md, PRIVACY.md, THIRD_PARTY_NOTICES.md or the VB-CABLE
notice. --check verifies committed app assets without writing them.
"""

import argparse
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TARGET = ROOT / "src/musiccast_bridge/legal_texts"
TITLES = {
    "TERMS.md": ("Zasady korzystania", "Terms of use"),
    "PRIVACY.md": ("Prywatność", "Privacy"),
    "THIRD_PARTY_NOTICES.md": ("Składniki zewnętrzne", "Third-party components"),
    "VB-CABLE.txt": ("VB-CABLE — składnik opcjonalny", "VB-CABLE — optional component"),
}


def expected_documents(project=ROOT):
    project = Path(project)
    documents = {}
    for filename, titles in TITLES.items():
        source = (project / "installer/VB-CABLE-NOTICE.txt" if filename == "VB-CABLE.txt"
                  else project / filename)
        text = source.read_text(encoding="utf-8")
        polish, english = text.split("\n## Polski\n", 1)[1].split("\n## English\n", 1)
        for language, title, body in zip(("pl", "en"), titles, (polish, english), strict=True):
            # Plain text is shared by the Qt reader and Inno's information page.
            body = re.sub(r"(?m)^#{1,6} ", "", body.strip()).replace("`", "")
            documents[f"{language}/{filename}"] = title + "\n\n" + body + "\n"
    documents["en/LICENSE.txt"] = (project / "LICENSE").read_text(encoding="utf-8")
    return documents


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)
    for name, text in expected_documents().items():
        target = TARGET / name
        if args.check:
            if not target.is_file() or target.read_text(encoding="utf-8") != text:
                raise SystemExit(f"Outdated document: {name}. Run scripts/localize_documents.py")
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(text, encoding="utf-8")


if __name__ == "__main__":
    main()

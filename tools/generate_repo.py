#!/usr/bin/env python3
"""
Kodi Repository Generator
Builds the addons.xml, hashes, and per-addon zip files for the FENtastic repository.
Output is written to the _repo/ directory which gets deployed to GitHub Pages.
"""
from __future__ import annotations

import hashlib
import os
import re
import shutil
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

ROOT = Path(__file__).resolve().parent.parent
OUTPUT = ROOT / "_repo"

# Addons to include in the repository.
# Value is either a subfolder name (str) or None to use the repo root itself.
ADDON_DIRS: dict[str, str | None] = {
    "skin.fentastic": None,          # addon.xml lives at the repo root
    "repository.fentastic": "repository.fentastic",
}

# Files/folders to exclude from addon zips
EXCLUDED = {
    ".git",
    ".github",
    ".gitignore",
    "__pycache__",
    "tools",
    "_repo",
    "README.md",
    "changelog.txt",
    "LICENSE.txt",
    "repository.fentastic",
}


def get_addon_version(addon_xml_path: Path) -> str:
    tree = ET.parse(addon_xml_path)
    return tree.getroot().get("version", "0.0.0")


def zip_addon(addon_id: str, addon_path: Path, dest_dir: Path) -> Path:
    version = get_addon_version(addon_path / "addon.xml")
    zip_name = f"{addon_id}-{version}.zip"
    zip_path = dest_dir / zip_name

    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for file in sorted(addon_path.rglob("*")):
            if any(part in EXCLUDED for part in file.parts):
                continue
            arcname = Path(addon_id) / file.relative_to(addon_path)
            zf.write(file, arcname)

    print(f"  Created {zip_name}")
    return zip_path


def copy_addon_assets(addon_id: str, addon_path: Path, dest_dir: Path):
    for asset in ("icon.png", "fanart.jpg"):
        src = addon_path / asset
        if not src.exists():
            # Fall back to resources/ subdirectory
            src = addon_path / "resources" / asset
        if src.exists():
            shutil.copy2(src, dest_dir / asset)


def build_addons_xml(addon_dirs: list[tuple[str, Path]]) -> str:
    root = ET.Element("addons")
    for addon_id, addon_path in addon_dirs:
        tree = ET.parse(addon_path / "addon.xml")
        root.append(tree.getroot())

    if hasattr(ET, "indent"):
        ET.indent(root, space="    ")
    xml_str = ET.tostring(root, encoding="unicode", xml_declaration=False)
    return '<?xml version="1.0" encoding="UTF-8"?>\n' + xml_str + "\n"


def md5_of(text: str) -> str:
    return hashlib.md5(text.encode("utf-8")).hexdigest()


def sha256_of(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def write_index_html(directory: Path, title: str, entries: list[str]):
    """Write an Apache-style directory listing that Kodi's HTTP VFS can parse."""
    links = "\n".join(
        f'<li><a href="{entry}">{entry}</a></li>' for entry in entries
    )
    html = (
        f"<!DOCTYPE html><html><head><title>{title}</title></head><body>\n"
        f"<h1>{title}</h1><ul>\n{links}\n</ul></body></html>\n"
    )
    (directory / "index.html").write_text(html, encoding="utf-8")


def main():
    OUTPUT.mkdir(exist_ok=True)
    (OUTPUT / ".nojekyll").touch()

    addon_pairs: list[tuple[str, Path]] = []

    for addon_id, subfolder in ADDON_DIRS.items():
        addon_path = ROOT if subfolder is None else ROOT / subfolder
        if not (addon_path / "addon.xml").exists():
            print(f"WARNING: {addon_id}/addon.xml not found, skipping.")
            continue

        dest_dir = OUTPUT / addon_id
        dest_dir.mkdir(exist_ok=True)

        print(f"Processing {addon_id}...")
        zip_file = zip_addon(addon_id, addon_path, dest_dir)
        copy_addon_assets(addon_id, addon_path, dest_dir)

        # Per-addon index.html listing all files in its directory
        sub_entries = sorted(f.name for f in dest_dir.iterdir())
        write_index_html(dest_dir, addon_id, sub_entries)

        addon_pairs.append((addon_id, addon_path))

    # Generate addons.xml
    print("Generating addons.xml...")
    addons_xml = build_addons_xml(addon_pairs)
    addons_xml_path = OUTPUT / "addons.xml"
    addons_xml_path.write_text(addons_xml, encoding="utf-8")

    # Generate hashes
    (OUTPUT / "addons.xml.md5").write_text(md5_of(addons_xml), encoding="utf-8")
    (OUTPUT / "addons.xml.sha256").write_text(sha256_of(addons_xml), encoding="utf-8")

    # Root index.html — lists addon subdirs and top-level files for Kodi browsing
    root_entries = sorted(
        [f"{addon_id}/" for addon_id, _ in addon_pairs]
        + ["addons.xml", "addons.xml.md5", "addons.xml.sha256"]
    )
    write_index_html(OUTPUT, "FENtastic Kodi Repository", root_entries)
    print("  index.html (root + per-addon)")

    print(f"\nDone! Repository written to: {OUTPUT}")
    print("  addons.xml")
    print("  addons.xml.md5")
    print("  addons.xml.sha256")


if __name__ == "__main__":
    main()

"""
Build script to pack built-in extensions into .oaext packages and generate builtin_catalog.json.
"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from extensions.extension_installer import ExtensionInstaller
from extensions.extension_security import ExtensionSecurity


def build_all():
    root = Path(__file__).resolve().parent.parent
    src_dir = root / "assets" / "extensions_src"
    out_dir = root / "assets" / "extensions"
    out_dir.mkdir(parents=True, exist_ok=True)

    extensions_meta = [
        ("python-essentials", "openarise.python-essentials-1.0.0.oaext"),
        ("dracula-theme", "openarise.theme-dracula-1.0.0.oaext"),
        ("json-formatter", "openarise.json-formatter-1.0.0.oaext"),
        ("ai-prompts", "openarise.ai-prompts-1.0.0.oaext"),
    ]

    catalog_entries = []

    for folder_name, pkg_name in extensions_meta:
        src = src_dir / folder_name
        dest = out_dir / pkg_name
        ExtensionInstaller.create_oaext_package(src, dest)
        pkg_hash = ExtensionSecurity.calculate_sha256(dest)

        manifest_data = json.loads((src / "manifest.json").read_text(encoding="utf-8"))
        readme_data = ""
        if (src / "README.md").exists():
            readme_data = (src / "README.md").read_text(encoding="utf-8")

        catalog_entries.append({
            "id": manifest_data["id"],
            "name": manifest_data["name"],
            "version": manifest_data["version"],
            "description": manifest_data["description"],
            "author": manifest_data["author"],
            "category": manifest_data["category"],
            "download_url": f"file://{dest.resolve().as_posix()}",
            "package_hash": pkg_hash,
            "minimum_openarise_version": manifest_data.get("minimum_openarise_version", "1.0.0"),
            "entry_point": manifest_data.get("entry_point"),
            "permissions": manifest_data.get("permissions", []),
            "contributes": manifest_data.get("contributes", {}),
            "icon": "",
            "readme": readme_data,
        })
        print(f"Built {pkg_name} (hash: {pkg_hash[:12]}...)")

    catalog = {
        "registry_version": "1.0.0",
        "extensions": catalog_entries,
    }
    catalog_path = out_dir / "builtin_catalog.json"
    catalog_path.write_text(json.dumps(catalog, indent=2), encoding="utf-8")
    print(f"Generated {catalog_path}")


if __name__ == "__main__":
    build_all()

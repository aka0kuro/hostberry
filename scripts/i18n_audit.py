#!/usr/bin/env python3
"""
i18n audit for HostBerry.

Outputs:
- Unused keys per locale (defined in locales/*.json but not referenced in code)
- Missing keys (referenced in code but missing from a locale)

By default it only reports. With --write-unused it can write a pruned copy to a target file.
We intentionally do NOT mutate locales/*.json by default.
"""

from __future__ import annotations

import argparse
import json
import os
import re
from pathlib import Path
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parents[1]
LOCALES_DIR = ROOT / "locales"

# Files/dirs to ignore while scanning for key usage
DEFAULT_IGNORE_DIRS = {
    ".git",
    "__pycache__",
    ".venv",
    "venv",
    "node_modules",
    "dist",
    "build",
}

DEFAULT_IGNORE_FILES = {
    "locales/en.json",
    "locales/es.json",
}


def flatten_keys(d: Any, prefix: str = "") -> set[str]:
    keys: set[str] = set()
    if isinstance(d, dict):
        for k, v in d.items():
            k_str = str(k)
            new_prefix = f"{prefix}.{k_str}" if prefix else k_str
            keys |= flatten_keys(v, new_prefix)
    else:
        if prefix:
            keys.add(prefix)
    return keys


def get_by_path(d: dict[str, Any], path: str) -> Any:
    cur: Any = d
    for part in path.split("."):
        if not isinstance(cur, dict) or part not in cur:
            return None
        cur = cur[part]
    return cur


def set_by_path(d: dict[str, Any], path: str, value: Any) -> None:
    cur: Any = d
    parts = path.split(".")
    for part in parts[:-1]:
        if part not in cur or not isinstance(cur[part], dict):
            cur[part] = {}
        cur = cur[part]
    cur[parts[-1]] = value


def delete_by_path(d: dict[str, Any], path: str) -> bool:
    """Delete a dotted path. Returns True if deleted."""
    cur: Any = d
    parts = path.split(".")
    for part in parts[:-1]:
        if not isinstance(cur, dict) or part not in cur:
            return False
        cur = cur[part]
    if isinstance(cur, dict) and parts[-1] in cur:
        del cur[parts[-1]]
        return True
    return False


def prune_empty_dicts(d: Any) -> Any:
    if isinstance(d, dict):
        for k in list(d.keys()):
            d[k] = prune_empty_dicts(d[k])
            if isinstance(d[k], dict) and not d[k]:
                del d[k]
        return d
    return d


def iter_source_files(root: Path, extensions: set[str], ignore_dirs: set[str], ignore_files: set[str]) -> Iterable[Path]:
    for dirpath, dirnames, filenames in os.walk(root):
        # Filter directories in-place
        dirnames[:] = [d for d in dirnames if d not in ignore_dirs and not d.startswith(".")]
        for fn in filenames:
            p = Path(dirpath) / fn
            rel = p.relative_to(root).as_posix()
            if rel in ignore_files:
                continue
            if p.suffix.lower() in extensions:
                yield p


KEY_PATTERNS = [
    # Jinja: {{ t('a.b.c', 'Default') }}
    re.compile(r"""\{\{\s*t\(\s*(['"])(?P<key>[^'"]+)\1"""),
    # JS: HostBerry.t('a.b.c', ...) or HostBerry.t?.('a.b.c', ...)
    re.compile(r"""HostBerry\.t\??\(\s*(['"])(?P<key>[^'"]+)\1"""),
    # JS: window.t('a.b.c', ...)
    re.compile(r"""\b(?:window\.)?t\(\s*(['"])(?P<key>[^'"]+)\1"""),
]


def extract_used_keys_from_text(text: str) -> set[str]:
    used: set[str] = set()
    for pat in KEY_PATTERNS:
        for m in pat.finditer(text):
            key = m.group("key").strip()
            if key:
                used.add(key)
    return used


def load_locale(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def main() -> int:
    ap = argparse.ArgumentParser(description="Audit unused/missing i18n keys in locales/*.json")
    ap.add_argument("--root", default=str(ROOT), help="Repo root (default: auto)")
    ap.add_argument("--locales-dir", default=str(LOCALES_DIR), help="Locales dir (default: locales/)")
    ap.add_argument("--extensions", default=".py,.js,.html", help="Comma-separated extensions to scan")
    ap.add_argument("--ignore-dirs", default=",".join(sorted(DEFAULT_IGNORE_DIRS)), help="Comma-separated dir names to ignore")
    ap.add_argument("--report-json", default=str(ROOT / "scripts" / "i18n_report.json"), help="Where to write JSON report")
    ap.add_argument("--write-unused", action="store_true", help="Write pruned locale copies to --out-dir (does not overwrite originals)")
    ap.add_argument("--out-dir", default=str(ROOT / "scripts" / "i18n_pruned"), help="Output dir for pruned locales when --write-unused")
    ap.add_argument("--keep-prefix", action="append", default=[], help="Keep keys with these prefixes even if unused (repeatable)")
    args = ap.parse_args()

    root = Path(args.root).resolve()
    locales_dir = Path(args.locales_dir).resolve()
    extensions = {e.strip() for e in args.extensions.split(",") if e.strip()}
    ignore_dirs = {d.strip() for d in args.ignore_dirs.split(",") if d.strip()}
    ignore_files = set(DEFAULT_IGNORE_FILES)

    locale_files = sorted(locales_dir.glob("*.json"))
    if not locale_files:
        raise SystemExit(f"No locale json files found in {locales_dir}")

    # Collect used keys
    used_keys: set[str] = set()
    for p in iter_source_files(root, extensions, ignore_dirs, ignore_files):
        try:
            text = p.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        used_keys |= extract_used_keys_from_text(text)

    report: dict[str, Any] = {
        "root": str(root),
        "scanned_extensions": sorted(extensions),
        "used_keys_count": len(used_keys),
        "locales": {},
        "used_keys_sample": sorted(list(used_keys))[:50],
    }

    # Analyze each locale file
    locale_data: dict[str, dict[str, Any]] = {}
    locale_flat_keys: dict[str, set[str]] = {}
    for lf in locale_files:
        code = lf.stem
        data = load_locale(lf)
        locale_data[code] = data
        locale_flat_keys[code] = flatten_keys(data)

    # Union of defined keys across locales
    defined_union: set[str] = set()
    for s in locale_flat_keys.values():
        defined_union |= s

    # Missing keys per locale: referenced but not defined
    for code in sorted(locale_data.keys()):
        defined = locale_flat_keys[code]
        missing = sorted(k for k in used_keys if k not in defined)

        # Unused keys: defined but not referenced
        keep_prefixes: list[str] = list(args.keep_prefix or [])
        unused = []
        for k in sorted(defined):
            if k in used_keys:
                continue
            if any(k.startswith(pref) for pref in keep_prefixes):
                continue
            unused.append(k)

        report["locales"][code] = {
            "file": str((locales_dir / f"{code}.json").relative_to(root)),
            "defined_keys_count": len(defined),
            "missing_keys_count": len(missing),
            "unused_keys_count": len(unused),
            "missing_keys": missing[:500],
            "unused_keys": unused[:500],
            "missing_keys_truncated": max(0, len(missing) - 500),
            "unused_keys_truncated": max(0, len(unused) - 500),
        }

    # Keys used but missing from ALL locales (strong signal)
    missing_all = sorted(k for k in used_keys if k not in defined_union)
    report["missing_in_all_locales"] = missing_all
    report["missing_in_all_locales_count"] = len(missing_all)

    # Write report
    report_path = Path(args.report_json).resolve()
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    # Optionally write pruned locale copies
    if args.write_unused:
        out_dir = Path(args.out_dir).resolve()
        out_dir.mkdir(parents=True, exist_ok=True)
        for code, data in locale_data.items():
            defined = locale_flat_keys[code]
            keep_prefixes = list(args.keep_prefix or [])
            to_delete = []
            for k in defined:
                if k in used_keys:
                    continue
                if any(k.startswith(pref) for pref in keep_prefixes):
                    continue
                to_delete.append(k)
            pruned = json.loads(json.dumps(data))  # deep copy
            for k in sorted(to_delete, key=lambda s: (-len(s), s)):
                delete_by_path(pruned, k)
            pruned = prune_empty_dicts(pruned)
            (out_dir / f"{code}.json").write_text(json.dumps(pruned, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(f"OK: wrote report to {report_path}")
    if args.write_unused:
        print(f"OK: wrote pruned locales to {Path(args.out_dir).resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())



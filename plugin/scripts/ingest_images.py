#!/usr/bin/env python3
"""Download remote images referenced from a markdown source into raw/assets/
and rewrite the source to use local paths.

Used by wiki-ingest. Skill calls this; it doesn't run itself unless asked.

Usage:
    ingest_images.py --wiki <wiki_root> --source <md_path> [--dry-run]

What it does:
1. Parses ![alt](url) and ![alt][ref] image references in the markdown
2. For each remote URL (http://, https://, file://):
     - Download to {wiki_root}/raw/assets/{source-stem}-{n}.{ext}
     - Cap each download at 10 MiB; cap total per source at 50 MiB
3. Rewrites <source> in place to use the local relative path

Local images (./foo.png, ../assets/x.jpg) are left untouched. The script never
touches anything under raw/ except writing new asset files into raw/assets/.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from wiki_lib import emit, find_wiki_root

IMG_INLINE_RE = re.compile(r"!\[([^\]]*)\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)")
PER_DOWNLOAD_LIMIT = 10 * 1024 * 1024
PER_SOURCE_LIMIT = 50 * 1024 * 1024
TIMEOUT = 30


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--wiki", default=None)
    p.add_argument("--source", required=True,
                   help="Path to the markdown source whose images to download")
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args()

    root = find_wiki_root(args.wiki)
    src = Path(args.source).resolve()
    if not src.exists():
        emit({"error": f"source not found: {src}"})
        return 2

    text = src.read_text(encoding="utf-8")
    assets_dir = root / "raw" / "assets"
    assets_dir.mkdir(parents=True, exist_ok=True)

    rewrites = []
    total_bytes = 0
    new_text = text
    seen = 0

    for m in IMG_INLINE_RE.finditer(text):
        alt, url = m.group(1), m.group(2).strip()
        if _is_local(url):
            continue
        seen += 1
        ext = _extension(url) or ".bin"
        local_name = f"{src.stem}-{seen}{ext}"
        local_path = assets_dir / local_name
        rel_path = local_path.relative_to(root).as_posix()

        if args.dry_run:
            rewrites.append({"url": url, "would_save_to": rel_path})
            continue

        if total_bytes >= PER_SOURCE_LIMIT:
            rewrites.append({"url": url, "skipped": "per-source size cap reached"})
            continue

        result = _download(url, local_path, PER_DOWNLOAD_LIMIT)
        if "error" in result:
            rewrites.append({"url": url, "skipped": result["error"]})
            continue

        total_bytes += result["bytes"]
        # Replace this specific occurrence in the text.
        # Use the original matched substring so we substitute exactly once.
        original = m.group(0)
        replacement = f"![{alt}]({rel_path})"
        new_text = new_text.replace(original, replacement, 1)
        rewrites.append({
            "url": url, "saved_to": rel_path, "bytes": result["bytes"],
        })

    if not args.dry_run and new_text != text:
        src.write_text(new_text, encoding="utf-8")

    emit({
        "wiki": str(root),
        "source": str(src),
        "dry_run": args.dry_run,
        "remote_images_seen": seen,
        "rewrites": rewrites,
        "total_bytes_downloaded": total_bytes,
        "limits": {
            "per_download": PER_DOWNLOAD_LIMIT,
            "per_source": PER_SOURCE_LIMIT,
        },
    })
    return 0


def _is_local(url: str) -> bool:
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme in ("http", "https", "file"):
        return False
    return True


def _extension(url: str) -> str:
    """Strip query string + fragment, return suffix from path."""
    parsed = urllib.parse.urlparse(url)
    path = parsed.path
    if "." in path:
        ext = path[path.rindex("."):]
        # Sanity: extensions should be short and alphabetic
        if 1 < len(ext) <= 6 and ext[1:].isalnum():
            return ext.lower()
    return ""


def _download(url: str, dest: Path, limit: int) -> dict:
    try:
        # urllib accepts file:// URLs too — useful for tests
        req = urllib.request.Request(url, headers={"User-Agent": "kata/1.5"})
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            chunks = []
            total = 0
            while True:
                chunk = resp.read(min(64 * 1024, limit - total + 1))
                if not chunk:
                    break
                total += len(chunk)
                if total > limit:
                    return {"error": f"exceeds per-download cap ({limit} bytes)"}
                chunks.append(chunk)
        dest.write_bytes(b"".join(chunks))
        return {"bytes": total}
    except urllib.error.URLError as e:
        return {"error": f"download failed: {e}"}
    except OSError as e:
        return {"error": f"write failed: {e}"}


if __name__ == "__main__":
    sys.exit(main())

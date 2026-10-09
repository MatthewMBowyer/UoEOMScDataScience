#!/usr/bin/env python3
"""Capture the delivered-site baseline BEFORE this improvement pass edits anything.

This is what makes the non-regression proof (AC-46 / INV-18) real: it records,
against the served pre-pass tree, the page -> HTTP status map, the internal-link
set, the navigation signature and the referenced-image set. `tests/verify_site.py`
re-derives the same shape after the pass and diffs the two.

    python3 scripts/before_baseline.py                       # serves work/pre_gen3_backup
    python3 scripts/before_baseline.py --root <dir>

Writes output/evidence/before_baseline.json.
"""
from __future__ import annotations

import argparse
import functools
import glob
import hashlib
import http.server
import json
import os
import socketserver
import threading
import urllib.error
import urllib.parse
import urllib.request

from lxml import html as LH

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(ROOT)

REMOVED_PAGES = [
    "index01.html", "index1.html", "2026.html", "AMsmash.html", "Americano.html",
    "Cute.html", "Mattgoals.html", "RobJo.html", "Team_Americano.html",
    "burpeeeeeees.html", "grumpgrump.html", "test.html",
]


class QuietHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *args):  # noqa: D102 - silence the per-request log
        pass


def sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def serve(root: str):
    handler = functools.partial(QuietHandler, directory=root)
    httpd = socketserver.ThreadingTCPServer(("127.0.0.1", 0), handler)
    httpd.daemon_threads = True
    port = httpd.server_address[1]
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return httpd, port


def probe(base: str, path: str) -> dict:
    url = base + "/" + urllib.parse.quote(path)
    try:
        with urllib.request.urlopen(url, timeout=10) as r:
            body = r.read()
            return {"path": path, "status": r.status,
                    "content_type": r.headers.get("Content-Type", ""),
                    "bytes": len(body)}
    except urllib.error.HTTPError as e:
        return {"path": path, "status": e.code, "content_type": "", "bytes": 0}
    except Exception as e:  # noqa: BLE001
        return {"path": path, "status": 0, "error": f"{type(e).__name__}: {e}",
                "bytes": 0}


def resolve_local(page: str, value: str) -> str | None:
    """Map an href/src to an on-disk relative path, or None if external."""
    if not value or value.startswith(("#", "mailto:", "tel:", "data:", "javascript:")):
        return None
    if "://" in value or value.startswith("//"):
        return None
    path = urllib.parse.unquote(value.split("#", 1)[0].split("?", 1)[0])
    path = path.replace("\\", "/")
    if path.startswith("/"):
        path = path.lstrip("/")
    base = os.path.dirname(page)
    return os.path.normpath(os.path.join(base, path)) if base else path


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=os.path.join(ROOT, "work", "pre_gen3_backup"))
    ap.add_argument("--out", default="output/evidence/before_baseline.json")
    args = ap.parse_args()
    root = args.root if os.path.isabs(args.root) else os.path.join(ROOT, args.root)
    if not os.path.isdir(root):
        print(f"baseline root missing: {root}")
        return 1

    httpd, port = serve(root)
    base = f"http://127.0.0.1:{port}"
    try:
        pages = sorted(os.path.basename(p)
                       for p in glob.glob(os.path.join(root, "*.html"))
                       if os.path.basename(p) != "footer.html")

        page_status: dict[str, int] = {}
        for page in pages:
            page_status[page] = probe(base, page)["status"]

        # Links and images, resolved against the served tree.
        internal_links: set[str] = set()
        broken_links: list[dict] = []
        images: set[str] = set()
        external_hosts: set[str] = set()
        nav_signatures: dict[str, list] = {}
        for page in pages:
            doc = LH.fromstring(open(os.path.join(root, page), encoding="utf-8",
                                     errors="replace").read())
            nav = doc.xpath('//nav[@id="nav"]//a')
            nav_signatures[page] = [(" ".join(a.xpath(".//text()")).strip(),
                                     a.get("href")) for a in nav]
            for el in doc.xpath("//a[@href]"):
                v = el.get("href") or ""
                if "://" in v:
                    external_hosts.add(urllib.parse.urlparse(v).netloc)
                    continue
                if v.startswith(("//", "#", "mailto:", "tel:", "javascript:", "data:")):
                    continue
                target = resolve_local(page, v)
                if target is None:
                    continue
                internal_links.add(target)
                if not os.path.exists(os.path.join(root, target)):
                    broken_links.append({"page": page, "href": v, "target": target})
            for el in doc.xpath("//img[@src]"):
                target = resolve_local(page, el.get("src") or "")
                if target:
                    images.add(target)

        asset_status = {p: probe(base, p)["status"] for p in sorted(internal_links | images)}

        page_hashes = {p: sha256(os.path.join(root, p)) for p in pages}
        payload = {
            "generated_utc": __import__("datetime").datetime.now(
                __import__("datetime").timezone.utc).isoformat(timespec="seconds"),
            "baseline_root": os.path.relpath(root, ROOT),
            "note": ("Delivered-site state BEFORE the generation-3 improvement pass. "
                     "Captured by serving the pre-pass tree over local HTTP and "
                     "probing every page and referenced asset."),
            "pages": pages,
            "page_status": page_status,
            "pages_non_200": {k: v for k, v in page_status.items() if v != 200},
            "page_sha256": page_hashes,
            "internal_links": sorted(internal_links),
            "internal_link_count": len(internal_links),
            "asset_status": asset_status,
            "assets_non_200": {k: v for k, v in asset_status.items() if v != 200},
            "brokен_links_placeholder": None,
            "broken_links": broken_links,
            "images": sorted(images),
            "image_count": len(images),
            "external_hosts": sorted(external_hosts),
            "nav_signature": nav_signatures,
            "removed_pages_absent": {p: not os.path.exists(os.path.join(root, p))
                                     for p in REMOVED_PAGES},
        }
        payload.pop("brokен_links_placeholder")
        out = os.path.join(ROOT, args.out)
        os.makedirs(os.path.dirname(out), exist_ok=True)
        with open(out, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, indent=2, ensure_ascii=False)
        print(f"pages={len(pages)} non_200={payload['pages_non_200']}")
        print(f"internal_links={len(internal_links)} broken={len(broken_links)}")
        print(f"assets={len(asset_status)} images={len(images)} "
              f"external_hosts={sorted(external_hosts)}")
        print(f"wrote {args.out}")
    finally:
        httpd.shutdown()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

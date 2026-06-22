#!/usr/bin/env python3
"""
build_demo.py — refresh nmap.org demo data for whatweb-recon GitHub Pages.
Run: python3 build_demo.py
"""

import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT     = Path(__file__).parent
SCRIPT   = ROOT / "whatweb-recon.py"
OUT_FILE = ROOT / "web" / "data" / "domains" / "nmap.org.json"
IDX_FILE = ROOT / "web" / "data" / "index.json"
DOMAIN   = "nmap.org"
DISPLAY_NAME = "fmfalgun"
DISPLAY_LOC  = "Chennai, India"


def main():
    OUT_FILE.parent.mkdir(parents=True, exist_ok=True)

    print(f"[build_demo] Running whatweb-recon on {DOMAIN} ...")
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "-d", DOMAIN,
         "-o", str(OUT_FILE), "--no-cache"],
        capture_output=True, text=True,
    )
    print(result.stdout)
    if result.stderr:
        print("[stderr]", result.stderr[:500])

    if not OUT_FILE.exists():
        print(f"[ERROR] {OUT_FILE} not found — whatweb-recon may have failed.")
        sys.exit(1)

    try:
        data = json.loads(OUT_FILE.read_text())
    except json.JSONDecodeError as e:
        print(f"[ERROR] Invalid JSON in {OUT_FILE}: {e}")
        sys.exit(1)

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    data.setdefault("display_name", DISPLAY_NAME)
    data.setdefault("display_loc",  DISPLAY_LOC)
    data["last_refreshed"] = now
    OUT_FILE.write_text(json.dumps(data, indent=2))

    # Update index.json
    if IDX_FILE.exists():
        try:
            index = json.loads(IDX_FILE.read_text())
        except json.JSONDecodeError:
            index = {"total_domains": 0, "domains": []}
    else:
        index = {"total_domains": 0, "domains": []}

    entry = {
        "domain":              DOMAIN,
        "display_name":        DISPLAY_NAME,
        "display_loc":         DISPLAY_LOC,
        "queried_at":          data.get("queried_at", now),
        "last_refreshed":      now,
        "url_count":           data.get("url_count", 0),
        "cms":                 data.get("cms"),
        "server":              data.get("server"),
        "php_version":         data.get("php_version"),
        "interesting_plugins": data.get("interesting_plugins", []),
        "method":              data.get("method", "whatweb"),
    }

    domains = [d for d in index.get("domains", []) if d.get("domain") != DOMAIN]
    domains.append(entry)
    domains.sort(key=lambda x: x["domain"])
    index["total_domains"] = len(domains)
    index["domains"] = domains
    IDX_FILE.write_text(json.dumps(index, indent=2))

    print(f"[build_demo] Done. {OUT_FILE.name} written. index.json updated ({len(domains)} domains).")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
whatweb-recon — WhatWeb fingerprinting wrapper with TTL cache and community submission.

Primary mode : wraps the whatweb Ruby CLI tool, parses JSON output.
Fallback mode : HTTP fingerprinting via urllib (stdlib only) when whatweb is absent.
Cache         : SQLite (cache.db), 24h TTL, keyed by domain.
Submit        : posts full JSON result to GitHub Issues as [submission] entry.
"""

import argparse
import datetime
import json
import os
import re
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import urllib.request
import urllib.error
from collections import Counter
from pathlib import Path
from urllib.parse import urlparse

# ── constants ─────────────────────────────────────────────────────────────────

__version__       = "1.0.0"
CACHE_DB          = "./cache.db"
CONFIG_PATH       = Path.home() / ".config" / "whatweb-recon" / "config.json"
GITHUB_ISSUES_URL = "https://api.github.com/repos/fmfalgun/whatweb-recon/issues"
DEFAULT_TTL       = 86400  # 24 hours

# ── ANSI helpers ──────────────────────────────────────────────────────────────

RESET  = "\033[0m"
BOLD   = "\033[1m"
RED    = "\033[31m"
YELLOW = "\033[33m"
CYAN   = "\033[36m"
GREEN  = "\033[32m"
DIM    = "\033[2m"

def _is_eol_php(version: str | None) -> bool:
    """Return True if the PHP version string is known-EOL (< 8.0)."""
    if not version:
        return False
    m = re.match(r"(\d+)\.(\d+)", version)
    if not m:
        return False
    major, minor = int(m.group(1)), int(m.group(2))
    return major < 8

# ── cache ─────────────────────────────────────────────────────────────────────

def get_cache_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(CACHE_DB)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS whatweb_cache (
            domain      TEXT PRIMARY KEY,
            result_json TEXT NOT NULL,
            cached_at   TEXT NOT NULL
        )
    """)
    conn.commit()
    return conn


def cache_get(conn: sqlite3.Connection, domain: str, ttl: int) -> dict | None:
    """Return cached result dict if present and within TTL, else None."""
    row = conn.execute(
        "SELECT result_json, cached_at FROM whatweb_cache WHERE domain = ?",
        (domain,)
    ).fetchone()
    if row is None:
        return None
    result_json, cached_at_str = row
    cached_at = datetime.datetime.fromisoformat(cached_at_str)
    age = (datetime.datetime.utcnow() - cached_at).total_seconds()
    if age < ttl:
        result = json.loads(result_json)
        result["cached"] = True
        return result
    return None


def cache_set(conn: sqlite3.Connection, domain: str, result: dict) -> None:
    """UPSERT result into cache, stamping cached_at to now."""
    now = datetime.datetime.utcnow().isoformat()
    conn.execute(
        "INSERT OR REPLACE INTO whatweb_cache (domain, result_json, cached_at) VALUES (?, ?, ?)",
        (domain, json.dumps(result), now)
    )
    conn.commit()

# ── config ────────────────────────────────────────────────────────────────────

def load_config() -> dict | None:
    if CONFIG_PATH.exists():
        try:
            with open(CONFIG_PATH) as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            return None
    return None


def save_config(cfg: dict) -> None:
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(CONFIG_PATH, "w") as f:
        json.dump(cfg, f, indent=2)


def setup_wizard() -> dict:
    print("First-time setup for community submission.")
    print()
    token = input("GitHub Personal Access Token (needs 'repo' scope for Issues write): ").strip()
    display_name = input("Your display name (shown on Tech Board, or leave blank): ").strip() or None
    display_loc  = input("Your location (city/country, or leave blank): ").strip() or None
    cfg = {
        "github_token": token,
        "display_name": display_name,
        "display_loc":  display_loc,
    }
    save_config(cfg)
    print(f"Config saved to {CONFIG_PATH}")
    return cfg

# ── core: field extraction ────────────────────────────────────────────────────

def extract_fields(entry: dict) -> dict:
    plugins = entry.get("plugins", {})

    def first_str(name):
        p = plugins.get(name, {})
        v = p.get("string", p.get("version", []))
        return v[0] if v else None

    def first_ver(name):
        p = plugins.get(name, {})
        v = p.get("version", p.get("string", []))
        return v[0] if v else None

    def present(name):
        return 1 if name in plugins else 0

    xmlrpc = 0
    uh_str = " ".join(plugins.get("UncommonHeaders", {}).get("string", [])).lower()
    if "x-pingback" in uh_str or "XML-RPC" in plugins:
        xmlrpc = 1

    server_os = None
    hs = plugins.get("HTTPServer", {})
    os_list = hs.get("os", [])
    if os_list:
        server_os = os_list[0]

    cms_name = None
    cms_version = None
    for cms in ["WordPress", "Joomla", "Drupal", "Magento", "PrestaShop",
                "Ghost", "TYPO3", "Shopify", "Wix", "Squarespace"]:
        if cms in plugins:
            cms_name = cms
            cms_version = first_ver(cms)
            break

    title_list = plugins.get("Title", {}).get("string", [])
    title = title_list[0].strip() if title_list else None

    return {
        "http_status":       entry.get("http_status"),
        "server":            first_str("HTTPServer"),
        "server_os":         server_os,
        "php_version":       first_ver("PHP"),
        "openssl_version":   first_ver("OpenSSL"),
        "iis_version":       first_ver("Microsoft-IIS"),
        "wordpress":         bool(present("WordPress")),
        "wp_version":        first_ver("WordPress"),
        "joomla":            bool(present("Joomla")),
        "drupal":            bool(present("Drupal")),
        "magento":           bool(present("Magento")),
        "title":             title,
        "ip_address":        first_str("IP"),
        "redirect_url":      first_str("RedirectLocation"),
        "cpanel":            bool(present("cPanel")),
        "whm":               bool(present("WHM")),
        "phpmyadmin":        bool(present("phpMyAdmin")),
        "phppgadmin":        bool(present("phpPgAdmin")),
        "xmlrpc":            bool(xmlrpc),
        "jquery_version":    first_ver("jQuery"),
        "bootstrap_version": first_ver("Bootstrap"),
        "cms_detected":      cms_name,
        "cms_version":       cms_version,
        "plugins":           plugins,
    }

# ── aggression ────────────────────────────────────────────────────────────────

def determine_aggression(urls: list[str], override: int | None = None) -> tuple[int, str]:
    if override is not None:
        return override, f"manual override --aggression {override}"
    if len(urls) > 30:
        return 1, "large URL set (>30 URLs) — stealthy to avoid rate limits"
    return 3, "standard URL set — aggressive fingerprinting"

# ── whatweb runner ────────────────────────────────────────────────────────────

def run_whatweb(urls: list[str], aggression: int, output_dir: str | None = None) -> list[dict]:
    """
    Run the whatweb binary against urls, parse JSON output.
    Returns list of per-URL result dicts (extract_fields shape + 'url' key).
    Falls back to http_fallback() if whatweb binary is not found.
    """
    if shutil.which("whatweb") is None:
        print(f"{YELLOW}[warn]{RESET} whatweb binary not found — using HTTP fallback.", file=sys.stderr)
        return http_fallback(urls)

    with tempfile.TemporaryDirectory() as tmpdir:
        url_file  = os.path.join(tmpdir, "urls.txt")
        json_file = os.path.join(tmpdir, "out.json")

        with open(url_file, "w") as f:
            f.write("\n".join(urls) + "\n")

        cmd = [
            "whatweb",
            "-i", url_file,
            f"-a{aggression}",
            "--no-errors",
            f"--log-json={json_file}",
        ]

        try:
            subprocess.run(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
            )
        except OSError as exc:
            print(f"{YELLOW}[warn]{RESET} whatweb execution failed ({exc}) — using HTTP fallback.", file=sys.stderr)
            return http_fallback(urls)

        if not os.path.exists(json_file):
            print(f"{YELLOW}[warn]{RESET} whatweb produced no output — using HTTP fallback.", file=sys.stderr)
            return http_fallback(urls)

        try:
            with open(json_file) as f:
                raw = f.read().strip()
            # whatweb emits one JSON object per line (NDJSON) or a JSON array
            if raw.startswith("["):
                entries = json.loads(raw)
            else:
                entries = [json.loads(line) for line in raw.splitlines() if line.strip()]
        except (json.JSONDecodeError, OSError) as exc:
            print(f"{YELLOW}[warn]{RESET} Could not parse whatweb output ({exc}) — using HTTP fallback.", file=sys.stderr)
            return http_fallback(urls)

    results = []
    for entry in entries:
        fields = extract_fields(entry)
        fields["url"]    = entry.get("target", "")
        fields["method"] = "whatweb"
        results.append(fields)

    # Preserve URL ordering; append any URLs whatweb silently skipped
    seen = {r["url"] for r in results}
    for url in urls:
        if url not in seen:
            results.append({"url": url, "method": "whatweb", "http_status": None})

    return results

# ── http fallback ─────────────────────────────────────────────────────────────

def _http_head(url: str, timeout: int = 10) -> tuple[int | None, dict]:
    """Perform a HEAD request; return (status, headers_dict)."""
    try:
        req = urllib.request.Request(url, method="HEAD")
        req.add_header("User-Agent", f"whatweb-recon/{__version__}")
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, dict(resp.headers)
    except urllib.error.HTTPError as e:
        return e.code, dict(e.headers)
    except Exception:
        return None, {}


def _http_get_body(url: str, timeout: int = 10) -> tuple[int | None, dict, str]:
    """Perform a GET request; return (status, headers_dict, body_text)."""
    try:
        req = urllib.request.Request(url)
        req.add_header("User-Agent", f"whatweb-recon/{__version__}")
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read(65536).decode("utf-8", errors="replace")
            return resp.status, dict(resp.headers), body
    except urllib.error.HTTPError as e:
        body = e.read(65536).decode("utf-8", errors="replace")
        return e.code, dict(e.headers), body
    except Exception:
        return None, {}, ""


def http_fallback(urls: list[str]) -> list[dict]:
    """
    Stdlib-only fingerprinting when whatweb binary is absent.
    Returns list of result dicts with same shape as extract_fields output.
    """
    results = []
    for url in urls:
        fields: dict = {
            "url":               url,
            "method":            "http_fallback",
            "http_status":       None,
            "server":            None,
            "server_os":         None,
            "php_version":       None,
            "openssl_version":   None,
            "iis_version":       None,
            "wordpress":         False,
            "wp_version":        None,
            "joomla":            False,
            "drupal":            False,
            "magento":           False,
            "title":             None,
            "ip_address":        None,
            "redirect_url":      None,
            "cpanel":            False,
            "whm":               False,
            "phpmyadmin":        False,
            "phppgadmin":        False,
            "xmlrpc":            False,
            "jquery_version":    None,
            "bootstrap_version": None,
            "cms_detected":      None,
            "cms_version":       None,
            "plugins":           {},
        }

        # 1. HEAD for server headers
        status, head_hdrs = _http_head(url)
        fields["http_status"] = status

        server_hdr = head_hdrs.get("Server", head_hdrs.get("server", ""))
        if server_hdr:
            fields["server"] = server_hdr

        xpb = head_hdrs.get("X-Powered-By", head_hdrs.get("x-powered-by", ""))
        if xpb:
            m = re.search(r"PHP/([\d.]+)", xpb, re.IGNORECASE)
            if m:
                fields["php_version"] = m.group(1)

        # x-pingback in HEAD → xmlrpc
        if "x-pingback" in {k.lower() for k in head_hdrs}:
            fields["xmlrpc"] = True

        # 2. GET body for meta generator, title, JS libs
        get_status, get_hdrs, body = _http_get_body(url)
        if get_status is not None:
            fields["http_status"] = get_status

        # inherit x-powered-by from GET headers if not already set
        if not fields["php_version"]:
            xpb_g = get_hdrs.get("X-Powered-By", get_hdrs.get("x-powered-by", ""))
            m = re.search(r"PHP/([\d.]+)", xpb_g, re.IGNORECASE)
            if m:
                fields["php_version"] = m.group(1)

        # x-pingback in GET headers
        if "x-pingback" in {k.lower() for k in get_hdrs}:
            fields["xmlrpc"] = True

        if body:
            # WordPress meta generator
            m = re.search(
                r'<meta[^>]+name=["\']generator["\'][^>]+content=["\']WordPress\s*([\d.]*)["\']',
                body, re.IGNORECASE
            )
            if m:
                fields["wordpress"]    = True
                fields["cms_detected"] = "WordPress"
                ver = m.group(1).strip()
                if ver:
                    fields["wp_version"]  = ver
                    fields["cms_version"] = ver

            # Joomla meta generator
            if re.search(
                r'<meta[^>]+name=["\']generator["\'][^>]+content=["\']Joomla',
                body, re.IGNORECASE
            ):
                fields["joomla"]       = True
                fields["cms_detected"] = fields["cms_detected"] or "Joomla"

            # Drupal
            if re.search(r'(?:Drupal\.settings|/sites/default/files)', body):
                fields["drupal"]       = True
                fields["cms_detected"] = fields["cms_detected"] or "Drupal"

            # Page title
            m = re.search(r"<title[^>]*>(.*?)</title>", body, re.IGNORECASE | re.DOTALL)
            if m:
                fields["title"] = re.sub(r"\s+", " ", m.group(1)).strip()

            # jQuery version
            m = re.search(r'jquery[.-](\d+\.\d+[\.\d]*)(\.min)?\.js', body, re.IGNORECASE)
            if m:
                fields["jquery_version"] = m.group(1)

            # Bootstrap version
            m = re.search(r'bootstrap[.-](\d+\.\d+[\.\d]*)(\.min)?\.(?:css|js)', body, re.IGNORECASE)
            if m:
                fields["bootstrap_version"] = m.group(1)

            # phpMyAdmin
            if re.search(r'phpMyAdmin|pma_', body, re.IGNORECASE):
                fields["phpmyadmin"] = True

        # 3. Probe /xmlrpc.php
        if not fields["xmlrpc"]:
            xrpc_url = url.rstrip("/") + "/xmlrpc.php"
            xrpc_status, _ = _http_head(xrpc_url)
            if xrpc_status == 200:
                fields["xmlrpc"] = True

        # 4. Probe /wp-login.php
        if not fields["wordpress"]:
            wplogin_url = url.rstrip("/") + "/wp-login.php"
            wp_status, _ = _http_head(wplogin_url)
            if wp_status == 200:
                fields["wordpress"]    = True
                fields["cms_detected"] = fields["cms_detected"] or "WordPress"

        results.append(fields)

    return results

# ── summary derivation ────────────────────────────────────────────────────────

def derive_summary(results: list[dict]) -> dict:
    """
    Derive top-level summary fields from per-URL result list.
    """
    cms_counts: Counter = Counter()
    server_counts: Counter = Counter()
    php_version = None

    interesting_plugins: list[str] = []
    plugin_flags = {
        "xmlrpc":    "xmlrpc",
        "phppgadmin":"phpPgAdmin",
        "cpanel":    "cPanel",
        "whm":       "WHM",
        "phpmyadmin":"phpMyAdmin",
    }

    seen_plugins: set[str] = set()

    for r in results:
        cms = r.get("cms_detected")
        if cms:
            cms_counts[cms] += 1

        srv = r.get("server")
        if srv:
            server_counts[srv] += 1

        if php_version is None:
            php_version = r.get("php_version")

        for field, label in plugin_flags.items():
            if r.get(field) and label not in seen_plugins:
                interesting_plugins.append(label)
                seen_plugins.add(label)

    cms    = cms_counts.most_common(1)[0][0] if cms_counts else None
    server = server_counts.most_common(1)[0][0] if server_counts else None

    return {
        "cms":                cms,
        "server":             server,
        "php_version":        php_version,
        "interesting_plugins": interesting_plugins,
    }

# ── terminal output ───────────────────────────────────────────────────────────

def print_result(result: dict) -> None:
    domain    = result.get("domain", "")
    url_count = result.get("url_count", 0)
    aggr      = result.get("aggression", "?")
    server    = result.get("server") or "unknown"
    cms       = result.get("cms")
    php_ver   = result.get("php_version")
    xmlrpc_any = "xmlrpc" in result.get("interesting_plugins", [])
    cached    = result.get("cached", False)
    method    = result.get("method", "whatweb")

    cached_tag = f"  {DIM}[cached]{RESET}" if cached else ""
    method_tag = f"  {DIM}[{method}]{RESET}" if method != "whatweb" else ""

    print()
    print(f"{BOLD}WhatWeb{RESET}  {CYAN}{domain}{RESET}  "
          f"({url_count} URL{'s' if url_count != 1 else ''}, aggression={aggr})"
          f"{cached_tag}{method_tag}")

    # server line
    server_os = None
    for r in result.get("results", []):
        if r.get("server_os"):
            server_os = r["server_os"]
            break
    server_display = server + (f" ({server_os})" if server_os else "")
    print(f"  server  : {server_display}")

    # CMS
    cms_display = f"{CYAN}{cms}{RESET}" if cms else "none"
    print(f"  cms     : {cms_display}")

    # PHP
    if php_ver:
        color = RED if _is_eol_php(php_ver) else GREEN
        print(f"  php     : {color}{php_ver}{RESET}{'  ← EOL' if _is_eol_php(php_ver) else ''}")
    else:
        print(f"  php     : none")

    # xmlrpc
    if xmlrpc_any:
        print(f"  xmlrpc  : {YELLOW}YES{RESET}")
    else:
        print(f"  xmlrpc  : NO")

    # interesting plugins
    plugins_list = result.get("interesting_plugins", [])
    if plugins_list:
        print(f"  plugins : {', '.join(plugins_list)}")

    # per-URL table
    print(f"  {'─' * 65}")
    for r in result.get("results", []):
        url     = r.get("url", "")
        status  = r.get("http_status")
        srv     = r.get("server") or ""
        redir   = r.get("redirect_url")
        jquery  = r.get("jquery_version")
        php     = r.get("php_version")

        status_str = str(status) if status else "???"
        status_col = (GREEN if status == 200
                      else YELLOW if status in (301, 302)
                      else RED if status and status >= 400
                      else RESET)

        extras = []
        if redir:
            extras.append(f"→ {redir}")
        if jquery:
            extras.append(f"jQuery {jquery}")
        if php:
            col = RED if _is_eol_php(php) else ""
            extras.append(f"{col}PHP {php}{RESET if col else ''}")
        extra_str = "  " + "  ".join(extras) if extras else ""

        print(f"  {url:<50}  {status_col}{status_str}{RESET}  {srv}{extra_str}")

    print()

# ── community submission ──────────────────────────────────────────────────────

def submit_result(result: dict, config: dict) -> None:
    domain       = result.get("domain", "")
    display_name = config.get("display_name") or "(anonymous)"
    display_loc  = config.get("display_loc")  or "(unset)"
    token        = config.get("github_token", "")

    print()
    print("Submission preview:")
    print(f"  domain       : {domain}")
    print(f"  display_name : {display_name}")
    print(f"  display_loc  : {display_loc}")
    print("This result will be publicly listed on the Tech Board.")
    print()
    ans = input("Submit? [y/N] ").strip().lower()
    if ans != "y":
        print("Cancelled.")
        return

    body_text = json.dumps(result, indent=2)
    payload = json.dumps({
        "title": f"[submission] {domain}",
        "body":  body_text,
        "labels": ["submission"],
    }).encode("utf-8")

    req = urllib.request.Request(
        GITHUB_ISSUES_URL,
        data=payload,
        method="POST",
    )
    req.add_header("Authorization",  f"Bearer {token}")
    req.add_header("Content-Type",   "application/json")
    req.add_header("Accept",         "application/vnd.github+json")
    req.add_header("X-GitHub-Api-Version", "2022-11-28")

    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            if resp.status in (200, 201):
                print("Submitted! Your domain will appear on the Tech Board shortly.")
            else:
                print(f"{RED}[error]{RESET} GitHub returned HTTP {resp.status}.")
    except urllib.error.HTTPError as e:
        err_body = e.read(2048).decode("utf-8", errors="replace")
        print(f"{RED}[error]{RESET} GitHub API error {e.code}: {err_body[:200]}")
    except Exception as exc:
        print(f"{RED}[error]{RESET} Submission failed: {exc}")

# ── main ──────────────────────────────────────────────────────────────────────

def build_output(
    domain: str,
    urls: list[str],
    results: list[dict],
    summary: dict,
    aggression: int,
    cached: bool,
    method: str,
    config: dict | None,
) -> dict:
    now = datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")

    # strip internal 'url' and 'method' keys that live only in per-url dicts
    clean_results = []
    for r in results:
        entry = dict(r)
        entry.pop("method", None)
        clean_results.append(entry)

    return {
        "domain":              domain,
        "queried_at":          now,
        "cached":              cached,
        "method":              method,
        "aggression":          aggression,
        "url_count":           len(urls),
        "cms":                 summary["cms"],
        "server":              summary["server"],
        "php_version":         summary["php_version"],
        "interesting_plugins": summary["interesting_plugins"],
        "results":             clean_results,
        "display_name":        config.get("display_name") if config else None,
        "display_loc":         config.get("display_loc")  if config else None,
        "last_refreshed":      now,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="whatweb-recon",
        description="WhatWeb fingerprinting wrapper with cache and community submission.",
    )
    parser.add_argument("-d", "--domain",
                        help="Apex domain — expanded to https://{d} and https://www.{d}")
    parser.add_argument("--input",
                        help="Text file of URLs, one per line")
    parser.add_argument("-o", "--output",
                        help="Write JSON result to this file path")
    parser.add_argument("--aggression", type=int, choices=[1, 3, 4],
                        help="WhatWeb aggression level (default: auto)")
    parser.add_argument("--no-cache", action="store_true",
                        help="Bypass TTL check — always run fresh scan")
    parser.add_argument("--ttl", type=int, default=DEFAULT_TTL,
                        help=f"Cache TTL in seconds (default: {DEFAULT_TTL})")
    parser.add_argument("--submit", action="store_true",
                        help="Submit result to community Tech Board via GitHub Issues")
    parser.add_argument("--reconfigure", action="store_true",
                        help="Re-run the first-time setup wizard")
    parser.add_argument("--version", action="store_true",
                        help="Print version and exit")

    args = parser.parse_args()

    # --version
    if args.version:
        print(f"whatweb-recon {__version__}")
        sys.exit(0)

    # --reconfigure
    if args.reconfigure:
        setup_wizard()
        sys.exit(0)

    # URL collection
    if not args.domain and not args.input:
        parser.error("Provide -d/--domain or --input.")

    urls: list[str] = []
    domain: str

    if args.domain:
        d = args.domain.lstrip("https://").lstrip("http://").rstrip("/")
        urls = [f"https://{d}", f"https://www.{d}"]
        domain = d
    elif args.input:
        input_path = Path(args.input)
        if not input_path.exists():
            print(f"{RED}[error]{RESET} Input file not found: {args.input}", file=sys.stderr)
            sys.exit(1)
        with open(input_path) as f:
            urls = [line.strip() for line in f if line.strip() and not line.startswith("#")]
        if not urls:
            print(f"{RED}[error]{RESET} Input file contains no URLs.", file=sys.stderr)
            sys.exit(1)
        domain = urlparse(urls[0]).netloc

    # Open cache
    conn = get_cache_conn()

    # Cache check
    if not args.no_cache:
        cached_result = cache_get(conn, domain, args.ttl)
        if cached_result is not None:
            print_result(cached_result)
            if args.output:
                out_path = Path(args.output)
                out_path.parent.mkdir(parents=True, exist_ok=True)
                with open(out_path, "w") as f:
                    json.dump(cached_result, f, indent=2)
                print(f"{DIM}[cache]{RESET} Written to {args.output}")
            if args.submit:
                config = load_config()
                if config is None:
                    config = setup_wizard()
                submit_result(cached_result, config)
            conn.close()
            return

    # Determine aggression
    aggression, reason = determine_aggression(urls, args.aggression)
    print(f"{DIM}[info]{RESET} aggression={aggression}  ({reason})", file=sys.stderr)

    # Run whatweb (or fallback)
    results = run_whatweb(urls, aggression)

    # Determine method used
    method = results[0].get("method", "whatweb") if results else "whatweb"

    # Derive summary
    summary = derive_summary(results)

    # Load config (for display_name/loc in output — no wizard prompt unless --submit)
    config = load_config()

    # Build output dict
    output = build_output(
        domain=domain,
        urls=urls,
        results=results,
        summary=summary,
        aggression=aggression,
        cached=False,
        method=method,
        config=config,
    )

    # Cache UPSERT
    cache_set(conn, domain, output)
    conn.close()

    # Print terminal summary
    print_result(output)

    # Write JSON output if requested
    if args.output:
        out_path = Path(args.output)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with open(out_path, "w") as f:
            json.dump(output, f, indent=2)
        print(f"{DIM}[info]{RESET} Written to {args.output}")

    # Community submission
    if args.submit:
        if config is None:
            config = setup_wizard()
        submit_result(output, config)


if __name__ == "__main__":
    main()

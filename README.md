# whatweb-recon

WhatWeb fingerprinting wrapper with community Tech Board, SQLite cache, and HTTP fallback.

**[→ Tech Board](https://fmfalgun.github.io/whatweb-recon/tech-board.html)**  
**[→ Live Site](https://fmfalgun.github.io/whatweb-recon/)**

---

## Install

```bash
# System dependency (Ruby gem — required for full mode)
gem install whatweb

# Clone
git clone https://github.com/fmfalgun/whatweb-recon
cd whatweb-recon

# No pip install needed — stdlib only
python3 whatweb-recon.py --version
```

If `whatweb` is not installed, the script automatically uses HTTP fallback mode
(checks `Server` header, `X-Powered-By`, meta generator tags, `/wp-login.php`, `/xmlrpc.php`).

---

## Usage

```bash
# Scan a domain
python3 whatweb-recon.py -d nmap.org

# Scan from a URL list
python3 whatweb-recon.py --input urls.txt

# Write JSON output
python3 whatweb-recon.py -d nmap.org -o result.json

# Override aggression level (1=stealthy, 3=aggressive, 4=heavy)
python3 whatweb-recon.py -d nmap.org --aggression 1

# Bypass cache
python3 whatweb-recon.py -d nmap.org --no-cache

# Submit to community Tech Board
python3 whatweb-recon.py -d nmap.org --submit

# Set custom TTL (seconds)
python3 whatweb-recon.py -d nmap.org --ttl 3600

# Reconfigure stored credentials
python3 whatweb-recon.py --reconfigure
```

---

## Aggression Levels

| Level | Name       | Description |
|-------|------------|-------------|
| 1     | Stealthy   | One HTTP request per URL. Minimal footprint. Auto-selected for large URL sets (>30 URLs). |
| 3     | Aggressive | Fetches additional pages. Default for most targets. |
| 4     | Heavy      | Many requests per URL. Manual override only. |

---

## Output Schema

```json
{
  "domain": "nmap.org",
  "method": "whatweb",
  "aggression": 3,
  "url_count": 3,
  "cms": null,
  "server": "Apache",
  "php_version": null,
  "interesting_plugins": [],
  "results": [
    {
      "url": "https://nmap.org",
      "http_status": 200,
      "server": "Apache",
      "server_os": "Debian",
      "php_version": null,
      "cms_detected": null,
      "wordpress": false,
      "xmlrpc": false,
      "cpanel": false,
      "jquery_version": "1.11.3"
    }
  ]
}
```

`interesting_plugins` is a list of security-relevant plugin names: `xmlrpc`, `cPanel`, `WHM`, `phpMyAdmin`, `phpPgAdmin`.

---

## Cache

Results are cached in `./cache.db` (SQLite, 24h TTL). Use `--no-cache` to bypass.

---

## Submission Flow

```
python3 whatweb-recon.py -d example.com --submit

  1. First run: setup wizard (GitHub PAT, display name, location)
  2. Tool scans the domain
  3. Consent prompt: "Submit to public Tech Board? [y/N]"
  4. On confirm: POST GitHub Issue → [submission] example.com
  5. CI workflow runs, adds domain to Tech Board
```

---

## License

MIT

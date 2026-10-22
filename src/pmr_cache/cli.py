#!/usr/bin/env python3
"""
pmr_cache.py - build a local SQLite cache of all published exposures in the
Physiome Model Repository (PMR2) using its Collection+JSON web service.

Design:
  * Every HTTP response is stored raw in the `responses` table (the cache).
  * Derived tables (exposures, exposure_files, links) are rebuilt from the
    raw cache by `rebuild`, so you can change the parsing logic and re-run
    without hitting the server again.

Usage:
  python pmr_cache.py explore https://models.physiomeproject.org/exposure
  python pmr_cache.py harvest              # exposures + exposure files
  python pmr_cache.py harvest --no-files   # exposures only (faster)
  python pmr_cache.py rebuild              # re-derive tables from cache
  python pmr_cache.py analyse              # summary statistics
  python pmr_cache.py opencor-links -o opencor_links.json   # list OpenCOR links
  sqlite3 pmr_cache.sqlite                 # ...then query freely
"""
import argparse
import json
import shutil
import sqlite3
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse, unquote

import requests

PMR_ROOT = "https://models.physiomeproject.org"
MEDIA_TYPE = "application/vnd.physiome.pmr2.json.1"
HEADERS = {
    "Accept": MEDIA_TYPE,
    "User-Agent": "pmr-cache/0.1 (research harvesting script)",
}
DEFAULT_DB = "pmr_cache.sqlite"
DEFAULT_OPENCOR_LINKS = "opencor_links.json"

SCHEMA = """
CREATE TABLE IF NOT EXISTS responses (
    url        TEXT PRIMARY KEY,
    status     INTEGER,
    fetched_at TEXT,
    body       TEXT            -- raw JSON text (NULL if not JSON)
);
CREATE TABLE IF NOT EXISTS exposures (
    url           TEXT PRIMARY KEY,
    title         TEXT,
    workspace_url TEXT,
    data_json     TEXT          -- all Collection+JSON data name/value pairs
);
CREATE TABLE IF NOT EXISTS exposure_files (
    url          TEXT PRIMARY KEY,
    exposure_url TEXT,
    filename     TEXT,
    extension    TEXT,
    kind         TEXT,          -- cellml | sedml | omex | other
    title        TEXT,
    data_json    TEXT
);
CREATE TABLE IF NOT EXISTS links (
    source_url TEXT,
    href       TEXT,
    rel        TEXT,
    prompt     TEXT,
    PRIMARY KEY (source_url, href, rel)
);
CREATE INDEX IF NOT EXISTS ix_ef_exposure ON exposure_files(exposure_url);
CREATE INDEX IF NOT EXISTS ix_ef_kind ON exposure_files(kind);
"""

# --------------------------------------------------------------------------
# HTTP
# --------------------------------------------------------------------------
_local = threading.local()


def _session():
    if not hasattr(_local, "s"):
        _local.s = requests.Session()
        _local.s.headers.update(HEADERS)
    return _local.s


def fetch(url, retries=4, delay=0.0):
    """Return (status, body_text_or_None). Retries transient failures."""
    for attempt in range(retries):
        try:
            if delay:
                time.sleep(delay)
            r = _session().get(url, timeout=60)
            if r.status_code in (429, 500, 502, 503, 504):
                raise requests.HTTPError(f"HTTP {r.status_code}")
            try:
                r.json()
                return r.status_code, r.text
            except ValueError:
                return r.status_code, None
        except requests.RequestException as e:
            wait = 2 ** attempt
            print(f"  ! {url}: {e} (retry in {wait}s)", file=sys.stderr)
            time.sleep(wait)
    return None, None


# --------------------------------------------------------------------------
# Cache helpers
# --------------------------------------------------------------------------
def open_db(path):
    db = sqlite3.connect(path)
    db.executescript(SCHEMA)
    return db


def cached(db, url):
    row = db.execute("SELECT body FROM responses WHERE url=?", (url,)).fetchone()
    return json.loads(row[0]) if row and row[0] else None


def is_cached(db, url):
    return db.execute("SELECT 1 FROM responses WHERE url=? AND status=200",
                      (url,)).fetchone() is not None


def store(db, url, status, body):
    db.execute("INSERT OR REPLACE INTO responses VALUES (?,?,?,?)",
               (url, status, datetime.now(timezone.utc).isoformat(), body))


def fetch_many(db, urls, workers, refresh, delay, label):
    todo = [u for u in dict.fromkeys(urls) if refresh or not is_cached(db, u)]
    print(f"{label}: {len(urls)} total, {len(todo)} to fetch")
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futs = {pool.submit(fetch, u, delay=delay): u for u in todo}
        for i, fut in enumerate(as_completed(futs), 1):
            status, body = fut.result()
            store(db, futs[fut], status, body)
            if i % 50 == 0 or i == len(todo):
                db.commit()
                print(f"  {i}/{len(todo)}")
    db.commit()


# --------------------------------------------------------------------------
# Collection+JSON parsing
# --------------------------------------------------------------------------
def coll(body):
    return (body or {}).get("collection", {}) or {}


def data_dict(data_list):
    return {d["name"]: d.get("value") for d in data_list or [] if d.get("name")}


def all_links(c):
    """Top-level links plus links/hrefs of every item."""
    out = list(c.get("links") or [])
    for item in c.get("items") or []:
        out.extend(item.get("links") or [])
    return out


def all_data(c):
    d = {}
    for item in c.get("items") or []:
        d.update(data_dict(item.get("data")))
    return d


def exposure_file_links(exposure_url, c):
    """Links that point *inside* the exposure, i.e. exposure files."""
    base = exposure_url.rstrip("/") + "/"
    found = {}
    for link in all_links(c):
        href = link.get("href") or ""
        if not href.startswith(base):
            continue
        rel_path = href[len(base):]
        if rel_path.endswith("/view"):
            rel_path = rel_path[: -len("/view")]
        rel_path = rel_path.strip("/")
        if not rel_path or "." not in rel_path.rsplit("/", 1)[-1]:
            continue  # not a file (e.g. an exposure-level view)
        found[href] = (unquote(rel_path), link.get("prompt"))
    return found


def classify(filename):
    name = filename.lower()
    ext = name.rsplit(".", 1)[-1] if "." in name else ""
    if ext == "cellml":
        return ext, "cellml"
    if ext in ("sedml", "sed-ml") or name.endswith(".sedml.xml"):
        return ext, "sedml"
    if ext == "omex":
        return ext, "omex"
    return ext, "other"


def listing_exposures(db):
    c = coll(cached(db, f"{PMR_ROOT}/exposure"))
    return {l["href"]: l.get("prompt") for l in c.get("links") or [] if l.get("href")}


def rebuild(db):
    """Re-derive structured tables from the raw response cache."""
    db.executescript("DELETE FROM exposures; DELETE FROM exposure_files; DELETE FROM links;")
    exposures = listing_exposures(db)
    for exp_url, listing_title in exposures.items():
        c = coll(cached(db, exp_url))
        data = all_data(c)
        links = all_links(c)
        for l in links:
            db.execute("INSERT OR IGNORE INTO links VALUES (?,?,?,?)",
                       (exp_url, l.get("href"), l.get("rel"), l.get("prompt")))
        ws = next((l["href"] for l in links
                   if l.get("rel") == "via" or "/workspace/" in (l.get("href") or "")
                   or "/w/" in (l.get("href") or "")), None)
        db.execute("INSERT OR REPLACE INTO exposures VALUES (?,?,?,?)",
                   (exp_url, data.get("title") or listing_title, ws, json.dumps(data)))

        for f_url, (filename, prompt) in exposure_file_links(exp_url, c).items():
            ext, kind = classify(filename)
            fc = coll(cached(db, f_url))  # may be empty if files not harvested
            fdata = all_data(fc)
            for l in all_links(fc):
                db.execute("INSERT OR IGNORE INTO links VALUES (?,?,?,?)",
                           (f_url, l.get("href"), l.get("rel"), l.get("prompt")))
            # A file type field mentioning SED-ML overrides the extension guess
            ftype = json.dumps(fdata).lower()
            if kind == "other" and ("sed-ml" in ftype or "sedml" in ftype):
                kind = "sedml"
            db.execute("INSERT OR REPLACE INTO exposure_files VALUES (?,?,?,?,?,?,?)",
                       (f_url, exp_url, filename, ext, kind,
                        fdata.get("title") or prompt, json.dumps(fdata)))
    db.commit()
    print(f"Rebuilt: {len(exposures)} exposures")


# --------------------------------------------------------------------------
# Commands
# --------------------------------------------------------------------------
def cmd_explore(args):
    status, body = fetch(args.url)
    print(f"HTTP {status}")
    print(json.dumps(json.loads(body), indent=2) if body else "(no JSON body)")


def cmd_harvest(args):
    db = open_db(args.db)
    fetch_many(db, [f"{PMR_ROOT}/exposure"], 1, True, 0, "Exposure listing")
    exposures = listing_exposures(db)
    if not exposures:
        sys.exit("No exposures found in listing - run `explore` on "
                 f"{PMR_ROOT}/exposure and check the response structure.")
    fetch_many(db, list(exposures), args.workers, args.refresh, args.delay, "Exposures")

    if not args.no_files:
        file_urls = []
        for exp_url in exposures:
            file_urls += list(exposure_file_links(exp_url, coll(cached(db, exp_url))))
        fetch_many(db, file_urls, args.workers, args.refresh, args.delay, "Exposure files")

    rebuild(db)
    cmd_analyse(args, db)


def cmd_rebuild(args):
    rebuild(open_db(args.db))


SUMMARY_QUERIES = [
    ("Published exposures", "SELECT COUNT(*) FROM exposures"),
    ("Exposure files (all)", "SELECT COUNT(*) FROM exposure_files"),
    ("CellML exposure files", "SELECT COUNT(*) FROM exposure_files WHERE kind='cellml'"),
    ("Distinct CellML filenames",
     "SELECT COUNT(DISTINCT filename) FROM exposure_files WHERE kind='cellml'"),
    ("SED-ML exposure files", "SELECT COUNT(*) FROM exposure_files WHERE kind='sedml'"),
    ("Exposures with >=1 CellML file",
     "SELECT COUNT(DISTINCT exposure_url) FROM exposure_files WHERE kind='cellml'"),
    ("Exposures with >=1 SED-ML file",
     "SELECT COUNT(DISTINCT exposure_url) FROM exposure_files WHERE kind='sedml'"),
    ("Exposures with CellML AND SED-ML", """
        SELECT COUNT(*) FROM (
          SELECT exposure_url FROM exposure_files GROUP BY exposure_url
          HAVING SUM(kind='cellml') > 0 AND SUM(kind='sedml') > 0)"""),
    ("Links mentioning OpenCOR",
     "SELECT COUNT(*) FROM links WHERE prompt LIKE '%OpenCOR%' OR href LIKE '%opencor%'"),
]


def cmd_analyse(args, db=None):
    db = db or open_db(args.db)
    print("\n=== PMR summary ===")
    for label, sql in SUMMARY_QUERIES:
        print(f"{label + ':':38s}{db.execute(sql).fetchone()[0]}")
    print("\nFile kinds:")
    for kind, n in db.execute(
            "SELECT kind, COUNT(*) FROM exposure_files GROUP BY kind ORDER BY 2 DESC"):
        print(f"  {kind:8s} {n}")
    print("\nMost common link rels (useful for refining the parser):")
    for rel, n in db.execute(
            "SELECT rel, COUNT(*) FROM links GROUP BY rel ORDER BY 2 DESC LIMIT 10"):
        print(f"  {str(rel):12s} {n}")


OPENCOR_SCHEME = "opencor://openFile/"


def cmd_opencor_links(args, db=None):
    """Write every link mentioning OpenCOR to a JSON file."""
    db = db or open_db(args.db)
    rows = db.execute("""
        SELECT l.source_url, l.href, l.prompt,
               ef.exposure_url, ef.filename, e.title
        FROM links l
        LEFT JOIN exposure_files ef ON ef.url = l.source_url
        LEFT JOIN exposures e ON e.url = COALESCE(ef.exposure_url, l.source_url)
        WHERE l.prompt LIKE '%OpenCOR%' OR l.href LIKE '%opencor%'
        ORDER BY ef.exposure_url, l.source_url, l.href""").fetchall()
    records = []
    for source_url, href, prompt, exp_url, filename, title in rows:
        file_url = href[len(OPENCOR_SCHEME):] if href.startswith(OPENCOR_SCHEME) else None
        records.append({
            "exposure_url": exp_url or source_url,
            "exposure_title": title,
            "source_page": source_url,
            "filename": filename,
            "prompt": prompt,
            "opencor_url": href,
            "file_url": file_url,
        })
    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(records, f, indent=2, ensure_ascii=False)
    print(f"Wrote {len(records)} OpenCOR links to {args.output}")


DASHBOARD_DATA_DIR = "dashboard/public/data"


def cmd_dashboard_data(args):
    """Export the cache summary and copy the OpenCOR JSON files for the dashboard."""
    db = open_db(args.db)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    one = lambda sql: db.execute(sql).fetchone()[0]
    summary = {
        "generated": datetime.now(timezone.utc).isoformat(),
        "metrics": [{"label": label, "value": one(sql)} for label, sql in SUMMARY_QUERIES],
        "file_kinds": [{"name": k, "count": n} for k, n in db.execute(
            "SELECT kind, COUNT(*) FROM exposure_files GROUP BY kind ORDER BY 2 DESC")],
        "extensions": [{"name": e or "(none)", "count": n} for e, n in db.execute(
            "SELECT extension, COUNT(*) FROM exposure_files GROUP BY extension "
            "ORDER BY 2 DESC LIMIT 15")],
        "link_rels": [{"name": str(r), "count": n} for r, n in db.execute(
            "SELECT rel, COUNT(*) FROM links GROUP BY rel ORDER BY 2 DESC LIMIT 10")],
        "files_per_exposure": [{"name": str(k), "count": n} for k, n in db.execute("""
            SELECT MIN(c, 10), COUNT(*) FROM (
              SELECT COUNT(*) AS c FROM exposure_files GROUP BY exposure_url)
            GROUP BY 1 ORDER BY 1""")],
    }
    (out / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(f"Wrote {out / 'summary.json'}")
    for src in (args.links, args.report):
        if not Path(src).exists():
            print(f"Skipped {src} (not found)")
            continue
        dest = out / Path(src).name
        if Path(src).name == Path(args.report).name:
            # Tracebacks contain local file paths; the exported data may be published.
            report = json.loads(Path(src).read_text(encoding="utf-8"))
            for r in report.get("results", []):
                r.pop("traceback", None)
            dest.write_text(json.dumps(report, indent=1), encoding="utf-8")
        else:
            shutil.copyfile(src, dest)
        print(f"Copied {src} -> {dest}")


def main():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--db", default=DEFAULT_DB)
    sub = p.add_subparsers(dest="cmd", required=True)

    e = sub.add_parser("explore", help="pretty-print the JSON for one URL")
    e.add_argument("url")
    e.set_defaults(func=cmd_explore)

    h = sub.add_parser("harvest", help="download everything into the cache")
    h.add_argument("--workers", type=int, default=4, help="parallel requests (be polite)")
    h.add_argument("--delay", type=float, default=0.1, help="seconds before each request")
    h.add_argument("--refresh", action="store_true", help="re-fetch cached URLs")
    h.add_argument("--no-files", action="store_true", help="skip exposure-file pages")
    h.set_defaults(func=cmd_harvest)

    sub.add_parser("rebuild", help="re-derive tables from cache").set_defaults(func=cmd_rebuild)
    sub.add_parser("analyse", help="print summary stats").set_defaults(func=cmd_analyse)

    o = sub.add_parser("opencor-links",
                       help="save a JSON listing of the 'Launch with OpenCOR' links")
    o.add_argument("-o", "--output", default=DEFAULT_OPENCOR_LINKS,
                   help=f"JSON file to write (default: {DEFAULT_OPENCOR_LINKS})")
    o.set_defaults(func=cmd_opencor_links)

    d = sub.add_parser("dashboard-data",
                       help="export the JSON data files used by the web dashboard")
    d.add_argument("--out", default=DASHBOARD_DATA_DIR,
                   help=f"output directory (default: {DASHBOARD_DATA_DIR})")
    d.add_argument("--links", default=DEFAULT_OPENCOR_LINKS,
                   help="OpenCOR links JSON to copy (default: %(default)s)")
    d.add_argument("--report", default="opencor_run_report.json",
                   help="OpenCOR run report JSON to copy (default: %(default)s)")
    d.set_defaults(func=cmd_dashboard_data)

    args = p.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
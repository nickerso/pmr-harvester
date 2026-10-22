"""
opencor_run_links.py - load and run every link in opencor_links.json using
OpenCOR's bundled Python interpreter, and report which ones load and run.

This script is standalone (standard library + OpenCOR's `opencor` module only).
Run it with OpenCOR's Python, e.g. on Windows:

  OpenCOR.com -c PythonShell::python scripts\\opencor_run_links.py
  OpenCOR.com -c PythonShell::python scripts\\opencor_run_links.py --limit 5

or from OpenCOR's Python console window:

  import sys; sys.argv = ["opencor_run_links.py", "--limit", "5"]
  exec(open("scripts/opencor_run_links.py").read())

Each distinct file_url is processed once. The report is rewritten after every
link, so partial results survive a crash, and re-running with --resume skips
links already in the report.
"""
import argparse
import csv
import json
import sys
import time
import traceback
from datetime import datetime, timezone

import opencor

DEFAULT_INPUT = "opencor_links.json"
DEFAULT_REPORT = "opencor_run_report.json"
OPENCOR_SCHEME = "opencor://openFile/"


def direct_url(link):
    """Extract the plain URL from an opencor://openFile/<url> link."""
    url = link.get("opencor_url") or ""
    if url.startswith(OPENCOR_SCHEME):
        return url[len(OPENCOR_SCHEME):]
    return link.get("file_url")


def unique_targets(links):
    """Map each distinct direct URL to the exposure URLs that link to it."""
    targets = {}
    for link in links:
        url = direct_url(link)
        if url:
            exposures = targets.setdefault(url, [])
            exp = link.get("exposure_url")
            if exp and exp not in exposures:
                exposures.append(exp)
    return targets


def try_link(url):
    """Load and run one simulation. Returns a result dict."""
    result = {"loaded": False, "ran": False, "issues": [], "error": None,
              "load_seconds": None, "run_seconds": None, "result_points": None}
    simulation = None
    try:
        t0 = time.time()
        simulation = opencor.open_simulation(url)
        result["load_seconds"] = round(time.time() - t0, 3)
        result["issues"] = [str(i) for i in simulation.issues()]
        result["loaded"] = bool(simulation.valid())
        if not result["loaded"]:
            result["error"] = "simulation is not valid"
            return result

        t0 = time.time()
        run_ok = simulation.run()
        result["run_seconds"] = round(time.time() - t0, 3)
        result["issues"] = [str(i) for i in simulation.issues()]
        # run() reports failure with False; also require some results.
        points = simulation.results().voi().values_count()
        result["result_points"] = points
        result["ran"] = run_ok is not False and points > 0
        if not result["ran"]:
            result["error"] = "run failed" if run_ok is False else "no results produced"
    except Exception as e:  # keep going whatever a single model does
        result["error"] = f"{type(e).__name__}: {e}"
        result["traceback"] = traceback.format_exc()
    finally:
        if simulation is not None:
            try:
                opencor.close_simulation(simulation)
            except Exception:
                pass
    return result


def write_report(path, entries):
    loaded = sum(e["loaded"] for e in entries)
    ran = sum(e["ran"] for e in entries)
    report = {
        "generated": datetime.now(timezone.utc).isoformat(),
        "summary": {"total": len(entries), "loaded": loaded, "ran": ran,
                    "failed_to_load": len(entries) - loaded,
                    "loaded_but_failed_to_run": loaded - ran},
        "results": entries,
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    csv_path = path.rsplit(".", 1)[0] + ".csv"
    with open(csv_path, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["file_url", "loaded", "ran", "load_seconds", "run_seconds",
                    "result_points", "error", "exposures"])
        for e in entries:
            w.writerow([e["file_url"], e["loaded"], e["ran"], e["load_seconds"],
                        e["run_seconds"], e["result_points"], e["error"],
                        " ".join(e["exposure_urls"])])


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("-i", "--input", default=DEFAULT_INPUT,
                   help=f"links JSON from `pmr-cache opencor-links` (default: {DEFAULT_INPUT})")
    p.add_argument("-o", "--output", default=DEFAULT_REPORT,
                   help=f"JSON report (a .csv is written alongside) (default: {DEFAULT_REPORT})")
    p.add_argument("--limit", type=int, help="only process the first N distinct URLs")
    p.add_argument("--resume", action="store_true",
                   help="skip URLs already present in an existing report")
    args = p.parse_args(sys.argv[1:] if argv is None else argv)

    with open(args.input, encoding="utf-8") as f:
        targets = unique_targets(json.load(f))

    entries = []
    if args.resume:
        try:
            with open(args.output, encoding="utf-8") as f:
                entries = json.load(f)["results"]
        except FileNotFoundError:
            pass
    done = {e["file_url"] for e in entries}
    todo = [(u, x) for u, x in targets.items() if u not in done]
    if args.limit:
        todo = todo[:args.limit]

    print(f"{len(targets)} distinct URLs, {len(todo)} to process")
    for n, (url, exposures) in enumerate(todo, 1):
        print(f"[{n}/{len(todo)}] {url}", flush=True)
        entry = {"file_url": url, "exposure_urls": exposures, **try_link(url)}
        entries.append(entry)
        print(f"    loaded={entry['loaded']} ran={entry['ran']}"
              + (f" error={entry['error']}" if entry["error"] else ""), flush=True)
        write_report(args.output, entries)

    loaded = sum(e["loaded"] for e in entries)
    ran = sum(e["ran"] for e in entries)
    print(f"\nDone: {len(entries)} total, {loaded} loaded, {ran} ran. "
          f"Report: {args.output}")


if __name__ == "__main__":
    main()

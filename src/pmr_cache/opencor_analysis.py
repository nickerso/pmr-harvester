"""
opencor_analysis.py - analyse the OpenCOR links listing produced by
`pmr-cache opencor-links`.

Usage:
  pmr-opencor-analysis                     # reads opencor_links.json
  pmr-opencor-analysis -i other_links.json
"""
import argparse
import json
import sys
from collections import Counter

DEFAULT_INPUT = "opencor_links.json"


def load_links(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def count_unique(links, field):
    return len({l[field] for l in links if l.get(field)})


def url_type(url):
    """File type of a URL: its extension (without '/view'), or '(none)'."""
    name = (url or "").rstrip("/")
    if name.endswith("/view"):
        name = name[: -len("/view")]
    name = name.rsplit("/", 1)[-1]
    return name.rsplit(".", 1)[-1].lower() if "." in name else "(none)"


def print_counts(title, counter):
    print(f"\n{title}")
    for kind, n in counter.most_common():
        print(f"  {kind:10s} {n}")

def main():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("-i", "--input", default=DEFAULT_INPUT,
                   help=f"JSON links file (default: {DEFAULT_INPUT})")
    args = p.parse_args()

    try:
        links = load_links(args.input)
    except FileNotFoundError:
        sys.exit(f"{args.input} not found - run `pmr-cache opencor-links` first.")

    print(f"Total OpenCOR links: {len(links)}")
    print(f"Unique opencor_url:  {count_unique(links, 'opencor_url')}")

    print_counts("source_page types:",
                 Counter(url_type(l.get("source_page")) for l in links))
    print_counts("opencor_url types for CellML source_page:",
                 Counter(url_type(l.get("opencor_url")) for l in links
                         if url_type(l.get("source_page")) == "cellml"))


if __name__ == "__main__":
    main()
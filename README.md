# pmr-cache

Command line utility that builds a local SQLite cache of all published
exposures in the [Physiome Model Repository](https://models.physiomeproject.org)
(PMR2), using its Collection+JSON web service.

Every HTTP response is stored raw in the `responses` table. Derived tables
(`exposures`, `exposure_files`, `links`) can be rebuilt from that cache without
contacting the server again.

## Requirements

- [uv](https://docs.astral.sh/uv/)
- Python 3.12+ (uv will fetch it if needed)

## Install

```powershell
uv sync
```

This creates `.venv` and installs the `pmr-cache` command and its dependencies.

## Run

```powershell
uv run pmr-cache --help
uv run pmr-cache explore https://models.physiomeproject.org/exposure
uv run pmr-cache harvest              # exposures + exposure files
uv run pmr-cache harvest --no-files   # exposures only (faster)
uv run pmr-cache rebuild              # re-derive tables from cache
uv run pmr-cache analyse              # summary statistics
uv run pmr-cache opencor-links        # write opencor_links.json
uv run pmr-cache opencor-links -o my_links.json
```

`opencor-links` reads the cache (no network access) and writes a JSON array of
every "Launch with OpenCOR" link. Each entry has `exposure_url`,
`exposure_title`, `source_page`, `filename`, `prompt`, `opencor_url` (the
`opencor://openFile/...` link) and `file_url` (the plain https URL OpenCOR will
open).

Global option: `--db PATH` (default `pmr_cache.sqlite`), given before the
subcommand, e.g. `uv run pmr-cache --db my.sqlite harvest`.

`harvest` options: `--workers N` (default 4), `--delay SECONDS` (default 0.1),
`--refresh` (re-fetch cached URLs), `--no-files`.

Query the result freely with `sqlite3 pmr_cache.sqlite`.

You can also run the module directly: `uv run python -m pmr_cache.cli analyse`.

## Analyse the OpenCOR links

```powershell
uv run pmr-opencor-analysis                  # reads opencor_links.json
uv run pmr-opencor-analysis -i my_links.json
```

Reports the total number of links, the number of unique `opencor_url` values,
a count of each `source_page` file type, and a count of each `opencor_url` file
type for links whose `source_page` is a CellML model.

## Run the links in OpenCOR

[scripts/opencor_run_links.py](scripts/opencor_run_links.py) is a standalone
script (it is not part of the uv project) that must be run with OpenCOR's own
Python interpreter, since it uses OpenCOR's `opencor` module. For each distinct
direct URL in `opencor_links.json` (taken from the `opencor://openFile/...`
link) it opens the simulation, checks it is valid, runs it, and records whether
it loaded and whether it ran (produced results).

```powershell
# from this folder; adjust the path to your OpenCOR install
& "C:\Program Files\OpenCOR\OpenCOR.com" -c PythonShell::python scripts\opencor_run_links.py --limit 5
& "C:\Program Files\OpenCOR\OpenCOR.com" -c PythonShell::python scripts\opencor_run_links.py
```

Options: `-i/--input` (default `opencor_links.json`), `-o/--output` (default
`opencor_run_report.json`; a `.csv` is written alongside), `--limit N`, and
`--resume` (skip URLs already in the report). The report is rewritten after each
link, so it survives a crash or a model that needs to be killed.

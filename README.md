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
```

Global option: `--db PATH` (default `pmr_cache.sqlite`), given before the
subcommand, e.g. `uv run pmr-cache --db my.sqlite harvest`.

`harvest` options: `--workers N` (default 4), `--delay SECONDS` (default 0.1),
`--refresh` (re-fetch cached URLs), `--no-files`.

Query the result freely with `sqlite3 pmr_cache.sqlite`.

You can also run the module directly: `uv run python -m pmr_cache.cli analyse`.

"""Command-line entrypoint for the runtime SQLite pilot."""

from .cli import main


if __name__ == "__main__":
    raise SystemExit(main())

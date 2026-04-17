"""Compatibility entrypoint for platforms that auto-detect app.py."""

from backend.server.app import app, main

__all__ = ["app", "main"]


if __name__ == "__main__":
    main()

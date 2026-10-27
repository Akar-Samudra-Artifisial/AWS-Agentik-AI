"""Lambda entrypoint api: re-export handler Mangum dari app."""

from .app import handler

__all__ = ["handler"]

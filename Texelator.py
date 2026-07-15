"""Texelator public entry point."""

import importlib
import Main as _implementation


def show_ui():
    """Reload the implementation to avoid stale Maya session modules."""
    global _implementation, TexelatorUI
    _implementation = importlib.reload(_implementation)
    TexelatorUI = _implementation.TexelatorUI
    return _implementation.show_ui()


TexelatorUI = _implementation.TexelatorUI
__all__ = ['TexelatorUI', 'show_ui']

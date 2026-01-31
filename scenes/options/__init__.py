"""Options menu package.

The options menu scene is split into modules for maintainability:
- constants.py: Navigation keys and helper functions
- core.py: Main OptionsScene class

This package is backward compatible - import OptionsScene from here.
"""

from .core import OptionsScene
from .constants import cycle_selection as _cycle_selection

__all__ = ["OptionsScene", "_cycle_selection"]

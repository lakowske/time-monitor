"""A Python project for monitoring and tracking time usage."""

__version__ = "0.1.0"
__author__ = "Seth"
__email__ = "seth@example.com"

from .actions.build import build
from .core import calculate_sum, greet

__all__ = ["greet", "calculate_sum", "build"]

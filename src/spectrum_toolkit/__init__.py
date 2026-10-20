"""Spectrum Toolkit: load, process and plot spectroscopic data."""

from .core import Spectrum, SpectrumCollection
from .io import load

__version__ = "0.0.1"
__all__ = ["Spectrum", "SpectrumCollection", "load"]

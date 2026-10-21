"""Spectrum Toolkit: load, process and plot spectroscopic data."""

from .core import Spectrum, SpectrumCollection
from .baseline import baseline, find_baseline
from .despike import despike
from .edit import check_axes, combine, cut, drop, resample, select, trim
from .io import load

__version__ = "0.0.1"
__all__ = ["Spectrum", "SpectrumCollection", "load", "combine", "check_axes", "trim", "cut", "select", "drop", "resample", "despike", "baseline", "find_baseline"]

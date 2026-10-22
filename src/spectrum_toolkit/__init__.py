"""Spectrum Toolkit: load, process and plot spectroscopic data."""

from .core import Spectrum, SpectrumCollection
from .baseline import baseline, find_baseline
from .despike import despike
from .smooth import smooth
from .normalize import normalize
from .derivative import derivative
from .edit import check_axes, combine, cut, drop, resample, select, trim
from .io import load
from .recipe import Recipe, apply
from .plot import compare, panels, plot, scatter
from .style import export, get_style, save_style, set_style, to_rgba

__version__ = "0.0.1"
__all__ = ["Spectrum", "SpectrumCollection", "load", "combine", "check_axes", "trim", "cut", "select", "drop", "resample", "despike", "baseline", "find_baseline", "smooth", "normalize", "derivative", "plot", "panels", "compare", "scatter", "export", "get_style", "set_style", "save_style", "to_rgba", "Recipe", "apply"]
